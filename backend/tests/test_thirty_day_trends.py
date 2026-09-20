"""Tests for 30-day trend analysis (FINAL MASTER SPEC §10–12)."""

from __future__ import annotations

from app.engines.trends import (
    ThirtyDayValues,
    analyze_30d,
    classify_momentum,
    compare_7d_30d,
    monthly_velocity,
    signal_band,
)


def test_monthly_velocity_matches_trend_velocity_math():
    assert monthly_velocity(120.0, 100.0) == 0.2
    assert monthly_velocity(0.0, 0.0) == 0.0  # epsilon guard, no crash
    assert monthly_velocity(50.0, 100.0) == -0.5
    assert monthly_velocity(1000.0, 1.0) == 3.0  # clipped
    assert monthly_velocity(0.0, 1000.0) == -1.0  # clipped


def test_classify_momentum_five_levels():
    assert classify_momentum(2.5) == "STRONGLY_RISING"
    assert classify_momentum(1.0) == "STRONGLY_RISING"
    assert classify_momentum(0.5) == "RISING"
    assert classify_momentum(0.25) == "RISING"
    assert classify_momentum(0.1) == "STABLE"
    assert classify_momentum(0.0) == "STABLE"
    assert classify_momentum(-0.2) == "STABLE"
    assert classify_momentum(-0.5) == "DECLINING"
    assert classify_momentum(-1.0) == "DECLINING"
    assert classify_momentum(-2.0) == "STRONGLY_DECLINING"


def test_signal_band_thresholds():
    assert signal_band(100) == "HIGH"
    assert signal_band(66) == "HIGH"
    assert signal_band(65.9) == "MEDIUM"
    assert signal_band(33) == "MEDIUM"
    assert signal_band(32.9) == "LOW"
    assert signal_band(0) == "LOW"


def test_analyze_30d_explainable():
    a = analyze_30d("ai portraits", ThirtyDayValues(m0=150.0, m1=100.0), 80.0)
    assert a.topic == "ai portraits"
    assert a.monthly_velocity == 0.5
    assert a.momentum == "RISING"
    assert a.signal == "HIGH"
    assert "ai portraits" in a.explanation
    assert "0.50" in a.explanation  # the velocity is spelled out


def test_compare_7d_30d_agreeing_windows():
    c = compare_7d_30d("drones", tv_7d=0.6, tv_30d=1.4, score_7d=70.0, score_30d=85.0)
    assert c.momentum_7d == "RISING"
    assert c.momentum_30d == "STRONGLY_RISING"
    assert c.signal_7d == "HIGH"
    assert c.signal_30d == "HIGH"
    assert c.momentum == "STRONGLY_RISING"
    assert "agree" in c.explanation


def test_compare_7d_30d_divergence_is_stable_with_note():
    c = compare_7d_30d("nft apes", tv_7d=0.8, tv_30d=-0.9, score_7d=72.0, score_30d=20.0)
    assert c.momentum_7d == "RISING"
    assert c.momentum_30d == "DECLINING"
    assert c.momentum == "STABLE"
    assert "diverge" in c.explanation


def test_compare_7d_30d_both_declining():
    c = compare_7d_30d("flatlays", tv_7d=-0.4, tv_30d=-1.5, score_7d=30.0, score_30d=10.0)
    assert c.momentum == "STRONGLY_DECLINING"
    assert c.signal_7d == "LOW"
    assert c.signal_30d == "LOW"


def test_compare_7d_30d_both_flat():
    c = compare_7d_30d("paper textures", tv_7d=0.05, tv_30d=-0.05, score_7d=50.0, score_30d=49.0)
    assert c.momentum == "STABLE"
    assert c.signal_7d == "MEDIUM"
