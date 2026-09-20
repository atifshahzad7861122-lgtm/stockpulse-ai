"""Market intelligence engine — FINAL MASTER SPEC §10–17.

Aggregates REAL collected data into:
- top categories
- top image topics / top video topics
- top keywords
- rising / declining trends
- 7-day vs 30-day comparison with momentum

All scores are 0–100 and explainable (factor math lives in engines.scoring /
engines.trends). Every insight carries provenance (source, data type,
collected time, window). MOCK rows are excluded unless dev mode is on.
Historical observations are never overwritten — this engine is read-only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.engines.scoring import norm100, trend_score
from app.engines.trends import (
    classify_momentum,
    compare_7d_30d,
    monthly_velocity,
    signal_band,
    trend_velocity,
    search_growth,
    keyword_momentum,
)
from app.models.intelligence import TrendSignal, TrendSnapshot, TrendSource
from app.models.taxonomy import Category, MicroNiche, Subcategory
from app.schemas.enums import DataProvenance, SignalKind
from app.services.dev_mode import is_dev_mode

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SNAPSHOT_SCAN_LIMIT = 500
SIGNAL_LOOKBACK_DAYS = 60
MIN_SIGNALS_PER_WINDOW = 2

_VIDEO_HINTS = (
    "video", "footage", "b-roll", "broll", "motion", "clip", "reel",
    "cinematic", "timelapse", "aerial video",
)
_IMAGE_HINTS = (
    "image", "photo", "illustration", "vector", "graphic", "portrait",
    "landscape", "mockup", "still",
)

_STOPWORDS = frozenset(
    "the a an and or of to in on for with by from as at is are was were be "
    "this that these those it its stock adobe new top best how why what who "
    "vs via per".split()
)


# ---------------------------------------------------------------------------
# Dataclasses (engine-internal; routers map them to pydantic schemas)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TopicIntelligence:
    topic: str
    category: str | None
    asset_type: str  # "image" | "video"
    velocity_7d: float
    velocity_30d: float | None
    momentum_7d: str
    momentum_30d: str | None
    momentum: str
    signal_7d: str
    signal_30d: str | None
    trend_signal: float  # 0-100, the 7D composite (canonical trend score)
    momentum_7d_score: float
    momentum_30d_score: float | None
    opportunity_signal: float  # 0-100 optional composite
    frequency: int
    keywords: tuple[str, ...]
    sources: tuple[str, ...]
    signal_kind: str
    provenance: str
    last_updated: str | None
    explanation: str


@dataclass(frozen=True)
class CategoryIntelligence:
    name: str
    slug: str
    signal_7d: str
    signal_30d: str
    momentum: str
    trend_signal: float
    frequency: int
    topic_count: int
    sources: tuple[str, ...]
    last_updated: str | None
    provenance: str


@dataclass(frozen=True)
class KeywordIntelligence:
    keyword: str
    frequency: int
    movement_7d: str
    movement_30d: str
    related_category: str | None
    related_image_topics: tuple[str, ...]
    related_video_topics: tuple[str, ...]
    source: str | None


# ---------------------------------------------------------------------------
# Signal-kind labeling (spec §8 — never call it "sales" unless the source
# genuinely provides sales figures)
# ---------------------------------------------------------------------------


def signal_kind_for(metric_name: str | None) -> SignalKind:
    name = (metric_name or "").lower()
    if "sale" in name or "earning" in name or "revenue" in name:
        return SignalKind.SALES
    if "download" in name:
        return SignalKind.DOWNLOADS
    if "search" in name:
        return SignalKind.SEARCH_SIGNAL
    if "popular" in name:
        return SignalKind.POPULARITY_SIGNAL
    if "trend" in name:
        return SignalKind.TREND_SIGNAL
    if "estimat" in name:
        return SignalKind.ESTIMATED_SIGNAL
    if "demand" in name:
        return SignalKind.PUBLIC_DEMAND_SIGNAL
    return SignalKind.PUBLIC_DEMAND_SIGNAL


def asset_type_for(topic: str, signal_texts: list[str]) -> str:
    """Heuristic image/video classification from topic + signal text.

    Deterministic and explainable; defaults to "image" (stills dominate stock
    demand) when neither side has evidence.
    """
    text = (topic + " " + " ".join(signal_texts)).lower()
    video_hits = sum(1 for h in _VIDEO_HINTS if h in text)
    image_hits = sum(1 for h in _IMAGE_HINTS if h in text)
    if video_hits > image_hits:
        return "video"
    return "image"


# ---------------------------------------------------------------------------
# Topic aggregation
# ---------------------------------------------------------------------------


def _snapshot_topics(db: Session) -> dict[str, dict]:
    """Latest snapshot payload per topic (payloads carry the canonical 7D
    window values written by the trend providers)."""
    rows = (
        db.query(TrendSnapshot)
        .order_by(TrendSnapshot.captured_at.desc())
        .limit(SNAPSHOT_SCAN_LIMIT)
        .all()
    )
    latest: dict[str, dict] = {}
    for s in rows:
        payload = s.payload or {}
        topic = payload.get("topic")
        if topic and topic not in latest:
            latest[topic] = {
                "snapshot": s,
                "payload": payload,
                "captured_at": s.captured_at,
            }
    return latest


def _signals_by_topic(db: Session, snapshot_topics: dict[str, dict]) -> dict[str, list]:
    """TrendSignal rows from the trailing SIGNAL_LOOKBACK_DAYS, keyed by topic
    via their snapshot's payload topic."""
    cutoff = datetime.now(UTC) - timedelta(days=SIGNAL_LOOKBACK_DAYS)
    snap_id_to_topic = {
        info["snapshot"].id: topic for topic, info in snapshot_topics.items()
    }
    rows = (
        db.query(TrendSignal)
        .filter(TrendSignal.observed_at >= cutoff)
        .order_by(TrendSignal.observed_at.desc())
        .limit(5000)
        .all()
    )
    by_topic: dict[str, list] = {}
    for r in rows:
        topic = snap_id_to_topic.get(r.trend_snapshot_id or "")
        if not topic:
            continue
        by_topic.setdefault(topic, []).append(r)
    return by_topic


