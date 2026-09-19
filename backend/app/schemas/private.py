"""Schemas for /api/private (CONTRACT.md §5.19, PHASE2_DESIGN.md §5).

Adobe Contributor session config is stored server-side in the settings table
and is NEVER echoed back in any response — only presence/configured flags.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class AdobeConnectionOut(BaseModel):
    status: str = Field(description="NOT_CONFIGURED | CONFIGURED | ERROR")
    configured: bool = False
    session_type: str | None = None
    required_config: list[str] = Field(default_factory=list)
    last_sync: datetime | None = None
    error: str | None = None


class AdobeConnectionUpdate(BaseModel):
    session_type: str = Field(
        min_length=1,
        max_length=60,
        description="How the session was captured, e.g. 'browser_export'.",
    )
    session_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Session material (cookies/tokens). Stored server-side ONLY — never returned.",
    )
    notes: str | None = Field(default=None, max_length=500)


class AdobeConnectionUpdateOut(BaseModel):
    status: str
    configured: bool
    session_type: str | None = None
    last_sync: datetime | None = None
    message: str


class ConnectionTestOut(BaseModel):
    valid: bool
    missing: list[str] = Field(default_factory=list)
    message: str = Field(
        description="Presence/format validation only — never simulates a real connection."
    )


class PerformanceTotals(BaseModel):
    earnings: float = 0.0
    downloads: int = 0
    currency: str = "USD"
    assets_tracked: int = 0


class CategoryPerformanceOut(BaseModel):
    category: str
    downloads: int = 0
    earnings: float = 0.0
    asset_count: int = 0
    snapshot_date: date | None = None


class KeywordPerformanceOut(BaseModel):
    keyword: str
    downloads: int = 0
    earnings: float = 0.0
    snapshot_date: date | None = None


class TrendPoint(BaseModel):
    date: date
    earnings: float = 0.0
    downloads: int = 0


class PerformanceSummaryOut(BaseModel):
    """Honest empty state: has_data=false when nothing has been collected."""

    has_data: bool = False
    totals: PerformanceTotals | None = None
    earnings_trend: list[TrendPoint] = Field(default_factory=list)
    downloads_trend: list[TrendPoint] = Field(default_factory=list)
    by_category: list[CategoryPerformanceOut] = Field(default_factory=list)
    acceptance_rate: float | None = Field(
        default=None, description="Accepted / (accepted + rejected) from submission results."
    )
    message: str | None = None
