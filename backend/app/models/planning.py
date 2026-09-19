"""Daily production planning models: daily_production_plans,
production_recommendations, concept_variations, prompt_packs (Phase 3).

Hard rules (enforced at the service/API layer):
- Nothing auto-generates or auto-submits. Every recommendation needs an
  explicit user action (approve/reject/edit/regenerate/prioritize/archive).
- HIGH_RISK compliance concepts never promote to the production queue.
- Never claim assets were auto-generated; Muse is export-only.
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

from app.db.base import AuditTimestampsMixin, Base, UUIDPrimaryKeyMixin, utcnow
from app.schemas.enums import AssetType, DataProvenance


def _prov_enum() -> SAEnum:
    return SAEnum(DataProvenance, native_enum=False, length=16)


class DailyProductionPlan(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin):
    """One plan per calendar day: the ranked "WHAT TO CREATE TODAY" list.

    status ∈ draft | active | completed. A plan starts as draft; the user
    activates it (or lets a slot mark it completed). Recommendations are the
    plan's rows.
    """

    __tablename__ = "daily_production_plans"

    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    target_images: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    target_videos: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    summary_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    data_provenance: Mapped[DataProvenance] = mapped_column(
        _prov_enum(), nullable=False, default=DataProvenance.ESTIMATED
    )

    __table_args__ = (
        UniqueConstraint("plan_date", name="uq_daily_production_plans_date"),
    )


class ProductionRecommendation(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin):
    """One ranked recommendation inside a daily plan.

    status ∈ recommended | approved | rejected | archived. Only an explicit
    user approve action creates a production_queue item (and only via legal
    queue transitions).
    """

    __tablename__ = "production_recommendations"

    plan_id: Mapped[str] = mapped_column(String(36), nullable=False)
    opportunity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    asset_type: Mapped[AssetType] = mapped_column(
        SAEnum(AssetType, native_enum=False, length=8), nullable=False
    )
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    micro_niche_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    unified_score: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    personal_fit: Mapped[float | None] = mapped_column(Numeric(6, 3), nullable=True)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="recommended")
    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class ConceptVariation(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin):
    """One distinct creative concept for a recommendation.

    concept_json carries the full spec (title, concept, commercial_use,
    subject, environment, composition, lighting, camera, perspective,
    orientation, aspect_ratio, originality_instructions,
    compliance_considerations — image variants — or title, scene, subject,
    action, movement, camera_movement, duration, orientation, loop_potential,
    commercial_use, visual_direction, originality_instructions,
    compliance_considerations — video variants).

    similarity_flags_json holds originality flags such as HIGH_SIMILARITY /
    POSSIBLE_DUPLICATE / LOW_ORIGINALITY with evidence.
    compliance_result ∈ PASS | REVIEW | HIGH_RISK (denormalized from
    compliance_result_json for easy filtering). HIGH_RISK blocks queue
    promotion until a human reviews it.
    """

    __tablename__ = "concept_variations"

    recommendation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    asset_type: Mapped[AssetType] = mapped_column(
        SAEnum(AssetType, native_enum=False, length=8), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    concept_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    originality_notes: Mapped[str] = mapped_column(Text, nullable=False)
    similarity_flags_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    compliance_result: Mapped[str | None] = mapped_column(String(16), nullable=True)
    compliance_result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    variation_round: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Explicit human decision: the asset produced from this concept WILL be
    # disclosed as AI-generated at submission time. NULL = not yet decided.
    # Setting this to True and re-screening clears the gen-01 BLOCK finding;
    # it is never defaulted — the user must record the decision explicitly.
    ai_disclosure: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)


class PromptPack(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin):
    """A generation prompt pack built from one concept variation.

    target_tool names the tool the pack is exported for (e.g. "muse").
    Export-only: no asset is ever generated from the pack automatically;
    the user copies the prompt into their own generation tool.
    """

    __tablename__ = "prompt_packs"

    concept_id: Mapped[str] = mapped_column(String(36), nullable=False)
    primary_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    alternative_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    negative_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    technical_requirements: Mapped[str] = mapped_column(Text, nullable=False)
    originality_instructions: Mapped[str] = mapped_column(Text, nullable=False)
    compliance_instructions: Mapped[str] = mapped_column(Text, nullable=False)
    target_tool: Mapped[str] = mapped_column(String(64), nullable=False, default="muse")
    format_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0")
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    export_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
