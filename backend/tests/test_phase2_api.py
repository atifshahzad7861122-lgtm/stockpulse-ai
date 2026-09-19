"""Source management API: queryability of sources, health, and collection
runs (PHASE2_DESIGN.md §9). Unit tests only — no real collection is triggered
(the collect endpoint launches background network work)."""

from __future__ import annotations


def test_list_sources_seeded(client, db):
    r = client.get("/api/sources")
    assert r.status_code == 200
    body = r.json()
    assert body["pagination"]["total"] >= 19  # Phase 2 seed
    first = body["data"][0]
    assert first["name"]
    assert first["source_type"]
    assert "data_provenance" in first


def test_get_source_detail(client, db):
    src_id = client.get("/api/sources").json()["data"][0]["id"]
    r = client.get(f"/api/sources/{src_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == src_id
    assert "recent_runs" in body


def test_get_source_unknown_404(client, db):
    r = client.get("/api/sources/no-such-source")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "SOURCE_NOT_FOUND"


def test_collect_unknown_source_404(client, db):
    # 404 path raises before any background job is submitted — safe in tests.
    r = client.post("/api/sources/no-such-source/collect")
    assert r.status_code == 404


def test_source_health_endpoint(client, db):
    from app.models.intelligence import TrendSource
    from app.models.sources import SourceHealth

    r = client.get("/api/sources/health")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # A health row written by the scheduler surfaces through the API.
    adobe_src = (
        db.query(TrendSource).filter_by(name="Adobe Contributor dashboard (private)").one()
    )
    db.add(
        SourceHealth(
            trend_source_id=adobe_src.id,
            status="NEEDS_AUTH",
            last_error="not configured",
        )
    )
    db.commit()
    rows = client.get("/api/sources/health").json()
    assert len(rows) >= 1
    adobe = next(h for h in rows if h["trend_source_id"] == adobe_src.id)
    assert adobe["status"] == "NEEDS_AUTH"
    assert adobe["last_error"] == "not configured"


def test_collection_runs_empty_initially(client, db):
    r = client.get("/api/sources/runs")
    assert r.status_code == 200
    assert r.json()["pagination"]["total"] == 0


def test_collection_run_unknown_404(client, db):
    r = client.get("/api/sources/runs/no-such-run")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "COLLECTION_RUN_NOT_FOUND"


def test_private_categories_keywords_empty_state(client, db):
    assert client.get("/api/private/performance/categories").json() == []
    assert client.get("/api/private/performance/keywords").json() == []


def test_settings_secrets_redacted(client, db):
    # Configure via the dedicated private endpoint, then verify the generic
    # settings surface never echoes secret material.
    r = client.put(
        "/api/private/connection",
        json={"session_type": "cookie", "session_data": {"cookie": "FAKE-SECRET-NOT-REAL"}},
    )
    assert r.status_code == 200

    r = client.get("/api/settings/adobe_contributor")
    assert r.status_code == 200
    body = r.json()
    assert body["value"]["redacted"] is True
    assert body["value"]["configured"] is True
    assert "FAKE-SECRET-NOT-REAL" not in r.text

    r = client.get("/api/settings")
    assert r.status_code == 200
    adobe = r.json().get("adobe_contributor")
    assert adobe is not None
    assert adobe.get("redacted") is True
    assert "FAKE-SECRET-NOT-REAL" not in r.text
