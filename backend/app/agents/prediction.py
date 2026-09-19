"""prediction agent — probabilistic demand forecasts (never guarantees)."""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.agents import _base
from app.engines.prediction import MODEL_VERSION, PredictionFeatures, predict
from app.models.intelligence import MarketMetric, Prediction
from app.models.platform import AgentRun
from app.models.taxonomy import MicroNiche
from app.schemas.enums import DataProvenance, PredictedDirection, PredictionHorizon


def _features_for(niche_name: str) -> PredictionFeatures:
    h = int(hashlib.sha256(niche_name.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return PredictionFeatures(
        trend_score=round(20 + 60 * h, 2),
        acceleration=round(20 + 60 * h, 2),
        search_persistence=round(20 + 60 * h, 2),
        content_demand=round(20 + 60 * h, 2),
        commercial_relevance=round(20 + 60 * h, 2),
        seasonality=round(30 + 60 * h, 2),
        saturation_headroom=round(20 + 60 * (1 - h), 2),
        keyword_breadth=round(20 + 60 * h, 2),
        engagement_momentum=round(20 + 60 * h, 2),
        historical_lift=50.0,
    )


def run(db: Session, run: AgentRun, input: dict[str, Any]) -> dict[str, Any]:
    horizons = [PredictionHorizon(h) for h in input.get("horizons", ["H30_DAYS", "H90_DAYS"])]
    niches = (
        db.query(MicroNiche)
        .order_by(MicroNiche.name)
        .limit(int(input.get("niche_limit", 10)))
        .all()
    )
    created = 0
    for niche in niches:
        metric = (
            db.query(MarketMetric)
            .filter_by(micro_niche_id=niche.id)
            .order_by(MarketMetric.period_end.desc())
            .first()
        )
        features = _features_for(niche.name)
        demand_index = (
            float(metric.demand_index) if metric and metric.demand_index is not None else 50.0
        )
        result = predict(
            features=features,
            commercial_potential_score=features.commercial_relevance,
            saturation_score_css=100.0 - features.saturation_headroom,
            spikiness_norm100=features.acceleration,
            prediction_confidence_pc=70.0,
            freshness_100=90.0,
            n_sources=5,
            baseline_weeks=2,
            user_data_present=False,
        )
        if result.withheld_from_ranking:
            _base.warn(db, run, f"Skipping {niche.name}: withheld from ranking (low confidence)")
            continue
        direction = (
            PredictedDirection.UP
            if result.estimates.thirty_day > demand_index
            else PredictedDirection.FLAT
        )
        db.add(
            Prediction(
                micro_niche_id=niche.id,
                horizon=horizons[0],
                predicted_demand_index=round(result.prediction_score, 2),
                predicted_direction=direction,
                confidence=round(result.confidence_score / 100.0, 3),
                methodology=(
                    f"{MODEL_VERSION} (rules-based, 10 features). {result.disclaimer} "
                    f"Factors: {', '.join(f.name for f in result.factors[:4])}. "
                    f"Band: {result.band}."
                ),
                data_provenance=DataProvenance.MOCK,
                based_on_metrics_from=date.today() - timedelta(days=14),
                based_on_metrics_to=date.today(),
                agent_run_id=run.id,
            )
        )
        created += 1
    db.commit()
    _base.info(db, run, f"Wrote {created} predictions (probabilistic, never guaranteed)")
    return {
        "predictions_created": created,
        "model_version": MODEL_VERSION,
        "provenance": "MOCK",
        "note": "Predictions are probabilistic estimates, never guarantees of sales. "
        + _base.MOCK_NOTE,
    }
