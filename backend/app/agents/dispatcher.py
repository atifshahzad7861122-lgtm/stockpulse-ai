"""Agent dispatcher: name → module run(db, run, input)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.agents import (
    category_intelligence,
    compliance_agent,
    ideation,
    market_analysis,
    metadata_agent,
    opportunity,
    originality_agent,
    performance_analysis,
    prediction,
    production_planning,
    prompt_agent,
    trend_research,
)
from app.models.platform import AgentRun

_DISPATCH: dict[str, Callable[[Session, AgentRun, dict[str, Any]], dict[str, Any]]] = {
    "trend_research": trend_research.run,
    "market_analysis": market_analysis.run,
    "category_intelligence": category_intelligence.run,
    "opportunity": opportunity.run,
    "image_ideation": ideation.run_image,
    "video_ideation": ideation.run_video,
    "prediction": prediction.run,
    "prompt": prompt_agent.run,
    "compliance": compliance_agent.run,
    "originality": originality_agent.run,
    "metadata": metadata_agent.run,
    "production_planning": production_planning.run,
    "performance_analysis": performance_analysis.run,
}


def dispatch(agent_name: str, db: Session, run: AgentRun, input: dict[str, Any]) -> dict[str, Any]:
    func = _DISPATCH.get(agent_name)
    if func is None:
        raise ValueError(f"Unknown agent: {agent_name}")
    return func(db, run, input)
