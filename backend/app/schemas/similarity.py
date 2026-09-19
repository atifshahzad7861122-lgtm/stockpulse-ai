"""Similarity schemas (CONTRACT.md §5.8)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import MockLabeled
from app.schemas.enums import DataProvenance, RiskLevel

SimilaritySubjectKind = Literal["image_idea", "video_idea", "prompt", "asset"]


class SimilarityCheckCreate(BaseModel):
    subject_kind: SimilaritySubjectKind
    subject_id: str


class SimilarityMatchOut(BaseModel):
    compared_cluster_label: str
    similarity_score: float = Field(ge=0, le=1)
    risk_level: RiskLevel
    cluster_sample_count: int | None = None
    differentiators: str | None = None


class SimilarityCheckOut(MockLabeled):
    model_config = ConfigDict(from_attributes=True)

    id: str
    subject: dict = Field(default_factory=dict)
    verdict: str
    max_score: float = Field(ge=0, le=1)
    risk_level: RiskLevel
    records: list[SimilarityMatchOut] = Field(default_factory=list)
    embedding_status: str = "embedding-unavailable"
    explanation: str | None = None
    data_provenance: DataProvenance
    created_at: datetime
