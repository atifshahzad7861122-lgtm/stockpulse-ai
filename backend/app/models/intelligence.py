"""Intelligence models: trend_sources → trend_snapshots → trend_signals →
market_metrics → predictions → opportunities (docs: 08 §5).

Single-user: no user_id columns. Snapshots are append-only; metrics/predictions
have no delete path; opportunities support soft delete.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditTimestampsMixin, Base, SoftDeleteMixin, UUIDPrimaryKeyMixin, utcnow
from app.schemas.enums import (
    DataProvenance,
    PredictedDirection,
    PredictionHorizon,
    TrendSourceType,
)


def _prov_enum() -> SAEnum:
    return SAEnum(DataProvenance, native_enum=False, length=16)


class TrendSource(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin, SoftDeleteMixin):
    """Registry of ingest sources (docs: 08 §5.1). Seed: 11 rows (SEED_PLAN.md §3)."""

    __tablename__ = "trend_sources"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_type: Mapped[TrendSourceType] = mapped_column(
        SAEnum(TrendSourceType, native_enum=False, length=32), nullable=False
    )
    endpoint_or_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetch_schedule: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_provenance: Mapped[DataProvenance] = mapped_column(_prov_enum(), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("name", name="uq_trend_sources_name"),)


class TrendSnapshot(Base, UUIDPrimaryKeyMixin):
    """Immutable raw capture of a source at a point in time (docs: 08 §5.2).

    Append-only: no updated_at, no deleted_at. Dedup on (source, payload_hash).
    """

    __tablename__ = "trend_snapshots"

    trend_source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        UniqueConstraint("trend_source_id", "payload_hash", name="uq_trend_snapshots_source_hash"),
    )


class TrendSignal(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin, SoftDeleteMixin):
    """Normalized, niche-tagged observation extracted from a snapshot (docs: 08 §5.3)."""

    __tablename__ = "trend_signals"

    trend_snapshot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    micro_niche_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    signal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metric_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metric_value: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    metric_unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    data_provenance: Mapped[DataProvenance] = mapped_column(_prov_enum(), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    agent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class MarketMetric(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin):
    """Aggregated demand/competition/supply per micro-niche per period (docs: 08 §5.4).

    No delete path: metrics are historical facts.
    """

    __tablename__ = "market_metrics"

    micro_niche_id: Mapped[str] = mapped_column(String(36), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    demand_index: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    supply_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    competition_index: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    avg_price_estimate: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    data_provenance: Mapped[DataProvenance] = mapped_column(_prov_enum(), nullable=False)
    agent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "micro_niche_id",
            "period_start",
            "period_end",
            name="uq_market_metrics_niche_period",
        ),
    )


class Prediction(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin):
    """Probabilistic demand forecast per micro-niche + horizon (docs: 08 §5.5).

    Never presented as guaranteed sales. Supersession via superseded_by_id.
    """

    __tablename__ = "predictions"

    micro_niche_id: Mapped[str] = mapped_column(String(36), nullable=False)
    horizon: Mapped[PredictionHorizon] = mapped_column(
        SAEnum(PredictionHorizon, native_enum=False, length=16), nullable=False
    )
    predicted_demand_index: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    predicted_direction: Mapped[PredictedDirection] = mapped_column(
        SAEnum(PredictedDirection, native_enum=False, length=16), nullable=False
    )
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    methodology: Mapped[str] = mapped_column(Text, nullable=False)
    data_provenance: Mapped[DataProvenance] = mapped_column(
        _prov_enum(), nullable=False, default=DataProvenance.PREDICTED
    )
    based_on_metrics_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    based_on_metrics_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    agent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    superseded_by_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class Opportunity(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin, SoftDeleteMixin):
    """Human-actionable scored opportunity (docs: 08 §5.6).

    status ∈ new | approved | rejected | in_progress | archived (CONTRACT.md §5.4).
    """

    __tablename__ = "opportunities"

    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    micro_niche_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    opportunity_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    demand_evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    risk_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_provenance: Mapped[DataProvenance] = mapped_column(_prov_enum(), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    agent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
