"""Phase 2 private (user-owned) time-series tables (PHASE2_DESIGN.md §3).

ALL TABLES ARE APPEND-ONLY: never update history rows. Each row records the
user's OWN Adobe Stock performance data, labeled
``data_provenance=USER_PROVIDED``. Absence of rows is a real signal (no data
→ personal_fit_score is None; confidence is lowered) — rows are never
invented or simulated.

UUID String(36) PKs, utcnow mixin, same style as models/intelligence.py.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin, utcnow
from app.schemas.enums import DataProvenance


def _prov_enum() -> SAEnum:
    return SAEnum(DataProvenance, native_enum=False, length=16)


class _PrivateBase:
    """Shared columns for private tables."""

    collection_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("collection_runs.id"), nullable=True
    )
    source: Mapped[str | None] = mapped_column(String(64), nullable=True, default="adobe_contributor")
    data_provenance: Mapped[DataProvenance] = mapped_column(
        _prov_enum(), nullable=False, default=DataProvenance.USER_PROVIDED
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class PrivateDailyEarning(Base, UUIDPrimaryKeyMixin, _PrivateBase):
    """Daily earnings total — one row per date (append-only)."""

    __tablename__ = "private_daily_earnings"

    date: Mapped[date] = mapped_column(Date, nullable=False)
    earnings: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    downloads: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (UniqueConstraint("date", name="uq_private_daily_earnings_date"),)


class PrivateDownload(Base, UUIDPrimaryKeyMixin, _PrivateBase):
    """Per-asset downloads on a date (time-series)."""

    __tablename__ = "private_downloads"

    date: Mapped[date] = mapped_column(Date, nullable=False)
    asset_external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    downloads: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("date", "asset_external_id", name="uq_private_downloads_date_asset"),
    )


class PrivateSale(Base, UUIDPrimaryKeyMixin, _PrivateBase):
    """Per-asset sales on a date (time-series)."""

    __tablename__ = "private_sales"

    date: Mapped[date] = mapped_column(Date, nullable=False)
    asset_external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    earnings: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    license_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint("date", "asset_external_id", "license_type", name="uq_private_sales_date_asset_license"),
    )


class PrivateAssetPerformance(Base, UUIDPrimaryKeyMixin, _PrivateBase):
    """Per-asset cumulative performance snapshot on a date."""

    __tablename__ = "private_asset_performance"

    asset_external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    downloads_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    earnings_total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    views: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "asset_external_id", "snapshot_date", name="uq_private_asset_perf_asset_date"
        ),
    )


class PrivateSubmissionResult(Base, UUIDPrimaryKeyMixin, _PrivateBase):
    """Submission review outcomes for the user's own assets."""

    __tablename__ = "private_submission_results"

    asset_external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # ACCEPTED/REJECTED/PENDING
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class PrivateCategoryPerformance(Base, UUIDPrimaryKeyMixin, _PrivateBase):
    """Category-level performance snapshot on a date."""

    __tablename__ = "private_category_performance"

    category: Mapped[str] = mapped_column(String(120), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    downloads: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    earnings: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    asset_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("category", "snapshot_date", name="uq_private_cat_perf_cat_date"),
    )


class PrivateKeywordPerformance(Base, UUIDPrimaryKeyMixin, _PrivateBase):
    """Keyword-level performance snapshot on a date."""

    __tablename__ = "private_keyword_performance"

    keyword: Mapped[str] = mapped_column(String(120), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    downloads: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    earnings: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("keyword", "snapshot_date", name="uq_private_kw_perf_kw_date"),
    )


class PrivateSnapshot(Base, UUIDPrimaryKeyMixin, _PrivateBase):
    """Daily summary snapshot (totals for the day)."""

    __tablename__ = "private_snapshots"

    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    summary_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (UniqueConstraint("snapshot_date", name="uq_private_snapshots_date"),)


class PrivateCollectionRun(Base, UUIDPrimaryKeyMixin):
    """Collection runs against the user's private (Adobe) data."""

    __tablename__ = "private_collection_runs"

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="QUEUED")
    records_collected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger: Mapped[str] = mapped_column(String(16), nullable=False, default="SCHEDULED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


__all__ = [
    "PrivateAssetPerformance",
    "PrivateCategoryPerformance",
    "PrivateCollectionRun",
    "PrivateDailyEarning",
    "PrivateDownload",
    "PrivateKeywordPerformance",
    "PrivateSale",
    "PrivateSnapshot",
    "PrivateSubmissionResult",
]
