"""Production queue (CONTRACT.md §5.11).

State machine: T01–T29 map is authoritative; unlisted transitions are
illegal. Illegal transitions → 422 + explanation (user requirement).
Enqueue requires compliance PASS → 422 COMPLIANCE_BLOCKED otherwise.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import (
    audit_log,
    get_db,
    get_idempotency_key,
    idempotent,
    not_found,
    paginate,
    pagination_params,
    unprocessable,
)
from app.engines.queue import (
    allowed_transitions,
    can_pause,
    deadline_state,
    is_legal_transition,
    transition_error_message,
)
from app.models.compliance import ComplianceCheck
from app.models.platform import AuditLog
from app.models.production import ProductionQueue
from app.models.settings import Setting
from app.schemas.common import Page, apply_labels
from app.schemas.enums import (
    AssetType,
    ComplianceResult,
    ProductionQueueStatus,
)
from app.schemas.production import (
    PriorityComponents,
    QueueAssign,
    QueueComplianceSummary,
    QueueHistoryEvent,
    QueueItemCreate,
    QueueItemDetail,
    QueueItemOut,
    QueuePause,
    QueueTransition,
)

router = APIRouter(prefix="/production", tags=["production"])


def _priority_components(row: ProductionQueue) -> PriorityComponents:
    return PriorityComponents(
        user_boost={"P0": 1.0, "P1": 0.75, "P2": 0.5, "P3": 0.25, "P4": 0.0}.get(
            row.priority_band, 0.5
        ),
        rework_penalty=min(row.rework_count * 0.1, 0.5),
    )


def _priority_score(row: ProductionQueue) -> float:
    comp = _priority_components(row)
    return round(100 * max(0.0, min(1.0, 0.5 + 0.3 * comp.user_boost - comp.rework_penalty)), 2)


def _compliance_summary(db: Session, row: ProductionQueue) -> QueueComplianceSummary | None:
    column = None
    if row.prompt_id:
        column = ("prompt_id", row.prompt_id)
    elif row.image_idea_id:
        column = ("image_idea_id", row.image_idea_id)
    elif row.video_idea_id:
        column = ("video_idea_id", row.video_idea_id)
    if column is None:
        return None
    check = (
        db.query(ComplianceCheck)
        .filter(getattr(ComplianceCheck, column[0]) == column[1])
        .order_by(ComplianceCheck.created_at.desc())
        .first()
    )
    if check is None:
        return None
    return QueueComplianceSummary(result=check.result.value, check_id=check.id)


def _out(db: Session, row: ProductionQueue) -> QueueItemOut:
    ds = deadline_state(row.target_date.isoformat()) if row.target_date else None
    return apply_labels(
        QueueItemOut(
            **{
                k: getattr(row, k)
                for k in (
                    "id",
                    "project_id",
                    "opportunity_id",
                    "image_idea_id",
                    "video_idea_id",
                    "prompt_id",
                    "asset_type",
                    "title",
                    "status",
                    "priority_band",
                    "target_date",
                    "paused",
                    "target_quantity",
                    "produced_count",
                    "generation_tool",
                    "rework_count",
                    "blocked_reason",
                    "notes",
                    "status_changed_at",
                    "created_at",
                    "updated_at",
                )
            },
            priority_score=_priority_score(row),
            priority_components=_priority_components(row),
            deadline_state=ds,  # type: ignore[arg-type]
            compliance=_compliance_summary(db, row),
        ),
        row,
    )


def _history(db: Session, row: ProductionQueue) -> list[QueueHistoryEvent]:
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.entity_kind == "production_queue", AuditLog.entity_id == row.id)
        .order_by(AuditLog.created_at.asc())
        .all()
    )
    events: list[QueueHistoryEvent] = []
    for log in logs:
        after = log.after or {}
        events.append(
            QueueHistoryEvent(
                at=log.created_at,
                kind=log.action,
                from_status=(log.before or {}).get("status"),
                to_status=after.get("status"),
                note=log.note,
                actor=log.actor_kind,
            )
        )
    return events


def _get(db: Session, queue_id: str) -> ProductionQueue:
    row = db.query(ProductionQueue).filter_by(id=queue_id).one_or_none()
    if row is None:
        raise not_found("QUEUE_ITEM_NOT_FOUND", f"Queue item {queue_id} not found.")
    return row


def _check_compliance_pass(db: Session, row: ProductionQueue) -> None:
    """Enqueue gating: latest relevant compliance check must be PASS."""
    summary = _compliance_summary(db, row)
    if summary is None or summary.result != ComplianceResult.PASS.value:
        raise unprocessable(
            "COMPLIANCE_BLOCKED",
            "Cannot proceed: the latest compliance check for this item is not PASS. "
            "Run a compliance screen and resolve all flags first. "
            "This assessment does not guarantee Adobe Stock acceptance.",
            latest_result=(summary.result if summary else "none"),
        )


@router.get("/queue", response_model=Page[QueueItemOut])
def board(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[dict, Depends(pagination_params)],
    status: ProductionQueueStatus | None = None,
    asset_type: AssetType | None = None,
    priority_band: Annotated[str | None, Query(pattern="^P[0-4]$")] = None,
    group_by_status: bool = False,
):
    q = db.query(ProductionQueue).order_by(ProductionQueue.created_at.desc())
    if status is not None:
        q = q.filter_by(status=status)
    if asset_type is not None:
        q = q.filter_by(asset_type=asset_type)
    if priority_band:
        q = q.filter_by(priority_band=priority_band)
    total = q.count()
    page, page_size = paging["page"], paging["page_size"]
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    return paginate([_out(db, r) for r in rows], page=page, page_size=page_size, total=total)


@router.post("/queue", response_model=QueueItemOut, status_code=201)
def enqueue(body: QueueItemCreate, db: Annotated[Session, Depends(get_db)]):
    row = ProductionQueue(
        opportunity_id=body.opportunity_id,
        image_idea_id=body.image_idea_id,
        video_idea_id=body.video_idea_id,
        prompt_id=body.prompt_id,
        asset_type=body.asset_type,
        title=body.title,
        status=ProductionQueueStatus.DISCOVERED,
        priority_band=body.priority_band,
        target_date=body.target_date,
        target_quantity=body.target_quantity,
        generation_tool=body.generation_tool,
        notes=body.notes,
    )
    db.add(row)
    db.flush()
    # Enqueue gating: compliance PASS required when the item has a screened subject.
    if body.prompt_id or body.image_idea_id or body.video_idea_id:
        try:
            _check_compliance_pass(db, row)
        except Exception:
            db.rollback()
            raise
    db.commit()
    db.refresh(row)
    audit_log(db, action="enqueue", entity_kind="production_queue", entity_id=row.id)
    db.commit()
    return _out(db, row)


@router.get("/queue/{queue_id}", response_model=QueueItemDetail)
def get_queue_item(queue_id: str, db: Annotated[Session, Depends(get_db)]):
    row = _get(db, queue_id)
    item = _out(db, row)
    return QueueItemDetail(
        **item.model_dump(),
        history=_history(db, row),
        allowed_transitions=[s.value for s in allowed_transitions(row.status)],
    )


@router.post("/queue/{queue_id}/transition", response_model=QueueItemDetail)
def transition(
    queue_id: str, body: QueueTransition, request: Request, db: Annotated[Session, Depends(get_db)]
):
    row = _get(db, queue_id)
    if row.paused:
        raise unprocessable(
            "QUEUE_PAUSED",
            "Item is paused; unpause before transitioning.",
            current_status=row.status.value,
        )
    if not is_legal_transition(row.status, body.to):
        # User requirement: illegal transitions → 422 + explanation.
        raise unprocessable(
            "ILLEGAL_TRANSITION",
            transition_error_message(row.status, body.to),
            current_status=row.status.value,
            attempted=body.to.value,
            allowed_transitions=[s.value for s in allowed_transitions(row.status)],
        )
    # Gate compliance-sensitive transitions on PASS.
    if body.to in (
        ProductionQueueStatus.APPROVED,
        ProductionQueueStatus.READY_TO_UPLOAD,
        ProductionQueueStatus.SUBMITTED,
    ):
        _check_compliance_pass(db, row)
    before = row.status
    row.status = body.to
    row.status_changed_at = datetime.now(UTC)
    if body.to == ProductionQueueStatus.IN_PRODUCTION and before == ProductionQueueStatus.REJECTED:
        row.rework_count = (row.rework_count or 0) + 1
    db.commit()
    audit_log(
        db,
        action="transition",
        entity_kind="production_queue",
        entity_id=row.id,
        before={"status": before.value},
        after={"status": body.to.value},
        note=body.note,
    )
    db.commit()
    result = QueueItemDetail(
        **_out(db, row).model_dump(),
        history=_history(db, row),
        allowed_transitions=[s.value for s in allowed_transitions(row.status)],
    )
    return idempotent(get_idempotency_key(request), result)


@router.post("/queue/{queue_id}/assign", response_model=QueueItemOut)
def assign_item(queue_id: str, body: QueueAssign, db: Annotated[Session, Depends(get_db)]):
    row = _get(db, queue_id)
    note = (
        f"Assignee (single-user; informational): {body.assignee}"
        if body.assignee
        else "Assignee cleared (single-user mode)."
    )
    row.notes = f"{row.notes}\n{note}" if row.notes else note
    db.commit()
    audit_log(db, action="assign", entity_kind="production_queue", entity_id=row.id, note=note)
    db.commit()
    return _out(db, row)


@router.post("/queue/{queue_id}/pause", response_model=QueueItemOut)
def pause_item(queue_id: str, body: QueuePause, db: Annotated[Session, Depends(get_db)]):
    row = _get(db, queue_id)
    if body.paused and not can_pause(row.status):
        raise unprocessable(
            "PAUSE_FORBIDDEN",
            f"Cannot pause an item in status {row.status.value}.",
            current_status=row.status.value,
        )
    row.paused = body.paused
    db.commit()
    audit_log(
        db,
        action="pause" if body.paused else "unpause",
        entity_kind="production_queue",
        entity_id=row.id,
        note=body.reason,
    )
    db.commit()
    return _out(db, row)


@router.post("/queue/{queue_id}/archive", response_model=QueueItemDetail)
def archive_item(queue_id: str, db: Annotated[Session, Depends(get_db)]):
    body = QueueTransition(to=ProductionQueueStatus.ARCHIVED)
    # Reuse the transition path (bypasses Request/idempotency; archive is user-initiated).
    row = _get(db, queue_id)
    if not is_legal_transition(row.status, body.to):
        raise unprocessable(
            "ILLEGAL_TRANSITION",
            transition_error_message(row.status, body.to),
            current_status=row.status.value,
            attempted=body.to.value,
            allowed_transitions=[s.value for s in allowed_transitions(row.status)],
        )
    row.status = ProductionQueueStatus.ARCHIVED
    row.status_changed_at = datetime.now(UTC)
    db.commit()
    audit_log(db, action="archive", entity_kind="production_queue", entity_id=row.id)
    db.commit()
    return QueueItemDetail(
        **_out(db, row).model_dump(),
        history=_history(db, row),
        allowed_transitions=[s.value for s in allowed_transitions(row.status)],
    )


@router.get("/slots", response_model=dict)
def capacity_slots(
    db: Annotated[Session, Depends(get_db)],
    week_start: Annotated[date, Query()],
):
    daily_cap = db.query(Setting).filter_by(key="planner.daily_capacity").one_or_none()
    weekly_cap = db.query(Setting).filter_by(key="planner.weekly_capacity").one_or_none()
    blackouts = db.query(Setting).filter_by(key="planner.blackout_dates").one_or_none()
    active = (
        db.query(ProductionQueue)
        .filter(ProductionQueue.status.notin_([ProductionQueueStatus.ARCHIVED]))
        .count()
    )
    return {
        "week_start": week_start.isoformat(),
        "daily_capacity": (daily_cap.value if daily_cap else None),
        "weekly_capacity": (weekly_cap.value if weekly_cap else None),
        "blackout_dates": (blackouts.value if blackouts else []),
        "active_items": active,
        "note": "Capacity is user-configured, never invented. Submission remains a manual human action.",
    }
