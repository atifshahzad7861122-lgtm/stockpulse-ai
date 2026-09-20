"""Idea provenance labels: the stored column wins; the agent writes the provider label.

Regression test for the Gemini wiring bug (2026-09-20): real THIRD_PARTY
output was stored without a provenance column, so resolve_provenance()
inferred MOCK from agent_run_id and the frontend showed "Demo data" for
genuinely generated ideas.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.agents import ideation
from app.models.ideation import ImageIdea, VideoIdea
from app.models.intelligence import Opportunity
from app.models.platform import AgentRun
from app.providers.providers import (
    LLMRequest,
    LLMResponse,
    PROVENANCE_MOCK,
    PROVENANCE_THIRD_PARTY,
)
from app.schemas.common import resolve_provenance
from app.schemas.enums import AgentRunKind, DataProvenance, IdeaStatus


class _FakeLLM:
    """Deterministic stand-in returning a fixed provenance, no network."""

    def __init__(self, provenance: str):
        self._provenance = provenance

    def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            text="Concept one: rooftop garden at dawn.\nConcept two: neon market alley.",
            model="test-model",
            provenance=self._provenance,
        )


def _opportunity(db) -> Opportunity:
    opp = Opportunity(
        title="Test micro-niche",
        summary="summary",
        opportunity_score=80,
        confidence=0.8,
        data_provenance=DataProvenance.VERIFIED,
        status="approved",
    )
    db.add(opp)
    db.flush()
    return opp


def _run(db) -> AgentRun:
    run = AgentRun(agent_name="provenance-test", run_kind=AgentRunKind.TREND_INGEST)
    db.add(run)
    db.flush()
    return run


def _run_ideation(db, monkeypatch, provenance: str, kind: str = "image"):
    monkeypatch.setattr(
        ideation, "get_llm_provider", lambda: _FakeLLM(provenance)
    )
    opp = _opportunity(db)
    out = ideation._run_kind(
        db, _run(db), {"opportunity_id": opp.id, "count": 2}, kind=kind
    )
    assert out["ideas_created"] == 2
    assert out["provenance"] == provenance
    return out


def test_third_party_run_stores_third_party_on_image_ideas(db, monkeypatch):
    _run_ideation(db, monkeypatch, PROVENANCE_THIRD_PARTY, kind="image")
    ideas = db.query(ImageIdea).all()
    assert len(ideas) == 2
    for idea in ideas:
        assert idea.data_provenance == "THIRD_PARTY"
        assert resolve_provenance(idea) == DataProvenance.THIRD_PARTY


def test_third_party_run_stores_third_party_on_video_ideas(db, monkeypatch):
    _run_ideation(db, monkeypatch, PROVENANCE_THIRD_PARTY, kind="video")
    ideas = db.query(VideoIdea).all()
    assert len(ideas) == 2
    for idea in ideas:
        assert idea.data_provenance == "THIRD_PARTY"
        assert resolve_provenance(idea) == DataProvenance.THIRD_PARTY


def test_mock_run_stores_mock_on_ideas(db, monkeypatch):
    _run_ideation(db, monkeypatch, PROVENANCE_MOCK, kind="image")
    ideas = db.query(ImageIdea).all()
    assert len(ideas) == 2
    for idea in ideas:
        assert idea.data_provenance == "MOCK"
        assert resolve_provenance(idea) == DataProvenance.MOCK


def test_stored_column_wins_over_agent_run_id_inference():
    """Even with agent_run_id set, an explicit THIRD_PARTY column wins."""
    row = SimpleNamespace(
        data_provenance="THIRD_PARTY",
        agent_run_id="run-123",
        originality_notes="Drafted with gemini (THIRD_PARTY)",
    )
    assert resolve_provenance(row) == DataProvenance.THIRD_PARTY


def test_null_column_falls_back_to_agent_run_id_inference():
    """Legacy rows without the column value keep the old MOCK inference."""
    row = SimpleNamespace(data_provenance=None, agent_run_id="run-123")
    assert resolve_provenance(row) == DataProvenance.MOCK
