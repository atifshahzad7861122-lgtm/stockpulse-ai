"""Personal Fit Score data assembly (Phase 2; extended to full spec in Phase 3).

Reads the append-only private tables (``app.models.private``) and computes the
Personal Fit Score via ``engines.opportunities.personal_fit_breakdown``. Every
private-model access is guarded: any failure returns None (honest "no private
data") instead of breaking the opportunities endpoints.

Phase 3 factors assembled here:
- category / keyword performance (Phase 2, kept)
- content-type performance: read from the sibling Phase 3
  ``PersonalContentTypeMetric`` table (``app.models.personal``) — real
  per-content-type private performance (image / video measured
  independently). Consumed read-only via the model; the sibling's file is
  never edited. The legacy ``asset`` component stays absent (private asset
  snapshots carry no asset_type and there is no reliable join key).
- theme performance: aggregated from the user's OWN asset titles
  (PrivateAssetPerformance.title) — a different data source than keywords.
- momentum: last-7d vs previous-7d downloads/earnings from PrivateDailyEarning.
- acceptance rate (Phase 2, kept), historical downloads/earnings totals.
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.engines.opportunities import PersonalFitResult, personal_fit_breakdown

_STOPWORDS = frozenset(
    "the a an and or of to in for on with as at by from is are was were be been "
    "this that these those it its you your we our they their he she his her "
    "free new best top how what why when where which who vs via per".split()
)


def _private_models():
    """Return the private models module, or None until it exists."""
    try:
        import app.models.private as pm

        return pm
    except ImportError:
        return None


def _category_slug(db: Session, micro_niche_id: str | None) -> str | None:
    if not micro_niche_id:
        return None
    try:
        from app.models.taxonomy import Category, MicroNiche, Subcategory

        niche = db.query(MicroNiche).filter_by(id=micro_niche_id).one_or_none()
        if niche is None:
            return None
        sub = db.query(Subcategory).filter_by(id=niche.subcategory_id).one_or_none()
        if sub is None:
            return None
        cat = db.query(Category).filter_by(id=sub.category_id).one_or_none()
        return cat.slug if cat else None
    except Exception:
        return None


def _latest_snapshot_rows(db: Session, model, date_col: str) -> list[Any]:
    """Rows from the most recent snapshot_date of an append-only perf table."""
    try:
        latest = db.query(func.max(getattr(model, date_col))).scalar()
        if latest is None:
            return []
        return db.query(model).filter(getattr(model, date_col) == latest).all()
    except Exception:
        return []


def _category_performance(db: Session, pm) -> dict[str, dict[str, float]]:
    rows = _latest_snapshot_rows(db, pm.PrivateCategoryPerformance, "snapshot_date")
    out: dict[str, dict[str, float]] = {}
    for r in rows:
        name = getattr(r, "category", None)
        if not name:
            continue
        out[str(name)] = {
            "downloads": float(getattr(r, "downloads", 0) or 0),
            "earnings": float(getattr(r, "earnings", 0) or 0),
        }
    return out


def _keyword_performance(db: Session, pm) -> dict[str, dict[str, float]]:
    rows = _latest_snapshot_rows(db, pm.PrivateKeywordPerformance, "snapshot_date")
    out: dict[str, dict[str, float]] = {}
    for r in rows:
        kw = getattr(r, "keyword", None)
        if not kw:
            continue
        out[str(kw)] = {
            "downloads": float(getattr(r, "downloads", 0) or 0),
            "earnings": float(getattr(r, "earnings", 0) or 0),
        }
    return out


def _acceptance_rate(db: Session, pm) -> float | None:
    try:
        accepted = (
            db.query(func.count())
            .select_from(pm.PrivateSubmissionResult)
            .filter(pm.PrivateSubmissionResult.status == "ACCEPTED")
            .scalar()
            or 0
        )
        rejected = (
            db.query(func.count())
            .select_from(pm.PrivateSubmissionResult)
            .filter(pm.PrivateSubmissionResult.status == "REJECTED")
            .scalar()
            or 0
        )
    except Exception:
        return None
    total = accepted + rejected
    return (accepted / total) if total else None


def _content_type_performance(db: Session) -> dict[str, dict[str, float]]:
    """Per-content-type performance from the sibling Phase 3 personal tables.

    Reads the latest ``PersonalContentTypeMetric`` rows (``app.models.personal``)
    — real private performance measured per content type. Images and videos are
    consumed independently, exactly as the sibling measures them; the
    ``"unknown"`` bucket is skipped (never used as a proxy). Keys are
    upper-cased to match the engine's format normalization. Returns {} when the
    sibling table is empty or unreadable — the engine then skips the component.
    """
    try:
        from app.models.personal import PersonalContentTypeMetric

        rows = (
            db.query(PersonalContentTypeMetric)
            .order_by(PersonalContentTypeMetric.created_at.desc())
            .all()
        )
    except Exception:
        return {}
    out: dict[str, dict[str, float]] = {}
    for r in rows:
        ctype = str(getattr(r, "content_type", "") or "").strip().upper()
        if ctype not in ("IMAGE", "VIDEO") or ctype in out:
            continue
        out[ctype] = {
            "downloads": float(getattr(r, "downloads", 0) or 0),
            "earnings": float(getattr(r, "earnings", 0) or 0),
        }
    return out


def _opportunity_keywords(title: str, summary: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", f"{title} {summary}".lower())
    seen: list[str] = []
    for w in words:
        if len(w) >= 4 and w not in _STOPWORDS and w not in seen:
            seen.append(w)
    return seen[:20]


def _micro_niche_name(db: Session, micro_niche_id: str | None) -> str | None:
    if not micro_niche_id:
        return None
    try:
        from app.models.taxonomy import MicroNiche

        niche = db.query(MicroNiche).filter_by(id=micro_niche_id).one_or_none()
        return niche.name if niche else None
    except Exception:
        return None


def _theme_performance(db: Session, pm) -> dict[str, dict[str, float]]:
    """Theme performance from the user's OWN asset titles.

    Tokenizes the latest PrivateAssetPerformance titles and aggregates
    downloads/earnings per token. This is a genuinely different signal from
    keyword performance (which comes from Adobe keyword stats): it answers
    "what have I actually produced about X, and how did it do?".
    """
    rows = _latest_snapshot_rows(db, pm.PrivateAssetPerformance, "snapshot_date")
    agg: dict[str, dict[str, float]] = {}
    for r in rows:
        title = getattr(r, "title", None)
        if not title:
            continue
        downloads = float(getattr(r, "downloads_total", 0) or 0)
        earnings = float(getattr(r, "earnings_total", 0) or 0)
        for token in _opportunity_keywords(str(title), ""):
            entry = agg.setdefault(token, {"downloads": 0.0, "earnings": 0.0})
            entry["downloads"] += downloads
            entry["earnings"] += earnings
    return agg


def _momentum_windows(db: Session, pm) -> dict[str, dict[str, float]] | None:
    """Last-7d vs previous-7d downloads/earnings from PrivateDailyEarning.

    Returns {"downloads": {"current_7d": x, "prev_7d": y},
             "earnings": {...}} or None when the table is empty.
    """
    try:
        latest = db.query(func.max(pm.PrivateDailyEarning.date)).scalar()
        if latest is None:
            return None
        cur_start = latest - timedelta(days=6)
        prev_start = latest - timedelta(days=13)
        prev_end = latest - timedelta(days=7)

        def _sums(start, end):
            rows = (
                db.query(
                    func.coalesce(func.sum(pm.PrivateDailyEarning.downloads), 0),
                    func.coalesce(func.sum(pm.PrivateDailyEarning.earnings), 0),
                )
                .filter(
                    pm.PrivateDailyEarning.date >= start,
                    pm.PrivateDailyEarning.date <= end,
                )
                .one()
            )
            return float(rows[0] or 0), float(rows[1] or 0)

        cur_dl, cur_earn = _sums(cur_start, latest)
        prev_dl, prev_earn = _sums(prev_start, prev_end)
        if cur_dl == 0 and cur_earn == 0 and prev_dl == 0 and prev_earn == 0:
            return None
        return {
            "downloads": {"current_7d": cur_dl, "prev_7d": prev_dl},
            "earnings": {"current_7d": cur_earn, "prev_7d": prev_earn},
        }
    except Exception:
        return None


def _historical_totals(db: Session, pm) -> tuple[float | None, float | None]:
    """Lifetime (downloads, earnings) totals — track-record depth inputs.

    PrivateDailyEarning first; falls back to latest PrivateAssetPerformance
    snapshot totals; (None, None) when neither table has rows.
    """
    try:
        row = (
            db.query(
                func.coalesce(func.sum(pm.PrivateDailyEarning.downloads), 0),
                func.coalesce(func.sum(pm.PrivateDailyEarning.earnings), 0),
            ).one()
        )
        if row and (float(row[0] or 0) > 0 or float(row[1] or 0) > 0):
            return float(row[0] or 0), float(row[1] or 0)
        perf_rows = _latest_snapshot_rows(db, pm.PrivateAssetPerformance, "snapshot_date")
        if perf_rows:
            dl = sum(float(getattr(r, "downloads_total", 0) or 0) for r in perf_rows)
            earn = sum(float(getattr(r, "earnings_total", 0) or 0) for r in perf_rows)
            if dl > 0 or earn > 0:
                return dl, earn
    except Exception:
        pass
    return None, None


def compute_personal_fit_breakdown(
    db: Session, *, micro_niche_id: str | None, title: str, summary: str
) -> PersonalFitResult | None:
    """Full-spec Personal Fit breakdown, or None when no private data exists."""
    pm = _private_models()
    if pm is None:
        return None
    try:
        niche_name = _micro_niche_name(db, micro_niche_id)
        themes = _opportunity_keywords(f"{niche_name or ''} {title or ''} {summary or ''}", "")
        hist_dl, hist_earn = _historical_totals(db, pm)
        return personal_fit_breakdown(
            opportunity_category=_category_slug(db, micro_niche_id),
            opportunity_keywords=tuple(_opportunity_keywords(title or "", summary or "")),
            opportunity_themes=tuple(themes),
            category_performance=_category_performance(db, pm),
            # The legacy asset component stays absent: private asset snapshots
            # carry no asset_type (PHASE2_DESIGN.md §3) and there is no reliable
            # join to production assets. Content-type performance now comes from
            # the sibling Phase 3 PersonalContentTypeMetric table (read-only).
            asset_type_performance=None,
            content_type_performance=_content_type_performance(db),
            keyword_performance=_keyword_performance(db, pm),
            theme_performance=_theme_performance(db, pm),
            momentum_windows=_momentum_windows(db, pm),
            overall_acceptance_rate=_acceptance_rate(db, pm),
            historical_downloads=hist_dl,
            historical_earnings=hist_earn,
        )
    except Exception:
        return None


def compute_personal_fit(
    db: Session, *, micro_niche_id: str | None, title: str, summary: str
) -> float | None:
    """0–100 Personal Fit Score, or None when there is no private data."""
    result = compute_personal_fit_breakdown(
        db, micro_niche_id=micro_niche_id, title=title, summary=summary
    )
    return result.score if result is not None else None


def personal_evidence_notes(result: PersonalFitResult) -> list[str]:
    """Factual evidence strings from a fit breakdown (for fusion explanations).

    Only describes components that had real private data — never invents.
    """
    notes: list[str] = []
    for name in ("category", "keyword", "theme", "content_type", "momentum", "acceptance"):
        value = result.components.get(name)
        if value is not None:
            notes.append(f"{name} component {value:.1f}/100 from your private performance data")
    return notes[:4]
