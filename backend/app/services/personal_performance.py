"""Personal Performance Engine (Phase 3, backend — Personal Intelligence).

Reads the user's OWN private data (app.models.private append-only tables) and
derives descriptive performance metrics: per-category, per content-type
(image vs video, measured independently), data-derived themes, per-keyword,
consistency, acceptance rate, and momentum windows.

Honesty contract (STOCKPULSE AI INTEGRITY BOUNDARIES):
- Adobe private data may be NOT_CONFIGURED (no rows). Every public function
  returns None (or an empty list) when its required private tables have no
  usable rows — never zeros disguised as data.
- MOCK-provenance rows are excluded from intelligence unless dev mode is on
  (app.services.dev_mode); then they drive metrics like any other rows.
- Theme labels are DERIVED from the user's titles/keywords by tokenization
  + co-occurrence (discover_themes), never hard-coded conclusions.
- Windows are anchored to the latest available data (``as_of``), not the wall
  clock, so stale data still yields correctly-labeled windows.
- No guarantees language: "opportunity/potential/confidence", never "will sell".
"""

from __future__ import annotations

import re
import statistics
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models import personal as pmodel
from app.models import private as pvm
from app.schemas.enums import DataProvenance, TrendLabel
from app.services.dev_mode import is_dev_mode

# ---------------------------------------------------------------------------
# Documented thresholds and formula versions
# ---------------------------------------------------------------------------

FORMULA_VERSION = "ppf-v1"

# Momentum: relative change of a window vs the equal-length window before it.
#   change > +15%  -> "growing"
#   change < -15%  -> "declining"
#   otherwise      -> "stable"
# Either window missing usable data -> no label (None), never a guess.
MOMENTUM_GROWING_MIN = 0.15
MOMENTUM_DECLINING_MAX = -0.15

MOMENTUM_WINDOWS = (7, 30, 90)

# Consistency: weekly earnings over the trailing CONSISTENCY_WEEKS weeks.
# score = 100 * (1 - CV), clamped to [0, 100], where CV = stdev/mean of weekly
# earnings. 100 = perfectly stable; 0 = wild swings (CV >= 1). Requires
# MIN_CONSISTENCY_WEEKS weeks with data, else the score is unavailable.
CONSISTENCY_WEEKS = 12
MIN_CONSISTENCY_WEEKS = 4

# Theme discovery: tokens must appear in at least MIN_THEME_ASSETS distinct
# asset titles to become a theme (co-occurrence, not one-offs).
TOKEN_MIN_LEN = 3
MIN_THEME_ASSETS = 2
MAX_THEMES = 8

