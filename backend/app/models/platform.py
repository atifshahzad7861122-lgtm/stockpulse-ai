"""Platform models: agent_runs, agent_logs, notifications, audit_logs (docs: 08 §11).

agent_logs: append-only, cascade-deleted with the run. audit_logs: immutable —
the application must not expose update/delete paths for this table.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditTimestampsMixin, Base, UUIDPrimaryKeyMixin, utcnow
from app.schemas.enums import (
    AgentLogLevel,
    AgentRunKind,
    AgentStatus,
    NotificationChannel,
    NotificationType,
)


class AgentRun(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin):
    """Execution record for every agent invocation (docs: 08 §11.1, 13 §18).

    CONTRACT §5.14 also names the run/job payload fields; jobs are a view over
    agent_runs (job_id == agent_run.id).
    """

    __tablename__ = "agent_runs"

    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    run_kind: Mapped[AgentRunKind] = mapped_column(
        SAEnum(AgentRunKind, native_enum=False, length=32), nullable=False
    )
    status: Mapped[AgentStatus] = mapped_column(
        SAEnum(AgentStatus, native_enum=False, length=16),
        nullable=False,
        default=AgentStatus.PENDING,
    )
    input_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    output_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(32), nullable=False, default="schedule")
    instructions_version: Mapped[str | None] = mapped_column(String(32), nullable=True)


class AgentLog(Base):
    """Append-only structured log line for an agent run (docs: 08 §11.2)."""

    __tablename__ = "agent_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    level: Mapped[AgentLogLevel] = mapped_column(
        SAEnum(AgentLogLevel, native_enum=False, length=16), nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class Notification(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin):
    """User-facing notification inbox (docs: 08 §11.3). Dismiss = is_read."""

    __tablename__ = "notifications"

    type: Mapped[NotificationType] = mapped_column(
        SAEnum(NotificationType, native_enum=False, length=32), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    link_entity_kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    link_entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    channel: Mapped[NotificationChannel] = mapped_column(
        SAEnum(NotificationChannel, native_enum=False, length=16),
        nullable=False,
        default=NotificationChannel.IN_APP,
    )
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    """Immutable record of consequential actions (docs: 08 §11.4).

    No updated_at / deleted_at: append-only. Never expose update/delete routes.
    """

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    before: Mapped[dict | None] = mapped_column("before_state", JSON, nullable=True)
    after: Mapped[dict | None] = mapped_column("after_state", JSON, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
