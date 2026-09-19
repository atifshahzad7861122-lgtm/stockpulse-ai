"""Submission planner (CONTRACT.md §5.12).

Hard rule: the API never submits to Adobe Stock. Plans are generated;
mark-submitted records the human's manual action; record-outcome records
Adobe's acceptance/rejection decision.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api import jobs
from app.api.deps import (
    audit_log,
    bad_request,
    get_db,
    get_idempotency_key,
    idempotent,
    not_found,
    paginate,
    pagination_params,
)
from app.models.production import Asset, ProductionQueue, SubmissionRecord
from app.models.production import MetadataRecord as Metadata
from app.models.settings import Setting
from app.schemas.agents import JobCreate
from app.schemas.common import Page
from app.schemas.enums import AgentRunKind, SubmissionStatus
from app.schemas.submissions import (
    SubmissionDetail,
    SubmissionMarkSubmitted,
    SubmissionOut,
    SubmissionPlanCreate,
    SubmissionRecordOutcome,
)

router = APIRouter(prefix="/submissions", tags=["submissions"])

_CHECKLIST = [
    "ai_disclosure",
    "metadata_complete",
    "compliance_pass",
    "export_dimensions",
    "release_review",
]


def _out(row: SubmissionRecord) -> SubmissionOut:
    return SubmissionOut.from_row(row)


def _get(db: Session, submission_id: str) -> SubmissionRecord:
    row = db.query(SubmissionRecord).filter_by(id=submission_id).one_or_none()
    if row is None:
        raise not_found("SUBMISSION_NOT_FOUND", f"Submission {submission_id} not found.")
    return row


def _capacity(db: Session) -> dict:
    keys = ("planner.daily_capacity", "planner.weekly_capacity", "planner.blackout_dates")
    values = {}
    for key in keys:
        row = db.query(Setting).filter_by(key=key).one_or_none()
        values[key] = row.value if row else None
    return values


@router.post("/plan", response_model=JobCreate, status_code=202)
def create_plan(
    body: SubmissionPlanCreate, request: Request, db: Annotated[Session, Depends(get_db)]
):
    def _run(db: Session, run):
        items = db.query(ProductionQueue).filter(ProductionQueue.id.in_(body.queue_ids)).all()
        return {
            "planned": len(items),
            "week_start": body.week_start.isoformat(),
            "capacity": _capacity(db),
            "note": "Plan only. The API never submits to Adobe Stock.",
        }

    result = jobs.submit_job(
        agent_name="production_planning",
        run_kind=AgentRunKind.PRODUCTION_PLAN,
        input_summary={"queue_ids": body.queue_ids, "week_start": body.week_start.isoformat()},
        func=_run,
    )
    return idempotent(get_idempotency_key(request), JobCreate(**result))


@router.get("", response_model=Page[SubmissionOut])
def list_submissions(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[dict, Depends(pagination_params)],
    status: SubmissionStatus | None = None,
    from_date: Annotated[date | None, Query()] = None,
    to_date: Annotated[date | None, Query()] = None,
):
    q = db.query(SubmissionRecord).order_by(SubmissionRecord.created_at.desc())
    if status is not None:
        q = q.filter_by(status=status)
    if from_date:
        q = q.filter(SubmissionRecord.submitted_at >= from_date)
    if to_date:
        q = q.filter(SubmissionRecord.submitted_at <= to_date)
    total = q.count()
    page, page_size = paging["page"], paging["page_size"]
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    return paginate([_out(r) for r in rows], page=page, page_size=page_size, total=total)


@router.post("", response_model=SubmissionOut, status_code=201)
def create_submission_record(
    db: Annotated[Session, Depends(get_db)],
    asset_id: Annotated[str, Query()],
    queue_id: Annotated[str | None, Query()] = None,
):
    """Create a PLANNED submission record — records intent, never submits."""
    asset = db.query(Asset).filter_by(id=asset_id).one_or_none()
    if asset is None:
        raise not_found("ASSET_NOT_FOUND", f"Asset {asset_id} not found.")
    current_version = next((v for v in asset.versions if v.id == asset.current_version_id), None)
    metadata = db.query(Metadata).filter_by(asset_id=asset.id, is_current=True).one_or_none()
    if metadata is None:
        raise bad_request(
            "METADATA_REQUIRED",
            "A current metadata bundle is required before planning a submission.",
        )
    row = SubmissionRecord(
        asset_id=asset.id,
        asset_version_id=(
            current_version.id
            if current_version
            else (asset.versions[0].id if asset.versions else "")
        ),
        metadata_id=metadata.id,
        production_queue_id=queue_id,
        status=SubmissionStatus.PLANNED,
    )
    if not row.asset_version_id:
        raise bad_request("ASSET_VERSION_REQUIRED", "Asset has no versions yet.")
    db.add(row)
    db.commit()
    db.refresh(row)
    audit_log(db, action="plan_submission", entity_kind="submission_record", entity_id=row.id)
    db.commit()
    return _out(row)


@router.get("/{submission_id}", response_model=SubmissionDetail)
def get_submission(submission_id: str, db: Annotated[Session, Depends(get_db)]):
    row = _get(db, submission_id)
    detail = SubmissionDetail(**_out(row).model_dump())
    detail.checklist = [{"item": item, "status": "pending"} for item in _CHECKLIST]
    detail.capacity_context = _capacity(db)
    return detail


@router.post("/{submission_id}/mark-submitted", response_model=SubmissionOut)
def mark_submitted(
    submission_id: str,
    body: SubmissionMarkSubmitted,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Record the HUMAN's manual submission to Adobe Stock (never automatic)."""
    row = _get(db, submission_id)
    if row.status != SubmissionStatus.PLANNED:
        raise bad_request(
            "INVALID_STATE",
            f"Only PLANNED submissions can be marked submitted; current is {row.status.value}.",
        )
    row.status = SubmissionStatus.SUBMITTED
    row.submitted_at = body.submitted_at or datetime.now(UTC)
    row.adobe_reference = body.adobe_reference
    db.commit()
    audit_log(
        db,
        action="mark_submitted",
        entity_kind="submission_record",
        entity_id=row.id,
        note="Human-recorded manual submission. The API never submits to Adobe Stock.",
    )
    db.commit()
    return idempotent(get_idempotency_key(request), _out(row))


@router.post("/{submission_id}/record-outcome", response_model=SubmissionOut)
def record_outcome(
    submission_id: str,
    body: SubmissionRecordOutcome,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    row = _get(db, submission_id)
    item = next((i for i in body.items if i.queue_id == row.production_queue_id), None)
    if item is None and body.items:
        item = body.items[0]
    if item is None:
        raise bad_request("NO_OUTCOME", "At least one outcome item is required.")
    mapping = {"accepted": SubmissionStatus.ACCEPTED, "rejected": SubmissionStatus.REJECTED}
    row.status = mapping[item.outcome]
    row.reviewed_at = datetime.now(UTC)
    if item.outcome == "rejected":
        row.rejection_reason = item.reason
    db.commit()
    audit_log(
        db,
        action="record_outcome",
        entity_kind="submission_record",
        entity_id=row.id,
        note=f"Adobe outcome: {item.outcome}",
    )
    db.commit()
    return idempotent(get_idempotency_key(request), _out(row))
