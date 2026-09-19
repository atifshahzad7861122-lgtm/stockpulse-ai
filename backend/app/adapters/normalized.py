"""Normalized signal dataclasses shared by all Phase 2 adapters.

These are the ONLY shapes adapters may emit. Field names are frozen by
PHASE2_DESIGN.md §1 (contract between implementation children):

    TrendSignalInput(micro_niche_id?, signal_name, description, metric_name,
        metric_value, metric_unit, observed_at, provenance, confidence,
        source_id, collection_method, data_timestamp, raw_reference)

``provenance`` is a :class:`DataProvenance` value (CONTRACT.md §3 is binding):
real public rows → THIRD_PARTY (VERIFIED only for official APIs);
private real rows → USER_PROVIDED. There is NO ``is_mock`` boolean anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.schemas.enums import DataProvenance

__all__ = [
    "TrendSignalInput",
    "MarketMetricInput",
    "PrivateSignalInput",
    "NormalizedSignal",
]


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class TrendSignalInput:
    """Normalized public trend observation → TrendSignal row (via TrendSnapshot)."""

    signal_name: str
    description: str | None = None
    metric_name: str | None = None
    metric_value: float | None = None
    metric_unit: str | None = None
    observed_at: datetime = field(default_factory=_utcnow)
    provenance: DataProvenance = DataProvenance.THIRD_PARTY
    confidence: float = 0.5
    micro_niche_id: str | None = None
    source_id: str | None = None
    collection_method: str = "adapter"
    data_timestamp: datetime | None = None
    raw_reference: dict = field(default_factory=dict)


@dataclass
class MarketMetricInput:
    """Aggregated demand/competition observation → MarketMetric row."""

    micro_niche_id: str
    period_start: str  # ISO date
    period_end: str  # ISO date
    demand_index: float | None = None
    supply_count: int | None = None
    competition_index: float | None = None
    avg_price_estimate: float | None = None
    provenance: DataProvenance = DataProvenance.THIRD_PARTY
    notes: str | None = None
    source_id: str | None = None
    collection_method: str = "adapter"
    raw_reference: dict = field(default_factory=dict)


@dataclass
class PrivateSignalInput:
    """Private (user-owned) observation → append-only private tables.

    ``kind`` selects the target private table: DAILY_EARNING, DOWNLOAD, SALE,
    ASSET_PERFORMANCE, SUBMISSION_RESULT, CATEGORY_PERFORMANCE,
    KEYWORD_PERFORMANCE, SNAPSHOT. Provenance is always USER_PROVIDED.
    """

    kind: str
    fields: dict = field(default_factory=dict)
    observed_at: datetime = field(default_factory=_utcnow)
    provenance: DataProvenance = DataProvenance.USER_PROVIDED
    source_id: str | None = None
    collection_method: str = "adobe_contributor_adapter"
    raw_reference: dict = field(default_factory=dict)


NormalizedSignal = TrendSignalInput | MarketMetricInput | PrivateSignalInput
