"""Daily workflow orchestrator — 16 steps with human gates (docs/13).

Supervised: automated queue recommendations stop at DISCOVERED/IDEA_READY;
the workflow never auto-submits anything. Steps that need a human decision
return a gate instead of proceeding.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agents import _base
from app.agents.dispatcher import dispatch
from app.models.platform import AgentRun
from app.models.production import ProductionQueue
from app.schemas.enums import ProductionQueueStatus

# Step plan: (step_no, name, agent, gate_after)
STEPS: list[tuple[int, str, str | None, str | None]] = [
    (1, "ingest_trends", "trend_research", None),
    (2, "analyze_trends", "market_analysis", None),
    (3, "refresh_category_intelligence", "category_intelligence", "review taxonomy proposals"),
    (4, "score_opportunities", "opportunity", "approve opportunities"),
    (5, "forecast_demand", "prediction", "review predictions"),
    (6, "generate_image_ideas", "image_ideation", None),
    (7, "generate_video_ideas", "video_ideation", "approve ideas"),
    (8, "draft_prompts", "prompt", None),
    (9, "screen_prompts", "compliance", None),
    (10, "originality_scan", "originality", "approve prompts"),
    (11, "draft_metadata", "metadata", None),
    (12, "plan_production", "production_planning", "approve production plan"),
    (13, "enqueue_discoveries", None, None),  # internal: DISCOVERED/IDEA_READY only
    (14, "analyze_performance", "performance_analysis", None),
    (15, "build_briefing", None, None),  # internal: notification
    (16, "report_gates", None, None),  # internal: summarize pending gates
]

GATE_STEPS = {3, 4, 5, 7, 10, 12}


def _enqueue_discoveries(db: Session, run: AgentRun) -> dict[str, Any]:
    """Automated recommendations stop at DISCOVERED/IDEA_READY (never further)."""
    from app.models.ideation import ImageIdea, VideoIdea

    created = 0
    for idea in db.query(ImageIdea).filter_by(status="READY").limit(10).all():
        exists = db.query(ProductionQueue).filter_by(image_idea_id=idea.id).one_or_none()
        if exists is None:
            db.add(
                ProductionQueue(
                    image_idea_id=idea.id,
                    opportunity_id=idea.opportunity_id,
                    asset_type="IMAGE",
                    title=idea.title,
                    status=ProductionQueueStatus.DISCOVERED,
                    priority_band="P2",
                    generation_tool="mock-generation-provider",
                    notes="Daily workflow: automated recommendation stops at DISCOVERED.",
                )
            )
            created += 1
    for idea in db.query(VideoIdea).filter_by(status="READY").limit(10).all():
        exists = db.query(ProductionQueue).filter_by(video_idea_id=idea.id).one_or_none()
        if exists is None:
            db.add(
                ProductionQueue(
                    video_idea_id=idea.id,
                    opportunity_id=idea.opportunity_id,
                    asset_type="VIDEO",
                    title=idea.title,
                    status=ProductionQueueStatus.IDEA_READY,
                    priority_band="P2",
                    generation_tool="mock-generation-provider",
                    notes="Daily workflow: automated recommendation stops at IDEA_READY.",
                )
            )
            created += 1
    db.commit()
    return {"queue_items_created": created, "max_state": "DISCOVERED/IDEA_READY"}


def _build_briefing(db: Session, run: AgentRun, step_results: dict) -> dict[str, Any]:
    from app.models.platform import Notification
    from app.providers.providers import LLMRequest, get_llm_provider
    from app.schemas.enums import NotificationType

    llm = get_llm_provider()
    briefing = llm.generate(
        LLMRequest(
            task="briefing",
            context={
                "opportunity_count": step_results.get(4, {}).get("opportunities_created", 0),
                "trend_count": step_results.get(2, {}).get("topics_analyzed", 0),
                "alert_count": 0,
                "pending_gates": "opportunities, predictions, ideas, prompts, production plan",
            },
        )
    )
    notif = Notification(
        type=NotificationType.BRIEFING_READY,
        title="Daily briefing ready",
        body=briefing.text[:2000],
    )
    db.add(notif)
    db.commit()
    return {"notification_id": notif.id, "briefing": briefing.text[:500]}


def run_daily(db: Session, run: AgentRun, input: dict[str, Any]) -> dict[str, Any]:
    """Execute the 16 steps with genuine human gates.

    When a gate step finishes and ``skip_gates`` is not set, the workflow
    PAUSES immediately: no downstream step runs until a human resumes with
    ``resume_from_step``. ``skip_gates=True`` runs everything (tests/demo only).
    """
    skip_gates = bool(input.get("skip_gates", False))
    start_step = int(input.get("resume_from_step", 1))
    step_results: dict[int, dict[str, Any]] = {}
    gates_hit: list[dict[str, Any]] = []
    paused_at: int | None = None

    for step_no, name, agent_name, gate in STEPS:
        if step_no < start_step:
            continue
        _base.info(db, run, f"Step {step_no}/16: {name}")
        if agent_name:
            try:
                step_results[step_no] = dispatch(agent_name, db, run, input.get(name, {}))
            except Exception as exc:  # noqa: BLE001 — record and continue workflow
                _base.warn(db, run, f"Step {step_no} ({name}) failed: {exc}")
                step_results[step_no] = {"error": str(exc)}
        elif name == "enqueue_discoveries":
            step_results[step_no] = _enqueue_discoveries(db, run)
        elif name == "build_briefing":
            step_results[step_no] = _build_briefing(db, run, step_results)
        elif name == "report_gates":
            step_results[step_no] = {"pending_gates": gates_hit}
        else:
            step_results[step_no] = {"ok": True}

        if gate and not skip_gates and step_no in GATE_STEPS:
            gates_hit.append({"step": step_no, "name": name, "gate": gate})
            _base.warn(db, run, f"Human gate after step {step_no}: {gate} — pausing workflow")
            paused_at = step_no
            break

    if paused_at is not None:
        _base.info(
            db,
            run,
            f"Daily workflow PAUSED at gate after step {paused_at}; "
            f"resume with resume_from_step={paused_at + 1}",
        )
        return {
            "status": "PAUSED",
            "paused_at_step": paused_at,
            "resume_from_step": paused_at + 1,
            "steps_completed": len(step_results),
            "gates_pending": gates_hit,
            "step_results": {str(k): v for k, v in step_results.items()},
            "note": "Paused at human gate — no downstream approval/production actions ran. "
            + _base.MOCK_NOTE,
        }

    _base.info(db, run, "Daily workflow finished: all 16 steps completed")
    return {
        "status": "COMPLETED",
        "steps_completed": len(STEPS),
        "gates_pending": gates_hit,
        "step_results": {str(k): v for k, v in step_results.items()},
        "note": "Automated recommendations stop at DISCOVERED/IDEA_READY; never auto-submits. "
        + _base.MOCK_NOTE,
    }
