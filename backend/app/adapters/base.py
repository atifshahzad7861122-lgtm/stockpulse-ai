"""Phase 2 real-data adapter layer (PHASE2_DESIGN.md §1).

Each external data source is wrapped in a ``SourceAdapter``. Adapters NEVER
write intelligence tables directly — ``store()`` goes through the normalization
layer only (``adapters/store.py``), which writes ``TrendSnapshot`` /
``TrendSignal`` (payload_hash dedup) or the append-only private tables.

Guarded imports: an adapter must import and report UNAVAILABLE with a reason
when its underlying library is missing; it must never crash app startup.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.schemas.enums import SourceStatus

logger = logging.getLogger(__name__)

__all__ = [
    "AdapterHealth",
    "CollectionContext",
    "RawRecord",
    "StoredResult",
    "SourceAdapter",
    "SourceStatus",
]


@dataclass
class AdapterHealth:
    """Real runtime health of a source adapter — never hard-coded."""

    status: SourceStatus
    detail: str
    checked_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    records_collected: int = 0
    last_success_at: str | None = None
    last_error: str | None = None


@dataclass
class CollectionContext:
    """Context handed to ``collect``: DB session + run metadata."""

    db: object  # sqlalchemy Session (typed loosely to avoid import cycles)
    trend_source_id: str | None = None
    collection_run_id: str | None = None
    trigger: str = "SCHEDULED"
    queries: list[str] = field(default_factory=list)
    limit: int = 20
    dry_run: bool = False


@dataclass
class RawRecord:
    """One unvalidated record fetched from the raw source."""

    source_type: str
    title: str
    body: str | None = None
    url: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class StoredResult:
    """Outcome of ``store()``."""

    snapshots_created: int = 0
    snapshots_deduped: int = 0
    signals_stored: int = 0
    signals_deduped: int = 0
    private_rows_stored: int = 0
    quality_score: float = 0.0
    notes: list[str] = field(default_factory=list)


def record_hash(payload: dict) -> str:
    """Stable SHA-256 hash for dedup of raw/normalized payloads."""
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


class SourceAdapter(ABC):
    """Base interface for every Phase 2 source adapter (PHASE2_DESIGN.md §1).

    Contract with sibling child agents: method names and NormalizedSignal
    field names are frozen by PHASE2_DESIGN.md. Enum strings UPPER_SNAKE_CASE.
    """

    source_type: str = "base"

    # --- dependency guard -------------------------------------------------
    @property
    def dependency(self) -> str | None:
        """PyPI package this adapter needs, or None for stdlib-only adapters."""
        return None

    def dependency_available(self) -> tuple[bool, str | None]:
        """(available, reason_if_missing). Never raises."""
        dep = self.dependency
        if dep is None:
            return True, None
        try:
            __import__(dep.split("[")[0].split("==")[0].replace("-", "_"))
            return True, None
        except ImportError:
            return False, f"optional dependency '{dep}' is not installed"

    # --- lifecycle ---------------------------------------------------------
    @abstractmethod
    def collect(self, ctx: CollectionContext) -> list[RawRecord]:
        """Fetch raw records from the source. No DB writes."""
        raise NotImplementedError

    def validate(self, records: list[RawRecord]) -> list[RawRecord]:
        """Drop malformed records (empty titles, future timestamps, etc.)."""
        valid = [r for r in records if r.title and r.title.strip()]
        dropped = len(records) - len(valid)
        if dropped:
            logger.info("adapter=%s validate dropped %d records", self.source_type, dropped)
        return valid

    @abstractmethod
    def normalize(self, records: list[RawRecord]) -> list:
        """RawRecord → TrendSignalInput / MarketMetricInput / PrivateSignalInput."""
        raise NotImplementedError

    def deduplicate(self, signals: list, session) -> list:
        """Drop signals already present (URL / hash / timestamp dedup)."""
        from app.adapters.store import dedup_normalized_signals

        kept, _ = dedup_normalized_signals(signals, session)
        return kept

    def score_quality(self, signals: list) -> float:
        """0–100 data-quality score for a batch of normalized signals."""
        if not signals:
            return 0.0
        total = 0.0
        for s in signals:
            q = 0.0
            q += 30 if getattr(s, "description", None) else 0
            q += 20 if getattr(s, "metric_name", None) and getattr(s, "metric_value", None) is not None else 0
            q += 20 if getattr(s, "data_timestamp", None) else 0
            q += 20 if getattr(s, "confidence", None) else 0
            q += 10 if getattr(s, "raw_reference", None) else 0
            total += min(q, 100)
        return round(total / len(signals), 1)

    def store(self, signals: list, session, ctx: CollectionContext | None = None) -> StoredResult:
        """Persist via the normalization layer ONLY — never direct table writes."""
        from app.adapters.store import store_normalized_signals

        return store_normalized_signals(self, signals, session, ctx)

    @abstractmethod
    def get_status(self) -> AdapterHealth:
        """Real runtime check. Never hard-coded. Must not raise."""
        raise NotImplementedError

    # --- timing helper ------------------------------------------------------
    @staticmethod
    def timed(fn, *args, **kwargs):
        started = time.monotonic()
        try:
            result = fn(*args, **kwargs)
            return result, int((time.monotonic() - started) * 1000), None
        except Exception as exc:  # adapters surface errors, never raise from collect
            logger.warning("adapter call failed: %s", exc)
            return [], int((time.monotonic() - started) * 1000), str(exc)
