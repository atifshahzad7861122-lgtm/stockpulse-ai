"""Production & submission models: assets, asset_versions, metadata, production_queue,
submission_records (docs: 08 §9).

The `metadata` table is named exactly that (CONTRACT.md §5.10); the ORM class is
MetadataRecord to avoid clashing with sqlalchemy.MetaData.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditTimestampsMixin, Base, SoftDeleteMixin, UUIDPrimaryKeyMixin, utcnow
from app.schemas.enums import AssetStatus, AssetType, ProductionQueueStatus, SubmissionStatus


class Asset(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin, SoftDeleteMixin):
    """Produced work identity row (docs: 08 §9.1); file versions in asset_versions."""

    __tablename__ = "assets"

    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    production_queue_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    image_idea_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    video_idea_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    prompt_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    prompt_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    asset_type: Mapped[AssetType] = mapped_column(
        SAEnum(AssetType, native_enum=False, length=8), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[AssetStatus] = mapped_column(
        SAEnum(AssetStatus, native_enum=False, length=16),
        nullable=False,
        default=AssetStatus.DRAFT,
    )
    current_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    storage_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    width_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)

    versions: Mapped[list[AssetVersion]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
        order_by="AssetVersion.version_number",
        primaryjoin="Asset.id == foreign(AssetVersion.asset_id)",
    )


class AssetVersion(Base, UUIDPrimaryKeyMixin):
    """Immutable file version (docs: 08 §9.2). Cascade-deleted with the asset."""

    __tablename__ = "asset_versions"

    asset_id: Mapped[str] = mapped_column(String(36), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    width_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    asset: Mapped[Asset] = relationship(
        back_populates="versions",
        primaryjoin="foreign(AssetVersion.asset_id) == Asset.id",
    )

    __table_args__ = (
        UniqueConstraint("asset_id", "version_number", name="uq_asset_versions_asset_number"),
    )


class MetadataRecord(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin):
    """Submission metadata bundle per asset (table: `metadata`, docs: 08 §9.3).

    Edits create new rows; exactly one is_current per asset. Never deleted.
    """

    __tablename__ = "metadata"

    asset_id: Mapped[str] = mapped_column(String(36), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    adobe_category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    micro_niche_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    agent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        UniqueConstraint("asset_id", "version_number", name="uq_metadata_asset_number"),
        # DB-level one-current-row-per-asset (partial unique index; SQLite + PG).
        Index(
            "uq_metadata_current_per_asset",
            "asset_id",
            unique=True,
            sqlite_where=text("is_current = 1"),
            postgresql_where=text("is_current = true"),
        ),
    )


class ProductionQueue(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin, SoftDeleteMixin):
    """Pipeline worklist — the 13-state queue (docs: 08 §9.4, 20).

    Legal transitions T01–T29 enforced at the API layer (schemas.enums).
    priority_band ∈ P0..P4 (docs: 20 §6).
    """

    __tablename__ = "production_queue"

    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    opportunity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    image_idea_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    video_idea_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    prompt_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    asset_type: Mapped[AssetType] = mapped_column(
        SAEnum(AssetType, native_enum=False, length=8), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[ProductionQueueStatus] = mapped_column(
        SAEnum(ProductionQueueStatus, native_enum=False, length=24),
        nullable=False,
        default=ProductionQueueStatus.DISCOVERED,
    )
    priority_band: Mapped[str] = mapped_column(String(2), nullable=False, default="P2")
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    target_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    produced_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generation_tool: Mapped[str | None] = mapped_column(String(120), nullable=True)
    rework_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class SubmissionRecord(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin):
    """Log of Adobe Stock submissions — created only from explicit user action.

    The platform NEVER auto-submits (docs: 08 §9.5, CONTRACT.md §5.12).
    """

    __tablename__ = "submission_records"

    asset_id: Mapped[str] = mapped_column(String(36), nullable=False)
    asset_version_id: Mapped[str] = mapped_column(String(36), nullable=False)
    metadata_id: Mapped[str] = mapped_column(String(36), nullable=False)
    production_queue_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[SubmissionStatus] = mapped_column(
        SAEnum(SubmissionStatus, native_enum=False, length=16),
        nullable=False,
        default=SubmissionStatus.PLANNED,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    adobe_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
