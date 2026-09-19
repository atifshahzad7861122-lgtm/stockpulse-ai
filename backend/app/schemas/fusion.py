"""Opportunity-fusion schemas (Phase 3)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import DataProvenance


class FusionComputeRequest(BaseModel):
    """POST /opportunity-fusion/compute body.

    Only ``opportunity_id`` is required. Market inputs left as null fall back
    to the neutral 50.0 default and are labeled ESTIMATED in component_json —
    they are never presented as measured. Personal inputs are NEVER accepted
    here: they come only from the private tables (None when absent).
    """

    opportunity_id: str = Field(min_length=1, max_length=36)
    trend_momentum: float | None = Field(default=None, ge=0, le=100)
    commercial_potential: float | None = Field(default=None, ge=0, le=100)
    seasonality: float | None = Field(default=None, ge=0, le=100)
    saturation_risk: float | None = Field(default=None, ge=0, le=100)
    data_freshness: float | None = Field(default=None, ge=0, le=1)
    n_sources: int | None = Field(default=None, ge=0)
    historical_consistency: float | None = Field(default=None, ge=0, le=1)
    market_signal_strength: float | None = Field(default=None, ge=0, le=100)
    demand_evidence_notes: list[str] = Field(default_factory=list)


class FusionComponentDetail(BaseModel):
    value: float | None = Field(ge=0, le=100)
    provenance: str


class FusionScoreOut(BaseModel):
    """Latest fusion score for an opportunity, with full breakdown."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    opportunity_id: str
    unified_score: float = Field(ge=0, le=100)
    market_opportunity: float = Field(ge=0, le=100)
    personal_fit: float | None = Field(default=None, ge=0, le=100)
    trend_momentum: float = Field(ge=0, le=100)
    commercial_potential: float = Field(ge=0, le=100)
    seasonality: float = Field(ge=0, le=100)
    saturation_risk: float = Field(ge=0, le=100)
    prediction_confidence: float = Field(ge=0, le=100)
    personal_momentum: float | None = Field(default=None, ge=0, le=100)
    historical_performance: float | None = Field(default=None, ge=0, le=100)
    component_json: dict[str, Any] = Field(
        description="Per-input {value, provenance}, weights used, saturation "
        "penalty, special case, explanation renderer."
    )
    explanation: str = Field(description="Evidence-grounded WHY paragraph.")
    confidence_score: float = Field(ge=0, le=100)
    confidence_factors_json: dict[str, Any] = Field(
        description="Confidence factor breakdown (freshness, sources, "
        "consistency, prediction confidence, private availability, signal)."
    )
    label: Literal["FUSED", "MARKET-ONLY"]
    data_provenance: DataProvenance
    computed_at: datetime
    created_at: datetime
    updated_at: datetime
