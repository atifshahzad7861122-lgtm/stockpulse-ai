"""Similarity thresholds: exact boundary behavior (docs/17 §4).

- < 0.60 → CLEAR
- 0.60 – < 0.80 → REVIEW
- ≥ 0.80 → HIGH_RISK
"""

from __future__ import annotations

import pytest

from app.engines.similarity import (
    HIGH_RISK_THRESHOLD,
    REVIEW_THRESHOLD,
    verdict_for,
)


@pytest.mark.parametrize(
    "score,expected",
    [
        (0.0, "CLEAR"),
        (0.5999, "CLEAR"),
        (0.60, "REVIEW"),
        (0.6001, "REVIEW"),
        (0.7999, "REVIEW"),
        (0.80, "HIGH_RISK"),
        (0.8001, "HIGH_RISK"),
        (1.0, "HIGH_RISK"),
    ],
)
def test_verdict_boundaries(score, expected):
    assert verdict_for(score) == expected


def test_threshold_constants():
    assert REVIEW_THRESHOLD == 0.60
    assert HIGH_RISK_THRESHOLD == 0.80


def test_verdict_embedding_available_same_boundaries():
    # Fallback band matches the authoritative REVIEW_THRESHOLD.
    for score, expected in [(0.5999, "CLEAR"), (0.60, "REVIEW"), (0.80, "HIGH_RISK")]:
        assert verdict_for(score, embedding_available=True) == expected
        assert verdict_for(score, embedding_available=False) == expected