def _source_name(db: Session, source_id: str | None) -> str | None:
    if not source_id:
        return None
    src = db.query(TrendSource).filter_by(id=source_id).one_or_none()
    return src.name if src else None


def _categories_for(db: Session, topic: str) -> list[str]:
    niche = db.query(MicroNiche).filter(MicroNiche.name == topic).one_or_none()
    if niche is None:
        return []
    sub = db.query(Subcategory).filter_by(id=niche.subcategory_id).one_or_none()
    if sub is None:
        return []
    cat = db.query(Category).filter_by(id=sub.category_id).one_or_none()
    return [cat.slug] if cat else []


def _naive(dt: datetime | None) -> datetime | None:
    """Strip tzinfo: SQLite returns naive datetimes while collectors write
    aware ones. Comparing the two raises TypeError."""
    return dt.replace(tzinfo=None) if dt is not None else None


def _window_mean(signals: list, start: datetime, end: datetime) -> tuple[float, int]:
    vals = [
        float(s.metric_value)
        for s in signals
        if s.metric_value is not None
        and (obs := _naive(s.observed_at)) is not None
        and start.replace(tzinfo=None) <= obs < end.replace(tzinfo=None)
    ]
    if not vals:
        return 0.0, 0
    return sum(vals) / len(vals), len(vals)


def _score_7d_from_payload(payload: dict) -> tuple[float, float]:
    """Canonical 7D trend score + velocity from a snapshot payload."""
    w0 = float(payload.get("w0_mean", 0) or 0)
    w1 = float(payload.get("w1_mean", 0) or 0)
    baseline = float(payload.get("baseline_mean", 0) or 1)
    tv = trend_velocity(w0, w1)
    score = trend_score(
        tv_100=norm100(tv, -1, 3),
        sg_100=norm100(search_growth(w0, baseline), -1, 3),
        km_100=norm100(keyword_momentum(list(payload.get("keyword_tvs", []))), -1, 3),
        eg_100=50.0,
        seasonality=float(payload.get("seasonal_event_strength", 0.4)),
    ).score
    return float(score), tv


