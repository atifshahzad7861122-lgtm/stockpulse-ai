"""Phase 3 — Opportunity Fusion Engine (backend).

Covers: fusion math transparency (components stored, documented sums),
personal-fit full formula with private data, NOT_CONFIGURED → None fit +
MARKET-ONLY label + lowered confidence, high-market/poor-fit explained not
rejected, high-fit/weak-market labeled personal-performance, explanations
built only from provided evidence, and no fake data anywhere.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from app.engines.fusion import (
    FUS_SATURATION_PENALTY,
    FusionInputs,
    OpportunityFusionEngine,
)
from app.engines.opportunities import personal_fit_breakdown, personal_fit_score


# ---------------------------------------------------------------------------
# Engine-level: fusion math transparency
# ---------------------------------------------------------------------------


def _full_inputs(**overrides) -> FusionInputs:
    base = dict(
        market_opportunity=80.0,
        trend_momentum=70.0,
        commercial_potential=75.0,
        seasonality=60.0,
        saturation_risk=30.0,
        prediction_confidence=80.0,
        personal_fit=90.0,
        personal_momentum=65.0,
        historical_performance=70.0,
        opportunity_title="Test opportunity",
    )
    base.update(overrides)
    return FusionInputs(**base)


def test_fusion_math_matches_documented_formula():
    """UNIFIED = Σ(w·c)/Σw − 0.15·saturation_risk (PHASE3_FORMULAS.md §2, §5)."""
    engine = OpportunityFusionEngine()
    result = engine.compute(_full_inputs())
    expected_base = (
        80 * 0.25 + 70 * 0.20 + 75 * 0.15 + 60 * 0.10 + 80 * 0.05
        + 90 * 0.15 + 65 * 0.05 + 70 * 0.05
    ) / 1.0
    expected = expected_base - FUS_SATURATION_PENALTY * 30.0
    assert result.unified_score == pytest.approx(expected, abs=0.01)
    assert result.label == "FUSED"


def test_fusion_components_all_stored_and_weights_sum_to_one():
    result = OpportunityFusionEngine().compute(_full_inputs())
    assert set(result.components) == {
        "market_opportunity",
        "trend_momentum",
        "commercial_potential",
        "seasonality",
        "saturation_risk",
        "prediction_confidence",
        "personal_fit",
        "personal_momentum",
        "historical_performance",
    }
    assert all(v is not None for v in result.components.values())
    # Saturation is subtractive: not in the weight denominator.
    assert "saturation_risk" not in result.weights_used
    assert sum(result.weights_used.values()) == pytest.approx(1.0)
    assert result.saturation_penalty_applied == pytest.approx(0.15 * 30.0)


def test_fusion_market_only_renormalizes_and_lowers_confidence():
    engine = OpportunityFusionEngine()
    fused = engine.compute(_full_inputs())
    market_only = engine.compute(
        _full_inputs(personal_fit=None, personal_momentum=None, historical_performance=None)
    )
    assert market_only.label == "MARKET-ONLY"
    assert market_only.components["personal_fit"] is None
    assert market_only.components["personal_momentum"] is None
    assert market_only.components["historical_performance"] is None
    # No personal numbers invented: weights renormalize over market components.
    assert sum(market_only.weights_used.values()) == pytest.approx(1.0)
    assert "personal_fit" not in market_only.weights_used
    # Confidence lowered for MARKET-ONLY.
    assert market_only.confidence_score < fused.confidence_score
    assert market_only.confidence_score == pytest.approx(fused.confidence_score - 10.0, abs=1.0) or (
        market_only.confidence_score <= fused.confidence_score - 5.0
    )


def test_fusion_scores_bounded():
    engine = OpportunityFusionEngine()
    extreme = FusionInputs(
        market_opportunity=100, trend_momentum=100, commercial_potential=100,
        seasonality=100, saturation_risk=100, prediction_confidence=100,
        personal_fit=100, personal_momentum=100, historical_performance=100,
    )
    assert 0.0 <= engine.compute(extreme).unified_score <= 100.0
    zero = FusionInputs(
        market_opportunity=0, trend_momentum=0, commercial_potential=0,
        seasonality=0, saturation_risk=100, prediction_confidence=0,
    )
    assert 0.0 <= engine.compute(zero).unified_score <= 100.0


# ---------------------------------------------------------------------------
# Engine-level: special cases
# ---------------------------------------------------------------------------


def test_high_market_poor_fit_explained_not_rejected():
    """market≥70 + fit≤35 → mismatch explained; score still computed."""
    result = OpportunityFusionEngine().compute(
        _full_inputs(market_opportunity=85.0, personal_fit=20.0)
    )
    assert result.special_case == "market_personal_mismatch"
    assert result.unified_score is not None
    assert result.label == "FUSED"  # not rejected, not hidden
    text = result.explanation.lower()
    assert "85" in result.explanation  # market value cited
    assert "20" in result.explanation  # fit value cited
    assert "not a rejection" in text or "rely on market demand" in text


def test_high_fit_weak_market_labeled_personal_performance():
    result = OpportunityFusionEngine().compute(
        _full_inputs(market_opportunity=30.0, personal_fit=85.0)
    )
    assert result.special_case == "personal_performance"
    assert "personal-performance opportunity" in result.explanation


def test_no_special_case_for_balanced_inputs():
    result = OpportunityFusionEngine().compute(_full_inputs())
    assert result.special_case is None


# ---------------------------------------------------------------------------
# Engine-level: explanation evidence rules
# ---------------------------------------------------------------------------

_BANNED = ("guarantee", "will sell", "will rank", "certain to sell", "sure thing")


def test_explanation_contains_only_provided_evidence():
    notes = ("buyers searched 'neon portraits' 40% more this week",)
    result = OpportunityFusionEngine().compute(
        _full_inputs(demand_evidence_notes=notes, personal_evidence_notes=("category component 95.0/100",))
    )
    assert "buyers searched 'neon portraits' 40% more this week" in result.explanation
    assert "category component 95.0/100" in result.explanation
    # An unsupported claim that was NOT passed in must not appear.
    assert "viral" not in result.explanation.lower()
    lowered = result.explanation.lower()
    for banned in _BANNED:
        assert banned not in lowered


def test_explanation_market_only_states_no_private_data():
    result = OpportunityFusionEngine().compute(
        _full_inputs(personal_fit=None, personal_momentum=None, historical_performance=None)
    )
    assert "no private performance data was available" in result.explanation.lower()
    assert "market-only" in result.explanation.lower() or "market view only" in result.explanation.lower()


def test_explanation_never_crashes_on_caller_evidence():
    """A caller-supplied note containing a banned-looking word is quoted as
    observed evidence — it must not crash compute via the banned-language
    assert (which covers only the engine's own template sentences)."""
    result = OpportunityFusionEngine().compute(
        _full_inputs(demand_evidence_notes=("a blog claimed this niche is 'guaranteed gold'",))
    )
    assert "guaranteed gold" in result.explanation
    assert result.unified_score is not None


def test_ollama_fallback_never_fails_or_fakes():
    """With STOCKPULSE_LLM_PROVIDER=ollama but no server, render_explanation
    falls back to the deterministic template and never raises."""
    import os

    from app.services.fusion_explanation import render_explanation

    old = os.environ.get("STOCKPULSE_LLM_PROVIDER")
    old_url = os.environ.get("OLLAMA_BASE_URL")
    os.environ["STOCKPULSE_LLM_PROVIDER"] = "ollama"
    os.environ["OLLAMA_BASE_URL"] = "http://127.0.0.1:1"  # dead port: instant refusal
    try:
        text, renderer = render_explanation(
            deterministic_text="deterministic WHY",
            title="t",
            components={"market_opportunity": 80.0, "personal_fit": None},
        )
    finally:
        if old is None:
            del os.environ["STOCKPULSE_LLM_PROVIDER"]
        else:
            os.environ["STOCKPULSE_LLM_PROVIDER"] = old
        if old_url is None:
            os.environ.pop("OLLAMA_BASE_URL", None)
        else:
            os.environ["OLLAMA_BASE_URL"] = old_url
    assert text == "deterministic WHY"
    assert renderer == "deterministic-template (ollama fallback)"


# ---------------------------------------------------------------------------
# Engine-level: personal fit full formula
# ---------------------------------------------------------------------------


def test_personal_fit_full_formula_all_components():
    result = personal_fit_breakdown(
        opportunity_category="business",
        opportunity_keywords=("portrait",),
        opportunity_formats=("IMAGE",),
        opportunity_themes=("studio",),
        category_performance={
            "business": {"downloads": 200.0, "earnings": 80.0},
            "nature": {"downloads": 20.0, "earnings": 5.0},
        },
        content_type_performance={
            "IMAGE": {"downloads": 180.0, "earnings": 70.0},
            "VIDEO": {"downloads": 20.0, "earnings": 10.0},
        },
        keyword_performance={"portrait": {"downloads": 90.0, "earnings": 30.0}},
        theme_performance={"studio": {"downloads": 150.0, "earnings": 60.0}},
        momentum_windows={
            "downloads": {"current_7d": 70.0, "prev_7d": 35.0},
            "earnings": {"current_7d": 140.0, "prev_7d": 70.0},
        },
        overall_acceptance_rate=0.8,
        historical_downloads=5000.0,
        historical_earnings=2500.0,
    )
    assert result is not None
    assert set(result.components) == {
        "category", "keyword", "content_type", "theme", "momentum",
        "acceptance", "historical_downloads", "historical_earnings",
    }
    assert result.missing == ("asset",)  # unavailable by design
    assert sum(result.weights.values()) == pytest.approx(1.0)
    # Strongest everywhere → high fit.
    assert result.score > 80.0
    # Manual check of the documented formula.
    expected = sum(
        result.components[name] * w
        for name, w in (
            ("category", 0.25), ("keyword", 0.15), ("content_type", 0.10),
            ("theme", 0.05), ("momentum", 0.10), ("acceptance", 0.15),
            ("historical_downloads", 0.05), ("historical_earnings", 0.05),
        )
    ) / (0.25 + 0.15 + 0.10 + 0.05 + 0.10 + 0.15 + 0.05 + 0.05)
    assert result.score == pytest.approx(expected, abs=0.05)


def test_personal_fit_momentum_math():
    # Doubled → 100; flat → 50; halved → 0.
    assert personal_fit_breakdown(
        momentum_windows={"downloads": {"current_7d": 70.0, "prev_7d": 35.0}}
    ).components["momentum"] == pytest.approx(100.0)
    assert personal_fit_breakdown(
        momentum_windows={"downloads": {"current_7d": 35.0, "prev_7d": 35.0}}
    ).components["momentum"] == pytest.approx(50.0)
    assert personal_fit_breakdown(
        momentum_windows={"downloads": {"current_7d": 0.0, "prev_7d": 35.0}}
    ).components["momentum"] == pytest.approx(0.0)


def test_personal_fit_still_none_without_private_data():
    assert personal_fit_score() is None
    assert personal_fit_breakdown() is None
    assert personal_fit_breakdown(opportunity_category="business") is None


def test_personal_fit_backward_compat():
    # Phase 2 callers keep working with identical semantics.
    assert personal_fit_score(overall_acceptance_rate=0.6) == pytest.approx(60.0)
    assert (
        personal_fit_score(
            opportunity_category="business",
            category_performance={
                "business": {"downloads": 200.0, "earnings": 80.0},
                "nature": {"downloads": 20.0, "earnings": 5.0},
            },
        )
        == pytest.approx(100.0)
    )


# ---------------------------------------------------------------------------
# API-level tests (need the app; run with the client fixture)
# ---------------------------------------------------------------------------


def _seed_private_portfolio(db):
    """Small honest private portfolio: category/keyword perf, submissions,
    14 days of daily earnings (second week doubled), titled assets."""
    from app.models.private import (
        PrivateAssetPerformance,
        PrivateCategoryPerformance,
        PrivateDailyEarning,
        PrivateKeywordPerformance,
        PrivateSubmissionResult,
    )

    today = date.today()
    db.add(
        PrivateCategoryPerformance(
            category="business", snapshot_date=today,
            downloads=200, earnings=80.0, asset_count=10,
        )
    )
    db.add(
        PrivateCategoryPerformance(
            category="nature", snapshot_date=today,
            downloads=20, earnings=5.0, asset_count=5,
        )
    )
    db.add(
        PrivateKeywordPerformance(
            keyword="portrait", snapshot_date=today, downloads=90, earnings=30.0
        )
    )
    db.add(
        PrivateKeywordPerformance(
            keyword="business", snapshot_date=today, downloads=120, earnings=40.0
        )
    )
    now = datetime.now(UTC)
    for i in range(4):
        db.add(
            PrivateSubmissionResult(
                asset_external_id=f"acc-{i}", submitted_at=now, status="ACCEPTED"
            )
        )
    db.add(
        PrivateSubmissionResult(asset_external_id="rej-1", submitted_at=now, status="REJECTED")
    )
    for d in range(14):
        day = today - timedelta(days=13 - d)
        mult = 2.0 if d >= 7 else 1.0
        db.add(
            PrivateDailyEarning(date=day, earnings=10.0 * mult, downloads=int(5 * mult))
        )
    db.add(
        PrivateAssetPerformance(
            asset_external_id="x1", title="business portrait studio",
            snapshot_date=today, downloads_total=150, earnings_total=60.0,
        )
    )
    db.add(
        PrivateAssetPerformance(
            asset_external_id="x2", title="corporate team portrait",
            snapshot_date=today, downloads_total=50, earnings_total=20.0,
        )
    )
    db.commit()


def _make_opportunity(client, db, **overrides):
    from app.models.taxonomy import MicroNiche

    niche = db.query(MicroNiche).filter_by(slug="boardroom-meetings").one_or_none()
    payload = {
        "title": "AI business portraits",
        "summary": "Studio-style corporate headshots with neon accents",
        "micro_niche_id": niche.id if niche else None,
    }
    payload.update(overrides)
    r = client.post("/api/opportunities", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_api_not_configured_gives_market_only_and_null_fit(client, db):
    """No private rows (NOT_CONFIGURED) → personal_fit None, label
    MARKET-ONLY, confidence lowered — never a fake number."""
    opp_id = _make_opportunity(client, db)
    r = client.post("/api/opportunity-fusion/compute", json={"opportunity_id": opp_id})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["label"] == "MARKET-ONLY"
    assert body["personal_fit"] is None
    assert body["personal_momentum"] is None
    assert body["historical_performance"] is None
    assert body["component_json"]["inputs"]["personal_fit"]["provenance"] == "ABSENT"
    assert 0.0 <= body["unified_score"] <= 100.0
    assert 0.0 <= body["confidence_score"] <= 100.0
    assert "no private performance data was available" in body["explanation"].lower()

    # GET returns the latest with the full breakdown + provenance per input.
    r = client.get(f"/api/opportunity-fusion/{opp_id}")
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["id"] == body["id"]
    assert got["label"] == "MARKET-ONLY"
    inputs = got["component_json"]["inputs"]
    assert set(inputs) >= {
        "market_opportunity", "trend_momentum", "commercial_potential",
        "seasonality", "saturation_risk", "prediction_confidence",
        "personal_fit", "personal_momentum", "historical_performance",
    }
    for name, detail in inputs.items():
        assert "value" in detail and "provenance" in detail, name


def test_api_private_data_gives_fused_with_higher_confidence(client, db):
    from app.models import private as pm

    _seed_private_portfolio(db)
    opp_id = _make_opportunity(client, db)
    payload = {
        "opportunity_id": opp_id,
        "trend_momentum": 70.0,
        "saturation_risk": 30.0,
        "demand_evidence_notes": ["search interest rising for boardroom portraits"],
    }
    r = client.post("/api/opportunity-fusion/compute", json=payload)
    assert r.status_code == 201, r.text
    fused = r.json()
    assert fused["label"] == "FUSED"
    assert fused["personal_fit"] is not None
    assert 0.0 <= fused["personal_fit"] <= 100.0
    assert fused["component_json"]["inputs"]["personal_fit"]["provenance"] == "USER_PROVIDED"
    assert "search interest rising for boardroom portraits" in fused["explanation"]
    # Supplied market inputs are honored; unsupplied ones are neutral ESTIMATED.
    assert fused["trend_momentum"] == pytest.approx(70.0)
    assert fused["saturation_risk"] == pytest.approx(30.0)
    assert fused["component_json"]["inputs"]["commercial_potential"]["provenance"] == "ESTIMATED"
    assert fused["component_json"]["inputs"]["trend_momentum"]["provenance"] == "USER_PROVIDED"
    assert fused["confidence_factors_json"]["market_only_penalty_applied"] == 0.0

    # Wipe private data (back to NOT_CONFIGURED) → MARKET-ONLY, confidence lowered.
    for model in (
        pm.PrivateDailyEarning,
        pm.PrivateDownload,
        pm.PrivateSale,
        pm.PrivateAssetPerformance,
        pm.PrivateSubmissionResult,
        pm.PrivateCategoryPerformance,
        pm.PrivateKeywordPerformance,
        pm.PrivateSnapshot,
    ):
        db.query(model).delete()
    db.commit()
    r = client.post("/api/opportunity-fusion/compute", json=payload)
    assert r.status_code == 201, r.text
    market_only = r.json()
    assert market_only["label"] == "MARKET-ONLY"
    assert market_only["personal_fit"] is None
    assert market_only["confidence_score"] < fused["confidence_score"]
    assert market_only["confidence_factors_json"]["market_only_penalty_applied"] == 10.0


def test_api_compute_404s_on_unknown_opportunity(client, db):
    r = client.post("/api/opportunity-fusion/compute", json={"opportunity_id": "nope"})
    assert r.status_code == 404
    r = client.get("/api/opportunity-fusion/nope")
    assert r.status_code == 404


def test_api_get_404s_when_no_score_computed(client, db):
    opp_id = _make_opportunity(client, db)
    r = client.get(f"/api/opportunity-fusion/{opp_id}")
    assert r.status_code == 404


def test_api_compute_is_idempotent_ish(client, db):
    """One fresh score per request; GET returns the latest."""
    opp_id = _make_opportunity(client, db)
    first = client.post("/api/opportunity-fusion/compute", json={"opportunity_id": opp_id}).json()
    second = client.post(
        "/api/opportunity-fusion/compute",
        json={"opportunity_id": opp_id, "trend_momentum": 90.0},
    ).json()
    assert first["id"] != second["id"]
    latest = client.get(f"/api/opportunity-fusion/{opp_id}").json()
    assert latest["id"] == second["id"]
    assert latest["trend_momentum"] == pytest.approx(90.0)


def test_api_no_guarantee_language(client, db):
    _seed_private_portfolio(db)
    opp_id = _make_opportunity(client, db)
    body = client.post(
        "/api/opportunity-fusion/compute", json={"opportunity_id": opp_id}
    ).json()
    lowered = body["explanation"].lower()
    for banned in _BANNED:
        assert banned not in lowered


def test_api_content_type_metrics_feed_personal_fit(client, db):
    """Sibling PersonalContentTypeMetric rows feed the content_type component
    (read-only; sibling file untouched). The 'unknown' bucket is ignored."""
    from app.models.personal import PersonalContentTypeMetric
    from app.services.personal_fit import compute_personal_fit_breakdown

    _seed_private_portfolio(db)
    db.add(
        PersonalContentTypeMetric(
            content_type="image", period_days=30, downloads=200, earnings=50.0
        )
    )
    db.add(
        PersonalContentTypeMetric(
            content_type="video", period_days=30, downloads=50, earnings=10.0
        )
    )
    db.add(
        PersonalContentTypeMetric(
            content_type="unknown", period_days=30, downloads=9999, earnings=9999.0
        )
    )
    db.commit()
    fit = compute_personal_fit_breakdown(
        db, micro_niche_id=None, title="t", summary="s"
    )
    assert fit is not None
    # image strength 100, video strength mean(25, 20) = 22.5 → 61.25.
    # The 'unknown' 9999 bucket must not leak in.
    assert fit.components["content_type"] == pytest.approx(61.25)
    assert "content_type" not in fit.missing

    # End to end: the fused API response carries a personal fit built on it.
    opp_id = _make_opportunity(client, db)
    body = client.post(
        "/api/opportunity-fusion/compute", json={"opportunity_id": opp_id}
    ).json()
    assert body["label"] == "FUSED"
    assert body["personal_fit"] is not None
    assert body["personal_fit"] > 0
