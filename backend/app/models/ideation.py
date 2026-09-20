"""Ideation models: image_ideas / video_ideas (docs: 08 §6).

originality_notes is mandatory at creation (enforced at the API layer too).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditTimestampsMixin, Base, SoftDeleteMixin, UUIDPrimaryKeyMixin
from app.schemas.enums import IdeaStatus


def _idea_status_enum() -> SAEnum:
    return SAEnum(IdeaStatus, native_enum=False, length=16)


class ImageIdea(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin, SoftDeleteMixin):
    """Original still-image concept (docs: 08 §6.1)."""

    __tablename__ = "image_ideas"

    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    opportunity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    micro_niche_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    concept: Mapped[str] = mapped_column(Text, nullable=False)
    originality_notes: Mapped[str] = mapped_column(Text, nullable=False)
    reference_mood: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[IdeaStatus] = mapped_column(
        _idea_status_enum(), nullable=False, default=IdeaStatus.DRAFT
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    agent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    data_provenance: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        comment="Provenance label from the generating LLM provider "
        "(MOCK / THIRD_PARTY). Wins over the agent_run_id inference in "
        "resolve_provenance so real provider output is never mislabeled MOCK.",
    )


class VideoIdea(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin, SoftDeleteMixin):
    """Original video/motion concept (docs: 08 §6.2)."""

    __tablename__ = "video_ideas"

    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    opportunity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    micro_niche_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    concept: Mapped[str] = mapped_column(Text, nullable=False)
    originality_notes: Mapped[str] = mapped_column(Text, nullable=False)
    duration_target_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shot_list: Mapped[list | None] = mapped_column(JSON, nullable=True)
    reference_mood: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[IdeaStatus] = mapped_column(
        _idea_status_enum(), nullable=False, default=IdeaStatus.DRAFT
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    agent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    data_provenance: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        comment="Provenance label from the generating LLM provider "
        "(MOCK / THIRD_PARTY). Wins over the agent_run_id inference in "
        "resolve_provenance so real provider output is never mislabeled MOCK.",
    )
