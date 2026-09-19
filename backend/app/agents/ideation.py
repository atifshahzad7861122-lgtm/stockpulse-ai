"""image_ideation + video_ideation agents — original concepts from opportunities."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agents import _base
from app.models.ideation import ImageIdea, VideoIdea
from app.models.intelligence import Opportunity
from app.models.platform import AgentRun
from app.providers.providers import LLMRequest, get_llm_provider
from app.schemas.enums import IdeaStatus


def _generate_concepts(
    kind: str, opportunity: Opportunity, count: int, db: Session, run: AgentRun
) -> list[dict]:
    llm = get_llm_provider()
    response = llm.generate(
        LLMRequest(
            task="ideate",
            context={
                "micro_niche": opportunity.title,
                "count": count,
                "subject_hint": opportunity.title,
                "mood": "clean commercial",
                "kind": kind,
            },
        )
    )
    concepts = []
    for i, line in enumerate(response.text.split("\n")):
        line = line.strip()
        if line:
            concepts.append(
                {
                    "title": f"{opportunity.title} — concept {i + 1}",
                    "concept": line,
                    "originality_notes": (
                        "Mock-generated concept; differentiators documented in concept text. "
                        "Run an originality scan before production."
                    ),
                }
            )
    return concepts


def run_image(db: Session, run: AgentRun, input: dict[str, Any]) -> dict[str, Any]:
    return _run_kind(db, run, input, kind="image")


def run_video(db: Session, run: AgentRun, input: dict[str, Any]) -> dict[str, Any]:
    return _run_kind(db, run, input, kind="video")


def _run_kind(db: Session, run: AgentRun, input: dict[str, Any], kind: str) -> dict[str, Any]:
    opportunity_id: str | None = input.get("opportunity_id")
    count = int(input.get("count", 3))
    q = db.query(Opportunity).filter(Opportunity.status == "approved")
    if opportunity_id:
        q = db.query(Opportunity).filter(Opportunity.id == opportunity_id)
    opportunities = q.limit(5).all()
    if not opportunities:
        _base.warn(db, run, "No approved opportunities found — nothing to ideate on")
        return {
            "ideas_created": 0,
            "note": "Ideation requires approved opportunities (human gate).",
        }

    created = 0
    for opp in opportunities:
        for c in _generate_concepts(kind, opp, count, db, run)[:count]:
            kwargs: dict[str, Any] = {
                "opportunity_id": opp.id,
                "micro_niche_id": opp.micro_niche_id,
                "title": c["title"][:200],
                "concept": c["concept"],
                "originality_notes": c["originality_notes"],
                "status": IdeaStatus.DRAFT,
                "agent_run_id": run.id,
            }
            if kind == "video":
                kwargs["duration_target_seconds"] = 8
                kwargs["shot_list"] = [
                    {
                        "shot": "Establishing",
                        "camera_move": "slow push",
                        "duration_s": 3,
                        "notes": "",
                    },
                    {"shot": "Detail", "camera_move": "static", "duration_s": 3, "notes": ""},
                    {
                        "shot": "Wide resolve",
                        "camera_move": "pull back",
                        "duration_s": 2,
                        "notes": "",
                    },
                ]
                db.add(VideoIdea(**kwargs))
            else:
                db.add(ImageIdea(**kwargs))
            created += 1
    db.commit()
    _base.info(db, run, f"Created {created} {kind} ideas (DRAFT — human review required)")
    return {
        "kind": kind,
        "ideas_created": created,
        "opportunities_used": len(opportunities),
        "provenance": "MOCK",
        "note": "Ideas are DRAFT and require human review. " + _base.MOCK_NOTE,
    }
