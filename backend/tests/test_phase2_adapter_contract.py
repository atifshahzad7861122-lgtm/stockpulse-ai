"""Phase 2 adapter interface contract (PHASE2_DESIGN.md §1, §9).

Every registered adapter implements the 7-method contract:
collect / validate / normalize / deduplicate / score_quality / store /
get_status. get_status() must never raise and must return a real
AdapterHealth. Network probes are stubbed so these tests stay hermetic —
only the acceptance run hits the network.
"""

from __future__ import annotations

import os

import pytest

from app.adapters import registry
from app.adapters.base import AdapterHealth, CollectionContext, RawRecord, SourceAdapter
from app.schemas.enums import SourceStatus

CONTRACT_METHODS = (
    "collect",
    "validate",
    "normalize",
    "deduplicate",
    "score_quality",
    "store",
    "get_status",
)

EXPECTED_SOURCE_TYPES = {
    "scrapegraph_web",
    "agentreach_web",
    "rss",
    "youtube_rss",
    "github_trending",
    "reddit",
    "x_trends",
    "instagram",
    "facebook",
    "adobe_contributor",
    "custom",
}

VALID_STATUSES = set(SourceStatus)


def test_registry_covers_expected_source_types():
    assert EXPECTED_SOURCE_TYPES <= set(registry.ADAPTERS.keys())


def test_get_adapter_roundtrip():
    for source_type, cls in registry.ADAPTERS.items():
        assert registry.get_adapter(source_type) is cls
    assert registry.get_adapter("no_such_source") is None


@pytest.mark.parametrize("source_type", sorted(registry.ADAPTERS.keys()))
def test_adapter_implements_contract(source_type):
    cls = registry.get_adapter(source_type)
    assert issubclass(cls, SourceAdapter)
    adapter = cls()
    assert adapter.source_type == source_type
    for method in CONTRACT_METHODS:
        assert callable(getattr(adapter, method, None)), f"{source_type} missing {method}"


def _stub_network_probes(adapter, monkeypatch):
    """Replace each adapter's network boundary with a deterministic fake."""
    st = adapter.source_type
    if st in ("rss", "youtube_rss"):
        import feedparser

        class _Feed(dict):
            def get(self, k, d=None):
                return super().get(k, d)

        def fake_parse(url):
            return _Feed(
                {
                    "entries": [
                        {
                            "title": "Stub entry",
                            "link": "https://example.com/stub",
                            "summary": "stub",
                            "published_parsed": None,
                        }
                    ],
                    "bozo": 0,
                }
            )

        monkeypatch.setattr(feedparser, "parse", fake_parse)
    elif st == "github_trending":
        monkeypatch.setattr(
            type(adapter),
            "_probe_rate_limit",
            staticmethod(lambda: {"resources": {"core": {"remaining": 42}}}),
        )
    elif st == "scrapegraph_web":
        monkeypatch.setattr(
            adapter,
            "_search_on_web",
            lambda q, max_results=5: [{"url": "https://example.com/a", "title": "Stub hit"}],
        )
    # agentreach_web: installed agent-reach 0.1.0 has no health module, so
    # get_status() degrades to TEMP_FAILING deterministically (no network).
    # adobe_contributor: get_status reads the test DB settings (no network).
    # reddit / x_trends / instagram / facebook / custom: env-based, no network.
    for var in (
        "REDDIT_SESSION_COOKIE",
        "TWITTER_AUTH_TOKEN",
        "TWITTER_CT0",
        "GITHUB_TOKEN",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)


@pytest.mark.parametrize("source_type", sorted(registry.ADAPTERS.keys()))
def test_get_status_never_raises(source_type, monkeypatch):
    adapter = registry.get_adapter(source_type)()
    _stub_network_probes(adapter, monkeypatch)
    health = adapter.get_status()
    assert isinstance(health, AdapterHealth)
    assert health.status in VALID_STATUSES
    assert isinstance(health.detail, str) and health.detail.strip()
    assert health.checked_at  # real runtime check, timestamped


@pytest.mark.parametrize("source_type", sorted(registry.ADAPTERS.keys()))
def test_validate_drops_malformed_records(source_type):
    adapter = registry.get_adapter(source_type)()
    records = [
        RawRecord(source_type=source_type, title="Good title", body="x"),
        RawRecord(source_type=source_type, title="   "),
        RawRecord(source_type=source_type, title=""),
    ]
    kept = adapter.validate(records)
    assert [r.title for r in kept] == ["Good title"]


@pytest.mark.parametrize("source_type", sorted(registry.ADAPTERS.keys()))
def test_score_quality_bounds(source_type):
    from app.adapters.normalized import TrendSignalInput

    adapter = registry.get_adapter(source_type)()
    assert adapter.score_quality([]) == 0.0
    full = TrendSignalInput(
        signal_name="s",
        description="d",
        metric_name="m",
        metric_value=1.0,
        data_timestamp=None,
        confidence=0.5,
        raw_reference={"url": "https://example.com"},
    )
    q = adapter.score_quality([full])
    assert 0.0 <= q <= 100.0


def test_dependency_guard_reports_missing_cleanly(monkeypatch):
    """Guarded import: missing optional dep → UNAVAILABLE with reason, no crash."""
    adapter = registry.get_adapter("scrapegraph_web")()
    monkeypatch.setattr(adapter, "dependency_available", lambda: (False, "not installed in test"))
    assert adapter.collect(CollectionContext(db=None)) == []
    health = adapter.get_status()
    assert health.status == SourceStatus.UNAVAILABLE
    assert "not installed" in health.detail
