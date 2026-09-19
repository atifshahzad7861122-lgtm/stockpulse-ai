"""Daily production planner schemas (Phase 3).

PlanStatus: draft | active | completed.
RecommendationStatus: recommended | approved | rejected | archived.
ConceptStatus: draft | screened | approved | archived.
Compliance outcomes stay PASS | REVIEW | HIGH_RISK (schemas.enums).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import MockLabeled
from app.schemas.enums import AssetType, DataProvenance

PlanStatus = Literal["draft", "active", "completed"]
RecommendationStatus = Literal["recommended", "approved", "rejected", "archived"]
ConceptStatus = Literal["draft", "screened", "approved", "archived"]
ComplianceOutcome = Literal["PASS", "REVIEW", "HIGH_RISK"]


# ---------------------------------------------------------------------------
# Capacity settings
# ---------------------------------------------------------------------------


class CapacitySettings(BaseModel):
    """User-configured daily production capacity (settings key
    "production_capacity"). Submission limits are NEVER hard-coded; they come
    from this user-editable setting."""

    weekly_capacity: int = Field(default=20, ge=0)
    daily_target: int = Field(default=4, ge=0)
    image_target: int = Field(default=3, ge=0)
    video_target: int = Field(default=1, ge=0)
    max_daily_generation: int = Field(default=10, ge=1)
    priority_preference: str = Field(default="score")


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------


class PlanBuildRequest(BaseModel):
    plan_date: date | None = Field(default=None, description="Defaults to today")
    target_images: int | None = Field(default=None, ge=0)
    target_videos: int | None = Field(default=None, ge=0)


class PlanSummaryOut(MockLabeled):
    model_config = ConfigDict(from_attributes=True)

    id: str
    plan_date: date
    target_images: int
    target_videos: int
    status: str
    recommendation_count: int = 0
    data_provenance: DataProvenance | None = None


class RecommendationOut(MockLabeled):
    model_config = ConfigDict(from_attributes=True)

    id: str
    plan_id: str
    opportunity_id: str | None = None
    rank: int
    asset_type: AssetType
    category: str | None = None
    micro_niche_id: str | None = None
    unified_score: float
    personal_fit: float | None = None
    confidence: float
    reason: str
    recommended_quantity: int
    status: str
    evidence_json: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class PlanDetailOut(PlanSummaryOut):
    summary_json: dict = Field(default_factory=dict)
    recommendations: list[RecommendationOut] = Field(default_factory=list)


class PlanStatusUpdate(BaseModel):
    status: PlanStatus


# ---------------------------------------------------------------------------
# Recommendation actions
# ---------------------------------------------------------------------------


class RecommendationUpdate(BaseModel):
    """User edit: only whitelisted fields may change."""

    asset_type: AssetType | None = None
    category: str | None = None
    reason: str | None = None
    recommended_quantity: int | None = Field(default=None, ge=1, le=50)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    note: str | None = None


class PrioritizeRequest(BaseModel):
    rank: int | None = Field(default=None, ge=1, description="Move to this rank")
    priority_note: str | None = None


class ApproveResponse(BaseModel):
    recommendation: RecommendationOut
    queue_item_id: str
    queue_status: str
    note: str


# ---------------------------------------------------------------------------
# Concepts
# ---------------------------------------------------------------------------


class ConceptGenerateRequest(BaseModel):
    count: int = Field(default=3, ge=1, le=6, description="Distinct concept variations")


class ConceptOut(MockLabeled):
    model_config = ConfigDict(from_attributes=True)

    id: str
    recommendation_id: str
    asset_type: AssetType
    title: str
    concept_json: dict = Field(default_factory=dict)
    originality_notes: str
    similarity_flags_json: dict = Field(default_factory=dict)
    compliance_result: str | None = None
    compliance_result_json: dict | None = None
    variation_round: int = 1
    status: str
    ai_disclosure: bool | None = None
    created_at: datetime
    updated_at: datetime


class ConceptStatusUpdate(BaseModel):
    status: ConceptStatus
    # Optional explicit disclosure decision. When provided, the concept is
    # re-screened with the decision recorded; clearing the gen-01 BLOCK
    # moves the concept out of HIGH_RISK (other findings may still block).
    ai_disclosure: bool | None = None


# ---------------------------------------------------------------------------
# Prompt packs
# ---------------------------------------------------------------------------


class PromptPackOut(MockLabeled):
    model_config = ConfigDict(from_attributes=True)

    id: str
    concept_id: str
    primary_prompt: str
    alternative_prompt: str | None = None
    negative_prompt: str
    technical_requirements: str
    originality_instructions: str
    compliance_instructions: str
    target_tool: str
    format_version: str
    exported_at: datetime | None = None
    export_uri: str | None = None
    created_at: datetime
    updated_at: datetime


class PromptPackGenerateRequest(BaseModel):
    target_tool: str = Field(default="muse", description="Tool the pack is exported for")
    format_version: str = Field(default="1.0")


class PromptPackExportOut(BaseModel):
    prompt_pack_id: str
    export_uri: str
    provider: str
    provenance: str
    note: str = Field(
        default="Export only — the asset was NOT auto-generated. "
        "Copy the prompt into your generation tool yourself."
    )


# ---------------------------------------------------------------------------
# Queue transition helper (used by recommendation approval)
# ---------------------------------------------------------------------------


class QueueTransitionRequest(BaseModel):
    to: str
    note: str | None = None


class GenerationProviderInfo(BaseModel):
    name: str
    health: dict[str, Any] = Field(default_factory=dict)
    export_only: bool = Field(default=True)
