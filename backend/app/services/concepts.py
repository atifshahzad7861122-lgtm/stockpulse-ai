"""Deterministic, template-based concept generation for recommendations
(Phase 3, backend only).

No fake AI claims: concepts are assembled from explicit composition pools
with a stable seed, so the same recommendation always yields the same set.
Distinctness is enforced — variations differ in subject, setting,
composition, or commercial use-case; never in minor color/camera tweaks.

Every concept is run through:
- the similarity engine (HIGH_SIMILARITY / POSSIBLE_DUPLICATE /
  LOW_ORIGINALITY flags), and
- the compliance engine run_screen → PASS / REVIEW / HIGH_RISK.
HIGH_RISK is stored on the concept and blocks queue promotion.
"""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy.orm import Session

from app.engines.compliance import RuleSpec, ScreenSubject, run_screen
from app.engines.similarity import (
    HIGH_RISK_THRESHOLD,
    combined_similarity,
    text_fingerprint,
)
from app.models.compliance import ComplianceRule
from app.models.planning import ConceptVariation, ProductionRecommendation
from app.models.production import Asset
from app.models.prompts import Prompt, PromptVersion

# ---------------------------------------------------------------------------
# Composition pools — explicit building blocks (no model inference)
# ---------------------------------------------------------------------------

_IMAGE_COMPOSITIONS = (
    "rule-of-thirds with generous negative space",
    "centered symmetrical composition",
    "diagonal leading lines drawing the eye",
    "macro close-up isolating texture and detail",
    "wide environmental establishing shot",
    "overhead flat-lay arrangement",
    "layered depth with foreground framing element",
    "low-angle heroic viewpoint",
)

_IMAGE_LIGHTING = (
    "soft diffused daylight",
    "warm golden-hour glow",
    "high-key bright studio lighting",
    "dramatic side-light with long shadows",
    "cool blue-hour ambient light",
    "clean even overcast light",
)

_IMAGE_CAMERAS = (
    "35mm wide-angle lens",
    "50mm natural-perspective lens",
    "85mm short telephoto compression",
    "macro lens for fine detail",
)

_IMAGE_PERSPECTIVES = (
    "eye-level straight-on",
    "slightly elevated three-quarter view",
    "overhead top-down",
    "ground-level looking up",
)

_VIDEO_CAMERA_MOVEMENTS = (
    "slow push-in",
    "gentle lateral dolly",
    "subtle parallax drift",
    "static locked-off tripod",
    "slow ascending reveal",
    "orbit around the subject",
)

_VIDEO_VISUAL_DIRECTIONS = (
    "clean minimal commercial aesthetic",
    "warm documentary realism",
    "bold editorial contrast",
    "calm lifestyle storytelling",
)

_COMMERCIAL_USES = (
    "website hero background",
    "blog article illustration",
    "social media campaign visual",
    "presentation slide backdrop",
    "advertising banner creative",
    "editorial feature image",
)

_VIDEO_DURATIONS = (6, 8, 10, 15)


