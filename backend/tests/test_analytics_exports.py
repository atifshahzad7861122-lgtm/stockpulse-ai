"""Analytics exports: list is backed by agent_runs; 10/hr rate limit."""

from __future__ import annotations

from app.api import deps
from app.models.platform import AgentRun
from app.schemas.enums import AgentRunKind, AgentStatus


def _export_run(db, name="performance_analysis", status=AgentStatus.COMPLETED) -> AgentRun:
    run = AgentRun(
        agent_name=name,
        run_kind=AgentRunKind.PERFORMANCE_DIGEST,
        status=status,
        input_summary={"format": "csv", "mock": True},
        output_summary={"format": "csv", "mock": True},
    )
    db.add(run)
    db.commit()
    return run


def test_exports_list_reflects_export_runs(client, db):
    _export_run(db)
    _export_run(db, status=AgentStatus.FAILED)

    r = client.get("/api/analytics/exports")
    assert r.status_code == 200
    body = r.json()
    assert body["pagination"]["total"] == 2
    statuses = {row["status"] for row in body["data"]}
    assert statuses == {"ready", "processing"}
    assert all(row["kind"] == "export" for row in body["data"])


def test_exports_create_then_list(client, db):
    deps._RATE_BUCKETS.clear()
    r = client.post("/api/analytics/exports", json={"format": "csv"})
    assert r.status_code == 202
    assert r.json()["kind"] == "export"

    r = client.get("/api/analytics/exports")
    assert r.json()["pagination"]["total"] == 1


def test_exports_rate_limited_10_per_hour(client, db):
    deps._RATE_BUCKETS.clear()
    for _ in range(10):
        r = client.post("/api/analytics/exports", json={"format": "csv"})
        assert r.status_code == 202
    r = client.post("/api/analytics/exports", json={"format": "csv"})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED"
