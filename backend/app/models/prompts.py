"""Prompt models: prompts (identity) + prompt_versions (immutable history).

docs: 08 §7, 14_PROMPT_ENGINE_SPECIFICATION §7. Exactly one of image_idea_id /
video_idea_id is set (enforced at API layer).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditTimestampsMixin, Base, SoftDeleteMixin, UUIDPrimaryKeyMixin, utcnow
from app.schemas.enums import AssetType, PromptStatus


class Prompt(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin, SoftDeleteMixin):
    """Generation prompt identity; text lives in prompt_versions."""

    __tablename__ = "prompts"

    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    image_idea_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    video_idea_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    asset_type: Mapped[AssetType] = mapped_column(
        SAEnum(AssetType, native_enum=False, length=8), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[PromptStatus] = mapped_column(
        SAEnum(PromptStatus, native_enum=False, length=16),
        nullable=False,
        default=PromptStatus.DRAFT,
    )
    current_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    versions: Mapped[list[PromptVersion]] = relationship(
        back_populates="prompt",
        cascade="all, delete-orphan",
        order_by="PromptVersion.version_number",
        primaryjoin="Prompt.id == foreign(PromptVersion.prompt_id)",
    )


class PromptVersion(Base, UUIDPrimaryKeyMixin):
    """Immutable prompt text version (docs: 08 §7.2). Never mutated in place."""

    __tablename__ = "prompt_versions"

    prompt_id: Mapped[str] = mapped_column(String(36), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    negative_prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    agent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    prompt: Mapped[Prompt] = relationship(
        back_populates="versions",
        primaryjoin="foreign(PromptVersion.prompt_id) == Prompt.id",
    )

    __table_args__ = (
        UniqueConstraint("prompt_id", "version_number", name="uq_prompt_versions_prompt_number"),
    )
