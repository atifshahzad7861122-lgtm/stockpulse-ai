"""Submission recording is human-only: no agent or job auto-submits."""

from __future__ import annotations

from pathlib import Path

from app.schemas.enums import ALLOWED_QUEUE_TRANSITIONS, ProductionQueueStatus

AGENTS_DIR = Path(__file__).resolve().parent.parent / "app" / "agents"


def test_no_agent_code_references_submission_recording():
    """Agents must never call mark_submitted or set SUBMITTED on submissions."""
    hits = []
    for path in AGENTS_DIR.glob("*.py"):
        src = path.read_text()
        if "mark_submitted" in src or "record-outcome" in src or "record_outcome" in src:
            hits.append(path.name)
    assert hits == [], f"agents must not record submissions: {hits}"


def test_queue_engine_never_auto_transitions_to_submitted():
    """SUBMITTED is entered only from READY_TO_UPLOAD (T21, human upload);
    its only exits are outcome recording (T24/T25)."""
    # SUBMITTED is reachable only from READY_TO_UPLOAD (the human upload step).
    sources = {
        s
        for s, targets in ALLOWED_QUEUE_TRANSITIONS.items()
        if ProductionQueueStatus.SUBMITTED in targets
    }
    assert sources == {ProductionQueueStatus.READY_TO_UPLOAD}, sources
    # SUBMITTED exits only to outcome states (human records Adobe's decision).
    assert set(ALLOWED_QUEUE_TRANSITIONS[ProductionQueueStatus.SUBMITTED]) == {
        ProductionQueueStatus.ACCEPTED,
        ProductionQueueStatus.REJECTED,
    }


def test_daily_workflow_never_marks_submitted():
    """The daily workflow source must not reference submission recording."""
    src = (AGENTS_DIR / "daily_workflow.py").read_text()
    assert "mark_submitted" not in src
    assert "record_outcome" not in src
