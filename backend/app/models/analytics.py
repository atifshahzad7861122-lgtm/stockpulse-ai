"""Analytics models: performance_metrics, saved_items (docs: 08 §10).

No invented Adobe sales statistics: rows carry data_provenance; only
USER_PROVIDED/VERIFIED rows may be treated as real dashboard numbers.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditTimestampsMixin, Base, UUIDPrimaryKeyMixin
from app.schemas.enums import DataProvenance, SavedItemKind


def _prov_enum() -> SAEnum:
    return SAEnum(DataProvenance, native_enum=False, length=16)


class PerformanceMetric(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin):
    """Time-series performance of submitted assets (docs: 08 §10.1).

    No delete path: corrections are new rows.
    """

    __tablename__ = "performance_metrics"

    asset_id: Mapped[str] = mapped_column(String(36), nullable=False)
    submission_record_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    micro_niche_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    downloads: Mapped[int | None] = mapped_column(Integer, nullable=True)
    revenue: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    data_provenance: Mapped[DataProvenance] = mapped_column(_prov_enum(), nullable=False)
    source_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "asset_id",
            "period_start",
            "period_end",
            "data_provenance",
            name="uq_performance_metrics_asset_period",
        ),
    )


class SavedItem(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin):
    """Polymorphic bookmark (docs: 08 §10.2). Unsaving = hard delete of the row."""

    __tablename__ = "saved_items"

    item_kind: Mapped[SavedItemKind] = mapped_column(
        SAEnum(SavedItemKind, native_enum=False, length=16), nullable=False
    )
    item_id: Mapped[str] = mapped_column(String(36), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("item_kind", "item_id", name="uq_saved_items_item"),)
