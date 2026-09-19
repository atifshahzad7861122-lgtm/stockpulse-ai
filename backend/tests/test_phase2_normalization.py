"""Normalization, dedup (hash/URL/timestamp), quality scoring, and the
normalization-layer store path (PHASE2_DESIGN.md §1, §2, §9).

Adapters never write intelligence tables directly: store() writes
TrendSnapshot (payload_hash dedup) + TrendSignal rows carrying THIRD_PARTY
(or VERIFIED for official APIs) provenance.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.adapters.base import CollectionContext, RawRecord
from app.adapters.github_adapter import GitHubAdapter
from app.adapters.normalized import PrivateSignalInput, TrendSignalInput
from app.adapters.rss_adapter import RSSAdapter
from app.adapters.store import dedup_normalized_signals, store_normalized_signals
from app.adapters.youtube_adapter import YouTubeRSSAdapter
from app.models.intelligence import TrendSignal, TrendSnapshot, TrendSource
from app.schemas.enums import DataProvenance


def _rec(title="T", url="https://example.com/x", **kw):
    return RawRecord(source_type="rss", title=title, url=url, **kw)


def test_rss_normalize_shape():
    signals = RSSAdapter().normalize(
        [_rec("Adobe launches Firefly 4", url="https://example.com/a",
              body="New image model", extra={"feed": "Adobe Blog", "category": "creative"})]
    )
    assert len(signals) == 1
    s = signals[0]
    assert s.signal_name == "Adobe launches Firefly 4"
    assert s.provenance == DataProvenance.THIRD_PARTY
    assert s.metric_name == "feed_mentions"
    assert s.collection_method == "rss_feed"
    assert s.raw_reference["url"] == "https://example.com/a"
    assert s.raw_reference["feed"] == "Adobe Blog"


def test_youtube_normalize_shape():
    signals = YouTubeRSSAdapter().normalize(
        [_rec("AI photo trends 2026", url="https://youtube.com/watch?v=abc")]
    )
    assert len(signals) == 1
    assert signals[0].provenance == DataProvenance.THIRD_PARTY
    assert signals[0].raw_reference["url"] == "https://youtube.com/watch?v=abc"


def test_github_normalize_verified_provenance():
    signals = GitHubAdapter().normalize(
        [
            RawRecord(
                source_type="github_trending",
                title="owner/cool-ai-tool",
                body="An AI image tool",
                url="https://github.com/owner/cool-ai-tool",
                extra={"stars": 1234, "language": "Python", "topics": ["ai"]},
            )
        ]
    )
    assert len(signals) == 1
    s = signals[0]
    assert s.provenance == DataProvenance.VERIFIED  # official api.github.com
    assert s.metric_name == "github_stars"
    assert s.metric_value == 1234.0
    assert s.raw_reference["language"] == "Python"


def test_dedup_by_url_within_batch(db):
    now = datetime.now(UTC)
    sigs = [
        TrendSignalInput(signal_name="A", observed_at=now,
                         raw_reference={"url": "https://example.com/dup"}),
        TrendSignalInput(signal_name="B", observed_at=now,
                         raw_reference={"url": "https://example.com/dup"}),
    ]
    kept, dropped = dedup_normalized_signals(sigs, db)
    assert len(kept) == 1 and dropped == 1


def test_dedup_by_name_and_timestamp_against_db(db):
    now = datetime.now(UTC)
    db.add(
        TrendSignal(
            trend_snapshot_id=None,
            signal_name="Existing signal",
            observed_at=now,
            data_provenance=DataProvenance.THIRD_PARTY,
        )
    )
    db.commit()
    sigs = [TrendSignalInput(signal_name="Existing signal", observed_at=now)]
    kept, dropped = dedup_normalized_signals(sigs, db)
    assert kept == [] and dropped == 1


def test_dedup_keeps_distinct_timestamps(db):
    earlier = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    later = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)
    db.add(
        TrendSignal(
            trend_snapshot_id=None,
            signal_name="Recurring signal",
            observed_at=earlier,
            data_provenance=DataProvenance.THIRD_PARTY,
        )
    )
    db.commit()
    kept, dropped = dedup_normalized_signals(
        [TrendSignalInput(signal_name="Recurring signal", observed_at=later)], db
    )
    assert len(kept) == 1 and dropped == 0


def test_store_writes_snapshot_and_signals_with_provenance(db):
    src = db.query(TrendSource).filter_by(name="ScrapeGraphAI web discovery").one()
    ctx = CollectionContext(db=db, trend_source_id=src.id, trigger="API")
    adapter = RSSAdapter()
    signals = [
        TrendSignalInput(
            signal_name="Stored signal",
            description="d",
            metric_name="feed_mentions",
            metric_value=2.0,
            observed_at=datetime.now(UTC),
            provenance=DataProvenance.THIRD_PARTY,
            confidence=0.6,
            raw_reference={"url": "https://example.com/stored"},
        )
    ]
    result = store_normalized_signals(adapter, signals, db, ctx)
    db.commit()
    assert result.snapshots_created == 1
    assert result.signals_stored == 1
    assert result.quality_score > 0

    snap = db.query(TrendSnapshot).filter_by(trend_source_id=src.id).one()
    assert snap.payload_hash  # dedup key present
    assert snap.payload["provenance"] == "THIRD_PARTY"
    # Regression: snapshot payload must carry a topic (query or source name) so
    # the /api/trends list — which groups by topic — shows real collections.
    assert snap.payload["topic"] == "ScrapeGraphAI web discovery"
    sig = db.query(TrendSignal).filter_by(trend_snapshot_id=snap.id).one()
    assert sig.signal_name == "Stored signal"
    assert sig.data_provenance == DataProvenance.THIRD_PARTY
    # Provenance chain: TrendSignal.trend_snapshot_id → TrendSnapshot.trend_source_id
    assert snap.trend_source_id == src.id


def test_store_snapshot_payload_hash_dedup(db):
    src = db.query(TrendSource).filter_by(name="ScrapeGraphAI web discovery").one()
    ctx = CollectionContext(db=db, trend_source_id=src.id, trigger="API")
    adapter = RSSAdapter()
    mk = lambda: [
        TrendSignalInput(
            signal_name="Same batch",
            observed_at=datetime(2026, 9, 19, 8, 0, tzinfo=UTC),
            provenance=DataProvenance.THIRD_PARTY,
            raw_reference={"url": "https://example.com/same"},
        )
    ]
    r1 = store_normalized_signals(adapter, mk(), db, ctx)
    db.commit()
    # Second identical batch: dedup layer drops the signal before storing.
    kept, _ = dedup_normalized_signals(mk(), db)
    r2 = store_normalized_signals(adapter, kept, db, ctx)
    db.commit()
    assert r1.signals_stored == 1
    assert r2.signals_stored == 0


def test_store_dry_run_writes_nothing(db):
    src = db.query(TrendSource).filter_by(name="ScrapeGraphAI web discovery").one()
    ctx = CollectionContext(db=db, trend_source_id=src.id, dry_run=True)
    result = store_normalized_signals(
        RSSAdapter(),
        [TrendSignalInput(signal_name="Dry", provenance=DataProvenance.THIRD_PARTY)],
        db,
        ctx,
    )
    db.commit()
    assert result.signals_stored == 1  # counted...
    assert db.query(TrendSnapshot).filter_by(trend_source_id=src.id).count() == 0  # ...not written


def test_store_private_signal_writes_user_provided_row(db):
    from datetime import date as date_cls

    adapter = RSSAdapter()  # any adapter; store routes on signal kind
    sig = PrivateSignalInput(
        kind="DAILY_EARNING",
        fields={"date": date_cls(2026, 9, 18), "earnings": 12.5, "currency": "USD", "downloads": 34},
    )
    result = store_normalized_signals(adapter, [sig], db, None)
    db.commit()
    assert result.private_rows_stored == 1
    from app.models.private import PrivateDailyEarning

    row = db.query(PrivateDailyEarning).one()
    assert row.data_provenance == DataProvenance.USER_PROVIDED
    assert float(row.earnings) == 12.5
    assert row.downloads == 34


def test_store_private_unknown_kind_skipped_with_note(db):
    result = store_normalized_signals(
        RSSAdapter(), [PrivateSignalInput(kind="NOPE", fields={})], db, None
    )
    assert result.private_rows_stored == 0
    assert any("unknown private kind" in n for n in result.notes)


def test_adapter_store_goes_through_normalization_layer(db):
    """adapter.store() delegates to the normalization layer (never direct writes)."""
    src = db.query(TrendSource).filter_by(name="ScrapeGraphAI web discovery").one()
    ctx = CollectionContext(db=db, trend_source_id=src.id, trigger="API")
    adapter = RSSAdapter()
    signals = adapter.normalize([_rec("Via adapter.store", url="https://example.com/v")])
    result = adapter.store(signals, db, ctx)
    db.commit()
    assert result.signals_stored == 1
    assert db.query(TrendSignal).filter_by(signal_name="Via adapter.store").count() == 1


def test_store_topic_prefers_explicit_query(db):
    from app.models.intelligence import TrendSource, TrendSnapshot

    src = db.query(TrendSource).filter_by(name="RSS feeds (blogs + photography press)").one()
    ctx = CollectionContext(
        db=db, trend_source_id=src.id, trigger="API", queries=["vintage film photography"]
    )
    adapter = RSSAdapter()
    signals = [
        TrendSignalInput(
            signal_name="S",
            observed_at=datetime(2026, 9, 19, 8, 0, tzinfo=UTC),
            provenance=DataProvenance.THIRD_PARTY,
        )
    ]
    store_normalized_signals(adapter, signals, db, ctx)
    db.commit()
    snap = db.query(TrendSnapshot).filter_by(trend_source_id=src.id).one()
    assert snap.payload["topic"] == "vintage film photography"
