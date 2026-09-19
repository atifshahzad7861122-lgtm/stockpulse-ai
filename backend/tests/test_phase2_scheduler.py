"""Scheduler collection lifecycle: skip-without-fake-data, failure health
mapping, success health mapping (PHASE2_DESIGN.md §9; CONTRACT.md §4.25).

All adapter boundaries are mocked — no network in unit tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.adapters.base import CollectionContext, RawRecord
from app.adapters.rss_adapter import RSSAdapter
from app.models.intelligence import TrendSignal, TrendSnapshot, TrendSource
from app.models.sources import CollectionRun, SourceHealth
from app.schemas.enums import DataProvenance, SourceStatus
from app.workers import scheduler


class _NeedsAuthAdapter(RSSAdapter):
    source_type = "fake_needs_auth"

    def get_status(self):
        from app.adapters.base import AdapterHealth

        return AdapterHealth(status=SourceStatus.NEEDS_AUTH, detail="needs credentials")

    def collect(self, ctx: CollectionContext):
        raise AssertionError("collect must not run when status is NEEDS_AUTH")


class _ExplodingAdapter(RSSAdapter):
    source_type = "fake_exploding"

    def collect(self, ctx: CollectionContext):
        raise RuntimeError("simulated network outage")


class _GoodAdapter(RSSAdapter):
    source_type = "fake_good"

    def collect(self, ctx: CollectionContext):
        return [
            RawRecord(
                source_type="fake_good",
                title="Real-shaped collected record",
                body="A real-shaped body for scheduler tests.",
                url="https://example.com/sched-1",
                published_at=datetime.now(UTC),
                extra={"feed": "test feed"},
            )
        ]


@pytest.fixture()
def _patch_adapter(monkeypatch):
    def _use(cls):
        monkeypatch.setattr(
            scheduler, "get_adapter", lambda source_type: cls if source_type == cls.source_type else None
        )

    return _use


def _source_id(db) -> str:
    return db.query(TrendSource).filter_by(name="ScrapeGraphAI web discovery").one().id


def test_skipped_when_needs_auth_records_no_fake_data(db, _patch_adapter):
    _patch_adapter(_NeedsAuthAdapter)
    sid = _source_id(db)
    run_id = scheduler._run_collection(db, sid, _NeedsAuthAdapter.source_type, "TEST")
    run = db.query(CollectionRun).filter_by(id=run_id).one()
    assert run.status == "SKIPPED"
    assert "NEEDS_AUTH" in (run.error or "")
    assert db.query(TrendSignal).count() == 0  # nothing collected, nothing faked
    health = db.query(SourceHealth).filter_by(trend_source_id=sid).one()
    assert health.status == SourceStatus.NEEDS_AUTH


def test_failed_run_marks_source_temp_failing(db, _patch_adapter):
    _patch_adapter(_ExplodingAdapter)
    sid = _source_id(db)
    run_id = scheduler._run_collection(db, sid, _ExplodingAdapter.source_type, "TEST")
    run = db.query(CollectionRun).filter_by(id=run_id).one()
    assert run.status == "FAILED"
    assert "simulated network outage" in (run.error or "")
    health = db.query(SourceHealth).filter_by(trend_source_id=sid).one()
    assert health.status == SourceStatus.TEMP_FAILING
    assert health.consecutive_failures == 1
    assert health.last_failure_at is not None
    assert "simulated network outage" in (health.last_error or "")


def test_consecutive_failures_accumulate(db, _patch_adapter):
    _patch_adapter(_ExplodingAdapter)
    sid = _source_id(db)
    scheduler._run_collection(db, sid, _ExplodingAdapter.source_type, "TEST")
    scheduler._run_collection(db, sid, _ExplodingAdapter.source_type, "TEST")
    health = db.query(SourceHealth).filter_by(trend_source_id=sid).one()
    assert health.consecutive_failures == 2


def test_successful_run_marks_available_and_stores_signals(db, _patch_adapter):
    _patch_adapter(_GoodAdapter)
    sid = _source_id(db)
    run_id = scheduler._run_collection(db, sid, _GoodAdapter.source_type, "TEST")
    run = db.query(CollectionRun).filter_by(id=run_id).one()
    assert run.status == "SUCCESS"
    assert run.records_stored == 1
    health = db.query(SourceHealth).filter_by(trend_source_id=sid).one()
    assert health.status == SourceStatus.AVAILABLE
    assert health.consecutive_failures == 0
    assert health.last_success_at is not None
    sig = db.query(TrendSignal).one()
    assert sig.data_provenance == DataProvenance.THIRD_PARTY
    snap = db.query(TrendSnapshot).filter_by(id=sig.trend_snapshot_id).one()
    assert snap.trend_source_id == sid
    assert snap.payload["provenance"] == "THIRD_PARTY"


def test_unknown_source_type_skipped(db):
    sid = _source_id(db)
    run_id = scheduler._run_collection(db, sid, "no_such_adapter", "TEST")
    run = db.query(CollectionRun).filter_by(id=run_id).one()
    assert run.status == "SKIPPED"
    assert "no adapter" in (run.error or "")


def test_recovery_resets_failure_counters(db, _patch_adapter):
    _patch_adapter(_ExplodingAdapter)
    sid = _source_id(db)
    scheduler._run_collection(db, sid, _ExplodingAdapter.source_type, "TEST")
    _patch_adapter(_GoodAdapter)
    scheduler._run_collection(db, sid, _GoodAdapter.source_type, "TEST")
    health = db.query(SourceHealth).filter_by(trend_source_id=sid).one()
    assert health.status == SourceStatus.AVAILABLE
    assert health.consecutive_failures == 0


def test_scheduler_enabled_is_bool():
    assert isinstance(scheduler.scheduler_enabled(), bool)
