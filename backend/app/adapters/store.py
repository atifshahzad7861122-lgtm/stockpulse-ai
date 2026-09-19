"""Normalization layer — the ONLY path adapters may use to persist data.

CRITICAL RULE (PHASE2_DESIGN.md §1): adapters never write intelligence tables
directly. This module:

- ``store_normalized_signals`` — writes TrendSnapshot (payload_hash dedup via
  the existing ``uq_trend_snapshots_source_hash``) + TrendSignal rows, or
  append-only private tables for PrivateSignalInput. TrendSignal rows link
  back to their snapshot (``trend_snapshot_id → TrendSnapshot.trend_source_id``)
  plus ``data_provenance`` + ``CollectionRun`` linkage — the provenance chain
  required by PHASE2_DESIGN.md §2.
- ``dedup_normalized_signals`` — hash/URL/timestamp dedup before storing.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.adapters.base import CollectionContext, StoredResult, record_hash
from app.adapters.normalized import (
    MarketMetricInput,
    PrivateSignalInput,
    TrendSignalInput,
)
from app.models.intelligence import TrendSignal, TrendSnapshot
from app.models import private as private_models
from app.schemas.enums import DataProvenance

logger = logging.getLogger(__name__)

__all__ = [
    "dedup_normalized_signals",
    "store_normalized_signals",
]

_PRIVATE_KIND_TO_MODEL: dict[str, type] = {
    "DAILY_EARNING": private_models.PrivateDailyEarning,
    "DOWNLOAD": private_models.PrivateDownload,
    "SALE": private_models.PrivateSale,
    "ASSET_PERFORMANCE": private_models.PrivateAssetPerformance,
    "SUBMISSION_RESULT": private_models.PrivateSubmissionResult,
    "CATEGORY_PERFORMANCE": private_models.PrivateCategoryPerformance,
    "KEYWORD_PERFORMANCE": private_models.PrivateKeywordPerformance,
    "SNAPSHOT": private_models.PrivateSnapshot,
}

# Fields allowed per private kind (everything else is dropped — explicit schema
# discipline so adapters cannot smuggle invented fields into private tables).
_PRIVATE_KIND_FIELDS: dict[str, tuple[str, ...]] = {
    "DAILY_EARNING": ("date", "earnings", "currency", "downloads"),
    "DOWNLOAD": ("date", "asset_external_id", "downloads"),
    "SALE": ("date", "asset_external_id", "earnings", "license_type"),
    "ASSET_PERFORMANCE": (
        "asset_external_id",
        "title",
        "snapshot_date",
        "downloads_total",
        "earnings_total",
        "views",
    ),
    "SUBMISSION_RESULT": (
        "asset_external_id",
        "submitted_at",
        "status",
        "reviewed_at",
        "rejection_reason",
    ),
    "CATEGORY_PERFORMANCE": ("category", "snapshot_date", "downloads", "earnings", "asset_count"),
    "KEYWORD_PERFORMANCE": ("keyword", "snapshot_date", "downloads", "earnings"),
    "SNAPSHOT": ("snapshot_date", "summary_json"),
}


def _signal_fingerprint(sig: TrendSignalInput | MarketMetricInput) -> str:
    """Stable dedup key: URL when present, else name+metric+observed_at."""
    ref = getattr(sig, "raw_reference", None) or {}
    url = ref.get("url")
    if url:
        return f"url:{url}"
    name = getattr(sig, "signal_name", getattr(sig, "micro_niche_id", ""))
    metric = getattr(sig, "metric_name", "") or ""
    ts = getattr(sig, "observed_at", "") or ""
    return f"shape:{name}|{metric}|{ts}"


def dedup_normalized_signals(
    signals: list, session: Session
) -> tuple[list, int]:
    """Drop signals whose fingerprint already exists. Returns (kept, dropped_count)."""
    seen: set[str] = set()
    kept: list = []
    for sig in signals:
        if isinstance(sig, (TrendSignalInput, MarketMetricInput)):
            fp = _signal_fingerprint(sig)
            signal_name = getattr(sig, "signal_name", "signal::" + fp[:16])
            # Dedup on (signal_name, observed_at); URL identity handled by
            # the per-run fingerprint guard (`seen`).
            query = session.query(TrendSignal).filter(TrendSignal.signal_name == signal_name)
            if getattr(sig, "observed_at", None):
                query = query.filter(TrendSignal.observed_at == sig.observed_at)
            if fp in seen or query.one_or_none() is not None:
                continue
            seen.add(fp)
            kept.append(sig)
        elif isinstance(sig, PrivateSignalInput):
            kept.append(sig)  # private rows are append-only; uniqueness enforced by DB
        else:
            kept.append(sig)
    return kept, len(signals) - len(kept)


def store_normalized_signals(
    adapter,
    signals: list,
    session: Session,
    ctx: CollectionContext | None = None,
) -> StoredResult:
    """Persist normalized signals through the normalization layer.

    Public signals → one TrendSnapshot per adapter batch (payload_hash dedup)
    + TrendSignal rows linked to the snapshot. Private signals → append-only
    private tables. ``dry_run`` ctx → no writes, counts only.
    """
    result = StoredResult()
    if not signals:
        return result

    dry_run = bool(ctx and ctx.dry_run)
    quality = adapter.score_quality(signals) if hasattr(adapter, "score_quality") else 0.0
    result.quality_score = quality

    public = [s for s in signals if isinstance(s, (TrendSignalInput, MarketMetricInput))]
    private = [s for s in signals if isinstance(s, PrivateSignalInput)]

    # --- public path: TrendSnapshot + TrendSignal -------------------------
    if public:
        provenance = public[0].provenance
        # Topic label: explicit query first, else the trend source's name so the
        # snapshot is visible/groupable in the trends API (which groups by topic).
        topic = (ctx.queries[0] if ctx and ctx.queries else None) or None
        if not topic and ctx and ctx.trend_source_id:
            from app.models.intelligence import TrendSource as _TrendSource

            _row = (
                session.query(_TrendSource).filter_by(id=ctx.trend_source_id).one_or_none()
            )
            topic = _row.name if _row is not None else None
        payload = {
            "adapter": adapter.source_type,
            "collection_method": getattr(public[0], "collection_method", "adapter"),
            "collected_at": datetime.now(UTC).isoformat(),
            "collection_run_id": ctx.collection_run_id if ctx else None,
            "provenance": provenance.value if isinstance(provenance, DataProvenance) else str(provenance),
            "topic": topic,
            "signals": [
                {
                    "signal_name": s.signal_name if isinstance(s, TrendSignalInput) else None,
                    "description": getattr(s, "description", None),
                    "metric_name": getattr(s, "metric_name", None),
                    "metric_value": getattr(s, "metric_value", None),
                    "metric_unit": getattr(s, "metric_unit", None),
                    "observed_at": (s.observed_at.isoformat() if getattr(s, "observed_at", None) else None),
                    "confidence": getattr(s, "confidence", None),
                    "micro_niche_id": getattr(s, "micro_niche_id", None),
                    "data_timestamp": (s.data_timestamp.isoformat() if getattr(s, "data_timestamp", None) else None),
                    "raw_reference": getattr(s, "raw_reference", {}),
                }
                for s in public
            ],
        }
        # collected_at / collection_run_id stay in the STORED payload for audit,
        # but are excluded from the HASHED payload: dedup must trigger when the
        # collected content is identical, regardless of when/which run saw it.
        hash_payload = {
            "adapter": payload["adapter"],
            "collection_method": payload["collection_method"],
            "provenance": payload["provenance"],
            "signals": payload["signals"],
        }
        payload_hash = record_hash(hash_payload)
        source_id = (ctx.trend_source_id if ctx else None) or getattr(public[0], "source_id", None) or "unknown"
        existing = (
            session.query(TrendSnapshot)
            .filter_by(trend_source_id=source_id, payload_hash=payload_hash)
            .one_or_none()
        )
        if existing is not None:
            result.snapshots_deduped += 1
            result.notes.append("identical batch already captured — snapshot skipped (payload_hash dedup)")
        elif not dry_run:
            snapshot = TrendSnapshot(
                trend_source_id=source_id,
                captured_at=datetime.now(UTC),
                payload=payload,
                payload_hash=payload_hash,
            )
            session.add(snapshot)
            session.flush()
            result.snapshots_created += 1
            for s in public:
                if isinstance(s, MarketMetricInput):
                    continue  # market metrics route to MarketMetric via agents; not direct-written
                session.add(
                    TrendSignal(
                        trend_snapshot_id=snapshot.id,
                        micro_niche_id=s.micro_niche_id,
                        signal_name=s.signal_name[:200],
                        description=s.description,
                        metric_name=s.metric_name,
                        metric_value=s.metric_value,
                        metric_unit=s.metric_unit,
                        observed_at=s.observed_at,
                        data_provenance=s.provenance,
                        confidence=min(max(s.confidence, 0.0), 1.0),
                    )
                )
                result.signals_stored += 1
        else:
            result.signals_stored = len([s for s in public if isinstance(s, TrendSignalInput)])
        session.flush()

    # --- private path: append-only private tables --------------------------
    for sig in private:
        model = _PRIVATE_KIND_TO_MODEL.get(sig.kind)
        if model is None:
            result.notes.append(f"unknown private kind '{sig.kind}' — skipped")
            continue
        allowed = _PRIVATE_KIND_FIELDS[sig.kind]
        row_kwargs = {k: v for k, v in sig.fields.items() if k in allowed}
        if dry_run:
            result.private_rows_stored += 1
            continue
        try:
            # SAVEPOINT per row: a unique-violation rollback must not undo the
            # public snapshot/signals already flushed in this transaction.
            with session.begin_nested():
                row = model(
                    data_provenance=DataProvenance.USER_PROVIDED,
                    collection_run_id=(ctx.collection_run_id if ctx else None),
                    **row_kwargs,
                )
                session.add(row)
                session.flush()
            result.private_rows_stored += 1
        except Exception as exc:  # unique violation → already captured, skip quietly
            logger.info("private row skipped (already present): %s", exc)
            result.notes.append(f"{sig.kind} row already present — skipped")

    if not dry_run:
        session.flush()
    return result
