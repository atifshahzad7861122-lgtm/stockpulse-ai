"""All 13 canonical agents run through the dispatcher without errors."""

from __future__ import annotations

import pytest

from app.agents.dispatcher import _DISPATCH, dispatch
from app.models.ideation import ImageIdea
from app.models.platform import AgentRun
from app.models.production import Asset
from app.schemas.enums import AgentRunKind, AssetType, IdeaStatus

CANONICAL_AGENTS = [
    "trend_research",
    "market_analysis",
    "category_intelligence",
    "opportunity",
    "image_ideation",
    "video_ideation",
    "prediction",
    "prompt",
    "compliance",
    "originality",
    "metadata",
    "production_planning",
    "performance_analysis",
]


def test_all_13_canonical_agents_registered():
    assert set(_DISPATCH) == set(CANONICAL_AGENTS)


def _run(db) -> AgentRun:
    run = AgentRun(agent_name="smoke", run_kind=AgentRunKind.TREND_INGEST)
    db.add(run)
    db.flush()
    return run


def _fixtures(db) -> dict[str, str]:
    idea = ImageIdea(
        title="smoke idea",
        concept="A lighthouse at dawn with dramatic clouds.",
        originality_notes="Smoke test originality.",
        status=IdeaStatus.DRAFT,
    )
    db.add(idea)
    db.flush()
    asset = Asset(asset_type=AssetType.IMAGE, title="smoke asset")
    db.add(asset)
    db.flush()
    db.commit()
    return {"idea_id": idea.id, "asset_id": asset.id}


@pytest.mark.parametrize("agent", CANONICAL_AGENTS)
def test_agent_smoke(db, agent):
    ids = _fixtures(db)
    inputs: dict[str, dict] = {
        "trend_research": {"topics": ["solar panels"]},
        "market_analysis": {"window_days": 7},
        "category_intelligence": {},
        "opportunity": {"topic_limit": 2},
        "image_ideation": {"opportunity_id": None, "count": 1},
        "video_ideation": {"opportunity_id": None, "count": 1},
        "prediction": {"niche_limit": 2},
        "prompt": {"idea_id": ids["idea_id"], "asset_type": "IMAGE", "tool": "midjourney"},
        "compliance": {
            "check_type": "PROMPT_SCREEN",
            "subject_kind": "image_idea",
            "subject_id": ids["idea_id"],
        },
        "originality": {"subject_kind": "image_idea", "subject_id": ids["idea_id"]},
        "metadata": {"asset_id": ids["asset_id"]},
        "production_planning": {},
        "performance_analysis": {},
    }
    out = dispatch(agent, db, _run(db), inputs[agent])
    assert isinstance(out, dict)
    assert out  # non-empty result
