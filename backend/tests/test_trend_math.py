"""Seven-day trend math (docs/08 §3): velocity, search growth, keyword momentum."""

from __future__ import annotations

import pytest

from app.engines.trends import (
    WindowValues,
    analyze_topic,
    keyword_momentum,
    search_growth,
    trend_velocity,
)


def test_trend_velocity_basic():
    # TV = (V(W0) − V(W1)) / max(V(W1), ε)
    assert trend_velocity(120.0, 100.0) == pytest.approx(0.2)
    assert trend_velocity(100.0, 100.0) == pytest.approx(0.0)
    # Clipped to [−1, +3]
    assert trend_velocity(1000.0, 100.0) == pytest.approx(3.0)
    assert trend_velocity(0.0, 100.0) == pytest.approx(-1.0)


def test_search_growth_basic():
    assert search_growth(150.0, 100.0) == pytest.approx(0.5)
    assert search_growth(100.0, 100.0) == pytest.approx(0.0)


def test_keyword_momentum_mean_of_top5():
    assert keyword_momentum([0.2, 0.4, 0.6, 0.8, 1.0]) == pytest.approx(0.6)
    assert keyword_momentum([]) == 0.0
    # More than 5 → still mean over all provided (top-5 selection upstream)
    assert keyword_momentum([1.0] * 5) == pytest.approx(1.0)


def test_analyze_topic_seven_day_window():
    analysis = analyze_topic(
        topic="solar panels",
        windows=WindowValues(w0=140.0, w1=100.0, baseline=100.0),
        keyword_tvs=[0.1, 0.2, 0.3, 0.4, 0.5],
        source_z_scores=[1.2, 0.8, 1.0],
        seasonality=0.6,
        provenance="MOCK",
    )
    assert analysis.topic == "solar panels"
    assert analysis.trend_velocity == pytest.approx(0.4)
    assert analysis.search_growth == pytest.approx(0.4)
    assert analysis.keyword_momentum == pytest.approx(0.3)
    assert analysis.seasonality == 0.6
    assert analysis.provenance == "MOCK"
    assert analysis.explanation  # human-readable explanation present
    assert analysis.velocity_flag in (
        "up",
        "down",
        "flat",
        "surging",
        "rising",
        "falling",
        "steady",
    )
