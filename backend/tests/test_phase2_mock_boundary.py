"""MOCK data boundary (PHASE2_DESIGN.md §1, §11): MOCK rows never drive
intelligence unless dev_mode is on. Dev-mode off = excluded everywhere it
matters; dev-mode on = visible for safe UI exploration.

Regression focus: the trends API must derive provenance from the snapshot
payload — real Phase 2 (THIRD_PARTY) snapshots must stay visible when
dev mode is off, while MOCK rows stay hidden."""

from __future__ import annotations

from app.models.intelligence import TrendSignal, TrendSnapshot
from app.models.settings import Setting
from app.schemas.enums import DataProvenance
from app.services.dev_mode import is_dev_mode


def _set_dev_mode(db, enabled: bool) -> None:
    """Toggle the seeded dev_mode setting (seed shape: {"value": ...})."""
    row = db.query(Setting).filter_by(key="dev_mode").one()
    row.value = {"value": enabled}
    db.commit()


def _enable(db):
    _set_dev_mode(db, True)


def _mock_snapshot(db, topic="solar panels"):
    db.add(
        TrendSnapshot(
            trend_source_id="demo-source",
            payload={"topic": topic, "trend_score": 67.05},
            payload_hash=f"mock-hash-{topic}",
        )
    )
    db.commit()


def _real_snapshot(db, topic="AI business portraits"):
    db.add(
        TrendSnapshot(
            trend_source_id="rss",
            payload={"topic": topic, "trend_score": 72.5, "provenance": "THIRD_PARTY"},
            payload_hash=f"real-hash-{topic}",
        )
    )
    db.commit()


def test_dev_mode_defaults_off(db):
    assert is_dev_mode(db) is False


def test_set_dev_mode_roundtrip(db):
    _enable(db)
    assert is_dev_mode(db) is True
    _set_dev_mode(db, False)
    assert is_dev_mode(db) is False


def test_mock_snapshot_hidden_unless_dev_mode(client, db):
    _mock_snapshot(db)
    r = client.get("/api/trends")
    assert r.status_code == 200
    assert r.json()["pagination"]["total"] == 0  # hidden by default

    _enable(db)
    r = client.get("/api/trends")
    body = r.json()
    items = body["data"]
    # Dev mode reveals every MOCK row, including the seeded demo batch, so
    # the total is >= 1. The mock boundary is that our snapshot is among them
    # and is honestly labeled MOCK.
    assert body["pagination"]["total"] >= 1
    mine = [i for i in items if i["title"] == "solar panels"]
    assert len(mine) == 1
    assert mine[0]["provenance"] == "MOCK"
    assert mine[0]["mock"] is True


def test_real_snapshot_visible_without_dev_mode(client, db):
    """Phase 2 real collection must surface through the API with the right
    provenance — not be filtered out as if it were MOCK."""
    _mock_snapshot(db)
    _real_snapshot(db)
    r = client.get("/api/trends")
    body = r.json()
    assert body["pagination"]["total"] == 1
    item = body["data"][0]
    assert item["title"] == "AI business portraits"
    assert item["provenance"] == "THIRD_PARTY"
    assert item["mock"] is False


def test_trend_detail_signals_filtered_by_provenance(client, db):
    from datetime import UTC, datetime

    snap = TrendSnapshot(
        trend_source_id="rss",
        payload={"topic": "portrait lighting", "trend_score": 60.0, "provenance": "THIRD_PARTY"},
        payload_hash="detail-hash-1",
    )
    db.add(snap)
    db.commit()
    now = datetime.now(UTC)
    db.add(
        TrendSignal(
            trend_snapshot_id=snap.id,
            signal_name="portrait lighting rss",
            observed_at=now,
            data_provenance=DataProvenance.THIRD_PARTY,
        )
    )
    db.add(
        TrendSignal(
            trend_snapshot_id=snap.id,
            signal_name="portrait lighting demo",
            observed_at=now,
            data_provenance=DataProvenance.MOCK,
        )
    )
    db.commit()

    r = client.get(f"/api/trends/{snap.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["provenance"] == "THIRD_PARTY"
    assert body["mock"] is False
    assert [s["signal_name"] for s in body["signals"]] == ["portrait lighting rss"]

    _enable(db)
    r = client.get(f"/api/trends/{snap.id}")
    assert len(r.json()["signals"]) == 2  # dev mode shows MOCK rows too


def test_dev_mode_toggle_via_settings_api(client, db):
    r = client.patch("/api/settings/dev_mode", json={"value": True})
    assert r.status_code == 200
    assert is_dev_mode(db) is True
    r = client.patch("/api/settings/dev_mode", json={"value": False})
    assert r.status_code == 200
    assert is_dev_mode(db) is False


def test_legacy_demo_payload_defaults_to_mock_label(client, db):
    """Snapshots without a provenance key (legacy demo rows) keep the MOCK
    label — the existing behavior the older tests assert."""
    _enable(db)
    _mock_snapshot(db, topic="legacy demo")
    r = client.get("/api/trends")
    item = next(t for t in r.json()["data"] if t["title"] == "legacy demo")
    assert item["provenance"] == "MOCK"
    assert item["mock"] is True
