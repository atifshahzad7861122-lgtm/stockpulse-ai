"""Personal Performance endpoints (Phase 3, backend — Personal Intelligence).

Honest availability contract: when Adobe private data is NOT_CONFIGURED
(no rows), every endpoint returns ``status="not_configured"`` with nulls /
empty lists — never fabricated values.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    bad_request,
    get_db,
    paginate,
    pagination_params,
)
from app.schemas.common import PageInfo
from app.schemas.personal_performance import (
    CategoryListOut,
    CategoryMetricOut,
    ContentTypeListOut,
    ContentTypeMetricOut,
    MomentumPairOut,
    PersonalPerformanceSummary,
    SnapshotPersistOut,
    ThemeListOut,
    ThemeMetricOut,
)
from app.services import personal_performance as engine

router = APIRouter(prefix="/personal-performance", tags=["personal-performance"])

PeriodParam = Literal["7d", "30d", "90d"]


def _period_days(period: str) -> int:
    return int(period[:-1])


def _empty_page(page: int, page_size: int) -> PageInfo:
    return PageInfo(page=page, page_size=page_size, total=0, total_pages=0)


def _summary_or_not_configured(
    db: Session, period: str
) -> PersonalPerformanceSummary:
    days = _period_days(period)
    summary = engine.overall_summary(db, days)
    if summary is None:
        return PersonalPerformanceSummary(
            status="not_configured",
            period=period,
            period_days=days,
            availability=engine.availability(db),
        )
    return PersonalPerformanceSummary(
        status="available",
        period=period,
        period_days=days,
        data_provenance=summary["data_provenance"],
        period_start=summary["period_start"],
        period_end=summary["period_end"],
        earnings_total=summary["earnings_total"],
        downloads_total=summary["downloads_total"],
        momentum=MomentumPairOut(**summary["momentum"]) if summary["momentum"] else None,
        acceptance=summary["acceptance"],
        consistency=summary["consistency"],
        top_categories=[CategoryMetricOut(**c) for c in summary["top_categories"]],
        top_themes=[ThemeMetricOut(**t) for t in summary["top_themes"]],
        availability=engine.availability(db),
    )


# ---------------------------------------------------------------------------
# GET /personal-performance — overall summary
# ---------------------------------------------------------------------------


@router.get("", response_model=PersonalPerformanceSummary)
def get_personal_performance(
    db: Annotated[Session, Depends(get_db)],
    period: PeriodParam = Query("30d", description="Time filter: 7d | 30d | 90d"),
):
    """Overall personal summary: availability, totals, momentum, acceptance,
    consistency, top categories/themes. Honest not_configured when no data."""
    return _summary_or_not_configured(db, period)


# ---------------------------------------------------------------------------
# GET /personal-performance/categories
# ---------------------------------------------------------------------------


@router.get("/categories", response_model=CategoryListOut)
def list_category_metrics(
    db: Annotated[Session, Depends(get_db)],
    period: PeriodParam = Query("30d", description="Time filter: 7d | 30d | 90d"),
    paging: dict = Depends(pagination_params),
):
    days = _period_days(period)
    rows = engine.compute_category_metrics(db, days)
    if rows is None:
        return CategoryListOut(
            status="not_configured",
            period=period,
            period_days=days,
            data=[],
            pagination=_empty_page(paging["page"], paging["page_size"]),
        )
    items = [CategoryMetricOut(**r) for r in rows]
    page = paginate(items, page=paging["page"], page_size=paging["page_size"], total=len(items))
    return CategoryListOut(
        status="available",
        period=period,
        period_days=days,
        data=page.data,
        pagination=page.pagination,
    )


# ---------------------------------------------------------------------------
# GET /personal-performance/content-types
# ---------------------------------------------------------------------------


@router.get("/content-types", response_model=ContentTypeListOut)
def list_content_type_metrics(
    db: Annotated[Session, Depends(get_db)],
    period: PeriodParam = Query("30d", description="Time filter: 7d | 30d | 90d"),
    paging: dict = Depends(pagination_params),
):
    """Image vs video metrics, computed independently. Unclassifiable assets
    sit in ``unknown`` — never guessed, never cross-inferred."""
    days = _period_days(period)
    rows = engine.compute_content_type_metrics(db, days)
    if rows is None:
        return ContentTypeListOut(
            status="not_configured",
            period=period,
            period_days=days,
            data=[],
            pagination=_empty_page(paging["page"], paging["page_size"]),
        )
    items = [ContentTypeMetricOut(**r) for r in rows]
    page = paginate(items, page=paging["page"], page_size=paging["page_size"], total=len(items))
    return ContentTypeListOut(
        status="available",
        period=period,
        period_days=days,
        data=page.data,
        pagination=page.pagination,
    )


# ---------------------------------------------------------------------------
# GET /personal-performance/themes
# ---------------------------------------------------------------------------


@router.get("/themes", response_model=ThemeListOut)
def list_themes(
    db: Annotated[Session, Depends(get_db)],
    period: PeriodParam = Query("30d", description="Time filter: 7d | 30d | 90d"),
    paging: dict = Depends(pagination_params),
):
    """Themes derived from the user's own titles/keywords (never hard-coded)."""
    days = _period_days(period)
    rows = engine.discover_themes(db, days)
    if rows is None:
        return ThemeListOut(
            status="not_configured",
            period=period,
            period_days=days,
            data=[],
            pagination=_empty_page(paging["page"], paging["page_size"]),
        )
    items = [ThemeMetricOut(**r) for r in rows]
    page = paginate(items, page=paging["page"], page_size=paging["page_size"], total=len(items))
    return ThemeListOut(
        status="available",
        period=period,
        period_days=days,
        data=page.data,
        pagination=page.pagination,
    )


# ---------------------------------------------------------------------------
# POST /personal-performance/snapshot — persist the current summary
# ---------------------------------------------------------------------------


@router.post("/snapshot", response_model=SnapshotPersistOut)
def persist_snapshot(
    db: Annotated[Session, Depends(get_db)],
    period: PeriodParam = Query("30d", description="Time filter: 7d | 30d | 90d"),
):
    """Compute the overall summary and store it as a PersonalPerformanceSnapshot."""
    row = engine.snapshot_period(db, _period_days(period))
    if row is None:
        raise bad_request(
            "NOT_CONFIGURED",
            "No private data to snapshot. Connect Adobe Contributor data first.",
        )
    db.commit()
    return SnapshotPersistOut(
        snapshot_id=row.id, period=period, period_days=row.period_days, created=True
    )
