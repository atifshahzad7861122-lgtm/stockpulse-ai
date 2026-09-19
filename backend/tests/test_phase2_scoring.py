"""Scoring: Personal Fit Score (None without private data, 0–100 with),
trend calc from real-shaped signals, and combined opportunity scoring
(PHASE2_DESIGN.md §6, §9; CONTRACT.md §8)."""

from __future__ import annotations

import pytest

from app.engines.opportunities import personal_fit_score
from app.engines.trends import WindowValues, analyze_topic, market_consistency


def test_personal_fit_none_without_private_data():
    assert personal_fit_score() is None
    assert (
        personal_fit_score(
            opportunity_category="business",
            category_performance={},
            keyword_performance={},
            overall_acceptance_rate=None,
        )
        is None
    )


def test_personal_fit_bounded_with_private_data():
    score = personal_fit_score(
        opportunity_category="business",
        opportunity_keywords=("portrait", "studio"),
        category_performance={
            "business": {"downloads": 200.0, "earnings": 80.0},
            "nature": {"downloads": 20.0, "earnings": 5.0},
        },
        keyword_performance={
            "portrait": {"downloads": 90.0, "earnings": 30.0},
            "landscape": {"downloads": 5.0, "earnings": 1.0},
        },
        overall_acceptance_rate=0.8,
    )
    assert score is not None
    assert 0.0 <= score <= 100.0
    # Strongest category + strong keyword + 80% acceptance → high fit.
    assert score > 70.0


def test_personal_fit_acceptance_only():
    score = personal_fit_score(overall_acceptance_rate=0.6)
    assert score == pytest.approx(60.0)


def test_personal_fit_weak_category_scores_low():
    strong = personal_fit_score(
        opportunity_category="business",
        category_performance={
            "business": {"downloads": 200.0, "earnings": 80.0},
            "nature": {"downloads": 20.0, "earnings": 5.0},
        },
    )
    weak = personal_fit_score(
        opportunity_category="nature",
        category_performance={
            "business": {"downloads": 200.0, "earnings": 80.0},
            "nature": {"downloads": 20.0, "earnings": 5.0},
        },
    )
    assert strong is not None and weak is not None
    assert strong > weak


def test_personal_fit_unknown_category_ignored():
    """An opportunity in a category with no private history yields None
    (never guesses from unrelated data)."""
    assert (
        personal_fit_score(
            opportunity_category="space",
            category_performance={"business": {"downloads": 1.0, "earnings": 1.0}},
        )
        is None
    )


def test_analyze_topic_real_shaped_signals():
    """The existing trend engine runs on real-shaped collected signals."""
    analysis = analyze_topic(
        topic="AI business portraits",
        windows=WindowValues(w0=14.0, w1=8.0, baseline=6.0),
        keyword_tvs=[0.6, 0.4, 0.2],
        source_z_scores=[1.2, 0.9, 1.1],
        seasonality=0.55,
        provenance="THIRD_PARTY",
    )
    assert analysis.topic == "AI business portraits"
    assert analysis.trend_velocity > 0  # 14 > 8 → rising
    assert analysis.velocity_flag in ("accelerating", "rising")
    assert analysis.provenance == "THIRD_PARTY"
    assert "AI business portraits" in analysis.explanation


def test_single_source_market_consistency_penalty():
    """Fewer independent sources → lower consistency (failure/degradation
    path: a source going down lowers confidence via this penalty)."""
    multi = market_consistency([1.2, 0.9, 1.1, 1.0])
    single = market_consistency([1.0])
    assert single == pytest.approx(0.3)  # MC_SINGLE_SOURCE_PENALTY
    assert multi > single


def test_data_confidence_formula_from_contract():
    """CONTRACT.md §8.2: data-confidence = 0.5·MC + 0.3·freshness + 0.2·(min(n,4)/4)."""
    mc, freshness, n = 0.71, 0.9, 5
    confidence = 0.5 * mc + 0.3 * freshness + 0.2 * (min(n, 4) / 4)
    assert confidence == pytest.approx(0.825)
    assert confidence >= 0.5  # actionable threshold
    # Degraded: one stale source.
    poor = 0.5 * 0.3 + 0.3 * 0.25 + 0.2 * (min(1, 4) / 4)
    assert poor < 0.5  # flagged "insufficient evidence — do not act"


def test_opportunity_scores_kept_separate(client, db):
    """opportunity_score and personal_fit_score coexist; null fit means
    'no private data', not 'bad fit' (PHASE2_DESIGN.md §6)."""
    r = client.post(
        "/api/opportunities",
        json={"title": "AI business portraits", "summary": "Studio-style corporate headshots"},
    )
    assert r.status_code == 201
    opp_id = r.json()["id"]
    r = client.get(f"/api/opportunities/{opp_id}")
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["opportunity_score"] <= 100.0
    assert body["personal_fit_score"] is None  # no private data → null, honest