_STOPWORDS = frozenset(
    "the a an and or of to in for on with as at by from is are was were be been "
    "this that these those it its you your we our they their he she his her "
    "free new best top how what why when where which who vs via per photo "
    "image video footage clip stock adobe".split()
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _dev_ok(db: Session) -> bool:
    return is_dev_mode(db)


def _usable(db: Session, model) -> list[Any]:
    """All rows of a private table, excluding MOCK unless dev mode is on."""
    rows = db.query(model).all()
    if _dev_ok(db):
        return rows
    return [r for r in rows if getattr(r, "data_provenance", None) != DataProvenance.MOCK]


def _f(value) -> float | None:
    if value is None:
        return None
    return float(value)


def _snapshot_value(points: list[tuple[date, float]], on_or_before: date) -> float | None:
    """Last snapshot value at or before a date (cumulative as-of semantics)."""
    best = None
    for d, v in points:
        if d <= on_or_before and (best is None or d >= best[0]):
            best = (d, v)
    return best[1] if best is not None else None


def trend_for_change(change_pct: float | None) -> TrendLabel | None:
    """Documented threshold mapping; None stays None (never fabricates)."""
    if change_pct is None:
        return None
    if change_pct > MOMENTUM_GROWING_MIN * 100:
        return TrendLabel.GROWING
    if change_pct < MOMENTUM_DECLINING_MAX * 100:
        return TrendLabel.DECLINING
    return TrendLabel.STABLE


def window_momentum(current: float | None, previous: float | None) -> dict[str, Any]:
    """Momentum of one window vs the previous equal-length window.

    change_pct is a percentage (e.g. 23.5 = +23.5%). ``available`` is False
    whenever either window lacks usable data — the caller must not present
    zeros as data.
    """
    if current is None or previous is None or previous <= 0:
        return {
            "current": current,
            "previous": previous,
            "change_pct": None,
            "trend": None,
            "available": False,
        }
    change = (current - previous) / previous
    trend = trend_for_change(change * 100)
    return {
        "current": current,
        "previous": previous,
        "change_pct": round(change * 100, 2),
        "trend": trend.value if trend else None,
        "available": True,
    }


def _momentum_windows(
    value_at: "callable[[date], float | None]",
    as_of: date,
    *,
    delta: bool,
) -> dict[str, dict[str, Any]]:
    """Momentum for 7/30/90d windows from a point-in-time value function.

    ``delta=True`` treats the series as cumulative as-of snapshots: each
    window's figure is value(as_of) - value(window_start), so the momentum
    compares genuine period deltas, not cumulative levels.
    """
    out: dict[str, dict[str, Any]] = {}
    for w in MOMENTUM_WINDOWS:
        cur_end = as_of
        cur_start = as_of - timedelta(days=w)
        prev_start = as_of - timedelta(days=2 * w)
        cur_v = value_at(cur_end)
        cur_s = value_at(cur_start)
        prev_s = value_at(prev_start)
        if delta:
            cur = (cur_v - cur_s) if cur_v is not None and cur_s is not None else None
            prev = (cur_s - prev_s) if cur_s is not None and prev_s is not None else None
        else:
            cur, prev = cur_v, cur_s
        out[f"{w}d"] = window_momentum(cur, prev)
    return out


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


def availability(db: Session) -> dict[str, Any]:
    """Honest data-availability report across the private tables."""
    counts = {
        "daily_earnings": len(_usable(db, pvm.PrivateDailyEarning)),
        "downloads": len(_usable(db, pvm.PrivateDownload)),
        "sales": len(_usable(db, pvm.PrivateSale)),
        "asset_performance": len(_usable(db, pvm.PrivateAssetPerformance)),
        "submission_results": len(_usable(db, pvm.PrivateSubmissionResult)),
        "category_performance": len(_usable(db, pvm.PrivateCategoryPerformance)),
        "keyword_performance": len(_usable(db, pvm.PrivateKeywordPerformance)),
        "snapshots": len(_usable(db, pvm.PrivateSnapshot)),
    }
    return {
        "has_private_data": any(counts.values()),
        "dev_mode": _dev_ok(db),
        "table_rows": counts,
    }


# ---------------------------------------------------------------------------
# Overall summary
# ---------------------------------------------------------------------------


def compute_acceptance_rate(db: Session) -> dict[str, Any] | None:
    """Overall acceptance from PrivateSubmissionResult. None when no rows."""
    rows = _usable(db, pvm.PrivateSubmissionResult)
    if not rows:
        return None
    accepted = sum(1 for r in rows if (r.status or "").upper() == "ACCEPTED")
    rejected = sum(1 for r in rows if (r.status or "").upper() == "REJECTED")
    pending = len(rows) - accepted - rejected
    decided = accepted + rejected
    rate = round(accepted / decided, 4) if decided else None
    return {
        "accepted": accepted,
        "rejected": rejected,
        "pending": pending,
        "acceptance_rate": rate,
        "available": decided > 0,
    }


def compute_consistency_score(db: Session) -> dict[str, Any] | None:
    """Weekly-earnings stability 0-100 from the coefficient of variation.

    Needs MIN_CONSISTENCY_WEEKS weeks with data; otherwise None (honest).
    """
    rows = _usable(db, pvm.PrivateDailyEarning)
    if not rows:
        return None
    as_of = max(r.date for r in rows)
    weeks: list[float] = []
    for w in range(CONSISTENCY_WEEKS):
        w_end = as_of - timedelta(days=7 * w)
        w_start = w_end - timedelta(days=6)
        total = sum(_f(r.earnings) or 0.0 for r in rows if w_start <= r.date <= w_end)
        if any(w_start <= r.date <= w_end for r in rows):
            weeks.append(total)
    if len(weeks) < MIN_CONSISTENCY_WEEKS:
        return None
    mean = statistics.fmean(weeks)
    sd = statistics.pstdev(weeks)
    cv = (sd / mean) if mean > 0 else None
    score = round(max(0.0, min(1.0, 1 - cv)) * 100, 1) if cv is not None else None
    return {
        "score": score,
        "cv": round(cv, 4) if cv is not None else None,
        "weeks_with_data": len(weeks),
        "weekly_earnings": [round(x, 2) for x in weeks],
        "available": score is not None,
    }


def _daily_series(db: Session) -> tuple[list[pvm.PrivateDailyEarning], date | None]:
    rows = sorted(_usable(db, pvm.PrivateDailyEarning), key=lambda r: r.date)
    if not rows:
        return [], None
    return rows, rows[-1].date


def overall_summary(db: Session, period_days: int) -> dict[str, Any] | None:
    """Overall personal summary for the trailing period. None when no data."""
    avail = availability(db)
    if not avail["has_private_data"]:
        return None
    rows, as_of = _daily_series(db)
    if not rows or as_of is None:
        # PrivateDailyEarning may be absent while other tables exist; totals
        # then come from per-asset snapshots instead.
        start = None
        earnings_total = None
        downloads_total = None
        momentum = None
    else:
        start = as_of - timedelta(days=period_days - 1)
        in_period = [r for r in rows if r.date >= start]
        earnings_total = round(sum(_f(r.earnings) or 0.0 for r in in_period), 2)
        downloads_total = int(sum(r.downloads or 0 for r in in_period))

        def _window_sum(metric: str, end: date, days: int) -> tuple[float | None, bool]:
            lo = end - timedelta(days=days)
            vals = [r for r in rows if lo < r.date <= end]
            if not vals:
                return None, False
            total = (
                sum(_f(r.earnings) or 0.0 for r in vals)
                if metric == "earnings"
                else float(sum(r.downloads or 0 for r in vals))
            )
            return total, True

        momentum = {}
        for metric in ("earnings", "downloads"):
            momentum[metric] = {}
            for w in MOMENTUM_WINDOWS:
                cur, cur_ok = _window_sum(metric, as_of, w)
                prev, prev_ok = _window_sum(metric, as_of - timedelta(days=w), w)
                # Both windows must have data; a window with no rows is
                # unavailable rather than zero.
                momentum[metric][f"{w}d"] = window_momentum(
                    cur if cur_ok else None, prev if prev_ok else None
                )
    cats = compute_category_metrics(db, period_days) or []
    themes = discover_themes(db, period_days) or []
    acceptance = compute_acceptance_rate(db)
    consistency = compute_consistency_score(db)
    return {
        "available": True,
        "data_provenance": DataProvenance.USER_PROVIDED.value,
        "period_days": period_days,
        "period_start": start.isoformat() if start else None,
        "period_end": as_of.isoformat() if as_of else None,
        "earnings_total": earnings_total,
        "downloads_total": downloads_total,
        "momentum": momentum,
        "acceptance": acceptance,
        "consistency": consistency,
        "top_categories": sorted(
            cats, key=lambda c: (c["earnings"] or 0.0), reverse=True
        )[:5],
        "top_themes": sorted(
            themes, key=lambda t: (t["downloads"] or 0), reverse=True
        )[:5],
    }


# ---------------------------------------------------------------------------
# Per-category metrics
# ---------------------------------------------------------------------------


def compute_category_metrics(db: Session, period_days: int) -> list[dict[str, Any]] | None:
    """Per-category metrics from PrivateCategoryPerformance snapshots.

    Values are as-of snapshot semantics; momentum compares period deltas.
    accepted/rejected/acceptance_rate stay None: submission rows carry no
    category linkage, so per-category acceptance is not derivable.
    """
    rows = _usable(db, pvm.PrivateCategoryPerformance)
    if not rows:
        return None
    as_of = max(r.snapshot_date for r in rows)
    start = as_of - timedelta(days=period_days - 1)
    by_cat: dict[str, list[pvm.PrivateCategoryPerformance]] = {}
    for r in rows:
        by_cat.setdefault(r.category, []).append(r)

    out: list[dict[str, Any]] = []
    for category in sorted(by_cat):
        cat_rows = sorted(by_cat[category], key=lambda r: r.snapshot_date)
        in_period = [r for r in cat_rows if r.snapshot_date >= start]
        if not in_period:
            continue  # stale category: not presented for this period
        latest = in_period[-1]
        downloads = latest.downloads or 0
        earnings = _f(latest.earnings) or 0.0
        assets = latest.asset_count or 0
        dl_points = [(r.snapshot_date, float(r.downloads or 0)) for r in cat_rows]
        earn_points = [(r.snapshot_date, _f(r.earnings) or 0.0) for r in cat_rows]
        momentum = {
            "downloads": _momentum_windows(
                lambda d, _p=dl_points: _snapshot_value(_p, d), as_of, delta=True
            ),
            "earnings": _momentum_windows(
                lambda d, _p=earn_points: _snapshot_value(_p, d), as_of, delta=True
            ),
        }
        trend_30 = momentum["earnings"]["30d"]["trend"]
        out.append(
            {
                "available": True,
                "category": category,
                "period_days": period_days,
                "assets_total": assets or None,
                "assets_accepted": None,
                "assets_rejected": None,
                "downloads": downloads,
                "earnings": round(earnings, 2),
                "avg_downloads_per_asset": round(downloads / assets, 2) if assets else None,
                "avg_earnings_per_asset": round(earnings / assets, 2) if assets else None,
                "acceptance_rate": None,
                "momentum": momentum,
                "trend_label": trend_30,
            }
        )
    return out or None


# ---------------------------------------------------------------------------
# Per content-type metrics (image vs video, independently)
# ---------------------------------------------------------------------------

_CONTENT_TYPES = ("image", "video", "unknown")


def compute_content_type_metrics(
    db: Session,
    period_days: int,
    *,
    content_type_map: dict[str, str] | None = None,
) -> list[dict[str, Any]] | None:
    """Image vs video metrics, computed INDEPENDENTLY of each other.

    ``content_type_map`` classifies asset_external_id -> "image"|"video".
    Assets that cannot be classified honestly sit in "unknown" — never
    guessed. Image metrics never inform video metrics (separate aggregates).
    """
    mapping = {
        k: v.lower()
        for k, v in (content_type_map or {}).items()
        if isinstance(v, str) and v.lower() in ("image", "video")
    }
    perf_rows = _usable(db, pvm.PrivateAssetPerformance)
    sub_rows = _usable(db, pvm.PrivateSubmissionResult)
    if not perf_rows and not sub_rows:
        return None

    def classify(external_id: str | None) -> str:
        if external_id and external_id in mapping:
            return mapping[external_id]
        return "unknown"

    # Per-asset latest snapshot (as-of semantics).
    latest: dict[str, pvm.PrivateAssetPerformance] = {}
    for r in sorted(perf_rows, key=lambda x: x.snapshot_date):
        latest[r.asset_external_id] = r
    as_of = None
    if latest:
        as_of = max(r.snapshot_date for r in latest.values())

    buckets: dict[str, list[pvm.PrivateAssetPerformance]] = {t: [] for t in _CONTENT_TYPES}
    for ext_id, row in latest.items():
        buckets[classify(ext_id)].append(row)

    sub_buckets: dict[str, list[pvm.PrivateSubmissionResult]] = {t: [] for t in _CONTENT_TYPES}
    for r in sub_rows:
        sub_buckets[classify(r.asset_external_id)].append(r)

    out: list[dict[str, Any]] = []
    for ctype in _CONTENT_TYPES:
        prows = buckets[ctype]
        srows = sub_buckets[ctype]
        if not prows and not srows:
            continue
        assets = len(prows)
        downloads = int(sum(r.downloads_total or 0 for r in prows))
        earnings = round(sum(_f(r.earnings_total) or 0.0 for r in prows), 2)
        accepted = sum(1 for r in srows if (r.status or "").upper() == "ACCEPTED")
        rejected = sum(1 for r in srows if (r.status or "").upper() == "REJECTED")
        decided = accepted + rejected
        if as_of is not None and prows:
            by_asset: dict[str, list[tuple[date, float]]] = {}
            by_asset_e: dict[str, list[tuple[date, float]]] = {}
            for r in perf_rows:
                if classify(r.asset_external_id) != ctype:
                    continue
                by_asset.setdefault(r.asset_external_id, []).append(
                    (r.snapshot_date, float(r.downloads_total or 0))
                )
                by_asset_e.setdefault(r.asset_external_id, []).append(
                    (r.snapshot_date, _f(r.earnings_total) or 0.0)
                )

            def dl_at(d: date, _b=by_asset) -> float | None:
                vals = [_snapshot_value(pts, d) for pts in _b.values()]
                return sum(v for v in vals if v is not None) or None

            def earn_at(d: date, _b=by_asset_e) -> float | None:
                vals = [_snapshot_value(pts, d) for pts in _b.values()]
                return sum(v for v in vals if v is not None) or None

            momentum = {
                "downloads": _momentum_windows(dl_at, as_of, delta=True),
                "earnings": _momentum_windows(earn_at, as_of, delta=True),
            }
            trend_30 = momentum["earnings"]["30d"]["trend"]
        else:
            momentum = None
            trend_30 = None
        out.append(
            {
                "available": True,
                "content_type": ctype,
                "period_days": period_days,
                "assets_total": assets or None,
                "assets_accepted": accepted or None,
                "assets_rejected": rejected or None,
                "downloads": downloads,
                "earnings": earnings,
                "avg_downloads_per_asset": round(downloads / assets, 2) if assets else None,
                "avg_earnings_per_asset": round(earnings / assets, 2) if assets else None,
                "acceptance_rate": round(accepted / decided, 4) if decided else None,
                "momentum": momentum,
                "trend_label": trend_30,
            }
        )
    return out or None


# ---------------------------------------------------------------------------
# Theme discovery (data-derived, never hard-coded)
# ---------------------------------------------------------------------------


def _tokenize(text: str | None) -> list[str]:
    if not text:
        return []
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if len(t) >= TOKEN_MIN_LEN and t not in _STOPWORDS]


