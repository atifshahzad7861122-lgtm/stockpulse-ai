"""Market intelligence schemas (FINAL MASTER SPEC §10–18)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CategoryIntelOut(BaseModel):
    name: str
    slug: str
    signal_7d: str
    signal_30d: str
    momentum: str
    trend_signal: float = Field(ge=0, le=100)
    frequency: int
    topic_count: int
    sources: list[str] = Field(default_factory=list)
    last_updated: str | None = None
    provenance: str


class TopicIntelOut(BaseModel):
    topic: str
    category: str | None = None
    asset_type: str
    signal_7d: str
    signal_30d: str | None = None
    momentum: str
    momentum_7d: str
    momentum_30d: str | None = None
    trend_signal: float = Field(ge=0, le=100)
    momentum_7d_score: float = Field(ge=0, le=100)
    momentum_30d_score: float | None = None
    opportunity_signal: float = Field(ge=0, le=100)
    frequency: int
    keywords: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    signal_kind: str
    provenance: str
    last_updated: str | None = None
    explanation: str


class KeywordIntelOut(BaseModel):
    keyword: str
    frequency: int
    movement_7d: str
    movement_30d: str
    related_category: str | None = None
    related_image_topics: list[str] = Field(default_factory=list)
    related_video_topics: list[str] = Field(default_factory=list)
    source: str | None = None


class MoverOut(BaseModel):
    topic: str
    asset_type: str
    momentum: str
    signal_7d: str
    signal_30d: str | None = None
    trend_signal: float = Field(ge=0, le=100)


class WindowComparisonOut(BaseModel):
    topic: str
    signal_7d: str
    signal_30d: str | None = None
    momentum: str
    momentum_7d: str
    momentum_30d: str | None = None
    trend_signal: float = Field(ge=0, le=100)
    momentum_7d_score: float = Field(ge=0, le=100)
    momentum_30d_score: float | None = None


class MarketIntelligenceOverview(BaseModel):
    generated_at: str
    last_data_update: str | None = None
    topic_count: int
    top_categories: list[CategoryIntelOut]
    top_image_topics: list[TopicIntelOut]
    top_video_topics: list[TopicIntelOut]
    top_keywords: list[KeywordIntelOut]
    rising_now: list[MoverOut]
    declining_now: list[MoverOut]
    window_comparison: list[WindowComparisonOut]
