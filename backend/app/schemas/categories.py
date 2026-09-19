"""Taxonomy schemas (CONTRACT.md §5.3)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

TAXONOMY_VERSION = "taxonomy_v1.0"


class MicroNicheOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    description: str | None = None
    demand_score: float | None = None
    competition_score: float | None = None
    data_provenance: str
    is_system: bool


class SubcategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    description: str | None = None
    sort_order: int
    is_system: bool
    micro_niches: list[MicroNicheOut] = Field(default_factory=list)


class TrendCoverage(BaseModel):
    signal_count: int = 0
    avg_score: float | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    description: str | None = None
    sort_order: int
    is_system: bool
    taxonomy_version: str = TAXONOMY_VERSION
    created_at: datetime
    updated_at: datetime


class CategoryDetail(CategoryOut):
    subcategories: list[SubcategoryOut] = Field(default_factory=list)
    trend_coverage: TrendCoverage = Field(default_factory=TrendCoverage)
    saturation_notes: str | None = None
