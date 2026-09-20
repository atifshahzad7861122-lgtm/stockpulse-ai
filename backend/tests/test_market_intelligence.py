"""Tests for the market intelligence engine (FINAL MASTER SPEC §10–17)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.engines import market_intelligence as mi
from app.models.intelligence import TrendSignal, TrendSnapshot, TrendSource
from app.models.taxonomy import Category, MicroNiche, Subcategory
from app.schemas.enums import DataProvenance, SignalKind, TrendSourceType


def _make_topic(db, topic, w0, w1, baseline, provenance="THIRD_PARTY",
                signal_plan=None, niche_name=None):
    """Create one topic: a snapshot with 7D payload values + signal rows.

    signal_plan: list of (days_ago, metric_value, metric_name, signal_name).
    """
    src = db.query(TrendSource).first()
    snap = TrendSnapshot(
        trend_source_id=src.id,
        captured_at=datetime.now(UTC),
        payload={
            "topic": topic,
            "w0_mean": w0,
            "w1_mean": w1,
            "baseline_mean": baseline,
            "keyword_tvs": [0.4, 0.3],
            "provenance": provenance,
            "keywords": ["ai", "business", "portrait"],
        },
        payload_hash=f"hash-{topic}",
    )
    db.add(snap)
    db.flush()
    for days_ago, value, metric_name, signal_name in (signal_plan or []):
        db.add(
            TrendSignal(
                trend_snapshot_id=snap.id,
                signal_name=signal_name,
                metric_name=metric_name,
                metric_value=value,
                observed_at=datetime.now(UTC) - timedelta(days=days_ago),
                data_provenance=DataProvenance.THIRD_PARTY,
            )
        )
    if niche_name:
        cat = db.query(Category).filter_by(slug="ai").one()
        sub = db.query(Subcategory).filter_by(category_id=cat.id).first()
        db.add(MicroNiche(subcategory_id=sub.id, name=niche_name, slug=niche_name.replace(" ", "-")))
    db.commit()
    return snap


def _signal_plan_rising():
    # Recent 30d stronger than prior 30d → RISING on both windows.
    plan = []
    for d in range(0, 30, 3):
        plan.append((d, 10.0 + d * 0.1, "trend_index", "ai business portraits trend"))
    for d in range(31, 60, 3):
        plan.append((d, 5.0, "trend_index", "ai business portraits trend"))
    return plan


def test_all_topics_ranks_and_labels(db):
    _make_topic(db, "ai business portraits", w0=400.0, w1=100.0, baseline=90.0,
                signal_plan=_signal_plan_rising(), niche_name="ai business portraits")
    _make_topic(db, "paper textures", w0=40.0, w1=60.0, baseline=55.0,
                signal_plan=[(d, 3.0, "trend_index", "paper textures trend") for d in range(0, 60, 5)])
    topics = mi.all_topics(db)
    assert len(topics) == 2
    assert topics[0].topic == "ai business portraits"  # higher 7D score first
    top = topics[0]
    assert top.signal_7d == "HIGH"
    assert top.momentum_7d in ("RISING", "STRONGLY_RISING")
    assert top.signal_30d is not None
    assert top.momentum in ("RISING", "STRONGLY_RISING", "STABLE")
    assert top.provenance == "THIRD_PARTY"
    assert top.signal_kind == SignalKind.TREND_SIGNAL.value
    assert top.category == "ai"
    assert top.asset_type == "image"
    assert "ai business portraits" in top.explanation
    # every insight carries provenance + window info
    assert top.last_updated is not None
    assert top.frequency > 0


def test_mock_rows_excluded_without_dev_mode(db):
    _make_topic(db, "demo topic", w0=200.0, w1=10.0, baseline=10.0, provenance="MOCK")
    assert mi.all_topics(db) == []


def test_insufficient_30d_history_leaves_30d_null(db):
    _make_topic(db, "fresh topic", w0=400.0, w1=100.0, baseline=90.0,
                signal_plan=[(1, 9.0, "trend_index", "fresh topic trend")])
    (topic,) = mi.all_topics(db)
    assert topic.signal_30d is None
    assert topic.momentum_30d is None
    assert topic.velocity_30d is None
    # 7D still works
    assert topic.signal_7d == "HIGH"


def test_rising_and_declining_split(db):
    _make_topic(db, "ai business portraits", w0=400.0, w1=100.0, baseline=90.0,
                signal_plan=_signal_plan_rising())
    declining_plan = []
    for d in range(0, 30, 3):
        declining_plan.append((d, 4.0, "trend_index", "fax machines trend"))
    for d in range(31, 60, 3):
        declining_plan.append((d, 10.0, "trend_index", "fax machines trend"))
    _make_topic(db, "fax machines", w0=40.0, w1=80.0, baseline=90.0,
                signal_plan=declining_plan)
    topics = mi.all_topics(db)
    rising = mi.rising_topics(topics)
    declining = mi.declining_topics(topics)
    assert [t.topic for t in rising] == ["ai business portraits"]
    assert [t.topic for t in declining] == ["fax machines"]


def test_top_categories_aggregates(db):
    _make_topic(db, "ai business portraits", w0=400.0, w1=100.0, baseline=90.0,
                signal_plan=_signal_plan_rising(), niche_name="ai business portraits")
    topics = mi.all_topics(db)
    cats = mi.top_categories(db, topics)
    assert len(cats) == 1
    cat = cats[0]
    assert cat.slug == "ai"
    assert cat.name == "AI"
    assert cat.signal_7d == "HIGH"
    assert cat.topic_count == 1
    assert cat.provenance == "THIRD_PARTY"


def test_top_keywords_with_movement(db):
    _make_topic(db, "ai business portraits", w0=400.0, w1=100.0, baseline=90.0,
                signal_plan=_signal_plan_rising())
    topics = mi.all_topics(db)
    kws = mi.top_keywords(db, topics)
    assert kws, "expected keywords extracted from signal names"
    names = [k.keyword for k in kws]
    assert "portraits" in names or "business" in names
    kw = next(k for k in kws if k.keyword in ("portraits", "business", "trend"))
    assert kw.frequency >= 1
    assert kw.movement_7d in ("STRONGLY_RISING", "RISING", "STABLE", "DECLINING", "STRONGLY_DECLINING")
    assert kw.related_image_topics or kw.related_video_topics


def test_signal_kind_labeling():
    assert mi.signal_kind_for("google_search_volume") == SignalKind.SEARCH_SIGNAL
    assert mi.signal_kind_for("total_sales") == SignalKind.SALES
    assert mi.signal_kind_for("download_count") == SignalKind.DOWNLOADS
    assert mi.signal_kind_for("popularity_rank") == SignalKind.POPULARITY_SIGNAL
    assert mi.signal_kind_for("trend_index") == SignalKind.TREND_SIGNAL
    assert mi.signal_kind_for("demand_score") == SignalKind.PUBLIC_DEMAND_SIGNAL
    assert mi.signal_kind_for(None) == SignalKind.PUBLIC_DEMAND_SIGNAL
    # never claim sales unless the source provides them
    assert mi.signal_kind_for("page_views") != SignalKind.SALES


def test_asset_type_heuristic():
    assert mi.asset_type_for("drone footage city", ["aerial video clip"]) == "video"
    assert mi.asset_type_for("business portraits", ["studio photo"]) == "image"
    assert mi.asset_type_for("abstract shapes", []) == "image"  # documented default


def test_overview_shape_and_last_update(db):
    _make_topic(db, "ai business portraits", w0=400.0, w1=100.0, baseline=90.0,
                signal_plan=_signal_plan_rising())
    ov = mi.overview(db)
    assert ov["topic_count"] == 1
    assert ov["last_data_update"] is not None
    assert len(ov["top_image_topics"]) == 1
    assert ov["top_video_topics"] == []
    assert len(ov["top_keywords"]) > 0
    assert len(ov["rising_now"]) == 1
    assert len(ov["window_comparison"]) == 1


def test_overview_empty_db_has_no_fake_data(db):
    ov = mi.overview(db)
    assert ov["topic_count"] == 0
    assert ov["top_categories"] == []
    assert ov["last_data_update"] is None


def test_trends_router_30d_window_uses_real_30d_scores(client, db):
    """window=30d must use real 30-day signal history, not the 7D label."""
    _make_topic(db, "ai business portraits", w0=400.0, w1=100.0, baseline=90.0,
                signal_plan=_signal_plan_rising())
    resp = client.get("/api/trends?window=30d")
    assert resp.status_code == 200
    items = resp.json()["data"]
    row = next(i for i in items if i["title"] == "ai business portraits")
    assert row["window"] == "30d"
    assert row["signal_30d"] is not None
    assert row["momentum_30d"] in (
        "STRONGLY_RISING", "RISING", "STABLE", "DECLINING", "STRONGLY_DECLINING")
    assert row["signal_kind"] == "TREND_SIGNAL"
    # 7D window keeps the 7D fields
    resp7 = client.get("/api/trends?window=7d")
    row7 = next(i for i in resp7.json()["data"] if i["title"] == "ai business portraits")
    assert row7["signal_7d"] == "HIGH"
    assert row7["signal_30d"] is None  # 7D view doesn't compute the 30D band
