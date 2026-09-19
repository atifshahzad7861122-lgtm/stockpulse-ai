"""Prompt Studio engine — prompt package generation (docs: 14_PROMPT_ENGINE_SPECIFICATION).

Package sections (§3.1): primary, alternative, negative, technical, quality,
originality instructions (mandatory §4), compliance instructions (mandatory §5).

Regeneration creates a new version; versions are never overwritten.
Prompt quality self-score: /40, minimum bar 28 to be shown (§8).
Negative prompt: 3 layers, 15–40 terms (§11).
"""

from __future__ import annotations

from dataclasses import dataclass, field

TEMPLATE_VERSION = "prompt_tpl_v1.0"

# Quality evaluation criteria (§8): 8 criteria × 5 points, minimum bar 28/40
QUALITY_CRITERIA = (
    "specificity",
    "completeness",
    "originality_steering",
    "compliance_coverage",
    "tool_fit",
    "negative_prompt_strength",
    "commercial_clarity",
    "non_duplication",
)
QUALITY_BAR_MIN = 28
QUALITY_MAX = 40

# Negative prompt layers (§11)
NEGATIVE_UNIVERSAL_LAYER = (
    "watermark",
    "logo",
    "text",
    "blurry",
    "low resolution",
    "deformed",
    "distorted",
)
NEGATIVE_TARGET_MIN_TERMS = 15
NEGATIVE_TARGET_MAX_TERMS = 40

# Regeneration cap (docs: 13 §10): max 5 regenerations per concept per session
MAX_REGENERATIONS = 5

ORIGINALITY_INSTRUCTIONS = (
    "**ORIGINALITY INSTRUCTIONS (v1.0):** Create an original composition. Do not "
    "recreate, imitate, or closely follow any existing stock photo, stock video, "
    "or artwork you may have seen — including popular or trending images in this "
    "niche. Combine the subject, environment, lighting, and composition below in "
    "a way that is fresh and distinctive, not a variation of a familiar stock "
    "image. Avoid cliché framings of this subject. If the result looks like "
    "something you have seen before in a stock library, change the composition "
    "or viewpoint substantially. Do not reference any artist, photographer, or "
    "specific work. Originality checklist: subject originality, compositional "
    "originality, no copied visual concept."
)

COMPLIANCE_INSTRUCTIONS_PREAMBLE = (
    "**COMPLIANCE INSTRUCTIONS (rules v{rules_version}):** This asset is intended "
    "for Adobe Stock submission. The following rules apply to this concept:"
)
COMPLIANCE_INSTRUCTIONS_SUFFIX = (
    "These instructions reduce risk; they do not guarantee acceptance. "
    "Verdicts are risk assessments, not promises of Adobe Stock acceptance."
)

NICHE_CLICHE_NOTES = {
    # micro-niche slug → cliché to counter (maintained by Category Intelligence, §14 §4)
    "data-center-ai-computing": (
        "avoid the generic empty blue-lit symmetrical server corridor as the whole "
        "image — include the human interaction or hologram as the differentiator."
    ),
}

TOOL_FAMILY_NOTES = {
    "photoreal_diffusion": (
        "Weight subject tokens early; put camera/lighting as comma-separated "
        "modifiers; negative prompt is well-supported — use it fully; aspect ratio "
        "via tool settings, reinforced in prompt text."
    ),
    "illustration": (
        "Style tokens dominate — lead with style; simpler compositions perform "
        "better; specify 'flat colors, clean shapes' explicitly."
    ),
    "text_to_video": (
        "Motion must be described explicitly (camera move + subject move + "
        "duration); keep the scene simple — one motion idea per prompt; put "
        "critical avoidances in the primary prompt too."
    ),
    "cgi": (
        "Specify render qualities only where the tool supports them; geometry "
        "clarity beats texture verbosity."
    ),
}


