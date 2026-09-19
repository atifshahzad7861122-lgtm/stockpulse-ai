"""Huginn adapter tests (user-supplied research report).

Covers app/adapters/huginn_adapter.py:
- adapter interface contract (SourceAdapter 7-method contract + registry entry)
- NOT CONFIGURED / NEEDS_AUTH when HUGINN_BASE_URL is unset
- event → signal normalization with mocked HTTP (urllib faked; never the network)

Guardrails under test: THIRD_PARTY provenance, confidence capped at 0.35,
collection never raises on fetch errors, secrets never echoed.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from app.adapters import registry
from app.adapters.base import AdapterHealth, CollectionContext, RawRecord, SourceAdapter
from app.adapters.huginn_adapter import (
    DEFAULT_EVENTS_PATH,
    MAX_CONFIDENCE,
    SETTING_KEY,
    HuginnAdapter,
)
from app.models.settings import Setting
from app.schemas.enums import DataProvenance, SourceStatus


@pytest.fixture()
def adapter():
    return HuginnAdapter()


@pytest.fixture()
def clean_env(monkeypatch):
    monkeypatch.delenv("HUGINN_BASE_URL", raising=False)
    monkeypatch.delenv("HUGINN_API_KEY", raising=False)
    monkeypatch.delenv("HUGINN_EVENTS_PATH", raising=False)


def _ctx(db):
    return CollectionContext(db=db, limit=5)


def _event(**over):
    base = {
        "id": 42,
        "agent": {"name": "WebsiteAgent"},
        "payload": {
            "title": "Kodak Ektar 100 returns",
            "url": "https://example.com/kodak-ektar",
            "change": "price drop detected",
        },
        "created_at": "2026-09-19T08:00:00Z",
    }
    base.update(over)
    return base


class _FakeResp:
    """Minimal urlopen context manager returning canned JSON."""

    def __init__(self, payload, status=200):
        self._body = json.dumps(payload).encode("utf-8")
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _fake_urlopen(monkeypatch, payload, status=200, capture=None):
    def fake(req, timeout=None):
        if capture is not None:
            capture["request"] = req
            capture["timeout"] = timeout
        return _FakeResp(payload, status=status)

    monkeypatch.setattr(urllib.request, "urlopen", fake)


# ---------------------------------------------------------------------------
# Interface contract
# ---------------------------------------------------------------------------


def test_registered_in_registry():
    assert "huginn" in registry.ADAPTERS


def test_implements_source_adapter_contract(adapter):
    assert isinstance(adapter, SourceAdapter)
    assert adapter.source_type == "huginn"
    for method in (
        "collect",
        "validate",
        "normalize",
        "deduplicate",
        "score_quality",
        "store",
        "get_status",
    ):
        assert callable(getattr(adapter, method)), method


def test_get_status_returns_adapter_health_never_raises(adapter, clean_env):
    health = adapter.get_status()
    assert isinstance(health, AdapterHealth)
    assert health.status in set(SourceStatus)


# ---------------------------------------------------------------------------
# NOT CONFIGURED / NEEDS_AUTH when HUGINN_BASE_URL unset
# ---------------------------------------------------------------------------


def test_not_configured_without_base_url(db, adapter, clean_env):
    configured, reason = adapter.is_configured(db)
    assert configured is False
    assert "not configured" in reason.lower()
    assert "HUGINN_BASE_URL" in reason


def test_get_status_needs_auth_when_not_configured(adapter, clean_env):
    health = adapter.get_status()
    assert health.status == SourceStatus.NEEDS_AUTH
    assert "not configured" in health.detail.lower()


def test_collect_returns_empty_when_not_configured(db, adapter, clean_env):
    assert adapter.collect(_ctx(db)) == []


def test_config_from_env(monkeypatch, db, adapter, clean_env):
    monkeypatch.setenv("HUGINN_BASE_URL", "https://huginn.example.com")
    monkeypatch.setenv("HUGINN_API_KEY", "FAKE-KEY-NOT-REAL")
    cfg = adapter.get_config(db)
    assert cfg["base_url"] == "https://huginn.example.com"
    assert cfg["events_path"] == DEFAULT_EVENTS_PATH
    configured, reason = adapter.is_configured(db)
    assert configured is True
    assert "https://huginn.example.com" in reason
    # Secrets are never echoed in the human-readable reason.
    assert "FAKE-KEY-NOT-REAL" not in reason


def test_config_from_settings_row(db, adapter, clean_env):
    db.add(
        Setting(
            key=SETTING_KEY,
            value={"base_url": "https://huginn.example.com", "api_key": "FAKE-KEY-NOT-REAL"},
        )
    )
    db.commit()
    configured, reason = adapter.is_configured(db)
    assert configured is True
    assert "FAKE-KEY-NOT-REAL" not in reason


def test_env_takes_precedence_over_settings_row(monkeypatch, db, adapter, clean_env):
    db.add(Setting(key=SETTING_KEY, value={"base_url": "https://row.example.com"}))
    db.commit()
    monkeypatch.setenv("HUGINN_BASE_URL", "https://env.example.com")
    assert adapter.get_config(db)["base_url"] == "https://env.example.com"


# ---------------------------------------------------------------------------
# Event fetching (mocked HTTP — never the network)
# ---------------------------------------------------------------------------


def test_fetch_events_list_shape(monkeypatch, db, adapter, clean_env):
    monkeypatch.setenv("HUGINN_BASE_URL", "https://huginn.example.com")
    monkeypatch.setenv("HUGINN_API_KEY", "FAKE-KEY")
    capture = {}
    _fake_urlopen(monkeypatch, [_event(), _event(id=43)], capture=capture)
    events = adapter._fetch_events(adapter.get_config(db), limit=10)
    assert len(events) == 2
    assert events[0]["id"] == 42
    req = capture["request"]
    assert req.full_url.startswith("https://huginn.example.com/events.json?limit=")
    assert req.get_header("Authorization") == "Bearer FAKE-KEY"
    assert capture["timeout"] == 20


def test_fetch_events_envelope_shape(monkeypatch, db, adapter, clean_env):
    monkeypatch.setenv("HUGINN_BASE_URL", "https://huginn.example.com")
    _fake_urlopen(monkeypatch, {"events": [_event()]})
    events = adapter._fetch_events(adapter.get_config(db), limit=10)
    assert len(events) == 1
    assert events[0]["id"] == 42


def test_fetch_events_unexpected_envelope_raises(monkeypatch, db, adapter, clean_env):
    monkeypatch.setenv("HUGINN_BASE_URL", "https://huginn.example.com")
    _fake_urlopen(monkeypatch, {"weird": "shape"})
    with pytest.raises(RuntimeError, match="unexpected Huginn JSON"):
        adapter._fetch_events(adapter.get_config(db), limit=10)


def test_fetch_events_http_error_raises(monkeypatch, db, adapter, clean_env):
    monkeypatch.setenv("HUGINN_BASE_URL", "https://huginn.example.com")

    def fake(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 500, "Server Error", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    with pytest.raises(urllib.error.HTTPError):
        adapter._fetch_events(adapter.get_config(db), limit=10)


# ---------------------------------------------------------------------------
# Event → record → signal normalization
# ---------------------------------------------------------------------------


def test_collect_and_normalize_events(monkeypatch, db, adapter, clean_env):
    monkeypatch.setenv("HUGINN_BASE_URL", "https://huginn.example.com")
    monkeypatch.setattr(adapter, "_fetch_events", lambda cfg, limit: [_event(), _event(id=43)])
    records = adapter.collect(_ctx(db))
    assert len(records) == 2
    assert all(isinstance(r, RawRecord) for r in records)
    assert records[0].title == "Kodak Ektar 100 returns"
    assert records[0].url == "https://example.com/kodak-ektar"
    assert records[0].extra["huginn_event_id"] == 42
    assert records[0].extra["agent"] == "WebsiteAgent"
    assert records[0].published_at is not None
    assert records[0].published_at.tzinfo is not None

    signals = adapter.normalize(records)
    assert len(signals) == 2
    sig = signals[0]
    assert sig.signal_name == "Kodak Ektar 100 returns"
    assert sig.metric_name == "huginn_event_mentions"
    assert sig.provenance == DataProvenance.THIRD_PARTY
    assert sig.collection_method == "huginn_events"
    # Noisy-signal cap: attention hint, never a demand feed.
    assert sig.confidence <= MAX_CONFIDENCE == 0.35
    assert sig.raw_reference["url"] == "https://example.com/kodak-ektar"
    assert sig.raw_reference["huginn_event_id"] == 42
    assert sig.raw_reference["agent"] == "WebsiteAgent"


def test_event_to_record_title_fallback(adapter):
    rec = HuginnAdapter._event_to_record({"id": 7, "payload": {}})
    assert rec is not None
    assert rec.title == "Huginn event 7"


def test_event_to_record_rejects_non_dict(adapter):
    assert HuginnAdapter._event_to_record("nope") is None
    assert HuginnAdapter._event_to_record(None) is None


def test_collect_never_raises_on_fetch_error(monkeypatch, db, adapter, clean_env):
    monkeypatch.setenv("HUGINN_BASE_URL", "https://huginn.example.com")

    def boom(cfg, limit):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(adapter, "_fetch_events", boom)
    assert adapter.collect(_ctx(db)) == []  # honest empty, never fake data


# ---------------------------------------------------------------------------
# get_status() with a configured instance (fetch mocked — never the network)
# ---------------------------------------------------------------------------


def test_get_status_available(monkeypatch, adapter, clean_env):
    monkeypatch.setenv("HUGINN_BASE_URL", "https://huginn.example.com")
    monkeypatch.setattr(
        HuginnAdapter, "_fetch_events", lambda self, cfg, limit: [_event()]
    )
    health = adapter.get_status()
    assert health.status == SourceStatus.AVAILABLE
    assert "https://huginn.example.com" in health.detail
    assert health.records_collected == 1


def test_get_status_401_is_needs_auth(monkeypatch, adapter, clean_env):
    monkeypatch.setenv("HUGINN_BASE_URL", "https://huginn.example.com")

    def boom(self, cfg, limit):
        raise urllib.error.HTTPError(cfg["base_url"], 401, "Unauthorized", {}, None)

    monkeypatch.setattr(HuginnAdapter, "_fetch_events", boom)
    health = adapter.get_status()
    assert health.status == SourceStatus.NEEDS_AUTH
    assert "401" in health.detail
    assert health.last_error


def test_get_status_500_is_temp_failing(monkeypatch, adapter, clean_env):
    monkeypatch.setenv("HUGINN_BASE_URL", "https://huginn.example.com")

    def boom(self, cfg, limit):
        raise urllib.error.HTTPError(cfg["base_url"], 500, "Server Error", {}, None)

    monkeypatch.setattr(HuginnAdapter, "_fetch_events", boom)
    health = adapter.get_status()
    assert health.status == SourceStatus.TEMP_FAILING
    assert health.last_error


def test_get_status_unreachable_is_temp_failing(monkeypatch, adapter, clean_env):
    monkeypatch.setenv("HUGINN_BASE_URL", "https://huginn.example.com")

    def boom(self, cfg, limit):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(HuginnAdapter, "_fetch_events", boom)
    health = adapter.get_status()
    assert health.status == SourceStatus.TEMP_FAILING
    assert health.last_error