def _topic_keywords(signals: list, payload: dict, limit: int = 8) -> tuple[str, ...]:
    counts: dict[str, int] = {}
    texts: list[str] = []
    for s in signals:
        if s.signal_name:
            texts.append(s.signal_name)
        if s.description:
            texts.append(s.description)
    pk = payload.get("keywords")
    if isinstance(pk, list):
        texts.extend(str(k) for k in pk)
    for text in texts:
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", text.lower()):
            if token not in _STOPWORDS:
                counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return tuple(k for k, _ in ranked[:limit])


def topic_intelligence(
    db: Session,
    topic: str,
    snapshot_info: dict | None,
    signals: list,
    source_names: dict[str, str | None],
) -> TopicIntelligence | None:
    """Build the full 7D/30D intelligence record for one topic.

    Returns None when there is no usable real data for the topic.
    """
    now = datetime.now(UTC)
    payload = (snapshot_info or {}).get("payload", {}) or {}
    prov_raw = payload.get("provenance")
    try:
        provenance = DataProvenance(prov_raw) if prov_raw else DataProvenance.MOCK
    except ValueError:
        provenance = DataProvenance.MOCK
    if provenance == DataProvenance.MOCK and not is_dev_mode(db):
        return None

    # --- 7D: canonical payload values when present, else signal windows ---
    if payload.get("w0_mean") is not None:
        score7, tv7 = _score_7d_from_payload(payload)
    else:
        w0, n0 = _window_mean(signals, now - timedelta(days=7), now)
        w1, n1 = _window_mean(signals, now - timedelta(days=14), now - timedelta(days=7))
        if n0 < MIN_SIGNALS_PER_WINDOW or n1 < MIN_SIGNALS_PER_WINDOW:
            return None
        tv7 = trend_velocity(w0, w1)
        score7 = float(norm100(tv7, -1, 3))
    momentum_7d = classify_momentum(tv7)

    # --- 30D: signal windows (trailing 60 days) ---
    m0, n0 = _window_mean(signals, now - timedelta(days=30), now)
    m1, n1 = _window_mean(signals, now - timedelta(days=60), now - timedelta(days=30))
    tv30: float | None = None
    score30: float | None = None
    momentum_30d: str | None = None
    band30: str | None = None
    if n0 >= MIN_SIGNALS_PER_WINDOW and n1 >= MIN_SIGNALS_PER_WINDOW:
        tv30 = monthly_velocity(m0, m1)
        score30 = float(norm100(tv30, -1, 3))
        momentum_30d = classify_momentum(tv30)
        band30 = signal_band(score30)

    if tv30 is None:
        comparison_momentum = momentum_7d
        comparison_note = "30-day window has insufficient signal history — 7D only."
    else:
        comparison = compare_7d_30d(topic, tv7, tv30, score7, score30 or 0.0)
        comparison_momentum = comparison.momentum
        comparison_note = comparison.explanation

    signal_texts = [(s.signal_name or "") + " " + (s.description or "") for s in signals]
    metric_names = [s.metric_name for s in signals if s.metric_name]
    dominant_metric = max(set(metric_names), key=metric_names.count) if metric_names else None

    cats = _categories_for(db, topic)
    keywords = _topic_keywords(signals, payload)
    # Source attribution: the snapshot's registered source name.
    src_name = source_names.get(
        snapshot_info["snapshot"].trend_source_id if snapshot_info else "", None
    )
    sources = tuple(s for s in [src_name] if s)

    last_times = [_naive(s.observed_at) for s in signals]
    if snapshot_info and snapshot_info.get("captured_at"):
        last_times.append(_naive(snapshot_info["captured_at"]))
    last_times = [t for t in last_times if t is not None]
    last_updated = max(last_times).isoformat() if last_times else None

    momentum_7d_score = float(norm100(tv7, -1, 3))
    momentum_30d_score = float(norm100(tv30, -1, 3)) if tv30 is not None else None
    opportunity_signal = round(0.6 * score7 + 0.4 * momentum_7d_score, 1)

    explanation = (
        f"{topic}: 7D signal {signal_band(score7)} ({score7:.0f}/100, "
        f"velocity {tv7:+.2f} {momentum_7d.lower().replace('_', ' ')}). "
        + comparison_note
    )
    return TopicIntelligence(
        topic=topic,
        category=cats[0] if cats else None,
        asset_type=asset_type_for(topic, signal_texts),
        velocity_7d=round(tv7, 3),
        velocity_30d=round(tv30, 3) if tv30 is not None else None,
        momentum_7d=momentum_7d,
        momentum_30d=momentum_30d,
        momentum=comparison_momentum,
        signal_7d=signal_band(score7),
        signal_30d=band30,
        trend_signal=round(score7, 1),
        momentum_7d_score=round(momentum_7d_score, 1),
        momentum_30d_score=round(momentum_30d_score, 1) if momentum_30d_score is not None else None,
        opportunity_signal=opportunity_signal,
        frequency=len(signals),
        keywords=keywords,
        sources=sources,
        signal_kind=signal_kind_for(dominant_metric).value,
        provenance=provenance.value,
        last_updated=last_updated,
        explanation=explanation,
    )


