"""Viral/high-performing asset analyzer (FINAL MASTER SPEC §21–32).

Flow: user selects a high-performing image/video opportunity
→ GENERATE ORIGINAL PROMPT → the EXISTING Gemini integration extracts
commercial attributes → generates a materially DIFFERENT original concept
(never an exact copy/composition/pose/style) → PROMPT A / B / C +
negative prompt, all as TEXT. No media is generated here; no Adobe upload.

Honesty rules:
- If the LLM provider is not configured (mock), generation is refused with a
  clear message — mock output is never presented as a real analysis.
- Provider failures surface as FAILED analyses with the honest error; no
  fabricated fallback content.
- Completed analyses are cached per (opportunity_id, asset_type).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.engines import market_intelligence as mi
from app.engines.trends import signal_band
from app.models.intelligence import AssetAnalysis, Opportunity
from app.providers.providers import LLMRequest, LLMResponse, get_llm_provider
from app.schemas.enums import DataProvenance

logger = logging.getLogger(__name__)

ASSET_TYPES = ("image", "video")


def _provenance_of(value: Any) -> DataProvenance:
    if isinstance(value, DataProvenance):
        return value
    try:
        return DataProvenance(str(value))
    except ValueError:
        return DataProvenance.THIRD_PARTY

# Phrases that betray a non-original (copy/recreation) output. The originality
# validator rejects any analysis whose concept or prompts contain them.
_BANNED_PHRASES = (
    "exact copy",
    "exact recreation",
    "recreate exactly",
    "same composition",
    "same pose",
    "same camera setup",
    "identical to",
    "copy of the reference",
    "copy of the original",
)

_REQUIRED_COMMERCIAL_KEYS = (
    "topic",
    "category",
    "micro_niche",
    "primary_keywords",
    "secondary_keywords",
    "commercial_use_case",
    "subject",
    "environment",
    "composition",
    "visual_characteristics",
    "content_type",
)

_MIN_PROMPT_CHARS = 80


def _keywords_from_text(text: str, limit: int = 10) -> list[str]:
    counts: dict[str, int] = {}
    for token in re.findall(r"[a-zA-Z][a-zA-Z0-9-]{3,}", text.lower()):
        if token not in mi._STOPWORDS:
            counts[token] = counts.get(token, 0) + 1
    return [k for k, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]]


def build_market_context(db: Session, opportunity_id: str) -> dict[str, Any]:
    """Assemble the market context shown next to the analysis (spec §31)."""
    opp = db.query(Opportunity).filter_by(id=opportunity_id).one_or_none()
    if opp is None:
        raise ValueError(f"Opportunity {opportunity_id} not found.")
    notes = " ".join(
        str(e.get("note", "")) for e in (opp.demand_evidence or []) if isinstance(e, dict)
    )
    # Find matching topic intelligence for 7D/30D signals when possible.
    topic_intel = None
    for t in mi.all_topics(db):
        if t.topic.lower() in opp.title.lower() or opp.title.lower() in t.topic.lower():
            topic_intel = t
            break
    keywords = _keywords_from_text(opp.title + " " + (opp.summary or "") + " " + notes)
    ctx: dict[str, Any] = {
        "opportunity_id": opp.id,
        "title": opp.title,
        "summary": opp.summary,
        "opportunity_score": float(opp.opportunity_score or 0),
        "keywords": keywords,
        "source": "opportunity demand evidence",
        "source_type": "opportunity",
        "collected_at": opp.created_at.isoformat() if opp.created_at else None,
        "provenance": opp.data_provenance.value if opp.data_provenance else "THIRD_PARTY",
        "signal_kind": _signal_kind_value(notes),
    }
    if topic_intel is not None:
        ctx.update(
            {
                "topic": topic_intel.topic,
                "category": topic_intel.category,
                "signal_7d": topic_intel.signal_7d,
                "signal_30d": topic_intel.signal_30d,
                "momentum": topic_intel.momentum,
                "momentum_7d": topic_intel.momentum_7d,
                "momentum_30d": topic_intel.momentum_30d,
                "trend_signal": topic_intel.trend_signal,
                "source": ", ".join(topic_intel.sources) or ctx["source"],
                "collected_at": topic_intel.last_updated or ctx["collected_at"],
                "provenance": topic_intel.provenance,
                "signal_kind": topic_intel.signal_kind,
            }
        )
    else:
        ctx.update(
            {
                "topic": opp.title,
                "category": None,
                "signal_7d": signal_band(float(opp.opportunity_score or 0)),
                "signal_30d": None,
                "momentum": "STABLE",
                "momentum_7d": "STABLE",
                "momentum_30d": None,
                "trend_signal": round(float(opp.opportunity_score or 0), 1),
            }
        )
    return ctx


def _signal_kind_value(notes: str) -> str:
    return mi.signal_kind_for(_dominant_metric_hint(notes)).value


def _dominant_metric_hint(notes: str) -> str | None:
    n = notes.lower()
    for hint in ("search", "download", "sale", "earning", "trend", "popular", "demand"):
        if hint in n:
            return hint
    return None


# ---------------------------------------------------------------------------
# Gemini prompt
# ---------------------------------------------------------------------------


def _system_prompt(asset_type: str) -> str:
    kind_specific = (
        "For an IMAGE asset, cover: main subject, secondary subject, environment, "
        "commercial context, general composition, perspective, lighting, color "
        "direction, objects, visual mood, topic, category, keywords."
        if asset_type == "image"
        else "For a VIDEO asset, cover: main subject, scene, environment, action, "
        "movement, camera movement, general framing, lighting, visual mood, "
        "topic, category, keywords, potential stock use cases."
    )
    prompt_fields = (
        "subject, environment, composition, perspective, camera, lighting, color "
        "direction, visual details, commercial context, technical quality, "
        "stock-friendly framing, negative requirements"
        if asset_type == "image"
        else "subject, environment, action, movement, camera movement, framing, "
        "lighting, duration suggestion, orientation, visual details, commercial "
        "context, technical quality, negative requirements"
    )
    return f"""You are a commercial stock-content strategist. You NEVER copy an existing asset.

