"""Daily production plans (Phase 3).

GET /daily-production/today — today's plan (404 if none built yet).
POST /daily-production/build — build/rebuild the plan for a date.
GET/PUT /daily-production/settings — production capacity settings.
Nothing here auto-generates or auto-submits; plans are recommendations.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    audit_log,
    get_db,
    not_found,
    paginate,
    pagination_params,
)
from app.models.planning import DailyProductionPlan, ProductionRecommendation
from app.models.settings import Setting
from app.schemas.common import Page, apply_labels
from app.schemas.planning import (
    CapacitySettings,
    PlanBuildRequest,
    PlanDetailOut,
    PlanStatusUpdate,
    PlanSummaryOut,
    RecommendationOut,
)
from app.services import production_planner

router = APIRouter(prefix="/daily-production", tags=["daily-production"])

_VALID_PLAN_STATUSES = ("draft", "active", "completed")


def _recs(db: Session, plan_id: str) -> list[RecommendationOut]:
    # Archived rows are history (kept for audit); the plan shows live ones.
    rows = (
        db.query(ProductionRecommendation)
        .filter_by(plan_id=plan_id)
        .filter(ProductionRecommendation.status != "archived")
        .order_by(ProductionRecommendation.rank.asc())
        .all()
    )
    return [apply_labels(RecommendationOut.model_validate(r), r) for r in rows]


def _plan_out(db: Session, plan: DailyProductionPlan, detail: bool = False):
    count = (
        db.query(ProductionRecommendation)
        .filter_by(plan_id=plan.id)
        .filter(ProductionRecommendation.status != "archived")
        .count()
    )
    base = apply_labels(
        PlanSummaryOut(
            **{k: getattr(plan, k) for k in ("id", "plan_date", "target_images",
                                             "target_videos", "status")},
            recommendation_count=count,
            data_provenance=plan.data_provenance,
        ),
        plan,
    )
    if not detail:
        return base
    return PlanDetailOut(
        **base.model_dump(),
        summary_json=plan.summary_json or {},
        recommendations=_recs(db, plan.id),
    )


@router.get("/today", response_model=PlanDetailOut)
def today(db: Annotated[Session, Depends(get_db)]):
    plan = (
        db.query(DailyProductionPlan)
        .filter_by(plan_date=date.today())
        .one_or_none()
    )
    if plan is None:
        raise not_found(
            "PLAN_NOT_FOUND",
            "No plan built for today yet. POST /daily-production/build to build one.",
        )
    return _plan_out(db, plan, detail=True)


@router.post("/build", response_model=PlanDetailOut, status_code=201)
def build_plan(body: PlanBuildRequest, db: Annotated[Session, Depends(get_db)]):
    plan = production_planner.build_plan(
        db,
        plan_date=body.plan_date,
        target_images=body.target_images,
        target_videos=body.target_videos,
    )
    db.commit()
    db.refresh(plan)
    audit_log(
        db,
        action="build_plan",
        entity_kind="daily_production_plan",
        entity_id=plan.id,
        after={"plan_date": plan.plan_date.isoformat()},
        note="Daily plan built (recommendations only — nothing auto-generated).",
    )
    db.commit()
    return _plan_out(db, plan, detail=True)


@router.get("", response_model=Page[PlanSummaryOut])
def list_plans(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[dict, Depends(pagination_params)],
    from_date: Annotated[date | None, Query()] = None,
    to_date: Annotated[date | None, Query()] = None,
):
    q = db.query(DailyProductionPlan).order_by(DailyProductionPlan.plan_date.desc())
    if from_date:
        q = q.filter(DailyProductionPlan.plan_date >= from_date)
    if to_date:
        q = q.filter(DailyProductionPlan.plan_date <= to_date)
    total = q.count()
    page, page_size = paging["page"], paging["page_size"]
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    return paginate([_plan_out(db, r) for r in rows], page=page, page_size=page_size, total=total)


@router.get("/settings", response_model=CapacitySettings)
def get_capacity(db: Annotated[Session, Depends(get_db)]):
    return production_planner.get_capacity(db)


@router.put("/settings", response_model=CapacitySettings)
def put_capacity(body: CapacitySettings, db: Annotated[Session, Depends(get_db)]):
    """User-configured capacity. Submission limits are never hard-coded —
    they are edited here."""
    row = (
        db.query(Setting).filter_by(project_id=None, key="production_capacity").one_or_none()
    )
    if row is None:
        row = Setting(project_id=None, key="production_capacity", value={})
        db.add(row)
        db.flush()
    row.value = {"value": body.model_dump()}
    db.commit()
    audit_log(
        db,
        action="update_capacity",
        entity_kind="setting",
        entity_id=row.id,
        after={"key": "production_capacity", "value": body.model_dump()},
    )
    db.commit()
    return production_planner.get_capacity(db)


# NOTE: /{plan_id} routes come after the literal /settings and /today paths
# so FastAPI matches the literals first.


@router.get("/{plan_id}", response_model=PlanDetailOut)
def get_plan(plan_id: str, db: Annotated[Session, Depends(get_db)]):
    plan = db.query(DailyProductionPlan).filter_by(id=plan_id).one_or_none()
    if plan is None:
        raise not_found("PLAN_NOT_FOUND", f"Plan {plan_id} not found.")
    return _plan_out(db, plan, detail=True)


@router.post("/{plan_id}/status", response_model=PlanSummaryOut)
def set_plan_status(plan_id: str, body: PlanStatusUpdate, db: Annotated[Session, Depends(get_db)]):
    plan = db.query(DailyProductionPlan).filter_by(id=plan_id).one_or_none()
    if plan is None:
        raise not_found("PLAN_NOT_FOUND", f"Plan {plan_id} not found.")
    if body.status not in _VALID_PLAN_STATUSES:
        from app.api.deps import bad_request

        raise bad_request(
            "INVALID_PLAN_STATUS",
            f"status must be one of {', '.join(_VALID_PLAN_STATUSES)}.",
        )
    before = plan.status
    plan.status = body.status
    db.commit()
    audit_log(
        db,
        action="plan_status",
        entity_kind="daily_production_plan",
        entity_id=plan.id,
        before={"status": before},
        after={"status": plan.status},
    )
    db.commit()
    return _plan_out(db, plan)
