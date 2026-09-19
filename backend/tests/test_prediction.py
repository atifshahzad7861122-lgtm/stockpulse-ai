"""Prediction engine tests: confidence, factors/evidence, model version,
timestamp, and the non-guarantee disclaimer (docs/16, CONTRACT.md §4.2)."""

from __future__ import annotations

from app.engines.prediction import (
    DISCLAIMER_TEXT,
    MODEL_VERSION,
    PredictionFeatures,
    predict,
)


def _good_features() -> PredictionFeatures:
    return PredictionFeatures(
        trend_score=80.0,
        acceleration=70.0,
        search_persistence=75.0,
        content_demand=70.0,
        commercial_relevance=75.0,
        seasonality=60.0,
        saturation_headroom=70.0,
        keyword_breadth=60.0,
        engagement_momentum=65.0,
        historical_lift=50.0,
    )


def _poor_features() -> PredictionFeatures:
    return PredictionFeatures(
        trend_score=20.0,
        acceleration=30.0,
        search_persistence=25.0,
        content_demand=20.0,
        commercial_relevance=25.0,
        seasonality=30.0,
        saturation_headroom=20.0,
        keyword_breadth=20.0,
        engagement_momentum=25.0,
        historical_lift=50.0,
    )


def test_prediction_good_case_confidence_ok():
    result = predict(
        features=_good_features(),
        commercial_potential_score=75.0,
        saturation_score_css=30.0,
        spikiness_norm100=40.0,
        prediction_confidence_pc=80.0,
        freshness_100=85.0,
        n_sources=5,
        baseline_weeks=12,
        user_data_present=False,
    )
    assert result.confidence_score >= 50
    assert result.withheld_from_ranking is False
    assert result.model_version == MODEL_VERSION
    assert result.prediction_timestamp.endswith("Z")
    assert result.disclaimer == DISCLAIMER_TEXT
    assert "not a guarantee" in result.disclaimer.lower()
    # Factors/evidence present: 10 named factors with contributions.
    assert len(result.factors) == 10
    for f in result.factors:
        assert f.name and f.direction in ("supports", "drags", "neutral")
    # Horizon estimates present.
    assert result.estimates.seven_day > 0
    assert result.estimates.thirty_day > 0


def test_prediction_poor_case_degraded():
    result = predict(
        features=_poor_features(),
        commercial_potential_score=20.0,
        saturation_score_css=85.0,
        spikiness_norm100=80.0,
        prediction_confidence_pc=25.0,
        freshness_100=30.0,
        n_sources=1,
        baseline_weeks=2,
        user_data_present=False,
    )
    assert result.confidence_score < 50
    assert result.withheld_from_ranking is True
    # Disclaimer is never dropped, even for degraded predictions.
    assert result.disclaimer == DISCLAIMER_TEXT
    assert result.model_version == MODEL_VERSION


def test_prediction_never_guarantees():
    result = predict(
        features=_good_features(),
        commercial_potential_score=95.0,
        saturation_score_css=5.0,
        spikiness_norm100=10.0,
        prediction_confidence_pc=95.0,
        freshness_100=95.0,
        n_sources=8,
        baseline_weeks=12,
        user_data_present=True,
    )
    assert result.prediction_score <= 100.0
    assert "guarantee" in result.disclaimer.lower()
    assert "probabilistic" in result.disclaimer.lower()