# ---------------------------------------------------------------------------
# Aggregation across topics
# ---------------------------------------------------------------------------


def all_topics(db: Session) -> list[TopicIntelligence]:
    """Every topic with usable real data, sorted by 7D trend signal desc."""
    snapshot_topics = _snapshot_topics(db)
    signals_by_topic = _signals_by_topic(db, snapshot_topics)
    source_names = {
        sid: _source_name(db, sid)
        for sid in {info["snapshot"].trend_source_id for info in snapshot_topics.values()}
    }
    topics = set(snapshot_topics) | set(signals_by_topic)
    out: list[TopicIntelligence] = []
    for topic in topics:
        info = snapshot_topics.get(topic)
        ti = topic_intelligence(db, topic, info, signals_by_topic.get(topic, []), source_names)
        if ti is not None:
            out.append(ti)
    out.sort(key=lambda t: t.trend_signal, reverse=True)
    return out


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def top_categories(db: Session, topics: list[TopicIntelligence], limit: int = 5) -> list[CategoryIntelligence]:
    grouped: dict[str, list[TopicIntelligence]] = {}
    for t in topics:
        if t.category:
            grouped.setdefault(t.category, []).append(t)
    out: list[CategoryIntelligence] = []
    for slug, ts in grouped.items():
        cat = db.query(Category).filter_by(slug=slug).one_or_none()
        name = cat.name if cat else slug
        score7 = _mean([t.trend_signal for t in ts])
        s30_vals = [t.momentum_30d_score for t in ts if t.momentum_30d_score is not None]
        score30 = _mean(s30_vals) if s30_vals else score7
        # Category momentum: classify the mean 7D velocity of its topics.
        mom = classify_momentum(_mean([t.velocity_7d for t in ts]))
        provs = {t.provenance for t in ts}
        provenance = next(iter(provs)) if len(provs) == 1 else "THIRD_PARTY"
        lasts = [t.last_updated for t in ts if t.last_updated]
        out.append(CategoryIntelligence(
            name=name,
            slug=slug,
            signal_7d=signal_band(score7),
            signal_30d=signal_band(score30),
            momentum=mom,
            trend_signal=round(score7, 1),
            frequency=sum(t.frequency for t in ts),
            topic_count=len(ts),
            sources=tuple(sorted({s for t in ts for s in t.sources})),
            last_updated=max(lasts) if lasts else None,
            provenance=provenance,
        ))
    out.sort(key=lambda c: c.trend_signal, reverse=True)
    return out[:limit]


