"""ScrapeGraphAI adapter tests (PHASE2_DESIGN.md §1, §9).

Guarded import (skip gracefully when scrapegraphai is missing) and the LLM
boundary (Tier 1 keyless vs Tier 2 SmartScraperGraph) is mocked — no network.
"""

from __future__ import annotations

import os

import pytest

from app.adapters.base import CollectionContext
from app.adapters.scrapegraph_adapter import ScrapeGraphAdapter
from app.schemas.enums import DataProvenance, SourceStatus


@pytest.fixture()
def adapter():
    return ScrapeGraphAdapter()


@pytest.fixture()
def ctx():
    return CollectionContext(db=None, queries=["stock photo trends"], limit=3)


def _hits(n=2):
    # Real scrapegraphai 2.x search_on_web returns List[str] (plain URLs).
    return [f"https://example.com/article-{i}" for i in range(n)]


def test_guarded_import_missing_dependency(adapter, ctx, monkeypatch):
    monkeypatch.setattr(adapter, "dependency_available", lambda: (False, "scrapegraphai absent"))
    assert adapter.collect(ctx) == []
    health = adapter.get_status()
    assert health.status == SourceStatus.UNAVAILABLE
    assert "scrapegraphai" in health.detail.lower()


def test_collect_tier1_keyless_no_llm(adapter, ctx, monkeypatch):
    """Tier 1: search_on_web + MarkdownifyGraph, no OPENAI_API_KEY → no LLM."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(adapter, "_search_on_web", lambda q, max_results=5: _hits())
    monkeypatch.setattr(adapter, "_markdownify", lambda url: f"# stub markdown for {url}")
    records = adapter.collect(ctx)
    assert len(records) == 2
    assert all(r.url.startswith("https://example.com/article-") for r in records)
    assert all("stub markdown" in (r.body or "") for r in records)
    assert all(r.extra.get("tier", 1) == 1 for r in records)


def test_collect_tier2_llm_boundary_mocked(adapter, ctx, monkeypatch):
    """Tier 2 (SmartScraperGraph) is only reached with OPENAI_API_KEY set; the
    LLM call itself is mocked — the boundary, not the network, is tested."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    monkeypatch.setattr(adapter, "_search_on_web", lambda q, max_results=5: _hits(1))
    calls = []
    monkeypatch.setattr(
        adapter, "_smart_scrape", lambda url, schema: calls.append(url) or {"insight": "x"}
    )
    markdown_calls = []
    monkeypatch.setattr(
        adapter, "_markdownify", lambda url: markdown_calls.append(url) or "md"
    )
    records = adapter.collect(ctx)
    assert len(records) == 1
    assert calls == ["https://example.com/article-0"]  # LLM tier used
    assert records[0].extra.get("tier") == 2
    assert markdown_calls == []  # markdownify skipped when smart scrape succeeds


def test_collect_search_failure_degrades_to_empty(adapter, ctx, monkeypatch):
    monkeypatch.setattr(adapter, "_search_on_web", lambda q, max_results=5: (_ for _ in ()).throw(RuntimeError("net down")))
    assert adapter.collect(ctx) == []


def test_normalize_emits_third_party_signals(adapter, ctx, monkeypatch):
    monkeypatch.setattr(adapter, "_search_on_web", lambda q, max_results=5: _hits(1))
    monkeypatch.setattr(adapter, "_markdownify", lambda url: "body text")
    records = adapter.collect(ctx)
    signals = adapter.normalize(records)
    assert len(signals) == 1
    sig = signals[0]
    assert sig.provenance == DataProvenance.THIRD_PARTY
    assert sig.signal_name == "https://example.com/article-0"
    assert "scrapegraph" in sig.collection_method
    assert sig.raw_reference["url"] == "https://example.com/article-0"
    assert 0.0 <= sig.confidence <= 1.0


def test_get_status_probe_success(adapter, monkeypatch):
    monkeypatch.setattr(
        adapter, "_search_on_web", lambda q, max_results=1: ["https://example.com/probe"]
    )
    health = adapter.get_status()
    assert health.status == SourceStatus.AVAILABLE
    assert "Tier 1" in health.detail


def test_get_status_probe_failure_temp_failing(adapter, monkeypatch):
    def boom(q, max_results=1):
        raise RuntimeError("duckduckgo unreachable")

    monkeypatch.setattr(adapter, "_search_on_web", boom)
    health = adapter.get_status()
    assert health.status == SourceStatus.TEMP_FAILING
    assert health.last_error


def test_get_status_empty_results_temp_failing(adapter, monkeypatch):
    monkeypatch.setattr(adapter, "_search_on_web", lambda q, max_results=1: [])
    health = adapter.get_status()
    assert health.status == SourceStatus.TEMP_FAILING


def test_search_on_web_normalizes_str_and_dict_shapes(adapter, monkeypatch):
    """Regression: scrapegraphai 2.x search_on_web returns List[str] (plain
    URLs), not hit dicts. The wrapper normalizes both shapes to URL strings —
    previously the adapter called .get() on strings and every real collection
    crashed with AttributeError."""
    import sys, types

    fake_mod = types.ModuleType("scrapegraphai.utils.research_web")

    def fake_search(query, max_results=5, search_engine="duckduckgo"):
        return [
            "https://example.com/real-url",
            {"url": "https://example.com/dict-hit", "title": "t"},
            "not-a-url",
        ]

    fake_mod.search_on_web = fake_search
    monkeypatch.setitem(sys.modules, "scrapegraphai.utils.research_web", fake_mod)
    urls = adapter._search_on_web("q", max_results=3)
    assert urls == ["https://example.com/real-url", "https://example.com/dict-hit"]


def test_collect_handles_url_string_hits(adapter, ctx, monkeypatch):
    """collect() must work with the real List[str] shape from _search_on_web."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        adapter, "_search_on_web", lambda q, max_results=5: ["https://example.com/a"]
    )
    monkeypatch.setattr(adapter, "_markdownify", lambda url: None)
    records = adapter.collect(ctx)
    assert len(records) == 1
    assert records[0].url == "https://example.com/a"
    assert records[0].title == "https://example.com/a"
