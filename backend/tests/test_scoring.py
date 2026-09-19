"""Engine formula tests: exact worked examples, stored vs display rounding.

Formulas (docs/08 §3, CONTRACT.md §4.2):
- TS = 0.30·TV₁₀₀ + 0.25·SG₁₀₀ + 0.20·KM₁₀₀ + 0.15·EG₁₀₀ + 0.10·(SE×100)
- OS = 0.35·TS + 0.25·(CR×100) + 0.20·(CD×100) + 0.20·(100 − CS×100)
- CSS = 100 × (0.55·CS + 0.45·CO); bands: Open ≤40 < Moderate ≤60 < Crowded ≤80 < Saturated
- Data confidence = 0.5·MC + 0.3·freshness + 0.2·(min(n_sources,4)/4)
"""

from __future__ import annotations

from app.engines.scoring import (
    DATA_CONFIDENCE_ACTIONABLE_MIN,
    OS_ACTIONABLE_MIN,
    opportunity_score,
    saturation_score,
    trend_score,
)


def test_trend_score_worked_example():
    # 0.30·80 + 0.25·70 + 0.20·60 + 0.15·50 + 0.10·(0.5·100) = 24+17.5+12+7.5+5
    result = trend_score(tv_100=80, sg_100=70, km_100=60, eg_100=50, seasonality=0.5)
    assert result.score == 66.0
    assert len(result.factors) == 5
    names = [f.name for f in result.factors]
    assert names == [
        "Trend velocity (TV)",
        "Search growth (SG)",
        "Keyword momentum (KM)",
        "Engagement signals (EG)",
        "Seasonality (SE)",
    ]
    # Stored: two decimals. Display: rounded integer.
    assert result.score == round(result.score, 2)
    assert int(round(result.score)) == 66


def test_trend_score_clips_to_0_100():
    assert trend_score(200, 200, 200, 200, 2.0).score == 100.0
    assert trend_score(-50, -50, -50, -50, -1.0).score == 0.0


def test_opportunity_score_worked_example():
    # TS=66, CR=0.7, CD=0.6, CS=0.4:
    # 0.35·66 + 0.25·70 + 0.20·60 + 0.20·60 = 23.1+17.5+12+12 = 64.6
    result = opportunity_score(
        trend_score_value=66.0,
        commercial_relevance=0.7,
        content_demand=0.6,
        content_saturation=0.4,
        market_consistency=0.8,
        source_freshness=0.9,
        n_sources=5,
        prediction_confidence=70.0,
    )
    assert result.score == 64.6
    # Data confidence: 0.5·0.8 + 0.3·0.9 + 0.2·(4/4) = 0.4+0.27+0.2 = 0.87
    assert result.data_confidence == 0.87
    assert result.actionable is True
    # Stored two decimals; display integer.
    assert int(round(result.score)) == 65


def test_opportunity_score_below_threshold_not_actionable():
    result = opportunity_score(
        trend_score_value=20.0,
        commercial_relevance=0.2,
        content_demand=0.2,
        content_saturation=0.9,
        market_consistency=0.3,
        source_freshness=0.2,
        n_sources=1,
        prediction_confidence=20.0,
    )
    assert result.score < OS_ACTIONABLE_MIN
    assert result.actionable is False
    assert any("below the actionable threshold" in n for n in result.notes)


def test_opportunity_score_low_data_confidence_not_actionable():
    result = opportunity_score(
        trend_score_value=80.0,
        commercial_relevance=0.9,
        content_demand=0.9,
        content_saturation=0.1,
        market_consistency=0.1,
        source_freshness=0.1,
        n_sources=1,
        prediction_confidence=80.0,
    )
    assert result.data_confidence < DATA_CONFIDENCE_ACTIONABLE_MIN
    assert result.actionable is False
    assert any("Insufficient evidence" in n for n in result.notes)


def test_saturation_bands():
    open_band = saturation_score(0.2, 0.2)  # 100·(0.11+0.09)=20
    assert open_band.score == 20.0
    assert open_band.band == "Open"

    moderate = saturation_score(0.5, 0.5)  # 100·(0.275+0.225)=50
    assert moderate.score == 50.0
    assert moderate.band == "Moderate"
    # Display rounding: 47.6 → 48
    assert int(round(47.6)) == 48

    crowded = saturation_score(0.7, 0.7)  # 70
    assert crowded.band == "Crowded"
    saturated = saturation_score(0.95, 0.95)  # 95
    assert saturated.band == "Saturated"
