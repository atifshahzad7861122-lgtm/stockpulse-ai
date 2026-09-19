"""Notification schemas (CONTRACT.md §5.16)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.common import MockLabeled
from app.schemas.enums import NotificationChannel, NotificationType


class NotificationOut(MockLabeled):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: NotificationType
    title: str
    body: str
    link_entity_kind: str | None = None
    link_entity_id: str | None = None
    channel: NotificationChannel
    is_read: bool
    read_at: datetime | None = None
    created_at: datetime


class NotificationList(BaseModel):
    items: list[NotificationOut]
    unread_count: int = 0
