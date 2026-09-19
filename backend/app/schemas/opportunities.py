"""Opportunity schemas (CONTRACT.md §5.4)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import MockLabeled
from app.schemas.enums import DataProvenance, StrEnum


class OpportunityStatus(StrEnum):
    """Opportunity lifecycle (CONTRACT.md §5.4). Lowercase values are the
    contract serialization; StrEnum members compare equal to plain strings."""

    NEW = "new"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"
    ARCHIVED = "archived"


class DemandEvidenceItem(BaseModel):
    signal_id: str | None = None
    metric_id: str | None = None
    note: str | None = None

    model_config = ConfigDict(extra="allow")


class OpportunityOut(MockLabeled):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str | None = None
    micro_niche_id: str | None = None
    title: str
    summary: str
    opportunity_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    demand_evidence: list[dict[str, Any]] = Field(default_factory=list)
    risk_notes: str | None = None
    data_provenance: DataProvenance
    status: str
    priority: int
    reviewed_at: datetime | None = None
    agent_run_id: str | None = None
    personal_fit_score: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Personal Fit Score 0–100 vs the user's own private performance; "
        "null when no private data (never guessed). Separate from opportunity_score "
        "(CONTRACT.md §5.4, v0.3.0).",
    )
    created_at: datetime
    updated_at: datetime


class OpportunityCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    summary: str = Field(min_length=10)
    micro_niche_id: str | None = None
    project_id: str | None = None
    priority: int = Field(default=0, ge=0)


class OpportunityUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    summary: str | None = Field(default=None, min_length=10)
    micro_niche_id: str | None = None
    priority: int | None = Field(default=None, ge=0)
    risk_notes: str | None = None


class OpportunityApprove(BaseModel):
    priority: Literal["high", "normal", "low"] | None = None
    note: str | None = None


class OpportunityApproveResponse(BaseModel):
    id: str
    status: Literal["approved"]
    approved_at: datetime


class OpportunityReject(BaseModel):
    reason: str = Field(min_length=3)
