"""Tests for the asset analyzer (FINAL MASTER SPEC §21–32)."""

from __future__ import annotations

import json

import pytest

from app.models.intelligence import AssetAnalysis, Opportunity
from app.schemas.enums import DataProvenance
from app.services import asset_analyzer


def _good_payload() -> dict:
    ca = {
        "topic": "ai business portraits",
        "category": "business",
        "micro_niche": "diverse team headshots",
        "primary_keywords": ["business portrait", "team"],
        "secondary_keywords": ["office", "diverse"],
        "commercial_use_case": "corporate websites",
        "subject": "a confident female executive",
        "environment": "bright modern coworking space",
        "composition": "shallow depth of field, subject right of center",
        "visual_characteristics": "warm natural light, authentic expression",
        "content_type": "image",
    }
    base = "Subject in a bright coworking space, shallow depth of field. " * 6
    return {
        "commercial_analysis": ca,
        "original_concept": (
            "A mid-career female founder laughing during a video call in a "
            "sunlit coworking lounge — different subject, environment, and mood "
            "from typical stiff headshots, targeting the same corporate buyer."
        ),
        "prompt_a": "Primary concept: " + base,
        "prompt_b": "Alternative concept, rooftop garden at golden hour: " + base,
        "prompt_c": "Different use case, website hero banner crop: " + base,
        "negative_prompt": "watermark, logo, text, distorted anatomy",
    }


class _FakeProvider:
    name = "fake"

    def __init__(self, text: str = "", model: str = "fake/test", provenance: str = "THIRD_PARTY"):
        self._text = text
        self._model = model
        self._provenance = provenance
        self.calls = 0

    def generate(self, request):
        self.calls += 1

        class R:
            text = self._text
            model = self._model
            provenance = self._provenance

        return R()


class _BoomProvider(_FakeProvider):
    def generate(self, request):
        raise RuntimeError("network down")


class _MockProvider(_FakeProvider):
    name = "mock"


def _make_opportunity(db) -> Opportunity:
    opp = Opportunity(
        title="AI business portraits — high demand",
        summary="Trend score 78/100 across 4 tracked topics.",
        opportunity_score=78.0,
        confidence=0.8,
        demand_evidence=[{"note": "ai business portraits: velocity +0.80 (rising)"}],
        data_provenance=DataProvenance.THIRD_PARTY,
        status="new",
    )
    db.add(opp)
    db.commit()
    return opp


# --- parsing ---------------------------------------------------------------


def test_parse_structured_plain_json():
    data = asset_analyzer.parse_structured(json.dumps(_good_payload()))
    assert data["prompt_a"].startswith("Primary concept")


def test_parse_structured_with_fences_and_prose():
    text = "Here is your analysis:\n```json\n" + json.dumps(_good_payload()) + "\n```\nDone."
    data = asset_analyzer.parse_structured(text)
    assert data["prompt_c"].startswith("Different use case")


def test_parse_structured_rejects_non_json():
    with pytest.raises(ValueError, match="no JSON object"):
        asset_analyzer.parse_structured("sorry, no json here")


# --- originality validation -------------------------------------------------


def test_validate_originality_accepts_good_payload():
    assert asset_analyzer.validate_originality(_good_payload()) == []


def test_validate_originality_rejects_banned_phrases():
    bad = _good_payload()
    bad["prompt_a"] = "An exact copy of the reference with the same composition. " + "x" * 120
    violations = asset_analyzer.validate_originality(bad)
    assert any("exact copy" in v for v in violations)


def test_validate_originality_rejects_short_prompts():
    bad = _good_payload()
    bad["prompt_b"] = "too short"
    violations = asset_analyzer.validate_originality(bad)
    assert any("prompt_b" in v and "too short" in v for v in violations)


def test_validate_originality_rejects_identical_prompts():
    bad = _good_payload()
    same = "Identical prompt text repeated three times for the test case. " * 4
    bad["prompt_a"] = bad["prompt_b"] = bad["prompt_c"] = same
    violations = asset_analyzer.validate_originality(bad)
    assert any("not materially different" in v for v in violations)


def test_validate_originality_requires_commercial_keys():
    bad = _good_payload()
    del bad["commercial_analysis"]["subject"]
    violations = asset_analyzer.validate_originality(bad)
    assert any("subject" in v for v in violations)


# --- market context ---------------------------------------------------------


def test_build_market_context_from_opportunity(db):
    opp = _make_opportunity(db)
    ctx = asset_analyzer.build_market_context(db, opp.id)
    assert ctx["title"] == opp.title
    assert ctx["signal_7d"] == "HIGH"  # opportunity_score 78
    assert ctx["provenance"] == "THIRD_PARTY"
    assert "portrait" in " ".join(ctx["keywords"])
    assert ctx["signal_kind"]  # labeled, never invented sales


def test_build_market_context_unknown_opportunity(db):
    with pytest.raises(ValueError, match="not found"):
        asset_analyzer.build_market_context(db, "nope")