def discover_themes(
    db: Session, period_days: int, *, max_themes: int = MAX_THEMES
) -> list[dict[str, Any]] | None:
    """Derive content themes from the user's own titles/keywords.

    Algorithm (documented, deterministic):
    1. Take each asset's latest PrivateAssetPerformance snapshot; tokenize
       its title (lowercase, len>=3, stopword-removed).
    2. token -> set of assets whose title contains it. Tokens in fewer than
       MIN_THEME_ASSETS assets are dropped (co-occurrence, not one-offs).
    3. Rank tokens by total downloads of their assets; keep top max_themes.
    4. Evidence = top co-occurring tokens in the same titles + matching
       keywords from PrivateKeywordPerformance.
    5. Theme downloads/earnings = sums of member assets' latest totals;
       momentum via the same window machinery; trend_label from 30d downloads.
    """
    perf_rows = _usable(db, pvm.PrivateAssetPerformance)
    if not perf_rows:
        return None
    latest: dict[str, pvm.PrivateAssetPerformance] = {}
    for r in sorted(perf_rows, key=lambda x: x.snapshot_date):
        latest[r.asset_external_id] = r
    as_of = max(r.snapshot_date for r in latest.values())

    asset_tokens: dict[str, set[str]] = {
        ext: set(_tokenize(r.title)) for ext, r in latest.items()
    }
    token_assets: dict[str, set[str]] = {}
    for ext, toks in asset_tokens.items():
        for t in toks:
            token_assets.setdefault(t, set()).add(ext)
    token_assets = {t: a for t, a in token_assets.items() if len(a) >= MIN_THEME_ASSETS}
    if not token_assets:
        return []

    kw_rows = _usable(db, pvm.PrivateKeywordPerformance)
    kw_latest: dict[str, pvm.PrivateKeywordPerformance] = {}
    for r in sorted(kw_rows, key=lambda x: x.snapshot_date):
        kw_latest[r.keyword.lower()] = r

    def theme_totals(members: set[str]) -> tuple[int, float]:
        dl = sum(latest[m].downloads_total or 0 for m in members)
        er = round(sum(_f(latest[m].earnings_total) or 0.0 for m in members), 2)
        return dl, er

    ranked = sorted(
        token_assets.items(),
        key=lambda kv: theme_totals(kv[1])[0],
        reverse=True,
    )[:max_themes]

    out: list[dict[str, Any]] = []
    for token, members in ranked:
        # Co-occurring tokens: tokens that appear alongside in the same titles.
        co: dict[str, int] = {}
        for m in members:
            for t in asset_tokens[m]:
                if t != token:
                    co[t] = co.get(t, 0) + 1
        co_tokens = sorted(co, key=lambda t: (-co[t], t))[:5]
        kw_evidence = sorted(
            {r.keyword for k, r in kw_latest.items() if token in k or k in token}
        )[:5]
        downloads, earnings = theme_totals(members)
        by_asset = {
            m: [
                (r.snapshot_date, float(r.downloads_total or 0))
                for r in perf_rows
                if r.asset_external_id == m
            ]
            for m in members
        }

        def dl_at(d: date, _b=by_asset) -> float | None:
            vals = [_snapshot_value(pts, d) for pts in _b.values()]
            return sum(v for v in vals if v is not None) or None

        momentum = {"downloads": _momentum_windows(dl_at, as_of, delta=True)}
        out.append(
            {
                "available": True,
                "theme_label": token,
                "period_days": period_days,
                "asset_count": len(members),
                "downloads": downloads,
                "earnings": earnings,
                "evidence_keywords": co_tokens + kw_evidence,
                "momentum": momentum,
                "trend_label": momentum["downloads"]["30d"]["trend"],
            }
        )
    return out


