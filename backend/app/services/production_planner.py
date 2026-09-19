"""Daily Production Planner (Phase 3, backend only).

Builds a ranked "WHAT TO CREATE TODAY" list from scored opportunities:
- capacity comes from the user-editable settings key "production_capacity"
  (NEVER hard-coded Adobe submission limits),
- diversification penalizes repeats of category / micro-niche / asset type /
  composition in the current plan and in recent plans,
- image/video balance follows the configured targets,
- output is capped at max_daily_generation.

Recommendations need explicit user actions (approve/reject/edit/regenerate/
prioritize/archive). Approval creates a production_queue item in DISCOVERED
via LEGAL transitions only; HIGH_RISK compliance concepts block promotion.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.engines.queue import is_legal_transition, transition_error_message
from app.models.intelligence import Opportunity
from app.models.planning import ConceptVariation, DailyProductionPlan, ProductionRecommendation
from app.models.production import ProductionQueue
from app.models.settings import Setting
from app.schemas.enums import AssetType, DataProvenance, ProductionQueueStatus
from app.schemas.planning import CapacitySettings
from app.services.concepts import blockers_for_promotion

# Named constants — repetition penalties (diversification).
RECENT_PLAN_LOOKBACK_DAYS = 7
CATEGORY_REPEAT_PENALTY = 6.0
NICHE_REPEAT_PENALTY = 10.0
ASSET_TYPE_REPEAT_PENALTY = 4.0
COMPOSITION_REPEAT_PENALTY = 8.0

DEFAULT_CAPACITY = {
    "weekly_capacity": 20,
    "daily_target": 4,
    "image_target": 3,
    "video_target": 1,
    "max_daily_generation": 10,
    "priority_preference": "score",
}


def get_capacity(db: Session) -> CapacitySettings:
    """Capacity from the user-editable settings key, with sane defaults.

    Adobe submission limits are NEVER hard-coded — the user configures them
    here (or accepts the defaults).
    """
    row = db.query(Setting).filter_by(project_id=None, key="production_capacity").one_or_none()
    merged = dict(DEFAULT_CAPACITY)
    if row and isinstance(row.value, dict):
        inner = row.value.get("value", row.value)
        if isinstance(inner, dict):
            merged.update({k: v for k, v in inner.items() if k in merged})
    return CapacitySettings(**merged)


def _fused_score(db: Session, opportunity: Opportunity) -> tuple[float, str]:
    """Unified score: use the opportunity-fusion sibling's score when
    available, otherwise fall back to opportunity_score (defensive)."""
    try:
        from app.services import opportunity_fusion  # sibling module (Phase 3)

        scorer = getattr(opportunity_fusion, "fused_opportunity_score", None)
        if callable(scorer):
            return float(scorer(db, opportunity)), "fused"
    except ImportError:
        pass
    return float(opportunity.opportunity_score or 0.0), "opportunity_score"


def _personal_fit(db: Session, opportunity: Opportunity) -> float | None:
    """0–100 Personal Fit Score, or None when there is no private data."""
    try:
        from app.services.personal_fit import compute_personal_fit

        return compute_personal_fit(
            db,
            micro_niche_id=opportunity.micro_niche_id,
            title=opportunity.title or "",
            summary=opportunity.summary or "",
        )
    except Exception:
        return None


def _composition_key(opportunity: Opportunity) -> str:
    """Stable composition signature for diversification.

    Derived from the niche and the opportunity's own words — two
    recommendations sharing it are treated as the same composition family.
    """
    import re

    words = re.findall(
        r"[a-z0-9]+", f"{opportunity.title or ''} {opportunity.summary or ''}".lower()
    )
    stop = frozenset(
        "the a an and or of to in for on with as at by from is are was were be been "
        "this that these those it its free new best top commercial stock".split()
    )
    tokens = sorted({w for w in words if len(w) >= 4 and w not in stop})[:12]
    return "|".join(tokens)


def _recent_repetition_counts(db: Session, plan_date: date) -> dict[tuple[str, str], int]:
    """(dimension, value) → occurrence counts in recent plans (lookback days).

    Covers category, micro_niche, asset_type, composition — the dimensions
    the diversification penalty applies to.
    """
    from datetime import timedelta

    since = plan_date - timedelta(days=RECENT_PLAN_LOOKBACK_DAYS)
    counts: dict[tuple[str, str], int] = {}
    plans = (
        db.query(DailyProductionPlan)
        .filter(DailyProductionPlan.plan_date >= since, DailyProductionPlan.plan_date < plan_date)
        .all()
    )
    plan_ids = [p.id for p in plans]
    if not plan_ids:
        return counts
    recs = (
        db.query(ProductionRecommendation)
        .filter(
            ProductionRecommendation.plan_id.in_(plan_ids),
            ProductionRecommendation.status.in_(["recommended", "approved"]),
        )
        .all()
    )
    for r in recs:
        if r.category:
            counts[("category", r.category)] = counts.get(("category", r.category), 0) + 1
        if r.micro_niche_id:
            key = ("micro_niche", r.micro_niche_id)
            counts[key] = counts.get(key, 0) + 1
        key = ("asset_type", r.asset_type.value)
        counts[key] = counts.get(key, 0) + 1
        comp = (r.evidence_json or {}).get("composition_key")
        if comp:
            counts[("composition", comp)] = counts.get(("composition", comp), 0) + 1
    return counts


def build_plan(
    db: Session,
    plan_date: date | None = None,
    target_images: int | None = None,
    target_videos: int | None = None,
) -> DailyProductionPlan:
    """Build (or rebuild) the daily plan for `plan_date`.

    Ranked candidates come from the top fused/scored opportunities with a
    diversification penalty, balanced against the image/video targets and
    capped at max_daily_generation.
    """
    from app.models.taxonomy import Category, MicroNiche, Subcategory

    plan_date = plan_date or date.today()
    capacity = get_capacity(db)
    target_images = capacity.image_target if target_images is None else target_images
    target_videos = capacity.video_target if target_videos is None else target_videos

    def category_of(opp: Opportunity) -> str | None:
        if not opp.micro_niche_id:
            return None
        try:
            niche = db.query(MicroNiche).filter_by(id=opp.micro_niche_id).one_or_none()
            if niche is None:
                return None
            sub = db.query(Subcategory).filter_by(id=niche.subcategory_id).one_or_none()
            if sub is None:
                return None
            cat = db.query(Category).filter_by(id=sub.category_id).one_or_none()
            return cat.slug if cat else None
        except Exception:
            return None

    opportunities = (
        db.query(Opportunity)
        .filter(Opportunity.status.in_(["new", "approved"]))
        .order_by(Opportunity.opportunity_score.desc())
        .limit(capacity.max_daily_generation * 4)
        .all()
    )

    repeat_counts = _recent_repetition_counts(db, plan_date)
    # Current-plan counts grow as we select (within-plan diversification).
    current_counts: dict[tuple[str, str], int] = {}

    def penalty_for(category, niche_id, asset_type_value, comp_key) -> tuple[float, list[str]]:
        parts: list[str] = []
        penalty = 0.0
        if category:
            n = repeat_counts.get(("category", category), 0) + current_counts.get(
                ("category", category), 0
            )
            if n:
                penalty += CATEGORY_REPEAT_PENALTY * math.sqrt(n)
                parts.append(f"category repeat ×{n}")
        if niche_id:
            n = repeat_counts.get(("micro_niche", niche_id), 0) + current_counts.get(
                ("micro_niche", niche_id), 0
            )
            if n:
                penalty += NICHE_REPEAT_PENALTY * math.sqrt(n)
                parts.append(f"micro-niche repeat ×{n}")
        n = repeat_counts.get(("asset_type", asset_type_value), 0) + current_counts.get(
            ("asset_type", asset_type_value), 0
        )
        if n:
            penalty += ASSET_TYPE_REPEAT_PENALTY * math.sqrt(n)
            parts.append(f"asset-type repeat ×{n}")
        if comp_key:
            n = repeat_counts.get(("composition", comp_key), 0) + current_counts.get(
                ("composition", comp_key), 0
            )
            if n:
                penalty += COMPOSITION_REPEAT_PENALTY * math.sqrt(n)
                parts.append(f"composition repeat ×{n}")
        return penalty, parts

    # Candidate pool: each opportunity × both asset types.
    candidates: list[dict[str, Any]] = []
    for opp in opportunities:
        base_score, source = _fused_score(db, opp)
        personal_fit = _personal_fit(db, opp)
        category = category_of(opp)
        comp_key = _composition_key(opp)
        for asset_type in (AssetType.IMAGE, AssetType.VIDEO):
            candidates.append(
                {
                    "opportunity": opp,
                    "asset_type": asset_type,
                    "base_score": base_score,
                    "score_source": source,
                    "personal_fit": personal_fit,
                    "category": category,
                    "comp_key": comp_key,
                }
            )

    def _grow_counts(cand: dict[str, Any]) -> None:
        if cand["category"]:
            key = ("category", cand["category"])
            current_counts[key] = current_counts.get(key, 0) + 1
        if cand["opportunity"].micro_niche_id:
            key = ("micro_niche", cand["opportunity"].micro_niche_id)
            current_counts[key] = current_counts.get(key, 0) + 1
        key = ("asset_type", cand["asset_type"].value)
        current_counts[key] = current_counts.get(key, 0) + 1
        if cand["comp_key"]:
            key = ("composition", cand["comp_key"])
            current_counts[key] = current_counts.get(key, 0) + 1

    def _score_candidate(cand: dict[str, Any]) -> dict[str, Any]:
        """Unified score with penalties recomputed against picks so far."""
        opp = cand["opportunity"]
        asset_type = cand["asset_type"]
        base = cand["base_score"]
        pf = cand["personal_fit"]
        unified = 0.7 * base
        if pf is not None:
            unified += 0.3 * pf
        penalty, penalty_parts = penalty_for(
            cand["category"], opp.micro_niche_id, asset_type.value, cand["comp_key"]
        )
        unified -= penalty
        confidence = float(opp.confidence or 0.5)
        return {
            **cand,
            "unified_score": round(unified, 3),
            "penalty": round(penalty, 3),
            "penalty_parts": penalty_parts,
            "confidence": confidence,
        }

    # Greedy selection: each pick recomputes penalties against the picks
    # already made, so within-plan repeats are genuinely diversified away.
    # Balance image/video to targets, cap at max_daily_generation.
    selected: list[dict[str, Any]] = []
    counts = {AssetType.IMAGE: 0, AssetType.VIDEO: 0}
    targets = {AssetType.IMAGE: target_images, AssetType.VIDEO: target_videos}
    remaining = list(candidates)
    while remaining and len(selected) < capacity.max_daily_generation:
        best: dict[str, Any] | None = None
        best_key: tuple[float, float] | None = None
        best_original: dict[str, Any] | None = None
        for cand in remaining:
            at = cand["asset_type"]
            if counts[at] >= targets[at]:
                continue
            scored = _score_candidate(cand)
            key = (-scored["unified_score"], -scored["confidence"])
            if best_key is None or key < best_key:
                best, best_key, best_original = scored, key, cand
        if best is None or best_original is None:
            break
        selected.append(best)
        counts[best["asset_type"]] += 1
        _grow_counts(best)
        remaining.remove(best_original)

    # Persist the plan (rebuild replaces the day's draft rows).
    plan = db.query(DailyProductionPlan).filter_by(plan_date=plan_date).one_or_none()
    if plan is None:
        plan = DailyProductionPlan(plan_date=plan_date)
        db.add(plan)
        db.flush()
    else:
        # Rebuild: archive the existing recommendations of this plan.
        for old in db.query(ProductionRecommendation).filter_by(plan_id=plan.id).all():
            if old.status == "recommended":
                old.status = "archived"
    plan.target_images = target_images
    plan.target_videos = target_videos
    if plan.status == "completed":
        plan.status = "draft"  # rebuilding a completed plan returns it to draft

    rows: list[ProductionRecommendation] = []
    for i, cand in enumerate(selected, start=1):
        opp = cand["opportunity"]
        penalty_note = (
            f" Diversification penalty {cand['penalty']:.1f}"
            f" ({', '.join(cand['penalty_parts'])})." if cand["penalty_parts"] else ""
        )
        fit_note = (
            f" Personal fit {cand['personal_fit']:.0f}/100."
            if cand["personal_fit"] is not None
            else ""
        )
        reason = (
            f"Scored {cand['base_score']:.1f} ({cand['score_source']})"
            f" in {cand['category'] or 'uncategorized'}"
            f"{fit_note} Confidence {cand['confidence']:.2f}."
            f"{penalty_note} Balanced {cand['asset_type'].value} slot {i}."
            " Recommendation only — approve to create a queue item."
        )
        row = ProductionRecommendation(
            plan_id=plan.id,
            opportunity_id=opp.id,
            rank=i,
            asset_type=cand["asset_type"],
            category=cand["category"],
            micro_niche_id=opp.micro_niche_id,
            unified_score=cand["unified_score"],
            personal_fit=cand["personal_fit"],
            confidence=cand["confidence"],
            reason=reason,
            recommended_quantity=1,
            status="recommended",
            evidence_json={
                "opportunity_score": cand["base_score"],
                "score_source": cand["score_source"],
                "diversification_penalty": cand["penalty"],
                "penalty_parts": cand["penalty_parts"],
                "composition_key": cand["comp_key"],
                "opportunity_title": opp.title,
            },
        )
        db.add(row)
        rows.append(row)
    db.flush()

    plan.summary_json = {
        "built_at": datetime.now().isoformat(),
        "capacity": capacity.model_dump(),
        "candidate_count": len(candidates),
        "selected_count": len(rows),
        "score_source": "fused_or_opportunity_score",
        "note": (
            "Recommendations only — nothing was auto-generated or auto-submitted. "
            "Approve a recommendation to create a production-queue item."
        ),
    }
    plan.data_provenance = DataProvenance.ESTIMATED
    db.flush()
    return plan


# ---------------------------------------------------------------------------
# Recommendation actions (all require an explicit user action)
# ---------------------------------------------------------------------------


def get_recommendation(db: Session, recommendation_id: str) -> ProductionRecommendation:
    row = db.query(ProductionRecommendation).filter_by(id=recommendation_id).one_or_none()
    if row is None:
        raise ValueError(f"Recommendation {recommendation_id} not found.")
    return row


def transition_queue_item(
    db: Session, queue_id: str, to_status, note: str | None = None
) -> ProductionQueue:
    """Validate and apply a queue transition. Rejects illegal transitions.

    `to_status` may be a ProductionQueueStatus or its string value.
    """
    to = to_status if isinstance(to_status, ProductionQueueStatus) else ProductionQueueStatus(to_status)
    row = db.query(ProductionQueue).filter_by(id=queue_id).one_or_none()
    if row is None:
        raise ValueError(f"Queue item {queue_id} not found.")
    if not is_legal_transition(row.status, to):
        raise ValueError(transition_error_message(row.status, to))
    row.status = to
    row.status_changed_at = datetime.now()
    if note:
        row.notes = f"{row.notes}\n{note}" if row.notes else note
    db.flush()
    return row


def approve_recommendation(
    db: Session, recommendation_id: str
) -> tuple[ProductionRecommendation, ProductionQueue]:
    """User approve: recommendation → approved + a DISCOVERED queue item.

    Blocked when any linked concept is HIGH_RISK compliance or carries an
    originality blocker — those stay for human review.
    """
    rec = get_recommendation(db, recommendation_id)
    if rec.status != "recommended":
        raise ValueError(
            f"Only 'recommended' recommendations can be approved (current: {rec.status})."
        )
    blockers: list[str] = []
    concepts = (
        db.query(ConceptVariation)
        .filter_by(recommendation_id=rec.id)
        .order_by(ConceptVariation.created_at.desc())
        .all()
    )
    for concept in concepts:
        if concept.status == "archived":
            # Explicitly retired by the user — no longer gates approval.
            continue
        blockers.extend(f"{concept.title}: {b}" for b in blockers_for_promotion(concept))
    if blockers:
        raise ValueError(
            "Approval blocked — resolve before promoting: " + " | ".join(blockers)
        )
    rec.status = "approved"
    queue_item = ProductionQueue(
        opportunity_id=rec.opportunity_id,
        asset_type=rec.asset_type,
        title=(rec.evidence_json or {}).get("opportunity_title") or rec.category or "Untitled",
        status=ProductionQueueStatus.DISCOVERED,
        priority_band="P2",
        target_quantity=rec.recommended_quantity,
        notes=(
            f"Created from daily-plan recommendation {rec.id} (rank {rec.rank}, "
            f"unified score {rec.unified_score}).\n{rec.reason}\n"
            "Nothing was auto-generated — produce the asset manually, then "
            "advance this item through the queue."
        ),
    )
    db.add(queue_item)
    db.flush()
    # The queue item enters at DISCOVERED (the legal entry state); the user
    # advances it through the T01–T29 transitions from here.
    return rec, queue_item


def reject_recommendation(db: Session, recommendation_id: str) -> ProductionRecommendation:
    rec = get_recommendation(db, recommendation_id)
    if rec.status != "recommended":
        raise ValueError(f"Only 'recommended' recommendations can be rejected (current: {rec.status}).")
    rec.status = "rejected"
    db.flush()
    return rec


def archive_recommendation(db: Session, recommendation_id: str) -> ProductionRecommendation:
    rec = get_recommendation(db, recommendation_id)
    if rec.status == "archived":
        raise ValueError("Recommendation is already archived.")
    rec.status = "archived"
    db.flush()
    return rec


def prioritize_recommendation(
    db: Session, recommendation_id: str, rank: int | None = None, note: str | None = None
) -> ProductionRecommendation:
    """User prioritize: move the recommendation to `rank`, re-sequencing the
    plan's remaining 'recommended' rows."""
    rec = get_recommendation(db, recommendation_id)
    if rec.status != "recommended":
        raise ValueError(
            f"Only 'recommended' recommendations can be reprioritized (current: {rec.status})."
        )
    if rank is None:
        return rec
    peers = (
        db.query(ProductionRecommendation)
        .filter_by(plan_id=rec.plan_id, status="recommended")
        .order_by(ProductionRecommendation.rank.asc())
        .all()
    )
    peers = [p for p in peers if p.id != rec.id]
    rank = max(1, min(rank, len(peers) + 1))
    peers.insert(rank - 1, rec)
    for i, p in enumerate(peers, start=1):
        p.rank = i
    if note:
        rec.reason = f"{rec.reason}\nPrioritized by user: {note}"
    db.flush()
    return rec


