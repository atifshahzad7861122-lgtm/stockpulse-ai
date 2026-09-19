"""Adobe Contributor adapter tests (PHASE2_DESIGN.md §1, §9, §11).

Hard rules under test:
- Default status is NOT CONFIGURED (NEEDS_AUTH); no collection attempted.
- Config validation checks presence/format only — never simulates success.
- No real credentials in tests; fake values only. Secrets never echoed.
"""

from __future__ import annotations

import pytest

from app.adapters.adobe_adapter import SETTING_KEY, AdobeContributorAdapter
from app.adapters.base import CollectionContext
from app.models.settings import Setting
from app.schemas.enums import DataProvenance, SourceStatus


@pytest.fixture()
def adapter():
    return AdobeContributorAdapter()


def _ctx(db):
    return CollectionContext(db=db, limit=5)


def test_default_not_configured(db, adapter):
    configured, reason = adapter.is_configured(db)
    assert configured is False
    assert "not configured" in reason


def test_get_status_not_configured_is_needs_auth(db, adapter):
    health = adapter.get_status()
    assert health.status == SourceStatus.NEEDS_AUTH
    assert "not configured" in health.detail.lower()


def test_collect_returns_empty_when_not_configured(db, adapter):
    assert adapter.collect(_ctx(db)) == []


def test_get_config_accepts_router_written_shape(db, adapter):
    """Regression: the /api/private router stores the config dict unwrapped;
    the adapter must recognize it (previously it only read {"value": ...})."""
    db.add(
        Setting(
            key=SETTING_KEY,
            value={
                "configured": True,
                "session_type": "cookie",
                "session_value": "FAKE-SESSION-NOT-REAL",
            },
        )
    )
    db.commit()
    configured, reason = adapter.is_configured(db)
    assert configured is True
    assert "cookie" in reason


def test_get_config_accepts_wrapped_seed_shape(db, adapter):
    db.add(
        Setting(
            key=SETTING_KEY,
            value={"value": {"configured": True, "session_type": "storage_state"}},
        )
    )
    db.commit()
    configured, _ = adapter.is_configured(db)
    assert configured is True


def test_get_config_garbage_shape_never_configured(db, adapter):
    db.add(Setting(key=SETTING_KEY, value={"value": "not-a-dict"}))
    db.commit()
    configured, _ = adapter.is_configured(db)
    assert configured is False


def test_normalize_emits_user_provided_snapshot(db, adapter):
    from app.adapters.base import RawRecord
    from datetime import UTC, datetime

    records = [
        RawRecord(
            source_type="adobe_contributor",
            title="Adobe contributor dashboard snapshot: earnings_overview",
            body="lifetime earnings 123.45",
            url="https://stock.adobe.com/contributor/dashboard",
            published_at=datetime.now(UTC),
            extra={"surface": "earnings_overview"},
        )
    ]
    signals = adapter.normalize(records)
    assert len(signals) == 1
    sig = signals[0]
    assert sig.kind == "SNAPSHOT"
    assert sig.provenance == DataProvenance.USER_PROVIDED
    assert "dashboard" in sig.fields["summary_json"]["url"]


def test_playwright_failure_raises_never_fakes(db, adapter, monkeypatch):
    """A failed dashboard extraction raises (scheduler records FAILED) —
    partial/fake rows are never written."""
    db.add(
        Setting(
            key=SETTING_KEY,
            value={"configured": True, "session_type": "cookie", "session_value": "FAKE"},
        )
    )
    db.commit()
    import playwright.sync_api

    class _Boom:
        def __call__(self, *a, **k):
            raise RuntimeError("browser crashed")

    monkeypatch.setattr(playwright.sync_api, "sync_playwright", _Boom())
    with pytest.raises(RuntimeError, match="Adobe dashboard extraction failed"):
        adapter._collect_via_playwright(_ctx(db))


def test_private_connection_api_not_configured_default(client, db):
    r = client.get("/api/private/connection")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "NOT_CONFIGURED"
    assert body["configured"] is False
    assert "session_value" not in body  # secrets never echoed


def test_private_connection_test_never_simulates_success(client, db):
    r = client.post("/api/private/connection/test")
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is False
    assert "never simulates" in body["message"]


def test_private_connection_put_configures_without_echoing_secret(client, db):
    r = client.put(
        "/api/private/connection",
        json={"session_type": "cookie", "session_data": {"cookie": "FAKE-SECRET-NOT-REAL"}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["configured"] is True
    assert "FAKE-SECRET-NOT-REAL" not in r.text  # secret never in response
    r2 = client.get("/api/private/connection")
    assert r2.json()["status"] == "CONFIGURED"
    assert r2.json()["configured"] is True
    assert "session_value" not in r2.json()


def test_private_performance_empty_state_is_honest(client, db):
    r = client.get("/api/private/performance/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["has_data"] is False
    assert body["totals"] is None  # no invented numbers
    assert "No private performance data yet" in body["message"]