# ---------------------------------------------------------------------------
# Per-keyword metrics
# ---------------------------------------------------------------------------


def compute_keyword_metrics(db: Session, period_days: int) -> list[dict[str, Any]] | None:
    """Per-keyword downloads/earnings from latest PrivateKeywordPerformance."""
    rows = _usable(db, pvm.PrivateKeywordPerformance)
    if not rows:
        return None
    latest: dict[str, pvm.PrivateKeywordPerformance] = {}
    for r in sorted(rows, key=lambda x: x.snapshot_date):
        latest[r.keyword] = r
    as_of = max(r.snapshot_date for r in latest.values())
    start = as_of - timedelta(days=period_days - 1)
    out = [
        {
            "available": True,
            "keyword": kw,
            "period_days": period_days,
            "downloads": r.downloads or 0,
            "earnings": round(_f(r.earnings) or 0.0, 2),
            "asset_count": None,  # private keyword rows carry no asset linkage
        }
        for kw, r in sorted(latest.items())
        if r.snapshot_date >= start
    ]
    return out or None


# ---------------------------------------------------------------------------
# Fit-score persistence (scores are computed by the Opportunity Fusion module)
# ---------------------------------------------------------------------------


def record_fit_score(
    db: Session,
    *,
    opportunity_id: str | None = None,
    micro_niche_id: str | None = None,
    score: float | None = None,
    components: dict[str, Any] | None = None,
    formula_version: str = FORMULA_VERSION,
) -> pmodel.PersonalFitScore:
    """Persist a personal-fit score with every component value.

    ``score`` may be None (honest "cannot compute from available data").
    """
    row = pmodel.PersonalFitScore(
        opportunity_id=opportunity_id,
        micro_niche_id=micro_niche_id,
        score=score,
        component_json=dict(components or {}),
        formula_version=formula_version,
    )
    db.add(row)
    db.flush()
    return row


def snapshot_period(db: Session, period_days: int) -> pmodel.PersonalPerformanceSnapshot | None:
    """Compute the overall summary and persist it as a snapshot row."""
    summary = overall_summary(db, period_days)
    if summary is None:
        return None
    row = pmodel.PersonalPerformanceSnapshot(
        period_days=period_days,
        period_start=date.fromisoformat(summary["period_start"])
        if summary["period_start"]
        else date.today(),
        period_end=date.fromisoformat(summary["period_end"])
        if summary["period_end"]
        else date.today(),
        metrics_json=summary,
    )
    db.add(row)
    db.flush()
    return row
