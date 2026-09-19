"""Personal Performance response schemas (Phase 3, backend).

Every shape carries the honest availability contract: when Adobe private data
is NOT_CONFIGURED, endpoints return ``status="not_configured"`` with nulls /
empty lists — never fabricated values.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import PageInfo
from app.schemas.enums import DataProvenance

AvailabilityStatus = Literal["available", "not_configured"]
TrendName = Literal["growing", "stable", "declining"]


class MomentumWindowOut(BaseModel):
    """One window (7d/30d/90d) vs the equal-length window before it.

    change_pct is a percentage (+23.5 = +23.5%). Thresholds: >+15% growing,
    <-15% declining, else stable (see services.personal_performance).
    available=False means a window lacked data — never shown as zero.
    """

    current: float | None = None
    previous: float | None = None
    change_pct: float | None = Field(
        default=None, description="Percentage change, e.g. 23.5 = +23.5%"
    )
    trend: TrendName | None = None
    available: bool = False


class MomentumPairOut(BaseModel):
    earnings: dict[str, MomentumWindowOut] = Field(default_factory=dict)
    downloads: dict[str, MomentumWindowOut] = Field(default_factory=dict)


class AcceptanceOut(BaseModel):
    accepted: int = 0
    rejected: int = 0
    pending: int = 0
    acceptance_rate: float | None = None
    available: bool = False


class ConsistencyOut(BaseModel):
    """Weekly-earnings stability: 100 = perfectly stable, 0 = wild swings."""

    score: float | None = Field(
        default=None, ge=0, le=100, description="0-100 stability, or None when unavailable"
    )
    cv: float | None = None
    weeks_with_data: int = 0
    weekly_earnings: list[float] = Field(default_factory=list)
    available: bool = False


class CategoryMetricOut(BaseModel):
    available: bool = True
    category: str
    period_days: int
    assets_total: int | None = None
    assets_accepted: int | None = Field(
        default=None, description="Not derivable: submission rows lack category linkage"
    )
    assets_rejected: int | None = Field(
        default=None, description="Not derivable: submission rows lack category linkage"
    )
    downloads: int | None = None
    earnings: float | None = None
    avg_downloads_per_asset: float | None = None
    avg_earnings_per_asset: float | None = None
    acceptance_rate: float | None = Field(
        default=None, description="Not derivable per category; see overall acceptance"
    )
    momentum: MomentumPairOut = Field(default_factory=MomentumPairOut)
    trend_label: TrendName | None = None


class ContentTypeMetricOut(BaseModel):
    """Image vs video, measured independently — never cross-inferred."""

    available: bool = True
    content_type: Literal["image", "video", "unknown"]
    period_days: int
    assets_total: int | None = None
    assets_accepted: int | None = None
    assets_rejected: int | None = None
    downloads: int | None = None
    earnings: float | None = None
    avg_downloads_per_asset: float | None = None
    avg_earnings_per_asset: float | None = None
    acceptance_rate: float | None = None
    momentum: MomentumPairOut | None = None
    trend_label: TrendName | None = None


class ThemeMetricOut(BaseModel):
    """A data-derived theme: label + the evidence that produced it."""

    available: bool = True
    theme_label: str
    period_days: int
    asset_count: int | None = None
    downloads: int | None = None
    earnings: float | None = None
    evidence_keywords: list[str] = Field(default_factory=list)
    momentum: dict[str, dict[str, MomentumWindowOut]] = Field(default_factory=dict)
    trend_label: TrendName | None = None


class PersonalPerformanceSummary(BaseModel):
    """GET /personal-performance. Nulls/empties when not_configured."""

    status: AvailabilityStatus
    period: str
    period_days: int
    data_provenance: DataProvenance | None = None
    period_start: str | None = None
    period_end: str | None = None
    earnings_total: float | None = None
    downloads_total: int | None = None
    momentum: MomentumPairOut | None = None
    acceptance: AcceptanceOut | None = None
    consistency: ConsistencyOut | None = None
    top_categories: list[CategoryMetricOut] = Field(default_factory=list)
    top_themes: list[ThemeMetricOut] = Field(default_factory=list)
    availability: dict[str, Any] = Field(default_factory=dict)


class CategoryListOut(BaseModel):
    status: AvailabilityStatus
    period: str
    period_days: int
    data: list[CategoryMetricOut] = Field(default_factory=list)
    pagination: PageInfo


class ContentTypeListOut(BaseModel):
    status: AvailabilityStatus
    period: str
    period_days: int
    data: list[ContentTypeMetricOut] = Field(default_factory=list)
    pagination: PageInfo


class ThemeListOut(BaseModel):
    status: AvailabilityStatus
    period: str
    period_days: int
    data: list[ThemeMetricOut] = Field(default_factory=list)
    pagination: PageInfo


class SnapshotPersistOut(BaseModel):
    snapshot_id: str
    period: str
    period_days: int
    created: bool = True
