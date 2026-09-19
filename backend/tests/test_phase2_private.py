"""Private (user-owned) data tables: append-only time-series, unique guards,
USER_PROVIDED provenance, and the aggregation that feeds Personal Fit Score
(PHASE2_DESIGN.md §3, §6, §9). No invented Adobe numbers anywhere."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import private as pm
from app.schemas.enums import DataProvenance
from app.services.personal_fit import compute_personal_fit


def _earning(db, day, earnings, downloads=0):
    row = pm.PrivateDailyEarning(date=day, earnings=earnings, downloads=downloads)
    db.add(row)
    return row


def test_daily_earning_unique_per_date(db):
    _earning(db, date(2026, 9, 18), 10.0)
    db.commit()
    _earning(db, date(2026, 9, 18), 99.0)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_tables_are_append_only(db):
    """Two snapshots for the same asset on different dates both persist —
    history rows are never updated in place."""
    for day in (date(2026, 9, 17), date(2026, 9, 18)):
        db.add(
            pm.PrivateAssetPerformance(
                asset_external_id="ext-1",
                title="Asset one",
                snapshot_date=day,
                downloads_total=5,
                earnings_total=1.5,
            )
        )
    db.commit()
    rows = (
        db.query(pm.PrivateAssetPerformance)
        .filter_by(asset_external_id="ext-1")
        .order_by(pm.PrivateAssetPerformance.snapshot_date)
        .all()
    )
    assert len(rows) == 2
    assert [r.downloads_total for r in rows] == [5, 5]


def test_category_performance_unique_per_day(db):
    db.add(
        pm.PrivateCategoryPerformance(
            category="technology", snapshot_date=date(2026, 9, 18), downloads=10
        )
    )
    db.commit()
    db.add(
        pm.PrivateCategoryPerformance(
            category="technology", snapshot_date=date(2026, 9, 18), downloads=11
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_private_rows_default_user_provided(db):
    row = pm.PrivateDailyEarning(date=date(2026, 9, 18), earnings=3.25, downloads=7)
    db.add(row)
    db.commit()
    db.refresh(row)
    assert row.data_provenance == DataProvenance.USER_PROVIDED


def test_keyword_and_snapshot_models(db):
    db.add(
        pm.PrivateKeywordPerformance(
            keyword="ai portrait", snapshot_date=date(2026, 9, 18), downloads=4, earnings=1.0
        )
    )
    db.add(
        pm.PrivateSnapshot(
            snapshot_date=date(2026, 9, 18),
            summary_json={"totals": {"earnings": 3.25, "downloads": 7}},
        )
    )
    db.commit()
    assert db.query(pm.PrivateKeywordPerformance).count() == 1
    snap = db.query(pm.PrivateSnapshot).one()
    assert snap.summary_json["totals"]["earnings"] == 3.25


def test_submission_results_feed_acceptance_rate(db):
    now = datetime.now(UTC)
    db.add(pm.PrivateSubmissionResult(asset_external_id="a1", submitted_at=now, status="ACCEPTED"))
    db.add(
        pm.PrivateSubmissionResult(
            asset_external_id="a2", submitted_at=now, status="REJECTED", rejection_reason="quality"
        )
    )
    db.commit()
    rows = db.query(pm.PrivateSubmissionResult).all()
    accepted = sum(1 for r in rows if r.status == "ACCEPTED")
    decided = sum(1 for r in rows if r.status in ("ACCEPTED", "REJECTED"))
    assert accepted / decided == pytest.approx(0.5)


def test_compute_personal_fit_none_without_private_data(db):
    assert (
        compute_personal_fit(
            db, micro_niche_id=None, title="AI business portraits", summary="Studio portraits"
        )
        is None
    )


def test_compute_personal_fit_scores_with_private_data(db):
    # Resolve a real niche → category slug, then make that slug the user's
    # strongest category. Fully deterministic regardless of seed content.
    from app.models.taxonomy import Category, MicroNiche, Subcategory

    niche = db.query(MicroNiche).first()
    assert niche is not None
    sub = db.query(Subcategory).filter_by(id=niche.subcategory_id).one()
    cat = db.query(Category).filter_by(id=sub.category_id).one()
    slug = cat.slug
    db.add(
        pm.PrivateCategoryPerformance(
            category=slug,
            snapshot_date=date(2026, 9, 18),
            downloads=120,
            earnings=45.0,
            asset_count=10,
        )
    )
    db.add(
        pm.PrivateCategoryPerformance(
            category="zz-weak-category",
            snapshot_date=date(2026, 9, 18),
            downloads=10,
            earnings=2.0,
            asset_count=8,
        )
    )
    db.commit()
    score = compute_personal_fit(
        db,
        micro_niche_id=niche.id,
        title=f"{cat.name} team portraits",
        summary="Corporate headshots and office scenes",
    )
    # The niche's own category is the user's strongest → high fit, 0–100.
    assert score is not None
    assert 0.0 <= score <= 100.0
    assert score > 50.0


def test_private_collection_run_lifecycle(db):
    run = pm.PrivateCollectionRun(status="RUNNING", trigger="MANUAL")
    db.add(run)
    db.commit()
    run.status = "SUCCESS"
    run.finished_at = datetime.now(UTC)
    db.commit()
    assert db.query(pm.PrivateCollectionRun).filter_by(status="SUCCESS").count() == 1