def top_keywords(db: Session, topics: list[TopicIntelligence], limit: int = 10) -> list[KeywordIntelligence]:
    """Keyword frequency + 7D/30D movement from topic keyword sets.

    Movement is derived from how the keyword's carrying topics move: a
    keyword "moves" with the mean velocity of topics that carry it.
    """
    from collections import defaultdict
    carrying: dict[str, list[TopicIntelligence]] = defaultdict(list)
    for t in topics:
        for kw in t.keywords:
            carrying[kw].append(t)
    out: list[KeywordIntelligence] = []
    for kw, ts in carrying.items():
        freq = len(ts)
        v7 = _mean([t.velocity_7d for t in ts])
        v30_vals = [t.velocity_30d for t in ts if t.velocity_30d is not None]
        v30 = _mean(v30_vals) if v30_vals else None
        cats = [t.category for t in ts if t.category]
        related_cat = max(set(cats), key=cats.count) if cats else None
        img = tuple(sorted({t.topic for t in ts if t.asset_type == "image"})[:5])
        vid = tuple(sorted({t.topic for t in ts if t.asset_type == "video"})[:5])
        srcs = [s for t in ts for s in t.sources]
        out.append(KeywordIntelligence(
            keyword=kw,
            frequency=freq,
            movement_7d=classify_momentum(v7),
            movement_30d=classify_momentum(v30) if v30 is not None else "STABLE",
            related_category=related_cat,
            related_image_topics=img,
            related_video_topics=vid,
            source=max(set(srcs), key=srcs.count) if srcs else None,
        ))
    out.sort(key=lambda k: (-k.frequency, k.keyword))
    return out[:limit]


def rising_topics(topics: list[TopicIntelligence], limit: int = 8) -> list[TopicIntelligence]:
    return [t for t in topics if t.momentum in ("RISING", "STRONGLY_RISING")][:limit]


def declining_topics(topics: list[TopicIntelligence], limit: int = 8) -> list[TopicIntelligence]:
    downs = [t for t in topics if t.momentum in ("DECLINING", "STRONGLY_DECLINING")]
    downs.sort(key=lambda t: t.trend_signal)
    return downs[:limit]


def last_data_update(db: Session) -> str | None:
    """Timestamp of the most recent REAL data update.

    Derived from the topics' last_updated values (which already exclude MOCK
    rows outside dev mode), so a database containing only demo/seed rows
    honestly reports None instead of a fake "update" time.
    """
    lasts = [t.last_updated for t in all_topics(db) if t.last_updated]
    return max(lasts) if lasts else None


def overview(db: Session) -> dict:
    """Full dashboard payload (spec §18): everything the main dashboard shows."""
    topics = all_topics(db)
    image_topics = [t for t in topics if t.asset_type == "image"]
    video_topics = [t for t in topics if t.asset_type == "video"]
    lasts = [t.last_updated for t in topics if t.last_updated]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        # Real-data only: MOCK/demo rows honestly report "no update".
        "last_data_update": max(lasts) if lasts else None,
        "top_categories": top_categories(db, topics),
        "top_image_topics": image_topics[:5],
        "top_video_topics": video_topics[:5],
        "top_keywords": top_keywords(db, topics),
        "rising_now": rising_topics(topics),
        "declining_now": declining_topics(topics),
        "window_comparison": topics[:12],
        "topic_count": len(topics),
    }


def topic_monthly(db: Session, topic: str) -> tuple[float, float, int, int] | None:
    """(m0, m1, n0, n1) 30-day window means for the trends router.

    Returns None when the topic has no usable signal history.
    """
    snapshot_topics = _snapshot_topics(db)
    info = snapshot_topics.get(topic)
    if not info:
        return None
    signals_by_topic = _signals_by_topic(db, {topic: info})
    signals = signals_by_topic.get(topic, [])
    now = datetime.now(UTC)
    m0, n0 = _window_mean(signals, now - timedelta(days=30), now)
    m1, n1 = _window_mean(signals, now - timedelta(days=60), now - timedelta(days=30))
    if n0 < MIN_SIGNALS_PER_WINDOW or n1 < MIN_SIGNALS_PER_WINDOW:
        return None
    return m0, m1, n0, n1
