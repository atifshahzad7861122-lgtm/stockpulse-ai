"""Category taxonomy (CONTRACT.md §5.3). 39 verbatim categories; system-owned."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.api.deps import (
    get_db,
    not_found,
    paginate,
    pagination_params,
)
from app.models.intelligence import TrendSignal
from app.models.taxonomy import Category, MicroNiche, Subcategory
from app.schemas.categories import (
    TAXONOMY_VERSION,
    CategoryDetail,
    CategoryOut,
    MicroNicheOut,
    SubcategoryOut,
    TrendCoverage,
)
from app.schemas.common import Page

router = APIRouter(prefix="/categories", tags=["categories"])


def _coverage(db: Session, slug: str) -> TrendCoverage:
    signals = (
        db.query(TrendSignal)
        .filter(TrendSignal.signal_name.contains(slug.replace("-", " ")[:24]))
        .limit(50)
        .all()
    )
    if not signals:
        return TrendCoverage(signal_count=0, avg_score=None)
    values = [float(s.metric_value) for s in signals if s.metric_value is not None]
    return TrendCoverage(
        signal_count=len(signals),
        avg_score=round(sum(values) / len(values), 2) if values else None,
    )


def _micro_out(niche: MicroNiche) -> MicroNicheOut:
    return MicroNicheOut.model_validate(niche)


def _sub_out(sub: Subcategory) -> SubcategoryOut:
    return SubcategoryOut(
        **{
            k: getattr(sub, k)
            for k in SubcategoryOut.model_fields
            if k != "micro_niches" and hasattr(sub, k)
        },
        micro_niches=[_micro_out(n) for n in sub.micro_niches],
    )


@router.get("", response_model=Page[CategoryOut])
def list_categories(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[dict, Depends(pagination_params)],
    with_trend_coverage: bool = False,
    with_counts: bool = False,
):
    cats = db.query(Category).order_by(Category.sort_order).all()
    out = []
    for cat in cats:
        data = CategoryOut.model_validate(cat)
        data.taxonomy_version = TAXONOMY_VERSION
        out.append(data)
    page, page_size = paging["page"], paging["page_size"]
    return paginate(
        out[(page - 1) * page_size : page * page_size],
        page=page,
        page_size=page_size,
        total=len(out),
    )


@router.get("/{category_id}", response_model=CategoryDetail)
def category_detail(category_id: str, db: Annotated[Session, Depends(get_db)]):
    cat = (
        db.query(Category)
        .options(joinedload(Category.subcategories).joinedload(Subcategory.micro_niches))
        .filter(Category.id == category_id)
        .one_or_none()
    )
    if cat is None:
        cat = (
            db.query(Category)
            .options(joinedload(Category.subcategories).joinedload(Subcategory.micro_niches))
            .filter(Category.slug == category_id)
            .one_or_none()
        )
    if cat is None:
        raise not_found("CATEGORY_NOT_FOUND", f"Category {category_id} not found.")
    detail = CategoryDetail(
        **CategoryOut.model_validate(cat).model_dump(),
        subcategories=[_sub_out(s) for s in sorted(cat.subcategories, key=lambda s: s.sort_order)],
        trend_coverage=_coverage(db, cat.slug),
        saturation_notes="Commercial subcategory saturation is demo text; not real Adobe data.",
    )
    detail.taxonomy_version = TAXONOMY_VERSION
    return detail