def edit_recommendation(db: Session, recommendation_id: str, **fields) -> ProductionRecommendation:
    """User edit: whitelisted fields only (asset_type, category, reason,
    recommended_quantity, confidence)."""
    rec = get_recommendation(db, recommendation_id)
    if rec.status not in ("recommended", "approved"):
        raise ValueError(f"Recommendation in status '{rec.status}' cannot be edited.")
    allowed = {"asset_type", "category", "reason", "recommended_quantity", "confidence"}
    for key, value in fields.items():
        if key not in allowed or value is None:
            continue
        if key == "asset_type":
            from app.schemas.enums import AssetType as _AT

            value = _AT(value) if not isinstance(value, _AT) else value
        setattr(rec, key, value)
    db.flush()
    return rec


class DailyProductionPlanner:
    """Object-oriented facade over the daily production planning workflow.

    All methods require explicit user action — nothing here auto-generates
    or auto-submits. Recommendations are approved/rejected/edited by the
    user; approval creates a production-queue item at DISCOVERED.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_capacity(self) -> CapacitySettings:
        return get_capacity(self.db)

    def build_plan(
        self,
        plan_date: date | None = None,
        target_images: int | None = None,
        target_videos: int | None = None,
    ) -> DailyProductionPlan:
        return build_plan(
            self.db,
            plan_date=plan_date,
            target_images=target_images,
            target_videos=target_videos,
        )

    def get_plan(self, plan_date: date | None = None) -> DailyProductionPlan | None:
        plan_date = plan_date or date.today()
        return (
            self.db.query(DailyProductionPlan)
            .filter_by(plan_date=plan_date)
            .one_or_none()
        )

    def approve(self, recommendation_id: str) -> tuple[ProductionRecommendation, ProductionQueue]:
        return approve_recommendation(self.db, recommendation_id)

    def reject(self, recommendation_id: str) -> ProductionRecommendation:
        return reject_recommendation(self.db, recommendation_id)

    def archive(self, recommendation_id: str) -> ProductionRecommendation:
        return archive_recommendation(self.db, recommendation_id)

    def prioritize(self, recommendation_id: str, rank: int) -> ProductionRecommendation:
        return prioritize_recommendation(self.db, recommendation_id, rank)

    def edit(self, recommendation_id: str, **fields) -> ProductionRecommendation:
        return edit_recommendation(self.db, recommendation_id, **fields)

    def regenerate(self, recommendation_id: str, count: int = 3) -> list:
        from app.services.concepts import regenerate_concepts

        rec = get_recommendation(self.db, recommendation_id)
        return regenerate_concepts(self.db, rec, count=count)

    def transition_queue_item(
        self, queue_item_id: str, to_status: ProductionQueueStatus | str
    ) -> ProductionQueue:
        return transition_queue_item(self.db, queue_item_id, to_status)
