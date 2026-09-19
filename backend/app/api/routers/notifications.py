"""Notification inbox (CONTRACT.md §5.16)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, not_found, paginate, pagination_params
from app.models.platform import Notification
from app.schemas.enums import NotificationType
from app.schemas.notifications import NotificationList, NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _out(row: Notification) -> NotificationOut:
    return NotificationOut.from_row(row)


@router.get("", response_model=NotificationList)
def inbox(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[dict, Depends(pagination_params)],
    unread_only: bool = False,
    type: NotificationType | None = None,
):
    q = db.query(Notification).order_by(Notification.created_at.desc())
    if unread_only:
        q = q.filter_by(is_read=False)
    if type is not None:
        q = q.filter_by(type=type)
    total = q.count()
    unread = db.query(Notification).filter_by(is_read=False).count()
    page, page_size = paging["page"], paging["page_size"]
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    items = paginate([_out(r) for r in rows], page=page, page_size=page_size, total=total)
    return NotificationList(items=items.data, unread_count=unread)


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: str, db: Annotated[Session, Depends(get_db)]):
    row = db.query(Notification).filter_by(id=notification_id).one_or_none()
    if row is None:
        raise not_found("NOTIFICATION_NOT_FOUND", f"Notification {notification_id} not found.")
    row.is_read = True
    row.read_at = datetime.now(UTC)
    db.commit()
    return _out(row)


@router.post("/read-all", response_model=dict)
def read_all(db: Annotated[Session, Depends(get_db)]):
    now = datetime.now(UTC)
    count = (
        db.query(Notification)
        .filter_by(is_read=False)
        .update({"is_read": True, "read_at": now}, synchronize_session=False)
    )
    db.commit()
    return {"marked_read": count}
