"""Market intelligence API (FINAL MASTER SPEC §10–18).

Read-only aggregation of real collected data: top categories, top image /
video topics, top keywords, rising / declining trends, and the 7-day vs
30-day comparison with momentum. MOCK rows are excluded unless dev mode.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, paginate, pagination_params
from app.engines import market_intelligence as mi
from app.schemas.common import Page
from app.schemas.market_intelligence import (
    CategoryIntelOut,
    KeywordIntelOut,
    MarketIntelligenceOverview,
    MoverOut,
    TopicIntelOut,
    WindowComparisonOut,
)

router = APIRouter(prefix="/market-intelligence", tags=["market-intelligence"])


def _topic_out(t: mi.TopicIntelligence) -> TopicIntelOut:
    return TopicIntelOut(
        topic=t.topic,
        category=t.category,
        asset_type=t.asset_type,
        signal_7d=t.signal_7d,
        signal_30d=t.signal_30d,
        momentum=t.momentum,
        momentum_7d=t.momentum_7d,
        momentum_30d=t.momentum_30d,
        trend_signal=t.trend_signal,
        momentum_7d_score=t.momentum_7d_score,
        momentum_30d_score=t.momentum_30d_score,
        opportunity_signal=t.opportunity_signal,
        frequency=t.frequency,
        keywords=list(t.keywords),
        sources=list(t.sources),
        signal_kind=t.signal_kind,
        provenance=t.provenance,
        last_updated=t.last_updated,
        explanation=t.explanation,
    )


def _mover_out(t: mi.TopicIntelligence) -> MoverOut:
    return MoverOut(
        topic=t.topic,
        asset_type=t.asset_type,
        momentum=t.momentum,
        signal_7d=t.signal_7d,
        signal_30d=t.signal_30d,
        trend_signal=t.trend_signal,
    )


def _comparison_out(t: mi.TopicIntelligence) -> WindowComparisonOut:
    return WindowComparisonOut(
        topic=t.topic,
        signal_7d=t.signal_7d,
        signal_30d=t.signal_30d,
        momentum=t.momentum,
        momentum_7d=t.momentum_7d,
        momentum_30d=t.momentum_30d,
        trend_signal=t.trend_signal,
        momentum_7d_score=t.momentum_7d_score,
        momentum_30d_score=t.momentum_30d_score,
    )


def _topics(db: Session, asset_type: str | None = None) -> list[mi.TopicIntelligence]:
    topics = mi.all_topics(db)
    if asset_type:
        topics = [t for t in topics if t.asset_type == asset_type]
    return topics


@router.get("/overview", response_model=MarketIntelligenceOverview)
def overview(db: Annotated[Session, Depends(get_db)]):
    data = mi.overview(db)
    topics = mi.all_topics(db)
    image_topics = [t for t in topics if t.asset_type == "image"]
    video_topics = [t for t in topics if t.asset_type == "video"]
    return MarketIntelligenceOverview(
        generated_at=data["generated_at"],
        last_data_update=data["last_data_update"],
        topic_count=data["topic_count"],
        top_categories=[
            CategoryIntelOut(
                name=c.name,
                slug=c.slug,
                signal_7d=c.signal_7d,
                signal_30d=c.signal_30d,
                momentum=c.momentum,
                trend_signal=c.trend_signal,
                frequency=c.frequency,
                topic_count=c.topic_count,
                sources=list(c.sources),
                last_updated=c.last_updated,
                provenance=c.provenance,
            )
            for c in data["top_categories"]
        ],
        top_image_topics=[_topic_out(t) for t in image_topics[:5]],
        top_video_topics=[_topic_out(t) for t in video_topics[:5]],
        top_keywords=[
            KeywordIntelOut(
                keyword=k.keyword,
                frequency=k.frequency,
                movement_7d=k.movement_7d,
                movement_30d=k.movement_30d,
                related_category=k.related_category,
                related_image_topics=list(k.related_image_topics),
                related_video_topics=list(k.related_video_topics),
                source=k.source,
            )
            for k in data["top_keywords"]
        ],
        rising_now=[_mover_out(t) for t in data["rising_now"]],
        declining_now=[_mover_out(t) for t in data["declining_now"]],
        window_comparison=[_comparison_out(t) for t in data["window_comparison"]],
    )


@router.get("/categories", response_model=Page[CategoryIntelOut])
def categories(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[dict, Depends(pagination_params)],
):
    cats = mi.top_categories(db, mi.all_topics(db), limit=100)
    items = [
        CategoryIntelOut(
            name=c.name,
            slug=c.slug,
            signal_7d=c.signal_7d,
            signal_30d=c.signal_30d,
            momentum=c.momentum,
            trend_signal=c.trend_signal,
            frequency=c.frequency,
            topic_count=c.topic_count,
            sources=list(c.sources),
            last_updated=c.last_updated,
            provenance=c.provenance,
        )
        for c in cats
    ]
    page, page_size = paging["page"], paging["page_size"]
    return paginate(items[(page - 1) * page_size : page * page_size], page=page,
                    page_size=page_size, total=len(items))


@router.get("/image-topics", response_model=Page[TopicIntelOut])
def image_topics(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[dict, Depends(pagination_params)],
    momentum: Annotated[str | None, Query(pattern="^(STRONGLY_RISING|RISING|STABLE|DECLINING|STRONGLY_DECLINING)$")] = None,
):
    topics = _topics(db, "image")
    if momentum:
        topics = [t for t in topics if t.momentum == momentum]
    items = [_topic_out(t) for t in topics]
    page, page_size = paging["page"], paging["page_size"]
    return paginate(items[(page - 1) * page_size : page * page_size], page=page,
                    page_size=page_size, total=len(items))


@router.get("/video-topics", response_model=Page[TopicIntelOut])
def video_topics(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[dict, Depends(pagination_params)],
    momentum: Annotated[str | None, Query(pattern="^(STRONGLY_RISING|RISING|STABLE|DECLINING|STRONGLY_DECLINING)$")] = None,
):
    topics = _topics(db, "video")
    if momentum:
        topics = [t for t in topics if t.momentum == momentum]
    items = [_topic_out(t) for t in topics]
    page, page_size = paging["page"], paging["page_size"]
    return paginate(items[(page - 1) * page_size : page * page_size], page=page,
                    page_size=page_size, total=len(items))


@router.get("/keywords", response_model=Page[KeywordIntelOut])
def keywords(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[dict, Depends(pagination_params)],
):
    kws = mi.top_keywords(db, mi.all_topics(db), limit=200)
    items = [
        KeywordIntelOut(
            keyword=k.keyword,
            frequency=k.frequency,
            movement_7d=k.movement_7d,
            movement_30d=k.movement_30d,
            related_category=k.related_category,
            related_image_topics=list(k.related_image_topics),
            related_video_topics=list(k.related_video_topics),
            source=k.source,
        )
        for k in kws
    ]
    page, page_size = paging["page"], paging["page_size"]
    return paginate(items[(page - 1) * page_size : page * page_size], page=page,
                    page_size=page_size, total=len(items))
