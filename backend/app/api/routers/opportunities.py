"""Opportunities (CONTRACT.md §5.4)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import (
    audit_log,
    bad_request,
    conflict,
    get_db,
    get_idempotency_key,
    idempotent,
    not_found,
    paginate,
    pagination_params,
)
from app.models.intelligence import Opportunity
from app.schemas.common import Page
from app.schemas.enums import DataProvenance
from app.schemas.opportunities import (
    OpportunityApprove,
    OpportunityApproveResponse,
    OpportunityCreate,
    OpportunityOut,
    OpportunityReject,
    OpportunityStatus,
    OpportunityUpdate,
)
from app.services.dev_mode import is_dev_mode
from app.services.personal_fit import compute_personal_fit

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


def _out(row: Opportunity, db: Session | None = None) -> OpportunityOut:
    data = OpportunityOut.from_row(row)
    data.status = str(row.status.value if hasattr(row.status, "value") else row.status).lower()
    data.priority = _priority_num(data.priority)
    data.personal_fit_score = (
        compute_personal_fit(
            db,
            micro_niche_id=row.micro_niche_id,
            title=row.title or "",
            summary=row.summary or "",
        )
        if db is not None
        else None
    )
    return data


def _priority_num(priority) -> int:
    mapping = {"low": 0, "normal": 5, "high": 10}
    if isinstance(priority, str):
        return mapping.get(priority, 0)
    return int(priority or 0)


def _get(db: Session, opportunity_id: str) -> Opportunity:
    row = db.query(Opportunity).filter_by(id=opportunity_id).one_or_none()
    if row is None:
        raise not_found("OPPORTUNITY_NOT_FOUND", f"Opportunity {opportunity_id} not found.")
    return row


@router.get("", response_model=Page[OpportunityOut])
def list_opportunities(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[dict, Depends(pagination_params)],
    status: OpportunityStatus | None = None,
    micro_niche_id: str | None = None,
    min_score: Annotated[float | None, Query(ge=0, le=100)] = None,
    min_confidence: Annotated[float | None, Query(ge=0, le=1)] = None,
    sort: Annotated[str, Query(pattern="^(-score|created_at)$")] = "-score",
):
    q = db.query(Opportunity)
    if status is not None:
        q = q.filter_by(status=status)
    if micro_niche_id:
        q = q.filter_by(micro_niche_id=micro_niche_id)
    if min_score is not None:
        q = q.filter(Opportunity.opportunity_score >= min_score)
    if min_confidence is not None:
        q = q.filter(Opportunity.confidence >= min_confidence)
    q = q.order_by(
        Opportunity.opportunity_score.desc() if sort == "-score" else Opportunity.created_at.desc()
    )
    # Phase 2: MOCK/demo rows stop driving intelligence unless dev mode is on.
    if not is_dev_mode(db):
        q = q.filter(Opportunity.data_provenance != DataProvenance.MOCK)
    total = q.count()
    page, page_size = paging["page"], paging["page_size"]
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    return paginate([_out(r, db) for r in rows], page=page, page_size=page_size, total=total)


@router.post("", response_model=OpportunityOut, status_code=201)
def create_opportunity(body: OpportunityCreate, db: Annotated[Session, Depends(get_db)]):
    row = Opportunity(
        micro_niche_id=body.micro_niche_id,
        title=body.title,
        summary=body.summary,
        opportunity_score=50.0,
        confidence=0.5,
        demand_evidence=[{"note": "Manual entry — no demand evidence yet."}],
        data_provenance=DataProvenance.USER_PROVIDED,
        status=OpportunityStatus.NEW,
        priority=body.priority,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    audit_log(db, action="create", entity_kind="opportunity", entity_id=row.id)
    db.commit()
    return _out(row, db)


@router.get("/{opportunity_id}", response_model=OpportunityOut)
def get_opportunity(opportunity_id: str, db: Annotated[Session, Depends(get_db)]):
    return _out(_get(db, opportunity_id), db)


@router.patch("/{opportunity_id}", response_model=OpportunityOut)
def update_opportunity(
    opportunity_id: str, body: OpportunityUpdate, db: Annotated[Session, Depends(get_db)]
):
    row = _get(db, opportunity_id)
    before = {"title": row.title, "priority": row.priority}
    for field in ("title", "summary", "micro_niche_id", "priority", "risk_notes"):
        value = getattr(body, field, None)
        if value is not None:
            setattr(row, field, value)
    db.commit()
    audit_log(
        db,
        action="update",
        entity_kind="opportunity",
        entity_id=row.id,
        before=before,
        after={"title": row.title, "priority": row.priority},
    )
    db.commit()
    return _out(row, db)


@router.post("/{opportunity_id}/approve", response_model=OpportunityApproveResponse)
def approve_opportunity(
    opportunity_id: str,
    body: OpportunityApprove,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    row = _get(db, opportunity_id)
    if row.status != OpportunityStatus.NEW:
        raise bad_request(
            "INVALID_TRANSITION",
            f"Cannot approve opportunity in status {row.status.value}; must be 'new'.",
        )
    row.status = OpportunityStatus.APPROVED
    now = datetime.now(UTC)
    row.reviewed_at = now
    db.commit()
    audit_log(db, action="approve", entity_kind="opportunity", entity_id=row.id)
    db.commit()
    return idempotent(
        get_idempotency_key(request),
        OpportunityApproveResponse(id=row.id, status="approved", approved_at=now),
    )


@router.post("/{opportunity_id}/reject", response_model=OpportunityOut)
def reject_opportunity(
    opportunity_id: str,
    body: OpportunityReject,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    row = _get(db, opportunity_id)
    if row.status != OpportunityStatus.NEW:
        raise bad_request(
            "INVALID_TRANSITION",
            f"Cannot reject opportunity in status {row.status.value}; must be 'new'.",
        )
    row.status = OpportunityStatus.REJECTED
    row.reviewed_at = datetime.now(UTC)
    db.commit()
    audit_log(db, action="reject", entity_kind="opportunity", entity_id=row.id, note=body.reason)
    db.commit()
    return idempotent(get_idempotency_key(request), _out(row, db))


@router.post("/{opportunity_id}/archive", response_model=OpportunityOut)
def archive_opportunity(opportunity_id: str, db: Annotated[Session, Depends(get_db)]):
    row = _get(db, opportunity_id)
    if row.status == OpportunityStatus.ARCHIVED:
        raise conflict("ALREADY_ARCHIVED", "Opportunity is already archived.")
    row.status = OpportunityStatus.ARCHIVED
    db.commit()
    audit_log(db, action="archive", entity_kind="opportunity", entity_id=row.id)
    db.commit()
    return _out(row, db)


@router.delete("/{opportunity_id}", status_code=204)
def delete_opportunity(opportunity_id: str, db: Annotated[Session, Depends(get_db)]):
    row = _get(db, opportunity_id)
    audit_log(db, action="hard_delete", entity_kind="opportunity", entity_id=row.id)
    db.delete(row)
    db.commit()
    return None
