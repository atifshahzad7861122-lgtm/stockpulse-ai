"""Agent-Reach family adapters (agentreach_web / v2ex / xueqiu).

All agent-reach boundaries are faked via sys.modules — no network, no real
package dependency. The installed PyPI agent-reach 0.1.0 lacks the v1.5
channel/health modules, so get_status() must degrade honestly (TEMP_FAILING),
never crash.
"""

from __future__ import annotations

import sys
import types

import pytest

from app.adapters.agentreach_adapter import AgentReachAdapter, V2EXAdapter, XueqiuAdapter
from app.adapters.base import CollectionContext
from app.adapters.registry import get_adapter
from app.schemas.enums import DataProvenance, SourceStatus


@pytest.fixture()
def ctx(db):
    return CollectionContext(db=db, limit=5)


def _install_fake(monkeypatch, modname: str, classname: str, cls):
    """Inject a fake agent_reach.channels.<modname>.<classname> (reverted)."""
    full = f"agent_reach.channels.{modname}"
    mod = types.ModuleType(full)
    setattr(mod, classname, cls)
    monkeypatch.setitem(sys.modules, full, mod)
    return mod


def test_registry_includes_all_three_channels():
    assert get_adapter("agentreach_web") is AgentReachAdapter
    assert get_adapter("v2ex") is V2EXAdapter
    assert get_adapter("xueqiu") is XueqiuAdapter


def test_collect_web_channel_mocked(ctx, monkeypatch):
    class _FakeWebChannel:
        def read(self, url):
            assert url.startswith("https://")
            return {"title": "Fake article", "content": "# Hello\n\nFake markdown body."}

    _install_fake(monkeypatch, "web", "WebChannel", _FakeWebChannel)
    records = AgentReachAdapter().collect(ctx)
    assert len(records) == len(AgentReachAdapter.DEFAULT_URLS[: ctx.limit])
    assert records[0].title == "Fake article"
    assert "Fake markdown" in records[0].body

    signals = AgentReachAdapter().normalize(records)
    assert signals[0].provenance == DataProvenance.THIRD_PARTY
    assert signals[0].collection_method == "agent_reach_channel"
    assert signals[0].raw_reference["channel"] == "web"


def test_collect_web_channel_import_failure_returns_empty(ctx, monkeypatch):
    monkeypatch.setitem(sys.modules, "agent_reach.channels.web", None)
    assert AgentReachAdapter().collect(ctx) == []


def test_collect_web_channel_read_failure_skips_url(ctx, monkeypatch):
    class _Flaky:
        def read(self, url):
            raise RuntimeError("jina exploded")

    _install_fake(monkeypatch, "web", "WebChannel", _Flaky)
    records = AgentReachAdapter().collect(
        CollectionContext(db=ctx.db, limit=5, queries=["https://example.com/a"])
    )
    assert records == []  # failed URL skipped, no fake row


def test_collect_v2ex_mocked(ctx, monkeypatch):
    class _FakeV2EX:
        def get_hot_topics(self, limit=20):
            return [
                {"title": "找工作暂时完结，转行啦", "url": "https://www.v2ex.com/t/1243028"},
                {"title": "Another topic", "url": "https://www.v2ex.com/t/1"},
            ]

    _install_fake(monkeypatch, "v2ex", "V2EXChannel", _FakeV2EX)
    records = V2EXAdapter().collect(ctx)
    assert len(records) == 2
    assert records[0].title == "找工作暂时完结，转行啦"
    assert records[0].url == "https://www.v2ex.com/t/1243028"
    signals = V2EXAdapter().normalize(records)
    assert all(s.provenance == DataProvenance.THIRD_PARTY for s in signals)


def test_collect_v2ex_failure_returns_empty(ctx, monkeypatch):
    monkeypatch.setitem(sys.modules, "agent_reach.channels.v2ex", None)
    assert V2EXAdapter().collect(ctx) == []


