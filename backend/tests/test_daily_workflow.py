"""Daily workflow: genuine human gates — pause, no downstream execution, resume."""

from __future__ import annotations

from app.agents.daily_workflow import GATE_STEPS, run_daily
from app.models.platform import AgentRun
from app.schemas.enums import AgentRunKind


def _run(db) -> AgentRun:
    run = AgentRun(agent_name="daily_workflow", run_kind=AgentRunKind.DAILY_WORKFLOW)
    db.add(run)
    db.flush()
    return run


def test_gate_steps_are_3_4_5_7_10_12():
    assert GATE_STEPS == {3, 4, 5, 7, 10, 12}


def test_workflow_pauses_at_first_gate(db):
    out = run_daily(db, _run(db), {})
    assert out["status"] == "PAUSED"
    assert out["paused_at_step"] == 3
    assert out["resume_from_step"] == 4
    # Only steps 1–3 ran; nothing downstream of the gate.
    assert set(out["step_results"]) == {"1", "2", "3"}
    assert out["steps_completed"] == 3


def test_resume_continues_and_pauses_at_next_gate(db):
    first = run_daily(db, _run(db), {})
    assert first["paused_at_step"] == 3

    second = run_daily(db, _run(db), {"resume_from_step": first["resume_from_step"]})
    assert second["status"] == "PAUSED"
    assert second["paused_at_step"] == 4
    assert second["resume_from_step"] == 5
    # Only the resumed step ran.
    assert set(second["step_results"]) == {"4"}


def test_skip_gates_runs_all_steps(db):
    out = run_daily(db, _run(db), {"skip_gates": True})
    assert out["status"] == "COMPLETED"
    assert out["steps_completed"] == 16
    assert len(out["step_results"]) == 16
    # Automated recommendations never auto-submit.
    assert "never auto-submits" in out["note"]


def test_automated_queue_recommendations_stop_at_discovered_or_idea_ready(db):
    from app.models.production import ProductionQueue

    run_daily(db, _run(db), {"skip_gates": True})
    items = db.query(ProductionQueue).all()
    for item in items:
        assert item.status.value in ("DISCOVERED", "IDEA_READY"), item.status
