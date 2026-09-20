"""Trend schemas (CONTRACT.md §5.2)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import MockLabeled
from app.schemas.enums import DataProvenance

Window = Literal["7d", "30d", "90d"]


class TrendSourceOut(MockLabeled):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    source_type: str
    endpoint_or_reference: str | None = None
    fetch_schedule: str | None = None
    is_active: bool
    last_fetched_at: datetime | None = None
    data_provenance: DataProvenance
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class TrendItem(BaseModel):
    id: str
    title: str
    score: float = Field(ge=0, le=100)
    window: Window = "7d"
    provenance: DataProvenance
    mock: bool = Field(default=False, description="Payload-level mock flag (CONTRACT.md §3)")
    categories: list[str] = Field(default_factory=list)
    signal_count: int = 0
    created_at: datetime
    updated_at: datetime
    # 7D/30D momentum + signal bands (FINAL MASTER SPEC §10–12). signal_30d /
    # momentum_30d are None when the 30-day window has insufficient history.
    momentum_7d: str | None = None
    momentum_30d: str | None = None
    signal_7d: str | None = None
    signal_30d: str | None = None
    signal_kind: str | None = None


class SignalBreakdown(BaseModel):
    signal_name: str
    metric_name: str | None = None
    metric_value: float | None = None
    metric_unit: str | None = None
    source_name: str | None = None
    provenance: DataProvenance
    mock: bool = Field(default=False, description="Payload-level mock flag (CONTRACT.md §3)")
    confidence: float | None = None
    observed_at: datetime


class TrendDetail(TrendItem):
    signals: list[SignalBreakdown] = Field(default_factory=list)
    analysis: dict[str, Any] = Field(default_factory=dict)


class TrendRefreshResponse(BaseModel):
    job_id: str
