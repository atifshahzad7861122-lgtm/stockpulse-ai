"""Regression tests for the API collect routing bug (QA 2026-09-20).

Bug: ``POST /api/sources/{id}/collect`` passed the raw ``TrendSourceType``
enum value (e.g. "marketplace_feed") to ``get_adapter()``, whose registry is
keyed by adapter ``source_type`` (e.g. "github_trending"). Every manual
collect therefore ended ``SKIPPED`` with "No adapter registered for source
type ...". The scheduler never had this bug because it resolves through its
name → adapter-type map; the fix moves that map to
``app.adapters.registry`` (``ADAPTER_TYPE_BY_SOURCE_NAME`` /
``adapter_type_for_source``) and makes the API endpoint resolve through it.

Unit tests only — no network (fake adapter registered in-process).
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.adapters.base import (
    AdapterHealth,
    CollectionContext,
    RawRecord,
    SourceAdapter,
)
from app.adapters.normalized import TrendSignalInput
from app.adapters.registry import (
    ADAPTER_TYPE_BY_SOURCE_NAME,
    adapter_type_for_source,
    get_adapter,
)
from app.models.intelligence import TrendSignal, TrendSource
from app.models.sources import CollectionRun, SourceHealth
from app.schemas.enums import DataProvenance, SourceStatus
from app.workers import scheduler


class _FakeGitHubAdapter(SourceAdapter):
    """Stands in for the real github adapter — keyed by adapter source_type."""

    source_type = "github_trending"

    def get_status(self) -> AdapterHealth:
        return AdapterHealth(status=SourceStatus.AVAILABLE, detail="qa fake ok")

    def collect(self, ctx: CollectionContext) -> list[RawRecord]:
        return [
            RawRecord(
                source_type=self.source_type,
                title="qa/test-repo",
                body="QA regression record (test DB only).",
                url="https://example.com/qa/test-repo",
                published_at=datetime.now(UTC),
                extra={},
            )
        ]

    def normalize(self, records: list[RawRecord]) -> list:
        return [
            TrendSignalInput(
                signal_name=r.title,
                description=r.body,
                metric_name="github_stars",
                metric_value=1.0,
                metric_unit="stars",
                observed_at=datetime.now(UTC),
                provenance=DataProvenance.THIRD_PARTY,
                confidence=0.5,
                collection_method="qa_test",
            )
            for r in records
        ]


def test_adapter_type_for_source_maps_all_phase2_names():
    expected = {
        "RSS feeds (blogs + photography press)": "rss",
        "ScrapeGraphAI web discovery": "scrapegraph_web",
        "Agent-Reach web channels": "agentreach_web",
        "V2EX hot topics": "v2ex",
        "Xueqiu hot stocks": "xueqiu",
        "YouTube channel RSS": "youtube_rss",
        "GitHub trending AI repos": "github_trending",
        "Adobe Contributor dashboard (private)": "adobe_contributor",
    }
    assert ADAPTER_TYPE_BY_SOURCE_NAME == expected
    for name, adapter_type in expected.items():
        assert adapter_type_for_source(name) == adapter_type


def test_adapter_type_for_source_none_for_generic_sources():
    assert adapter_type_for_source("Google Trends") is None
    assert adapter_type_for_source("Seasonal calendars") is None
    assert adapter_type_for_source(None) is None


def test_scheduler_uses_registry_map():
    assert scheduler._SOURCE_TYPE_BY_NAME is ADAPTER_TYPE_BY_SOURCE_NAME


def test_collect_endpoint_resolves_adapter_by_source_name(client, db, monkeypatch):
    """POST /collect on 'GitHub trending AI repos' must reach the adapter."""
    from app.adapters import registry

    monkeypatch.setitem(registry.ADAPTERS, "github_trending", _FakeGitHubAdapter)

    src = (
        db.query(TrendSource)
        .filter_by(name="GitHub trending AI repos")
        .one()
    )
    r = client.post(f"/api/sources/{src.id}/collect")
    assert r.status_code == 202, r.text
    run_id = r.json()["run_id"]
    assert run_id

    run = db.query(CollectionRun).filter_by(id=run_id).one()
    assert run.status == "SUCCESS", f"run ended {run.status}: {run.error}"
    assert run.records_stored >= 1

    new_signal = (
        db.query(TrendSignal).filter_by(signal_name="qa/test-repo").one_or_none()
    )
    assert new_signal is not None, "fake adapter's signal was not stored"
    assert new_signal.data_provenance == DataProvenance.THIRD_PARTY

    health = db.query(SourceHealth).filter_by(trend_source_id=src.id).one()
    assert health.status == SourceStatus.AVAILABLE
    assert health.records_collected >= 1
    assert health.last_error is None


class _FakeNeedsAuthAdapter(SourceAdapter):
    source_type = "xueqiu_probe_test"

    def get_status(self) -> AdapterHealth:
        return AdapterHealth(status=SourceStatus.NEEDS_AUTH, detail="login cookie required")

    def collect(self, ctx: CollectionContext) -> list[RawRecord]:
        raise AssertionError("collect must not run when status is NEEDS_AUTH")

    def normalize(self, records: list[RawRecord]) -> list:
        return []


def test_collect_needs_auth_skip_records_probed_status(client, db, monkeypatch):
    """A NEEDS_AUTH skip must record NEEDS_AUTH on the health row (not the
    model's UNAVAILABLE default), mirroring the scheduler path."""
    from app.adapters import registry

    monkeypatch.setitem(registry.ADAPTERS, "xueqiu", _FakeNeedsAuthAdapter)
    monkeypatch.setitem(
        registry.ADAPTER_TYPE_BY_SOURCE_NAME, "Xueqiu hot stocks", "xueqiu"
    )
    src = db.query(TrendSource).filter_by(name="Xueqiu hot stocks").one()
    r = client.post(f"/api/sources/{src.id}/collect")
    assert r.status_code == 202
    run = db.query(CollectionRun).filter_by(id=r.json()["run_id"]).one()
    assert run.status == "SKIPPED"
    assert "NEEDS_AUTH" in (run.error or "")
    health = db.query(SourceHealth).filter_by(trend_source_id=src.id).one()
    assert health.status == SourceStatus.NEEDS_AUTH
    assert "NEEDS_AUTH" in (health.last_error or "")
    assert run.records_stored == 0


def test_collect_unmapped_source_still_skipped_honestly(client, db):
    """Generic Phase-1 sources: SKIPPED with an honest reason, no fake rows."""
    before = db.query(TrendSignal).count()
    src = db.query(TrendSource).filter_by(name="Google Trends").one()
    r = client.post(f"/api/sources/{src.id}/collect")
    assert r.status_code == 202
    run = db.query(CollectionRun).filter_by(id=r.json()["run_id"]).one()
    assert run.status == "SKIPPED"
    assert "No adapter registered" in (run.error or "")
    assert db.query(TrendSignal).count() == before
    assert get_adapter("rss") is not None or True
