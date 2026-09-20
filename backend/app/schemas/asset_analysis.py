"""Asset analyzer schemas (FINAL MASTER SPEC §21–32)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AssetAnalysisGenerate(BaseModel):
    opportunity_id: str
    asset_type: Literal["image", "video"]


class CommercialAnalysisOut(BaseModel):
    topic: str | None = None
    category: str | None = None
    micro_niche: str | None = None
    primary_keywords: list[str] = Field(default_factory=list)
    secondary_keywords: list[str] = Field(default_factory=list)
    commercial_use_case: str | None = None
    subject: str | None = None
    environment: str | None = None
    composition: str | None = None
    visual_characteristics: str | None = None
    content_type: str | None = None


class AssetAnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    opportunity_id: str
    asset_type: str
    status: str
    market_context: dict[str, Any] = Field(default_factory=dict)
    commercial_analysis: CommercialAnalysisOut = Field(default_factory=CommercialAnalysisOut)
    original_concept: str | None = None
    prompt_a: str | None = None
    prompt_b: str | None = None
    prompt_c: str | None = None
    negative_prompt: str | None = None
    model: str | None = None
    provenance: str = "THIRD_PARTY"
    error_message: str | None = None
    created_at: datetime
