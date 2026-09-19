"""Phase 2 source-health models (PHASE2_DESIGN.md §3).

- ``SourceHealth`` — per-source health: status (SourceStatus str), last
  success/failure, error, collection counts, duration, consecutive failures,
  auth state. One row per trend_source (unique FK).
- ``CollectionRun`` — every collection execution (scheduler + manual):
  QUEUED/RUNNING/SUCCESS/PARTIAL/FAILED/SKIPPED with counts, error, trigger.
- ``RawPayload`` — raw adapter payload archive with payload_hash dedup.

UUID String(36) PKs, utcnow mixin, same style as models/intelligence.py.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditTimestampsMixin, Base, UUIDPrimaryKeyMixin, utcnow
from app.schemas.enums import SourceStatus


class SourceHealth(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin):
    """Health record per trend source (one row per source)."""

    __tablename__ = "source_health"

    trend_source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("trend_sources.id"), nullable=False
    )
    status: Mapped[SourceStatus] = mapped_column(
        SAEnum(SourceStatus, native_enum=False, length=16),
        nullable=False,
        default=SourceStatus.UNAVAILABLE,
    )
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_failure_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    records_collected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auth_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fallback_status: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (UniqueConstraint("trend_source_id", name="uq_source_health_source"),)


class CollectionRun(Base, UUIDPrimaryKeyMixin):
    """One collection execution (scheduler or manual trigger)."""

    __tablename__ = "collection_runs"

    trend_source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("trend_sources.id"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="QUEUED")
    records_collected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_stored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger: Mapped[str] = mapped_column(String(16), nullable=False, default="SCHEDULED")
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class RawPayload(Base, UUIDPrimaryKeyMixin):
    """Archive of raw adapter payloads (dedup on payload_hash)."""

    __tablename__ = "raw_payloads"

    source: Mapped[str] = mapped_column(String(64), nullable=False)
    collection_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    adapter_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    collection_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("collection_runs.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        UniqueConstraint("source", "payload_hash", name="uq_raw_payloads_source_hash"),
    )


__all__ = ["SourceHealth", "CollectionRun", "RawPayload"]