def test_collect_xueqiu_mocked(ctx, monkeypatch):
    class _FakeXueqiu:
        def get_hot_stocks(self, limit=20):
            return [{"name": "贵州茅台", "code": "SH600519"}]

        def get_hot_posts(self, limit=20):
            return [{"title": "Market chatter"}]

    _install_fake(monkeypatch, "xueqiu", "XueqiuChannel", _FakeXueqiu)
    records = XueqiuAdapter().collect(ctx)
    assert len(records) == 2
    assert "贵州茅台" in records[0].title
    assert records[1].title == "Market chatter"


def test_collect_xueqiu_failure_returns_empty(ctx, monkeypatch):
    monkeypatch.setitem(sys.modules, "agent_reach.channels.xueqiu", None)
    assert XueqiuAdapter().collect(ctx) == []


@pytest.mark.parametrize(
    "statuses, expected",
    [
        ({"web": {"status": "ok", "message": "fine"}}, SourceStatus.AVAILABLE),
        ({"web": {"status": "error", "message": "boom"}}, SourceStatus.TEMP_FAILING),
        ({"web": {"status": "off", "message": "disabled"}}, SourceStatus.UNAVAILABLE),
        (
            {"web": {"status": "warn", "message": "需要登录 cookie"}},
            SourceStatus.NEEDS_AUTH,
        ),
        (
            {"web": {"status": "warn", "message": "rate limited, retry later"}},
            SourceStatus.TEMP_FAILING,
        ),
        (None, SourceStatus.TEMP_FAILING),
        ({}, SourceStatus.TEMP_FAILING),
    ],
)
def test_health_mapping(statuses, expected):
    status, detail = AgentReachAdapter._map_health(statuses)
    assert status == expected
    assert detail


def test_get_status_maps_channel_probe(monkeypatch):
    """get_status() maps the check_all probe for its own channel (probe is
    mocked here — the real probe does local backend checks, no network)."""
    monkeypatch.setattr(
        AgentReachAdapter,
        "_channel_statuses",
        staticmethod(lambda: {"web": {"status": "ok", "message": "fine"}}),
    )
    health = AgentReachAdapter().get_status()
    assert health.status == SourceStatus.AVAILABLE

    monkeypatch.setattr(
        AgentReachAdapter,
        "_channel_statuses",
        staticmethod(lambda: {"web": {"status": "warn", "message": "需要登录"}}),
    )
    health = AgentReachAdapter().get_status()
    assert health.status == SourceStatus.NEEDS_AUTH


def test_get_status_probe_failure_is_temp_failing(monkeypatch):
    monkeypatch.setattr(
        AgentReachAdapter, "_channel_statuses", staticmethod(lambda: None)
    )
    health = AgentReachAdapter().get_status()
    # No "web" row in the probe output → honestly UNAVAILABLE, never faked.
    assert health.status == SourceStatus.UNAVAILABLE
    assert "web channel missing" in health.detail


def test_get_status_probe_exception_is_temp_failing(monkeypatch):
    def _boom():
        raise RuntimeError("probe exploded")

    monkeypatch.setattr(AgentReachAdapter, "_channel_statuses", staticmethod(_boom))
    health = AgentReachAdapter().get_status()
    assert health.status == SourceStatus.TEMP_FAILING
    assert health.last_error


def test_subchannel_get_status_maps_own_channel(monkeypatch):
    monkeypatch.setattr(
        V2EXAdapter,
        "_channel_statuses",
        staticmethod(lambda: {"v2ex": {"status": "ok", "message": "fine"}}),
    )
    assert V2EXAdapter().get_status().status == SourceStatus.AVAILABLE
    monkeypatch.setattr(
        V2EXAdapter, "_channel_statuses", staticmethod(lambda: None)
    )
    assert V2EXAdapter().get_status().status == SourceStatus.TEMP_FAILING


def test_real_check_all_probe_runs_without_network():
    """The installed agent-reach (1.5.0) health probe does local backend
    checks only — safe to call, but slow (~5s), so unit tests mock it."""
    import time

    t = time.time()
    health = AgentReachAdapter().get_status()
    elapsed = time.time() - t
    assert health.status in (
        SourceStatus.AVAILABLE,
        SourceStatus.NEEDS_AUTH,
        SourceStatus.UNAVAILABLE,
        SourceStatus.TEMP_FAILING,
    )
    assert elapsed < 60  # local checks, no network fetch