ORIGINALITY REQUIREMENT (strict):
- Do NOT produce an exact recreation, exact copy, same composition, same pose,
  same camera setup, same artist style, or contributor style imitation.
- Do NOT reverse-engineer a prompt for the reference.
- You MAY preserve: topic, market, keywords, commercial intent, general subject
  category. You MUST change meaningful creative elements (different subject
  variant, different environment, different composition, different lighting or
  mood) so the result is a genuinely original commercial concept targeting the
  same market opportunity.

TASK:
1. Analyze the market context below. {kind_specific}
2. Extract commercial attributes as JSON (see schema).
3. Invent ONE materially different original concept for the same commercial opportunity.
4. Write three full generation prompts from that concept:
   - prompt_a: primary original commercial concept
   - prompt_b: alternative original concept (different creative direction)
   - prompt_c: a different commercial use case for the same topic/market
   Each prompt must cover: {prompt_fields}.
5. Write a negative prompt covering: watermarks, logos, brand names, unwanted
   text, copyrighted characters, distorted anatomy, extra limbs, deformed
   objects, low-quality details, visual artifacts.

OUTPUT: strict JSON only, no markdown fences, matching this schema exactly:
{{
  "commercial_analysis": {{
    "topic": str, "category": str|null, "micro_niche": str,
    "primary_keywords": [str], "secondary_keywords": [str],
    "commercial_use_case": str, "subject": str, "environment": str,
    "composition": str, "visual_characteristics": str, "content_type": "{asset_type}"
  }},
  "original_concept": str (2-4 sentences, describes what makes it original),
  "prompt_a": str, "prompt_b": str, "prompt_c": str,
  "negative_prompt": str
}}"""


def _user_prompt(market_context: dict[str, Any], asset_type: str) -> str:
    mc = market_context
    lines = [
        f"ASSET TYPE: {asset_type}",
        f"OPPORTUNITY: {mc.get('title')}",
        f"SUMMARY: {mc.get('summary')}",
        f"TOPIC: {mc.get('topic')}",
        f"CATEGORY: {mc.get('category')}",
        f"7D SIGNAL: {mc.get('signal_7d')}  30D SIGNAL: {mc.get('signal_30d')}",
        f"MOMENTUM: {mc.get('momentum')} (7D {mc.get('momentum_7d')} / 30D {mc.get('momentum_30d')})",
        f"TREND SIGNAL: {mc.get('trend_signal')}/100",
        f"KEYWORDS: {', '.join(mc.get('keywords', []))}",
        f"SOURCE: {mc.get('source')}  PROVENANCE: {mc.get('provenance')}",
        f"SIGNAL KIND: {mc.get('signal_kind')}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Parsing + originality validation
# ---------------------------------------------------------------------------


def parse_structured(text: str) -> dict[str, Any]:
    """Extract the JSON object from an LLM response (tolerates fences/prose)."""
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM response contained no JSON object.")
    try:
        data = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM response was not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("LLM response JSON was not an object.")
    return data


def validate_originality(data: dict[str, Any]) -> list[str]:
    """Return a list of violations; empty means the analysis is acceptable."""
    violations: list[str] = []
    ca = data.get("commercial_analysis")
    if not isinstance(ca, dict):
        violations.append("missing commercial_analysis object")
    else:
        missing = [k for k in _REQUIRED_COMMERCIAL_KEYS if not ca.get(k)]
        if missing:
            violations.append(f"commercial_analysis missing keys: {', '.join(missing)}")
    concept = data.get("original_concept") or ""
    if len(concept.strip()) < 40:
        violations.append("original_concept too short to describe an original idea")
    for key in ("prompt_a", "prompt_b", "prompt_c"):
        prompt = data.get(key) or ""
        if len(prompt.strip()) < _MIN_PROMPT_CHARS:
            violations.append(f"{key} too short (<{_MIN_PROMPT_CHARS} chars)")
    haystack = " ".join(
        str(data.get(k, "")) for k in ("original_concept", "prompt_a", "prompt_b", "prompt_c")
    ).lower()
    for phrase in _BANNED_PHRASES:
        if phrase in haystack:
            violations.append(f"non-original language detected: '{phrase}'")
    # The three prompts must differ materially from each other.
    prompts = [str(data.get(k, "")).strip().lower() for k in ("prompt_a", "prompt_b", "prompt_c")]
    if len(set(prompts)) < 3 and all(prompts):
        violations.append("prompt_a/b/c are not materially different from each other")
    return violations


# ---------------------------------------------------------------------------
# Generation entry point
# ---------------------------------------------------------------------------


def get_cached_analysis(
    db: Session, opportunity_id: str, asset_type: str
) -> AssetAnalysis | None:
    return (
        db.query(AssetAnalysis)
        .filter_by(opportunity_id=opportunity_id, asset_type=asset_type, status="SUCCEEDED")
        .order_by(AssetAnalysis.created_at.desc())
        .first()
    )


def generate(
    db: Session,
    opportunity_id: str,
    asset_type: str,
    provider_factory: Callable[[], Any] | None = None,
    force: bool = False,
) -> AssetAnalysis:
    """Generate (or return the cached) asset analysis for an opportunity.

    Raises ValueError for bad input, RuntimeError for provider/parse failures
    (persisted as a FAILED row so the failure is visible, never silent).
    """
    if asset_type not in ASSET_TYPES:
        raise ValueError(f"asset_type must be one of {ASSET_TYPES}, got '{asset_type}'.")
    if not force:
        cached = get_cached_analysis(db, opportunity_id, asset_type)
        if cached is not None:
            return cached

    market_context = build_market_context(db, opportunity_id)

    provider = (provider_factory or get_llm_provider)()
    if getattr(provider, "name", "") == "mock":
        raise RuntimeError(
            "LLM provider is not configured (mock). Set STOCKPULSE_LLM_PROVIDER=gemini "
            "with a valid GEMINI_API_KEY to generate original prompts."
        )

    row = AssetAnalysis(
        opportunity_id=opportunity_id,
        asset_type=asset_type,
        status="PENDING",
        market_context=market_context,
        data_provenance=_provenance_of(market_context.get("provenance", "THIRD_PARTY")),
    )
    db.add(row)
    db.flush()

    try:
        response: LLMResponse = provider.generate(
            LLMRequest(
                task="asset_analysis",
                context={
                    "asset_type": asset_type,
                    "market_context": market_context,
                    # Full instructions are inlined in the context because the
                    # provider serializes context into the user message; the
                    # provider's own system instruction reinforces the same rules.
                    "originality_rules": _system_prompt(asset_type),
                    "analysis_request": _user_prompt(market_context, asset_type),
                },
                max_tokens=4000,
            )
        )

    except Exception as exc:
        row.status = "FAILED"
        row.error_message = f"LLM provider error ({provider.name}): {exc}"
        db.commit()
        raise RuntimeError(row.error_message) from exc

    try:
        data = parse_structured(response.text)
    except ValueError as exc:
        row.status = "FAILED"
        row.error_message = f"Could not parse structured LLM output: {exc}"
        row.model = response.model
        db.commit()
        raise RuntimeError(row.error_message) from exc

    violations = validate_originality(data)
    if violations:
        row.status = "FAILED"
        row.error_message = "Originality validation failed: " + "; ".join(violations)
        row.model = response.model
        db.commit()
        raise RuntimeError(row.error_message)

    row.commercial_analysis = data["commercial_analysis"]
    row.original_concept = data["original_concept"]
    row.prompt_a = data["prompt_a"]
    row.prompt_b = data["prompt_b"]
    row.prompt_c = data["prompt_c"]
    row.negative_prompt = data.get("negative_prompt")
    row.model = response.model
    prov = _provenance_of(response.provenance) if response.provenance else None
    row.data_provenance = prov or row.data_provenance
    row.status = "SUCCEEDED"
    db.commit()
    db.refresh(row)
    return row