@dataclass(frozen=True)
class PromptSelections:
    """User selections per docs/14 §2 (stored with the package version)."""

    asset_type: str  # "IMAGE" | "VIDEO"
    category: str
    micro_niche: str
    concept: str
    visual_style: str
    aspect_ratio: str
    orientation: str
    camera: str
    lighting: str
    environment: str
    subject: str
    composition: str
    commercial_use_case: str
    tool_family: str  # one of TOOL_FAMILY_NOTES keys
    duration_seconds: int | None = None
    fps: int | None = None


@dataclass(frozen=True)
class PromptPackage:
    primary_prompt: str
    alternative_prompt: str
    negative_prompt: str
    technical_requirements: str
    quality_requirements: str
    originality_instructions: str
    compliance_instructions: str
    tool_adaptation_notes: str
    quality_score: int
    quality_criteria: dict[str, int]
    selections: PromptSelections
    template_version: str = TEMPLATE_VERSION
    rules_version: str = "1.0.0"
    provenance: str = "MOCK"
    conflicts: tuple[str, ...] = field(default_factory=tuple)


def _detect_conflicts(sel: PromptSelections) -> tuple[str, ...]:
    conflicts: list[str] = []
    if (
        sel.visual_style == "photorealistic"
        and "drone" in sel.camera.lower()
        and "interior" in sel.environment.lower()
    ):
        conflicts.append(
            "Conflicting selections: drone aerial camera with an interior environment. "
            "Suggested minimal change: camera → 24mm wide."
        )
    if (
        sel.asset_type == "VIDEO"
        and sel.orientation == "portrait"
        and (sel.duration_seconds or 0) > 20
    ):
        conflicts.append(
            "High production risk: portrait video with long duration flagged for feasibility review."
        )
    return tuple(conflicts)


def build_negative_prompt(sel: PromptSelections, concept_risks: list[str]) -> str:
    """Negative prompt from 3 layers (§11): universal + concept-risk + style-counter."""
    terms: list[str] = list(NEGATIVE_UNIVERSAL_LAYER)

    # Concept-risk layer: people present → anatomical/IP terms; tech → brand terms
    text = f"{sel.concept} {sel.subject}".lower()
    people_present = any(
        w in text for w in ("person", "people", "technician", "hand", "face", "worker")
    )
    if people_present:
        terms += [
            "extra fingers",
            "malformed hands",
            "distorted face",
            "recognizable person",
            "celebrity",
        ]
    if any(w in text for w in ("server", "data center", "hardware", "device", "phone")):
        terms += ["brand name", "trademark", "brand mark"]
    terms += concept_risks

    # Style-counter layer
    if sel.visual_style == "flat illustration":
        terms += ["photorealistic", "3d render", "cluttered"]
    elif sel.visual_style == "photorealistic":
        terms += ["cartoon", "illustration", "oversaturated"]
    if sel.asset_type == "VIDEO":
        terms += ["flicker", "morphing geometry", "shaky camera", "low fps look"]

    # De-duplicate, preserve order
    seen: set[str] = set()
    unique = [t for t in terms if not (t in seen or seen.add(t))]
    return ", ".join(unique)


def build_compliance_instructions(rules: list[dict], rules_version: str = "1.0.0") -> str:
    """Render relevant compliance rules in plain language (§5)."""
    lines = [COMPLIANCE_INSTRUCTIONS_PREAMBLE.format(rules_version=rules_version)]
    for rule in rules:
        lines.append(f"— ({rule['rule_key']}) {rule['requirement_text']}")
    lines.append(COMPLIANCE_INSTRUCTIONS_SUFFIX)
    return " ".join(lines)


