"""Phase 3 Personal Performance Engine (backend).

Covers: category metrics math; momentum growing/stable/declining thresholds;
image/video independence; data-derived (never hard-coded) themes;
NOT_CONFIGURED honesty; MOCK exclusion; acceptance; consistency; fit-score
persistence; snapshot persistence. No mock/invented private data anywhere —
all rows are seeded explicitly in the tests.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from app.models import personal as pmodel
from app.models import private as pm
from app.schemas.enums import DataProvenance
from app.services import personal_performance as engine

AS_OF = date(2026, 9, 19)


def _daily(db, day, earnings, downloads=0, prov=DataProvenance.USER_PROVIDED):
    db.add(
        pm.PrivateDailyEarning(
            date=day, earnings=earnings, downloads=downloads, data_provenance=prov
        )
    )


def _cat(db, category, snap_date, downloads, earnings, asset_count):
    db.add(
        pm.PrivateCategoryPerformance(
            category=category,
            snapshot_date=snap_date,
            downloads=downloads,
            earnings=earnings,
            asset_count=asset_count,
        )
    )


def _asset(db, ext_id, title, snap_date, downloads_total, earnings_total):
    db.add(
        pm.PrivateAssetPerformance(
            asset_external_id=ext_id,
            title=title,
            snapshot_date=snap_date,
            downloads_total=downloads_total,
            earnings_total=earnings_total,
        )
    )


def _sub(db, ext_id, status, submitted):
    db.add(
        pm.PrivateSubmissionResult(
            asset_external_id=ext_id, submitted_at=submitted, status=status
        )
    )


def _kw(db, keyword, snap_date, downloads, earnings):
    db.add(
        pm.PrivateKeywordPerformance(
            keyword=keyword,
            snapshot_date=snap_date,
            downloads=downloads,
            earnings=earnings,
        )
    )


def _sub_dt(day):
    return datetime(day.year, day.month, day.day)


# ---------------------------------------------------------------------------
# Category metrics math
# ---------------------------------------------------------------------------


def test_category_metrics_math(db):
    """Cumulative snapshots: as-of totals, averages; per-category acceptance
    is honestly None (submission rows carry no category linkage)."""
    _cat(db, "technology", AS_OF - timedelta(days=30), 100, 10.0, 10)
    _cat(db, "technology", AS_OF, 220, 25.0, 20)
    _cat(db, "nature", AS_OF, 60, 6.0, 6)
    db.commit()

    rows = engine.compute_category_metrics(db, 90)
    assert rows is not None
    tech = next(r for r in rows if r["category"] == "technology")
    assert tech["downloads"] == 220
    assert tech["earnings"] == 25.0
    assert tech["assets_total"] == 20
    assert tech["avg_downloads_per_asset"] == 11.0
    assert tech["avg_earnings_per_asset"] == 1.25
    assert tech["assets_accepted"] is None
    assert tech["assets_rejected"] is None
    assert tech["acceptance_rate"] is None
    nat = next(r for r in rows if r["category"] == "nature")
    assert nat["avg_downloads_per_asset"] == 10.0


def test_category_metrics_none_without_data(db):
    assert engine.compute_category_metrics(db, 30) is None


# ---------------------------------------------------------------------------
# Momentum thresholds: >+15% growing, <-15% declining, else stable
# ---------------------------------------------------------------------------


def _seed_daily_windows(db):
    """Two 7d windows: recent (AS_OF-6..AS_OF), previous (AS_OF-13..AS_OF-7)."""
    recent = [AS_OF - timedelta(days=d) for d in range(7)]
    previous = [AS_OF - timedelta(days=d) for d in range(7, 14)]
    return recent, previous


def test_momentum_growing(db):
    recent, previous = _seed_daily_windows(db)
    for d in recent:
        _daily(db, d, 100.0, downloads=20)
    for d in previous:
        _daily(db, d, 50.0, downloads=10)
    db.commit()
    summary = engine.overall_summary(db, 30)
    w = summary["momentum"]["earnings"]["7d"]
    assert w["available"] is True
    assert w["change_pct"] == 100.0
    assert w["trend"] == "growing"


def test_momentum_declining(db):
    recent, previous = _seed_daily_windows(db)
    for d in recent:
        _daily(db, d, 40.0, downloads=5)
    for d in previous:
        _daily(db, d, 50.0, downloads=10)
    db.commit()
    summary = engine.overall_summary(db, 30)
    w = summary["momentum"]["earnings"]["7d"]
    assert w["available"] is True
    assert w["change_pct"] == -20.0
    assert w["trend"] == "declining"


def test_momentum_stable_within_band(db):
    recent, previous = _seed_daily_windows(db)
    for d in recent:
        _daily(db, d, 105.0, downloads=10)
    for d in previous:
        _daily(db, d, 100.0, downloads=10)
    db.commit()
    summary = engine.overall_summary(db, 30)
    w = summary["momentum"]["earnings"]["7d"]
    assert w["available"] is True
    assert w["change_pct"] == 5.0
    assert w["trend"] == "stable"


def test_momentum_unavailable_without_prior_window(db):
    """Only recent data: no previous window -> no label, never fabricated."""
    recent, _ = _seed_daily_windows(db)
    for d in recent:
        _daily(db, d, 100.0, downloads=10)
    db.commit()
    summary = engine.overall_summary(db, 30)
    w = summary["momentum"]["earnings"]["7d"]
    assert w["available"] is False
    assert w["change_pct"] is None
    assert w["trend"] is None


def test_category_momentum_from_snapshot_deltas(db):
    """Category momentum compares period deltas of cumulative snapshots."""
    _cat(db, "technology", AS_OF - timedelta(days=60), 80, 8.0, 10)
    _cat(db, "technology", AS_OF - timedelta(days=30), 100, 10.0, 10)
    _cat(db, "technology", AS_OF - timedelta(days=14), 110, 11.0, 10)
    _cat(db, "technology", AS_OF - timedelta(days=7), 120, 12.0, 10)
    _cat(db, "technology", AS_OF, 200, 20.0, 10)
    db.commit()
    rows = engine.compute_category_metrics(db, 90)
    tech = next(r for r in rows if r["category"] == "technology")
    m7 = tech["momentum"]["downloads"]["7d"]
    assert m7["available"] is True
    assert m7["current"] == 80.0  # 200 - 120
    assert m7["previous"] == 10.0  # 120 - 110
    assert m7["trend"] == "growing"
    # 30d earnings: cur = 20-10, prev = 10-8 -> +400% -> growing
    m30 = tech["momentum"]["earnings"]["30d"]
    assert m30["available"] is True
    assert m30["change_pct"] == 400.0
    assert m30["trend"] == "growing"
    assert tech["trend_label"] == "growing"  # from 30d earnings


# ---------------------------------------------------------------------------
# Content types: images vs videos independently
# ---------------------------------------------------------------------------


def _seed_content_types(db):
    _asset(db, "ext-img1", "Business team meeting photo", AS_OF, 100, 20.0)
    _asset(db, "ext-img2", "Office desk workspace", AS_OF, 60, 12.0)
    _asset(db, "ext-vid1", "Aerial city drone footage", AS_OF, 400, 90.0)
    _asset(db, "ext-zzz", "Unknown mystery asset", AS_OF, 10, 1.0)
    _sub(db, "ext-img1", "ACCEPTED", _sub_dt(AS_OF - timedelta(days=40)))
    _sub(db, "ext-vid1", "REJECTED", _sub_dt(AS_OF - timedelta(days=40)))
    db.commit()


def test_content_type_independence(db):
    """Image metrics never inform video metrics; unmapped -> 'unknown'."""
    _seed_content_types(db)
    cmap = {"ext-img1": "image", "ext-img2": "image", "ext-vid1": "video"}
    rows = engine.compute_content_type_metrics(db, 90, content_type_map=cmap)
    by_type = {r["content_type"]: r for r in rows}

    img = by_type["image"]
    assert img["assets_total"] == 2
    assert img["downloads"] == 160
    assert img["earnings"] == 32.0
    assert img["avg_downloads_per_asset"] == 80.0
    assert img["acceptance_rate"] == 1.0  # 1 accepted / 1 decided

    vid = by_type["video"]
    assert vid["assets_total"] == 1
    assert vid["downloads"] == 400
    assert vid["earnings"] == 90.0
    assert vid["acceptance_rate"] == 0.0  # 0 accepted / 1 decided

    unk = by_type["unknown"]
    assert unk["assets_total"] == 1
    assert unk["downloads"] == 10
    # No image data leaked into video metrics (or vice versa).
    assert vid["downloads"] != img["downloads"]


def test_content_type_none_without_data(db):
    assert engine.compute_content_type_metrics(db, 30) is None


# ---------------------------------------------------------------------------
# Theme discovery: derived from data, never hard-coded
# ---------------------------------------------------------------------------


def _seed_themes(db):
    _asset(db, "a1", "Mountain sunrise landscape", AS_OF, 100, 20.0)
    _asset(db, "a2", "Mountain lake reflection", AS_OF, 80, 15.0)
    _asset(db, "a3", "City night street neon", AS_OF, 50, 10.0)
    _kw(db, "mountain photography", AS_OF, 30, 5.0)
    db.commit()


def test_themes_derived_from_titles_not_hardcoded(db):
    _seed_themes(db)
    themes = engine.discover_themes(db, 90)
    assert themes is not None
    labels = [t["theme_label"] for t in themes]
    # "mountain" co-occurs in 2 titles -> theme; "city" appears once -> dropped.
    assert "mountain" in labels
    assert "city" not in labels
    assert "landscape" not in labels
    mountain = next(t for t in themes if t["theme_label"] == "mountain")
    assert mountain["asset_count"] == 2
    assert mountain["downloads"] == 180
    assert mountain["earnings"] == 35.0
    # Evidence is auditable: co-occurring tokens + matching keyword rows.
    assert any("mountain" in e for e in mountain["evidence_keywords"])


def test_themes_ranked_by_downloads(db):
    _seed_themes(db)
    themes = engine.discover_themes(db, 90)
    assert themes[0]["theme_label"] == "mountain"


def test_themes_none_without_data(db):
    assert engine.discover_themes(db, 30) is None


def test_themes_need_cooccurrence(db):
    """No shared tokens across titles -> no themes (not one-offs)."""
    _asset(db, "b1", "Alpine glacier expedition", AS_OF, 10, 1.0)
    _asset(db, "b2", "Desert caravan dunes", AS_OF, 20, 2.0)
    db.commit()
    assert engine.discover_themes(db, 90) == []


# ---------------------------------------------------------------------------
# NOT_CONFIGURED honesty (engine + API)
# ---------------------------------------------------------------------------


def test_not_configured_engine(db):
    assert engine.availability(db)["has_private_data"] is False
    assert engine.overall_summary(db, 30) is None
    assert engine.compute_category_metrics(db, 30) is None
    assert engine.compute_content_type_metrics(db, 30) is None
    assert engine.discover_themes(db, 30) is None
    assert engine.compute_keyword_metrics(db, 30) is None
    assert engine.compute_acceptance_rate(db) is None
    assert engine.compute_consistency_score(db) is None
    assert engine.snapshot_period(db, 30) is None


def test_not_configured_api_summary(client):
    r = client.get("/api/personal-performance")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "not_configured"
    assert body["earnings_total"] is None
    assert body["downloads_total"] is None
    assert body["momentum"] is None
    assert body["acceptance"] is None
    assert body["consistency"] is None
    assert body["top_categories"] == []
    assert body["top_themes"] == []


def test_not_configured_api_lists(client):
    for path in (
        "/api/personal-performance/categories",
        "/api/personal-performance/content-types",
        "/api/personal-performance/themes",
    ):
        r = client.get(path)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "not_configured", path
        assert body["data"] == []
        assert body["pagination"]["total"] == 0


def test_snapshot_post_not_configured(client):
    r = client.post("/api/personal-performance/snapshot")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "NOT_CONFIGURED"


# ---------------------------------------------------------------------------
# MOCK rows excluded from intelligence unless dev mode
# ---------------------------------------------------------------------------


def test_mock_rows_excluded_from_intelligence(db):
    _daily(db, AS_OF, 999.0, downloads=999, prov=DataProvenance.MOCK)
    db.commit()
    avail = engine.availability(db)
    assert avail["has_private_data"] is False
    assert engine.overall_summary(db, 30) is None


# ---------------------------------------------------------------------------
# Acceptance rate math
# ---------------------------------------------------------------------------


def test_acceptance_rate_math(db):
    _sub(db, "e1", "ACCEPTED", _sub_dt(AS_OF - timedelta(days=50)))
    _sub(db, "e2", "ACCEPTED", _sub_dt(AS_OF - timedelta(days=49)))
    _sub(db, "e3", "ACCEPTED", _sub_dt(AS_OF - timedelta(days=48)))
    _sub(db, "e4", "REJECTED", _sub_dt(AS_OF - timedelta(days=47)))
    _sub(db, "e5", "PENDING", _sub_dt(AS_OF - timedelta(days=46)))
    db.commit()
    acc = engine.compute_acceptance_rate(db)
    assert acc["accepted"] == 3
    assert acc["rejected"] == 1
    assert acc["pending"] == 1
    assert acc["acceptance_rate"] == 0.75
    assert acc["available"] is True


def test_acceptance_rate_none_when_no_decisions(db):
    _sub(db, "e1", "PENDING", _sub_dt(AS_OF - timedelta(days=5)))
    db.commit()
    acc = engine.compute_acceptance_rate(db)
    assert acc["acceptance_rate"] is None
    assert acc["available"] is False


# ---------------------------------------------------------------------------
# Consistency score
# ---------------------------------------------------------------------------


def _seed_weeks(db, weekly_earnings):
    for w, total in enumerate(weekly_earnings):
        _daily(db, AS_OF - timedelta(days=7 * w), total, downloads=10)
    db.commit()


def test_consistency_stable_scores_high(db):
    _seed_weeks(db, [100.0] * 8)
    c = engine.compute_consistency_score(db)
    assert c["available"] is True
    assert c["score"] == 100.0
    assert c["weeks_with_data"] == 8


def test_consistency_volatile_scores_low(db):
    _seed_weeks(db, [10.0, 500.0, 20.0, 400.0, 15.0, 450.0, 25.0, 380.0])
    c = engine.compute_consistency_score(db)
    assert c["available"] is True
    assert c["score"] < 40.0


def test_consistency_none_with_too_few_weeks(db):
    _seed_weeks(db, [100.0, 100.0, 100.0])
    assert engine.compute_consistency_score(db) is None


# ---------------------------------------------------------------------------
# Fit-score persistence + snapshot persistence
# ---------------------------------------------------------------------------


def test_record_fit_score_honest_none(db):
    row = engine.record_fit_score(
        db,
        opportunity_id="opp-1",
        micro_niche_id=None,
        score=None,
        components={"acceptance_rate": None, "reason": "no private data"},
    )
    db.commit()
    got = db.query(pmodel.PersonalFitScore).filter_by(id=row.id).one()
    assert got.score is None
    assert got.formula_version == "ppf-v1"
    assert got.component_json["acceptance_rate"] is None
    assert got.opportunity_id == "opp-1"


def test_snapshot_period_persists(db):
    for d in range(30):
        _daily(db, AS_OF - timedelta(days=d), 10.0, downloads=5)
    db.commit()
    row = engine.snapshot_period(db, 30)
    db.commit()
    assert row is not None
    assert row.period_days == 30
    assert row.data_provenance == DataProvenance.USER_PROVIDED
    metrics = row.metrics_json
    assert metrics["earnings_total"] == 300.0
    assert metrics["downloads_total"] == 150


# ---------------------------------------------------------------------------
# API: available state
# ---------------------------------------------------------------------------


def test_api_summary_available(client, db):
    for d in range(30):
        _daily(db, AS_OF - timedelta(days=d), 10.0, downloads=5)
    _cat(db, "technology", AS_OF, 100, 10.0, 10)
    _sub(db, "e1", "ACCEPTED", _sub_dt(AS_OF - timedelta(days=50)))
    db.commit()

    r = client.get("/api/personal-performance?period=30d")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "available"
    assert body["earnings_total"] == 300.0
    assert body["downloads_total"] == 150
    assert body["acceptance"]["acceptance_rate"] == 1.0
    assert body["data_provenance"] == "USER_PROVIDED"
    assert body["top_categories"][0]["category"] == "technology"

    r = client.get("/api/personal-performance/categories?period=30d")
    body = r.json()
    assert body["status"] == "available"
    assert body["data"][0]["category"] == "technology"
    assert body["pagination"]["total"] == 1

    r = client.post("/api/personal-performance/snapshot?period=30d")
    assert r.status_code == 200
    assert r.json()["created"] is True


def test_api_period_filter_validation(client):
    r = client.get("/api/personal-performance?period=45d")
    assert r.status_code == 422
