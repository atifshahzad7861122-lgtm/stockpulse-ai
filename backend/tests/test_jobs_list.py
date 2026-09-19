"""Jobs list_runs: status filter is applied in the DB; total reflects the filter."""

from __future__ import annotations

from app.models.platform import AgentRun
from app.schemas.enums import AgentRunKind, AgentStatus


def _run(db, name: str, status: AgentStatus) -> AgentRun:
    run = AgentRun(
        agent_name=name,
        run_kind=AgentRunKind.TREND_INGEST,
        status=status,
        input_summary={"mock": True},
        output_summary={"mock": True},
    )
    db.add(run)
    db.commit()
    return run


def test_list_runs_status_filter_total_is_exact(client, db):
    _run(db, "trend_research", AgentStatus.COMPLETED)
    _run(db, "trend_research", AgentStatus.FAILED)
    _run(db, "market_analysis", AgentStatus.COMPLETED)

    r = client.get("/api/agents/runs", params={"status": "succeeded"})
    assert r.status_code == 200
    body = r.json()
    assert body["pagination"]["total"] == 2
    assert len(body["data"]) == 2

    r = client.get("/api/agents/runs", params={"status": "failed"})
    body = r.json()
    assert body["pagination"]["total"] == 1
    assert len(body["data"]) == 1


def test_list_runs_no_filter_returns_all(client, db):
    _run(db, "trend_research", AgentStatus.COMPLETED)
    _run(db, "trend_research", AgentStatus.FAILED)

    r = client.get("/api/agents/runs")
    assert r.json()["pagination"]["total"] == 2