def generate_package(
    selections: PromptSelections,
    niche_slug: str | None = None,
    compliance_rules: list[dict] | None = None,
    concept_risks: list[str] | None = None,
    regenerate_from: PromptPackage | None = None,
) -> PromptPackage:
    """Generate a full prompt package (§3.1, §10 slot mapping)."""
    sel = selections
    conflicts = _detect_conflicts(sel)
    concept_risks = concept_risks or []

    lead = f"{sel.visual_style} {sel.asset_type.lower()}: {sel.subject}"
    setting = f"in {sel.environment}"
    framing = f"{sel.composition}, {sel.camera}, {sel.lighting} lighting"
    negative_space = (
        "with generous negative space in the upper third for headline text"
        if "landing page" in sel.commercial_use_case.lower()
        or "blog" in sel.commercial_use_case.lower()
        else ""
    )
    primary = (
        f"{lead} {setting}. {framing}. "
        f"Use case: {sel.commercial_use_case}. {negative_space} "
        f"Original composition, high-end commercial stock aesthetic."
    ).strip()

    if regenerate_from is not None:
        # Regenerate = a meaningfully different take, not a paraphrase (§7)
        alternative_seed = (
            f"Reworked take on the same concept with a substantially different "
            f"viewpoint: {sel.subject} {setting}, seen from an unexpected angle "
            f"({sel.camera} pushed to an extreme), {sel.lighting} lighting, "
            f"{sel.composition} deliberately broken for freshness."
        )
    else:
        alternative_seed = (
            f"Alternative take on the same concept: {sel.subject} {setting} from a "
            f"different viewpoint, {sel.lighting} lighting with a shifted mood "
            f"(warmer/cooler counterpoint), {sel.composition} varied — not a "
            f"paraphrase of the primary."
        )
    alternative = alternative_seed

    negative = build_negative_prompt(sel, concept_risks)

    if sel.asset_type == "VIDEO":
        technical = (
            f"{sel.aspect_ratio} ({sel.orientation}), ≥1080p, "
            f"{sel.fps or 24}fps, {sel.duration_seconds or 8}s, clean loop point where relevant. "
            "sRGB, master + working file retained."
        )
        quality = (
            "Temporally stable geometry (no morphing); smooth camera move; no flicker; "
            "clean blacks; tack-sharp focal subject."
        )
    else:
        pixel_target = {
            "16:9": "6000×3376",
            "3:2": "6000×4000",
            "1:1": "4096×4096",
            "4:3": "6000×4500",
            "9:16": "3376×6000",
        }.get(sel.aspect_ratio, "6000px on the long edge")
        technical = (
            f"{sel.aspect_ratio} {sel.orientation}, minimum 4 MP (target {pixel_target}), "
            "sRGB, JPEG/PNG master + working file retained."
        )
        quality = (
            "Tack-sharp on focal subject; clean edges; no visible noise in shadows; "
            "no compression banding in gradients."
        )

    cliche = NICHE_CLICHE_NOTES.get(niche_slug or "")
    originality = ORIGINALITY_INSTRUCTIONS + (f" Niche cliché note: {cliche}" if cliche else "")
    compliance = build_compliance_instructions(compliance_rules or [])

    tool_notes = TOOL_FAMILY_NOTES.get(
        sel.tool_family,
        "Adapted per family notes, unvalidated for this specific tool.",
    )

    criteria = {
        "specificity": 5 if len(sel.subject) > 10 and len(sel.environment) > 5 else 3,
        "completeness": 5,
        "originality_steering": 5,
        "compliance_coverage": 5 if compliance_rules else 2,
        "tool_fit": 4 if sel.tool_family in TOOL_FAMILY_NOTES else 2,
        "negative_prompt_strength": (
            5 if len(negative.split(",")) >= NEGATIVE_TARGET_MIN_TERMS else 3
        ),
        "commercial_clarity": 5 if sel.commercial_use_case else 3,
        "non_duplication": 4 if regenerate_from is not None else 5,
    }
    quality_score = sum(criteria.values())

    return PromptPackage(
        primary_prompt=primary,
        alternative_prompt=alternative,
        negative_prompt=negative,
        technical_requirements=technical,
        quality_requirements=quality,
        originality_instructions=originality,
        compliance_instructions=compliance,
        tool_adaptation_notes=tool_notes,
        quality_score=quality_score,
        quality_criteria=criteria,
        selections=sel,
        conflicts=conflicts,
    )


def meets_quality_bar(package: PromptPackage) -> bool:
    return package.quality_score >= QUALITY_BAR_MIN
