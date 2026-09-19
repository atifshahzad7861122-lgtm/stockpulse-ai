"""Performance analytics (CONTRACT.md §5.13).

Every metric carries data_provenance. Predictions show confidence, never
guarantees. Demo/MOCK data is labeled; never invents Adobe sales numbers.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api import jobs
from app.api.deps import (
    check_rate_limit,
    get_db,
    get_idempotency_key,
    idempotent,
    not_found,
    paginate,
    pagination_params,
)
from app.models.intelligence import Opportunity, Prediction
from app.models.platform import AgentRun
from app.models.production import ProductionQueue, SubmissionRecord
from app.schemas.analytics import (
    AnalyticsEventsIngest,
    AnalyticsFunnel,
    AnalyticsOverview,
    ExportOut,
    ExportRequest,
    FunnelStage,
    KpiValue,
    OpportunityPerformance,
)
from app.schemas.common import Page
from app.schemas.enums import AgentRunKind, AgentStatus, DataProvenance

router = APIRouter(prefix="/analytics", tags=["analytics"])

MOCK_NOTE = (
    "Demo values: deterministic mock snapshots. Not real Adobe Stock data; "
    "never invent or imply real sales figures."
)


@router.get("/overview", response_model=AnalyticsOverview)
def overview(
    db: Annotated[Session, Depends(get_db)],
    from_date: Annotated[date, Query(alias="from")],
    to_date: Annotated[date, Query(alias="to")],
):
    def _kpi(value, provenance=DataProvenance.MOCK):
        return KpiValue(value=value, provenance=provenance)

    opportunities = db.query(Opportunity).count()
    approved = db.query(Opportunity).filter_by(status="approved").count()
    queue_active = (
        db.query(ProductionQueue).filter(ProductionQueue.status.notin_(["ARCHIVED"])).count()
    )
    submitted = db.query(SubmissionRecord).filter_by(status="SUBMITTED").count()
    accepted = db.query(SubmissionRecord).filter_by(status="ACCEPTED").count()
    return AnalyticsOverview(
        range={"from": from_date, "to": to_date},
        kpis={
            "opportunities": _kpi(opportunities),
            "opportunities_approved": _kpi(approved),
            "queue_active": _kpi(queue_active),
            "submitted": _kpi(submitted),
            "accepted": _kpi(accepted),
            "acceptance_rate": _kpi(round(accepted / submitted, 3) if submitted else None),
        },
        provenance_notes=MOCK_NOTE,
    )


@router.get("/funnel", response_model=AnalyticsFunnel)
def funnel(db: Annotated[Session, Depends(get_db)]):
    stages = [
        ("opportunities", db.query(Opportunity).count()),
        ("ideas", 0),  # combined image+video below
        ("prompts", 0),
        (
            "queue_active",
            db.query(ProductionQueue).filter(ProductionQueue.status.notin_(["ARCHIVED"])).count(),
        ),
        ("submitted", db.query(SubmissionRecord).filter_by(status="SUBMITTED").count()),
        ("accepted", db.query(SubmissionRecord).filter_by(status="ACCEPTED").count()),
    ]
    from app.models.ideation import ImageIdea, VideoIdea
    from app.models.prompts import Prompt

    ideas = db.query(ImageIdea).count() + db.query(VideoIdea).count()
    prompts = db.query(Prompt).count()
    stages[1] = ("ideas", ideas)
    stages[2] = ("prompts", prompts)
    return AnalyticsFunnel(stages=[FunnelStage(stage=name, count=count) for name, count in stages])


@router.get("/opportunities/{opportunity_id}/performance", response_model=OpportunityPerformance)
def opportunity_performance(opportunity_id: str, db: Annotated[Session, Depends(get_db)]):
    opp = db.query(Opportunity).filter_by(id=opportunity_id).one_or_none()
    if opp is None:
        raise not_found("OPPORTUNITY_NOT_FOUND", f"Opportunity {opportunity_id} not found.")
    queue_items = db.query(ProductionQueue).filter_by(opportunity_id=opp.id).all()
    queue_ids = [q.id for q in queue_items]
    submissions = (
        db.query(SubmissionRecord).filter(SubmissionRecord.production_queue_id.in_(queue_ids)).all()
        if queue_ids
        else []
    )
    accepted = sum(1 for s in submissions if s.status.value == "ACCEPTED")
    total = len(submissions)
    sample_warning = (
        "Small sample (n<10): acceptance rate is not statistically meaningful."
        if total < 10
        else None
    )
    return OpportunityPerformance(
        opportunity_id=opp.id,
        submissions=total,
        accepted=accepted,
        acceptance_rate=round(accepted / total, 3) if total else None,
        sample_warning=sample_warning,
        provenance_notes=MOCK_NOTE,
    )


@router.post("/events", status_code=204)
def ingest_events(
    body: AnalyticsEventsIngest, request: Request, db: Annotated[Session, Depends(get_db)]
):
    """Structured usage events — stored on agent_runs input_summary for auditability."""
    from app.models.platform import AgentRun

    run = AgentRun(
        agent_name="performance_analysis",
        run_kind=AgentRunKind.PERFORMANCE_DIGEST,
        status="SUCCEEDED",
        input_summary={
            "events": [e.model_dump(mode="json") for e in body.events],
            "mock": True,
        },
        output_summary={"ingested": len(body.events)},
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    db.add(run)
    db.commit()
    return None


@router.post("/exports", response_model=ExportOut, status_code=202)
def create_export(body: ExportRequest, request: Request, db: Annotated[Session, Depends(get_db)]):
    check_rate_limit("analytics:exports", max_calls=10, per_seconds=3600)

    def _run(db: Session, run):
        return {
            "format": body.format,
            "from_date": body.from_date.isoformat() if body.from_date else None,
            "to_date": body.to_date.isoformat() if body.to_date else None,
            "mock": True,
            "note": MOCK_NOTE,
        }

    result = jobs.submit_job(
        agent_name="performance_analysis",
        run_kind=AgentRunKind.PERFORMANCE_DIGEST,
        input_summary=body.model_dump(mode="json"),
        func=_run,
    )
    return idempotent(
        get_idempotency_key(request),
        ExportOut(
            id=result["job_id"],
            kind="export",
            status="processing",
            download_url=None,
            created_at=datetime.now(UTC),
        ),
    )


@router.get("/exports", response_model=Page[ExportOut])
def list_exports(
    db: Annotated[Session, Depends(get_db)], paging: Annotated[dict, Depends(pagination_params)]
):
    # Exports are backed by agent_runs (run_kind=PERFORMANCE_DIGEST); no exports table.
    q = (
        db.query(AgentRun)
        .filter(AgentRun.run_kind == AgentRunKind.PERFORMANCE_DIGEST)
        .order_by(AgentRun.created_at.desc())
    )
    total = q.count()
    rows = q.offset((paging["page"] - 1) * paging["page_size"]).limit(paging["page_size"]).all()
    return paginate(
        [
            ExportOut(
                id=row.id,
                kind="export",
                status="ready" if row.status == AgentStatus.COMPLETED else "processing",
                download_url=None,
                created_at=row.created_at,
            )
            for row in rows
        ],
        page=paging["page"],
        page_size=paging["page_size"],
        total=total,
    )


@router.get("/predictions/{prediction_id}")
def prediction_detail(prediction_id: str, db: Annotated[Session, Depends(get_db)]):
    """Prediction with confidence, evidence, model version, timestamp — never a guarantee."""
    row = db.query(Prediction).filter_by(id=prediction_id).one_or_none()
    if row is None:
        raise not_found("PREDICTION_NOT_FOUND", f"Prediction {prediction_id} not found.")
    methodology = row.methodology or ""
    model_version = methodology.split()[0].rstrip("(),") if methodology else "unknown"
    return {
        "id": row.id,
        "micro_niche_id": row.micro_niche_id,
        "horizon": row.horizon.value if hasattr(row.horizon, "value") else row.horizon,
        "predicted_demand_index": float(row.predicted_demand_index),
        "predicted_direction": (
            row.predicted_direction.value
            if hasattr(row.predicted_direction, "value")
            else row.predicted_direction
        ),
        "confidence": float(row.confidence),
        "factors": [
            f"based_on_metrics: {row.based_on_metrics_from} → {row.based_on_metrics_to}",
            f"methodology: {methodology[:200]}",
        ],
        "model_version": model_version,
        "generated_at": row.created_at.isoformat(),
        "superseded_by_id": row.superseded_by_id,
        "disclaimer": (
            "Probabilistic forecast with uncertainty — never a guarantee of sales "
            "or acceptance. Demo model output on mock data."
        ),
        "data_provenance": row.data_provenance.value,
    }