# --- generate: success, caching, failures ----------------------------------


def test_generate_success_and_caching(db):
    opp = _make_opportunity(db)
    provider = _FakeProvider(json.dumps(_good_payload()))
    row = asset_analyzer.generate(db, opp.id, "image", provider_factory=lambda: provider)
    assert row.status == "SUCCEEDED"
    assert row.prompt_a.startswith("Primary concept")
    assert row.negative_prompt == "watermark, logo, text, distorted anatomy"
    assert row.commercial_analysis["subject"] == "a confident female executive"
    assert row.model == "fake/test"
    assert provider.calls == 1
    # Second call hits the cache — no new provider call.
    row2 = asset_analyzer.generate(db, opp.id, "image", provider_factory=lambda: provider)
    assert row2.id == row.id
    assert provider.calls == 1


def test_generate_force_bypasses_cache(db):
    opp = _make_opportunity(db)
    provider = _FakeProvider(json.dumps(_good_payload()))
    row1 = asset_analyzer.generate(db, opp.id, "video", provider_factory=lambda: provider)
    row2 = asset_analyzer.generate(
        db, opp.id, "video", provider_factory=lambda: provider, force=True
    )
    assert row2.id != row1.id
    assert provider.calls == 2


def test_generate_rejects_mock_provider(db):
    opp = _make_opportunity(db)
    with pytest.raises(RuntimeError, match="not configured"):
        asset_analyzer.generate(db, opp.id, "image", provider_factory=_MockProvider)
    # Nothing persisted — no fake analysis rows.
    assert db.query(AssetAnalysis).count() == 0


def test_generate_provider_failure_persisted_as_failed(db):
    opp = _make_opportunity(db)
    with pytest.raises(RuntimeError, match="LLM provider error"):
        asset_analyzer.generate(db, opp.id, "image", provider_factory=_BoomProvider)
    row = db.query(AssetAnalysis).one()
    assert row.status == "FAILED"
    assert "network down" in row.error_message


def test_generate_bad_json_persisted_as_failed(db):
    opp = _make_opportunity(db)
    provider = _FakeProvider("not json at all")
    with pytest.raises(RuntimeError, match="no JSON object"):
        asset_analyzer.generate(db, opp.id, "image", provider_factory=lambda: provider)
    assert db.query(AssetAnalysis).one().status == "FAILED"


def test_generate_originality_violation_persisted_as_failed(db):
    opp = _make_opportunity(db)
    bad = _good_payload()
    bad["prompt_a"] = "An exact recreation of the reference image. " + "x" * 120
    provider = _FakeProvider(json.dumps(bad))
    with pytest.raises(RuntimeError, match="Originality validation failed"):
        asset_analyzer.generate(db, opp.id, "image", provider_factory=lambda: provider)
    row = db.query(AssetAnalysis).one()
    assert row.status == "FAILED"
    assert "exact recreation" in row.error_message


def test_generate_rejects_bad_asset_type(db):
    opp = _make_opportunity(db)
    with pytest.raises(ValueError, match="asset_type"):
        asset_analyzer.generate(db, opp.id, "hologram")


# --- API --------------------------------------------------------------------


def test_api_generate_refuses_mock_provider(client, db, monkeypatch):
    opp = _make_opportunity(db)
    import app.api.routers.asset_analysis as router_mod

    monkeypatch.setattr(router_mod, "get_llm_provider", lambda: _MockProvider(""))
    resp = client.post(
        "/api/asset-analysis/generate",
        json={"opportunity_id": opp.id, "asset_type": "image"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "LLM_NOT_CONFIGURED"


def test_api_by_opportunity_roundtrip(client, db, monkeypatch):
    opp = _make_opportunity(db)
    import app.services.asset_analyzer as analyzer_mod

    fake = _FakeProvider(json.dumps(_good_payload()))
    # generate() resolves the provider inside the service module
    monkeypatch.setattr(analyzer_mod, "get_llm_provider", lambda: fake)
    resp = client.post(
        "/api/asset-analysis/generate",
        json={"opportunity_id": opp.id, "asset_type": "video"},
    )
    assert resp.status_code == 202
    # jobs run synchronously; the cached analysis is immediately available
    got = client.get(f"/api/asset-analysis/by-opportunity/{opp.id}?asset_type=video")
    assert got.status_code == 200
    body = got.json()
    assert body["asset_type"] == "video"
    assert body["prompt_a"].startswith("Primary concept")
    assert body["commercial_analysis"]["subject"] == "a confident female executive"
    assert body["market_context"]["title"] == opp.title


def test_api_by_opportunity_404_when_missing(client, db):
    resp = client.get("/api/asset-analysis/by-opportunity/nope?asset_type=image")
    assert resp.status_code == 404


def test_api_market_intelligence_overview_empty(client, db):
    resp = client.get("/api/market-intelligence/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["topic_count"] == 0
    assert body["top_categories"] == []
    assert body["last_data_update"] is None