def _seed_int(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


def _pick(pool: tuple, seed: int, offset: int) -> str:
    return pool[(seed + offset * 7919) % len(pool)]


def _niche_label(recommendation: ProductionRecommendation) -> str:
    return recommendation.category or "commercial stock"


def _subject_variants(niche: str) -> tuple[str, str, str, str, str, str]:
    """Meaningfully different subject treatments for one niche."""
    return (
        f"hero subject in {niche} shown at human scale",
        f"detail study: texture and craft of {niche}",
        f"environmental scene placing {niche} in everyday context",
        f"abstract arrangement inspired by {niche} themes",
        f"hands-on interaction with {niche} elements",
        f"aerial-scale overview of a {niche} setting",
    )


def _environment_variants(niche: str) -> tuple[str, str, str, str, str, str]:
    return (
        f"bright modern interior, {niche} context",
        f"outdoor natural setting, {niche} context",
        f"minimal studio backdrop, {niche} accents",
        f"urban street environment, {niche} context",
        f"cozy domestic space, {niche} context",
        f"abstract gradient environment, {niche} mood",
    )


# ---------------------------------------------------------------------------
# Spec builders
# ---------------------------------------------------------------------------


def build_image_spec(
    recommendation: ProductionRecommendation, index: int, variation_round: int = 1
) -> dict[str, Any]:
    niche = _niche_label(recommendation)
    seed = _seed_int(f"{recommendation.id}|image|{variation_round}")
    spec = {
        "concept": (
            f"A commercial still photograph for {_pick(_COMMERCIAL_USES, seed, index)}: "
            f"{_pick(_subject_variants(niche), seed, index * 2)} "
            f"set in {_pick(_environment_variants(niche), seed, index * 3)}."
        ),
        "commercial_use": _pick(_COMMERCIAL_USES, seed, index),
        "subject": _pick(_subject_variants(niche), seed, index * 2),
        "environment": _pick(_environment_variants(niche), seed, index * 3),
        "composition": _pick(_IMAGE_COMPOSITIONS, seed, index * 4),
        "lighting": _pick(_IMAGE_LIGHTING, seed, index * 5),
        "camera": _pick(_IMAGE_CAMERAS, seed, index * 6),
        "perspective": _pick(_IMAGE_PERSPECTIVES, seed, index * 7),
        "orientation": "landscape" if index % 2 == 0 else "portrait",
        "aspect_ratio": "3:2" if index % 2 == 0 else "4:5",
        "originality_instructions": (
            "Compose an original arrangement — do not recreate any existing "
            "photograph, artwork, or brand campaign. Vary props, positions, and "
            "styling so the frame reads as a new creation, not a reskin."
        ),
        "compliance_considerations": (
            "Human review required before production: confirm no recognizable "
            "people (releases), no trademarks or logos, no copyrighted artwork "
            "in frame. This screen covers text fields only, not pixels."
        ),
    }
    spec["title"] = f"{niche.title()} — {_pick(_COMMERCIAL_USES, seed, index).title()} ({index + 1})"
    return spec


def build_video_spec(
    recommendation: ProductionRecommendation, index: int, variation_round: int = 1
) -> dict[str, Any]:
    niche = _niche_label(recommendation)
    seed = _seed_int(f"{recommendation.id}|video|{variation_round}")
    duration = _VIDEO_DURATIONS[(seed + index) % len(_VIDEO_DURATIONS)]
    spec = {
        "scene": (
            f"A {duration}-second commercial clip for {_pick(_COMMERCIAL_USES, seed, index)}: "
            f"{_pick(_subject_variants(niche), seed, index * 2)} "
            f"in {_pick(_environment_variants(niche), seed, index * 3)}."
        ),
        "subject": _pick(_subject_variants(niche), seed, index * 2),
        "action": _pick(
            (
                "subject settles into place as the scene opens",
                "slow reveal of the key element mid-shot",
                "gentle interaction: hands arrange the scene",
                "ambient motion: light and shadow shift naturally",
            ),
            seed,
            index * 4,
        ),
        "movement": _pick(_VIDEO_CAMERA_MOVEMENTS, seed, index * 5),
        "camera_movement": _pick(_VIDEO_CAMERA_MOVEMENTS, seed, index * 5),
        "duration": duration,
        "orientation": "landscape" if index % 2 == 0 else "vertical",
        "loop_potential": (
            "seamless loop: opening and closing frames match"
            if index % 2 == 0
            else "single-pass clip with a clean ending beat"
        ),
        "commercial_use": _pick(_COMMERCIAL_USES, seed, index),
        "visual_direction": _pick(_VIDEO_VISUAL_DIRECTIONS, seed, index * 6),
        "originality_instructions": (
            "Shoot an original sequence — do not restage any existing footage, "
            "advertisement, or film scene. Change the choreography, pacing, and "
            "framing so the clip stands on its own."
        ),
        "compliance_considerations": (
            "Human review required before production: confirm no recognizable "
            "people (releases), no trademarks or logos, no copyrighted music or "
            "artwork. This screen covers text fields only, not pixels."
        ),
    }
    spec["title"] = (
        f"{niche.title()} — {_pick(_COMMERCIAL_USES, seed, index).title()} clip ({index + 1})"
    )
    return spec


def _spec_text(asset_type: str, spec: dict[str, Any]) -> str:
    if asset_type == "VIDEO":
        parts = [spec.get("title", ""), spec.get("scene", ""), spec.get("visual_direction", "")]
    else:
        parts = [spec.get("title", ""), spec.get("concept", ""), spec.get("composition", "")]
    return " ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Distinctness
# ---------------------------------------------------------------------------


def _distinctness_key(asset_type: str, spec: dict[str, Any]) -> tuple:
    if asset_type == "VIDEO":
        return (
            spec.get("subject"),
            spec.get("scene"),
            spec.get("commercial_use"),
            spec.get("visual_direction"),
        )
    return (
        spec.get("subject"),
        spec.get("environment"),
        spec.get("composition"),
        spec.get("commercial_use"),
    )


def assert_distinct(specs: list[dict[str, Any]], asset_type: str) -> None:
    """Raise if two specs are only trivially different.

    Distinctness means differing in subject, setting, composition, or
    commercial use-case — never in minor color/camera tweaks alone.
    """
    keys = [_distinctness_key(asset_type, s) for s in specs]
    if len(set(keys)) != len(keys):
        raise ValueError(
            "Concept variations are not meaningfully distinct: subject, setting, "
            "composition, or use-case repeats across variations."
        )


# ---------------------------------------------------------------------------
# Originality (similarity) screen
# ---------------------------------------------------------------------------


def _similarity_corpus(db: Session, exclude_concept_id: str | None) -> list[tuple[str, str]]:
    """(label, text) corpus: other concepts, prompts, assets, ideas."""
    corpus: list[tuple[str, str]] = []
    for row in db.query(ConceptVariation).all():
        if row.id == exclude_concept_id:
            continue
        spec = row.concept_json or {}
        text = f"{row.title} {spec.get('concept') or spec.get('scene') or ''}"
        corpus.append((f"concept:{row.id}", text))
    for row in db.query(Prompt).all():
        version_text = ""
        versions = sorted(row.versions, key=lambda v: v.version_number)
        if versions:
            version_text = versions[-1].prompt_text or ""
        corpus.append((f"prompt:{row.id}", f"{row.name} {version_text}"))
    for row in db.query(Asset).all():
        corpus.append((f"asset:{row.id}", row.title or ""))
    return corpus


def screen_similarity(
    db: Session, concept_text: str, exclude_concept_id: str | None = None
) -> dict[str, Any]:
    """Flag HIGH_SIMILARITY / POSSIBLE_DUPLICATE / LOW_ORIGINALITY.

    Thresholds follow the similarity engine (docs/17 §3): ≥0.80 HIGH_RISK,
    0.60–0.80 REVIEW. Never claims legal certainty.
    """
    flags: list[dict[str, Any]] = []
    own_fp = text_fingerprint(concept_text)
    best_score = 0.0
    best_label = None
    for label, text in _similarity_corpus(db, exclude_concept_id):
        if not text.strip():
            continue
        if text_fingerprint(text) == own_fp:
            flags.append(
                {
                    "flag": "POSSIBLE_DUPLICATE",
                    "matched": label,
                    "similarity": 1.0,
                    "note": (
                        "Text fingerprint identical to an existing item — treat as "
                        "a possible duplicate, not as legal proof."
                    ),
                }
            )
            best_score = 1.0
            best_label = label
            continue
        score = combined_similarity(concept_text, text)
        if score > best_score:
            best_score, best_label = score, label
    if best_score >= HIGH_RISK_THRESHOLD:
        flags.append(
            {
                "flag": "HIGH_SIMILARITY",
                "matched": best_label,
                "similarity": round(best_score, 4),
                "note": (
                    "Assessed as highly similar to an existing item "
                    f"(similarity {best_score:.2f} ≥ {HIGH_RISK_THRESHOLD}). "
                    "Differentiate further or retire this concept."
                ),
            }
        )
    if best_label and not flags and best_score >= 0.60:
        flags.append(
            {
                "flag": "LOW_ORIGINALITY",
                "matched": best_label,
                "similarity": round(best_score, 4),
                "note": (
                    "Assessed in the REVIEW band (0.60–0.80): overlaps materially "
                    "with an existing item. Strengthen the differentiating "
                    "elements before approving."
                ),
            }
        )
    return {
        "flags": flags,
        "best_similarity": round(best_score, 4),
        "best_match": best_label,
        "corpus_size": len(_similarity_corpus(db, exclude_concept_id)),
    }


# ---------------------------------------------------------------------------
# Compliance precheck
# ---------------------------------------------------------------------------


def _rule_specs(db: Session) -> list[RuleSpec]:
    rows = db.query(ComplianceRule).filter_by(is_enabled=True).all()
    return [
        RuleSpec(
            rule_key=r.rule_key,
            severity=r.severity,
            check_method=(r.rule_config or {}).get("check_method", "human_review"),
            applies_to=tuple(r.applies_to or []),
        )
        for r in rows
    ]


def screen_compliance(
    db: Session, asset_type: str, spec: dict[str, Any], title: str,
    ai_disclosure: bool | None = None,
) -> tuple[str, dict[str, Any]]:
    """Run every concept through the compliance engine.

    Returns (outcome, result_json). HIGH_RISK outcomes block queue promotion
    and stay for human review.

    ``ai_disclosure`` carries the user's explicit disclosure decision
    (recorded on the concept). None = undecided, which leaves the gen-01
    BLOCK finding triggered — the user must decide before approval.
    """
    concept_text = spec.get("concept") or spec.get("scene") or ""
    subject = ScreenSubject(
        concept=concept_text,
        originality_notes=spec.get("originality_instructions", ""),
        title=title,
        asset_type=asset_type,
        ai_disclosure=ai_disclosure,
    )
    result = run_screen("PROMPT_SCREEN", subject, _rule_specs(db))
    result_json = {
        "result": result.result,
        "risk_level": result.risk_level,
        "explanation": result.explanation,
        "rules_version": result.rules_version,
        "findings": [
            {
                "rule_key": f.rule_key,
                "severity": f.severity.value,
                "triggered": f.triggered,
                "explanation": f.explanation,
                "remediation": f.remediation,
            }
            for f in result.findings
        ],
    }
    return result.result, result_json


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def originality_notes_for(spec: dict[str, Any], asset_type: str) -> str:
    if asset_type == "VIDEO":
        return (
            f"Original {spec['duration']}s {spec['orientation']} clip: "
            f"{spec['visual_direction']}; subject '{spec['subject']}' with "
            f"'{spec['camera_movement']}' movement for {spec['commercial_use']}. "
            "Composition, choreography, and pacing are original to this concept."
        )
    return (
        f"Original still: {spec['composition']}, {spec['lighting']}, "
        f"{spec['camera']} ({spec['perspective']}, {spec['orientation']} "
        f"{spec['aspect_ratio']}) for {spec['commercial_use']}. "
        f"Subject: {spec['subject']} in {spec['environment']}. "
        "Arrangement is original to this concept."
    )


def generate_concepts(
    db: Session,
    recommendation: ProductionRecommendation,
    count: int = 3,
    variation_round: int = 1,
) -> list[ConceptVariation]:
    """Generate `count` distinct, screened concept variations for a
    recommendation. Deterministic (template-based); persisted to DB."""
    builder = build_video_spec if recommendation.asset_type.value == "VIDEO" else build_image_spec
    specs = [builder(recommendation, i, variation_round) for i in range(count)]
    assert_distinct(specs, recommendation.asset_type.value)

    rows: list[ConceptVariation] = []
    for i, spec in enumerate(specs):
        title = spec["title"]
        text = _spec_text(recommendation.asset_type.value, spec)
        sim_flags = screen_similarity(db, text)
        comp_outcome, comp_json = screen_compliance(
            db, recommendation.asset_type.value, spec, title
        )
        row = ConceptVariation(
            recommendation_id=recommendation.id,
            asset_type=recommendation.asset_type,
            title=title,
            concept_json=spec,
            originality_notes=originality_notes_for(spec, recommendation.asset_type.value),
            similarity_flags_json=sim_flags,
            compliance_result=comp_outcome,
            compliance_result_json=comp_json,
            variation_round=variation_round,
            status="draft" if comp_outcome != "HIGH_RISK" else "screened",
        )
        db.add(row)
        db.flush()
        rows.append(row)
    return rows


def regenerate_concepts(
    db: Session,
    recommendation: ProductionRecommendation,
    count: int = 3,
) -> list[ConceptVariation]:
    """New variation round; prior rounds are archived (kept for audit)."""
    existing = (
        db.query(ConceptVariation)
        .filter_by(recommendation_id=recommendation.id)
        .order_by(ConceptVariation.variation_round.desc())
        .all()
    )
    next_round = (existing[0].variation_round + 1) if existing else 1
    for old in existing:
        if old.status != "archived":
            old.status = "archived"
    return generate_concepts(
        db, recommendation, count=count, variation_round=next_round
    )


def blockers_for_promotion(concept: ConceptVariation) -> list[str]:
    """Reasons a concept may not promote to the queue. Empty = clear."""
    blockers: list[str] = []
    if concept.compliance_result == "HIGH_RISK":
        blockers.append(
            "Compliance assessed HIGH_RISK — stays for human review; "
            "resolve the findings or retire the concept."
        )
    flags = (concept.similarity_flags_json or {}).get("flags", [])
    for flag in flags:
        if flag.get("flag") in ("POSSIBLE_DUPLICATE", "HIGH_SIMILARITY"):
            blockers.append(
                f"Originality flag {flag['flag']} (similarity "
                f"{flag.get('similarity')}) — differentiate or retire."
            )
    return blockers
