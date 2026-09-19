"""Analytics schemas (CONTRACT.md §5.13).

Every metric carries data_provenance; predictions show confidence, never
guarantees. No invented Adobe sales numbers.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import DataProvenance


class KpiValue(BaseModel):
    value: float | int | None
    provenance: DataProvenance


class AnalyticsOverview(BaseModel):
    range: dict[str, date]
    kpis: dict[str, KpiValue]
    provenance_notes: str


class FunnelStage(BaseModel):
    stage: str
    count: int


class AnalyticsFunnel(BaseModel):
    stages: list[FunnelStage]


class OpportunityPerformance(BaseModel):
    opportunity_id: str
    submissions: int
    accepted: int
    acceptance_rate: float | None
    sample_warning: str | None = None
    provenance_notes: str


class AnalyticsEvent(BaseModel):
    name: str = Field(pattern=r"^[a-z0-9_]+\.[a-z0-9_]+$")
    entity_id: str | None = None
    route: str | None = None
    at: datetime | None = None


class AnalyticsEventsIngest(BaseModel):
    events: list[AnalyticsEvent] = Field(min_length=1, max_length=500)


class ExportRequest(BaseModel):
    format: Literal["csv", "pdf"] = "csv"
    from_date: date | None = None
    to_date: date | None = None


class ExportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str = "export"
    status: str = "ready"
    download_url: str | None = None
    created_at: datetime
