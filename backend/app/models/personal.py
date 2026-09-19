"""Phase 3 personal performance tables (PERSONAL INTELLIGENCE).

All tables here aggregate the USER's OWN private data (append-only tables in
app.models.private). Rows are derived snapshots/metrics computed by
app.services.personal_performance — the private source rows are never edited.

Hard rules (same as private.py):
- data_provenance defaults to USER_PROVIDED. MOCK rows are excluded from
  intelligence unless dev mode is on (app.services.dev_mode).
- Absence of rows = "not available": metric fields stay NULL and availability
  is reported honestly, never as zeros disguised as data.
- No guarantees language anywhere: these are descriptive metrics
  ("opportunity/potential/confidence"), never promises of sales.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, Integer, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin, utcnow
from app.schemas.enums import DataProvenance, TrendLabel


def _prov_enum() -> SAEnum:
    return SAEnum(DataProvenance, native_enum=False, length=16)


class _PersonalBase:
    """Shared columns for personal (user-derived) tables."""

    data_provenance: Mapped[DataProvenance] = mapped_column(
        _prov_enum(), nullable=False, default=DataProvenance.USER_PROVIDED
    )


class PersonalPerformanceSnapshot(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin, _PersonalBase):
    """Persisted aggregate snapshot of the user's performance for one period.

    ``metrics_json`` carries the full engine output (totals, momentum,
    acceptance, consistency, top categories/themes) so historical "how was I
    doing then" views work without recomputing from raw rows.
    """

    __tablename__ = "personal_performance_snapshots"

    period_days: Mapped[int] = mapped_column(Integer, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    metrics_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class PersonalCategoryMetric(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin, _PersonalBase):
    """Per-category performance metrics for a period.

    ``assets_accepted`` / ``assets_rejected`` / ``acceptance_rate`` stay NULL
    per category because PrivateSubmissionResult rows carry no category
    linkage — acceptance is only reported at the overall level. NULL means
    "not derivable", never zero.
    """

    __tablename__ = "personal_category_metrics"

    category: Mapped[str] = mapped_column(String(120), nullable=False)
    period_days: Mapped[int] = mapped_column(Integer, nullable=False)
    assets_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assets_accepted: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assets_rejected: Mapped[int | None] = mapped_column(Integer, nullable=True)
    downloads: Mapped[int | None] = mapped_column(Integer, nullable=True)
    earnings: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    avg_downloads_per_asset: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_earnings_per_asset: Mapped[float | None] = mapped_column(Float, nullable=True)
    acceptance_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    momentum_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    trend_label: Mapped[TrendLabel | None] = mapped_column(
        SAEnum(TrendLabel, native_enum=False, length=12), nullable=True
    )


class PersonalContentTypeMetric(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin, _PersonalBase):
    """Per content-type (image / video) performance metrics for a period.

    Images and videos are measured INDEPENDENTLY — image performance is never
    used as a proxy for video performance. Assets that cannot be classified
    honestly are bucketed under ``"unknown"``, never guessed.
    """

    __tablename__ = "personal_content_type_metrics"

    content_type: Mapped[str] = mapped_column(String(16), nullable=False)  # image|video|unknown
    period_days: Mapped[int] = mapped_column(Integer, nullable=False)
    assets_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assets_accepted: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assets_rejected: Mapped[int | None] = mapped_column(Integer, nullable=True)
    downloads: Mapped[int | None] = mapped_column(Integer, nullable=True)
    earnings: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    avg_downloads_per_asset: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_earnings_per_asset: Mapped[float | None] = mapped_column(Float, nullable=True)
    acceptance_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    momentum_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    trend_label: Mapped[TrendLabel | None] = mapped_column(
        SAEnum(TrendLabel, native_enum=False, length=12), nullable=True
    )


class PersonalThemeMetric(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin, _PersonalBase):
    """Data-derived content themes for a period.

    Theme labels are DERIVED from the user's own asset titles/keywords by
    tokenization + co-occurrence (see services.personal_performance) — they
    are never hard-coded conclusions. ``evidence_keywords_json`` records the
    tokens/keywords that produced the label so the derivation is auditable.
    """

    __tablename__ = "personal_theme_metrics"

    theme_label: Mapped[str] = mapped_column(String(120), nullable=False)
    period_days: Mapped[int] = mapped_column(Integer, nullable=False)
    asset_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    downloads: Mapped[int | None] = mapped_column(Integer, nullable=True)
    earnings: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    evidence_keywords_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    momentum_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    trend_label: Mapped[TrendLabel | None] = mapped_column(
        SAEnum(TrendLabel, native_enum=False, length=12), nullable=True
    )


class PersonalKeywordMetric(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin, _PersonalBase):
    """Per-keyword performance for a period (from PrivateKeywordPerformance)."""

    __tablename__ = "personal_keyword_metrics"

    keyword: Mapped[str] = mapped_column(String(120), nullable=False)
    period_days: Mapped[int] = mapped_column(Integer, nullable=False)
    downloads: Mapped[int | None] = mapped_column(Integer, nullable=True)
    earnings: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    asset_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # NULL: private keyword rows carry no asset linkage


class PersonalFitScore(Base, UUIDPrimaryKeyMixin, _PersonalBase):
    """Persisted personal-fit score for an opportunity and/or micro-niche.

    The score itself is computed by the Opportunity Fusion module (sibling);
    this table stores it with every component value in ``component_json`` so
    the number is reproducible and auditable. ``score`` may be NULL when the
    user's data cannot support a score (honest "cannot compute").
    """

    __tablename__ = "personal_fit_scores"

    opportunity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    micro_niche_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    component_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    formula_version: Mapped[str] = mapped_column(String(32), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


__all__ = [
    "PersonalCategoryMetric",
    "PersonalContentTypeMetric",
    "PersonalFitScore",
    "PersonalKeywordMetric",
    "PersonalPerformanceSnapshot",
    "PersonalThemeMetric",
]
