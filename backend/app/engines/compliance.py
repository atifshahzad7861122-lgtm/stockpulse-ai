"""Compliance rule engine — screens concepts/prompts/metadata against the 28
seeded rules (docs: 18_COMPLIANCE_ENGINE_SPECIFICATION, SEED_PLAN.md §4).

Scope limitation (documented): we analyze text fields (concepts, prompts,
metadata), not pixels. `model_assisted`/`human_review` rules cannot be executed
by pure code — they return REVIEW findings flagged "requires human review".
Fail-closed: check errors or unevaluatable rules → REVIEW, never PASS.

Severity mapping (SEED_PLAN.md §4): blocker → HIGH_RISK, major → REVIEW,
minor → REVIEW (low weight). One HIGH_RISK finding → HIGH_RISK overall.
3 minor findings in one report escalate to HIGH_RISK.

Language: outcomes say "assessed as", never "guaranteed acceptance".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.enums import RuleSeverity

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------
RULES_VERSION = "1.0.0"
MINORS_ESCALATE_THRESHOLD = 3

# Heuristic tripwire lists (documented as illustrative, non-exhaustive).
# These are examples used for pattern screening; absence of a match is NOT a
# clearance — human review is still required for the model_assisted rules.
_BRAND_KEYWORDS = (
    "apple",
    "nike",
    "coca-cola",
    "coca cola",
    "pepsi",
    "adidas",
    "samsung",
    "google",
    "microsoft",
    "amazon",
    "tesla",
    "bmw",
    "mercedes",
    "lego",
    "disney",
    "mcdonald's",
    "mcdonalds",
    "starbucks",
    "louis vuitton",
)
_CHARACTER_KEYWORDS = (
    "mickey mouse",
    "batman",
    "superman",
    "spider-man",
    "spiderman",
    "pikachu",
    "hello kitty",
    "darth vader",
    "harry potter",
    "mario",
)
_CELEBRITY_KEYWORDS = (
    "taylor swift",
    "elon musk",
    "beyonce",
    "leonardo dicaprio",
    "cristiano ronaldo",
    "kim kardashian",
)
_MISLEADING_CLAIMS = (
    "bestselling",
    "best-selling",
    "viral",
    "trending now",
    "award-winning",
    "guaranteed",
    "#1",
    "number one bestseller",
)
_BAIT_TERMS = ("free download", "click here", "100% free")

MIN_IMAGE_MEGAPIXELS = 4.0
MIN_VIDEO_HEIGHT_PX = 1080

_KNOWN_ADOBE_CATEGORIES = (
    # Common Adobe Stock buyer categories (non-authoritative subset; the full
    # current list must be verified against Adobe's published categories).
    "animals",
    "business",
    "technology",
    "people",
    "nature",
    "travel",
    "food",
    "lifestyle",
    "healthcare",
    "education",
    "sports",
    "architecture",
    "science",
    "abstract",
    "backgrounds",
    "textures",
    "fashion",
    "beauty",
)


@dataclass(frozen=True)
class RuleFinding:
    rule_key: str
    rule_version: str
    severity: RuleSeverity  # INFO | WARN | BLOCK
    triggered: bool
    explanation: str
    matched_excerpt: str | None = None
    remediation: str | None = None


@dataclass(frozen=True)
class ComplianceResult:
    result: str  # PASS | REVIEW | HIGH_RISK
    risk_level: str  # LOW | MEDIUM | HIGH | CRITICAL
    findings: tuple[RuleFinding, ...]
    explanation: str
    rules_version: str = RULES_VERSION


@dataclass
class ScreenSubject:
    """Text + metadata fields of the subject being screened."""

    prompt_text: str = ""
    negative_prompt_text: str = ""
    concept: str = ""
    originality_notes: str = ""
    title: str = ""
    description: str = ""
    keywords: tuple[str, ...] = ()
    adobe_category: str | None = None
    ai_disclosure: bool | None = None
    generation_tool: str | None = None
    generation_date: str | None = None
    width_px: int | None = None
    height_px: int | None = None
    asset_type: str = "IMAGE"


def _contains_any(text: str, terms: tuple[str, ...]) -> str | None:
    lowered = text.lower()
    for term in terms:
        if term.lower() in lowered:
            return term
    return None


def _pattern_found(text: str, pattern: str) -> re.Match | None:
    return re.search(pattern, text, re.IGNORECASE)


def _finding(
    rule_key: str,
    severity: RuleSeverity,
    triggered: bool,
    explanation: str,
    matched_excerpt: str | None = None,
    remediation: str | None = None,
) -> RuleFinding:
    return RuleFinding(
        rule_key=rule_key,
        rule_version=RULES_VERSION,
        severity=severity,
        triggered=triggered,
        explanation=explanation,
        matched_excerpt=matched_excerpt,
        remediation=remediation,
    )


# ---------------------------------------------------------------------------
# Automated check implementations (one per rule_key that is machine-checkable)
# ---------------------------------------------------------------------------


def check_gen_01(subject: ScreenSubject) -> RuleFinding:
    if subject.ai_disclosure is True:
        return _finding(
            "gen-01", RuleSeverity.BLOCK, False, "AI-generated disclosure flag is present and set."
        )
    return _finding(
        "gen-01",
        RuleSeverity.BLOCK,
        True,
        "AI-generated disclosure flag is missing or not set on the asset record.",
        remediation="Set the AI-generated disclosure flag before submission.",
    )


def check_gen_02(subject: ScreenSubject) -> RuleFinding:
    if subject.generation_tool:
        return _finding(
            "gen-02", RuleSeverity.WARN, False, f"Generating tool named: {subject.generation_tool}."
        )
    return _finding(
        "gen-02",
        RuleSeverity.WARN,
        True,
        "No generating tool/model recorded; the disclosure must name the actual tool.",
        remediation="Record the exact tool/model from the generation record.",
    )


def check_gen_03(subject: ScreenSubject) -> RuleFinding:
    if subject.generation_date:
        return _finding(
            "gen-03",
            RuleSeverity.INFO,
            False,
            f"Generation date recorded: {subject.generation_date}.",
        )
    return _finding(
        "gen-03",
        RuleSeverity.INFO,
        True,
        "Generation date not recorded.",
        remediation="Record the generation date (ISO 8601).",
    )


def check_gen_04(subject: ScreenSubject) -> RuleFinding:
    text = f"{subject.prompt_text} {subject.concept}"
    patterns = (
        r"hide.{0,20}(ai|artificial intelligence)",
        r"(don'?t|do not).{0,20}mention.{0,20}ai",
        r"pass.{0,20}as.{0,20}(real|genuine|photo)",
        r"undisclosed",
    )
    for pattern in patterns:
        m = _pattern_found(text, pattern)
        if m:
            return _finding(
                "gen-04",
                RuleSeverity.BLOCK,
                True,
                "Prompt language instructs concealing the AI origin of the asset.",
                matched_excerpt=m.group(0),
                remediation="Remove language that hides AI origin; disclosure is mandatory.",
            )
    return _finding(
        "gen-04", RuleSeverity.BLOCK, False, "No AI-origin concealment language detected."
    )


def check_ip_01(subject: ScreenSubject) -> RuleFinding:
    text = f"{subject.prompt_text} {subject.concept} {subject.title}"
    m = _pattern_found(text, r"\blogo(s)?\b|\bbrand(ing|ed)?\s+(mark|packaging)\b")
    if m:
        return _finding(
            "ip-01",
            RuleSeverity.BLOCK,
            True,
            "Possible logo/brand-mark reference detected in text fields.",
            matched_excerpt=m.group(0),
            remediation="Remove logo references or flag the asset for manual review.",
        )
    return _finding(
        "ip-01",
        RuleSeverity.BLOCK,
        False,
        "No logo/brand-mark reference detected in text. Visual check still required (model-assisted).",
    )


def check_ip_02(subject: ScreenSubject) -> RuleFinding:
    text = f"{subject.prompt_text} {subject.concept} {' '.join(subject.keywords)}"
    hit = _contains_any(text, _BRAND_KEYWORDS)
    if hit:
        return _finding(
            "ip-02",
            RuleSeverity.BLOCK,
            True,
            f"Possible trademark term detected: '{hit}'.",
            matched_excerpt=hit,
            remediation="Remove the trademark term; this list is illustrative, not exhaustive.",
        )
    return _finding(
        "ip-02", RuleSeverity.BLOCK, False, "No trademark terms from the heuristic list detected."
    )


def check_ip_03(subject: ScreenSubject) -> RuleFinding:
    text = f"{subject.prompt_text} {subject.concept}"
    hit = _contains_any(text, _CHARACTER_KEYWORDS)
    if hit:
        return _finding(
            "ip-03",
            RuleSeverity.BLOCK,
            True,
            f"Possible copyrighted character reference: '{hit}'.",
            matched_excerpt=hit,
            remediation="Remove the character reference entirely.",
        )
    return _finding(
        "ip-03",
        RuleSeverity.BLOCK,
        False,
        "No copyrighted-character terms from the heuristic list detected.",
    )


def check_ip_04(subject: ScreenSubject) -> RuleFinding:
    text = f"{subject.prompt_text} {subject.concept}"
    hit = _contains_any(text, _CELEBRITY_KEYWORDS)
    if hit:
        return _finding(
            "ip-04",
            RuleSeverity.BLOCK,
            True,
            f"Possible celebrity/public-figure likeness reference: '{hit}'.",
            matched_excerpt=hit,
            remediation="Remove any depiction or reference to real, recognizable people.",
        )
    return _finding(
        "ip-04",
        RuleSeverity.BLOCK,
        False,
        "No celebrity-likeness terms from the heuristic list detected.",
    )


def check_ip_05(subject: ScreenSubject) -> RuleFinding:
    text = f"{subject.prompt_text} {subject.concept}"
    m = _pattern_found(text, r"in the style of\s+([A-Z][a-zA-Z'’\- ]{1,40})")
    if m:
        return _finding(
            "ip-05",
            RuleSeverity.BLOCK,
            True,
            "Artist-style request detected ('in the style of …').",
            matched_excerpt=m.group(0),
            remediation="Remove the artist-name style request; describe the style in neutral terms.",
        )
    return _finding("ip-05", RuleSeverity.BLOCK, False, "No living-artist style request detected.")


def check_ip_06(subject: ScreenSubject) -> RuleFinding:
    text = f"{subject.prompt_text} {subject.concept}"
    m = _pattern_found(text, r"\b(album|book|movie)\s+(cover|poster)\b|distinctive design")
    if m:
        return _finding(
            "ip-06",
            RuleSeverity.BLOCK,
            True,
            "Possible reference to recognizable copyrighted material.",
            matched_excerpt=m.group(0),
            remediation="Remove the reference; create original artwork references only.",
        )
    return _finding(
        "ip-06",
        RuleSeverity.BLOCK,
        False,
        "No recognizable-copyrighted-material pattern detected in text.",
    )


def check_ip_07(subject: ScreenSubject) -> RuleFinding:
    text = " ".join(subject.keywords)
    hit = _contains_any(text, _BRAND_KEYWORDS + _CHARACTER_KEYWORDS + _CELEBRITY_KEYWORDS)
    if hit:
        return _finding(
            "ip-07",
            RuleSeverity.WARN,
            True,
            f"Metadata keyword may carry IP risk: '{hit}'.",
            matched_excerpt=hit,
            remediation="Remove brand/artist/celebrity names from keywords (spam + IP risk).",
        )
    return _finding(
        "ip-07", RuleSeverity.WARN, False, "No brand/artist/celebrity names in keywords."
    )


def check_ip_08(subject: ScreenSubject) -> RuleFinding:
    text = f"{subject.concept} {subject.originality_notes}"
    m = _pattern_found(text, r"inspired by\s+([A-Z][a-zA-Z'’\- ]{1,40})")
    if m:
        return _finding(
            "ip-08",
            RuleSeverity.WARN,
            True,
            "'Inspired by' language referencing an identifiable source detected.",
            matched_excerpt=m.group(0),
            remediation="Describe the concept without referencing identifiable individual works.",
        )
    return _finding(
        "ip-08",
        RuleSeverity.WARN,
        False,
        "No 'inspired by' reference to identifiable works detected.",
    )


def check_tq_01(subject: ScreenSubject) -> RuleFinding:
    if subject.asset_type == "VIDEO":
        if subject.height_px and subject.height_px >= MIN_VIDEO_HEIGHT_PX:
            return _finding(
                "tq-01",
                RuleSeverity.BLOCK,
                False,
                f"Video height {subject.height_px}px meets 1080p minimum.",
            )
        return _finding(
            "tq-01",
            RuleSeverity.BLOCK,
            True,
            "Video resolution below 1080p minimum or unknown.",
            remediation="Export at ≥1080p.",
        )
    if subject.width_px and subject.height_px:
        mp = (subject.width_px * subject.height_px) / 1_000_000
        if mp >= MIN_IMAGE_MEGAPIXELS:
            return _finding(
                "tq-01",
                RuleSeverity.BLOCK,
                False,
                f"Image resolution {mp:.1f} MP meets the 4 MP minimum.",
            )
        return _finding(
            "tq-01",
            RuleSeverity.BLOCK,
            True,
            f"Image resolution {mp:.1f} MP below the 4 MP minimum.",
            remediation="Upscale or regenerate at higher resolution.",
        )
    return _finding(
        "tq-01",
        RuleSeverity.BLOCK,
        False,
        "Resolution unknown from available fields — verify manually before production.",
    )


def _unverifiable_visual(rule_key: str, severity: RuleSeverity, what: str) -> RuleFinding:
    return _finding(
        rule_key,
        severity,
        False,
        f"{what} cannot be evaluated from text/metadata fields alone; "
        "visual inspection is required before submission.",
        remediation="Inspect the rendered asset visually for this criterion.",
    )


def check_mh_01(subject: ScreenSubject) -> RuleFinding:
    if not subject.title.strip():
        return _finding(
            "mh-01",
            RuleSeverity.INFO,
            True,
            "Title is missing.",
            remediation="Add an accurate, descriptive title.",
        )
    if len(subject.title) > 200:
        return _finding(
            "mh-01",
            RuleSeverity.INFO,
            True,
            f"Title is {len(subject.title)} characters (limit 200).",
            remediation="Shorten the title to ≤ 200 characters.",
        )
    return _finding("mh-01", RuleSeverity.INFO, False, "Title present and within length limits.")


def check_mh_02(subject: ScreenSubject) -> RuleFinding:
    if subject.description and len(subject.description) > 1000:
        return _finding(
            "mh-02",
            RuleSeverity.INFO,
            True,
            f"Description is {len(subject.description)} characters (limit 1000).",
            remediation="Shorten the description to ≤ 1000 characters.",
        )
    if not subject.description:
        return _finding(
            "mh-02",
            RuleSeverity.INFO,
            True,
            "Description missing.",
            remediation="Add a 1–3 sentence description.",
        )
    return _finding("mh-02", RuleSeverity.INFO, False, "Description present and within limits.")


def check_mh_03(subject: ScreenSubject) -> RuleFinding:
    n = len(subject.keywords)
    if n > 25:
        return _finding(
            "mh-03",
            RuleSeverity.INFO,
            True,
            f"Keyword count {n} exceeds the 25-keyword limit.",
            remediation="Trim to 15–20 most relevant keywords.",
        )
    if n < 10:
        return _finding(
            "mh-03",
            RuleSeverity.INFO,
            True,
            f"Keyword count {n} below the 10-keyword minimum.",
            remediation="Add relevant keywords (target 15–20).",
        )
    lowered = [k.lower() for k in subject.keywords]
    if len(set(lowered)) != len(lowered):
        return _finding(
            "mh-03",
            RuleSeverity.INFO,
            True,
            "Duplicate keywords detected.",
            remediation="Remove duplicates.",
        )
    return _finding(
        "mh-03", RuleSeverity.INFO, False, f"Keyword count {n} within limits; no duplicates."
    )


def check_mh_04(subject: ScreenSubject) -> RuleFinding:
    from app.engines.metadata import spam_check

    violations = spam_check(
        title=subject.title, description=subject.description or "", keywords=list(subject.keywords)
    )
    if violations:
        worst = violations[0]
        return _finding(
            "mh-04",
            RuleSeverity.WARN,
            True,
            f"Spam rule violated: {worst.rule_id} — {worst.message}",
            matched_excerpt=", ".join(worst.offending_terms[:5]),
            remediation=worst.fix,
        )
    return _finding(
        "mh-04", RuleSeverity.WARN, False, "No spam violations detected (SPAM-01…SPAM-07)."
    )


def check_mh_05(subject: ScreenSubject) -> RuleFinding:
    if not subject.adobe_category:
        return _finding(
            "mh-05",
            RuleSeverity.INFO,
            True,
            "No Adobe category mapped.",
            remediation="Map to an Adobe Stock category.",
        )
    if subject.adobe_category.lower() in _KNOWN_ADOBE_CATEGORIES:
        return _finding(
            "mh-05",
            RuleSeverity.INFO,
            False,
            f"Category '{subject.adobe_category}' is a recognized category.",
        )
    return _finding(
        "mh-05",
        RuleSeverity.INFO,
        True,
        f"Category '{subject.adobe_category}' not in the known category list — verify against Adobe's current categories.",
        remediation="Verify the category against Adobe's current category list.",
    )


def check_mh_06(
    subject: ScreenSubject, existing_fingerprints: list[str] | None = None
) -> RuleFinding:
    """Near-duplicate vs submitted assets: corpus entries are canonical token
    strings ("tok1|tok2|…") so Jaccard comparison is possible, not just exact match."""
    from app.engines.similarity import canonical_token_string, max_token_similarity

    if not existing_fingerprints:
        return _finding(
            "mh-06",
            RuleSeverity.WARN,
            False,
            "No submitted-asset fingerprint store available; near-duplicate check deferred.",
        )
    tokens = canonical_token_string(f"{subject.title} {subject.concept}")
    best = max_token_similarity(tokens, existing_fingerprints)
    if best >= 0.90:
        return _finding(
            "mh-06",
            RuleSeverity.WARN,
            True,
            f"Near-duplicate of an already-submitted asset (similarity {best:.2f} ≥ 0.90).",
            remediation="Do not resubmit; create a materially different asset.",
        )
    return _finding(
        "mh-06",
        RuleSeverity.WARN,
        False,
        f"No near-duplicate detected (best similarity {best:.2f}).",
    )


# Automated rules per check type (rule_key → implementation).
AUTOMATED_CHECKS: dict[str, dict] = {
    "gen-01": {"fn": check_gen_01, "types": ("PROMPT_SCREEN", "ASSET_SCREEN")},
    "gen-02": {"fn": check_gen_02, "types": ("PROMPT_SCREEN", "ASSET_SCREEN")},
    "gen-03": {"fn": check_gen_03, "types": ("PROMPT_SCREEN", "ASSET_SCREEN")},
    "gen-04": {"fn": check_gen_04, "types": ("PROMPT_SCREEN", "ASSET_SCREEN")},
    "ip-01": {"fn": check_ip_01, "types": ("PROMPT_SCREEN", "ASSET_SCREEN", "METADATA_SCREEN")},
    "ip-02": {"fn": check_ip_02, "types": ("PROMPT_SCREEN", "ASSET_SCREEN", "METADATA_SCREEN")},
    "ip-03": {"fn": check_ip_03, "types": ("PROMPT_SCREEN", "ASSET_SCREEN", "METADATA_SCREEN")},
    "ip-04": {"fn": check_ip_04, "types": ("PROMPT_SCREEN", "ASSET_SCREEN", "METADATA_SCREEN")},
    "ip-05": {"fn": check_ip_05, "types": ("PROMPT_SCREEN", "ASSET_SCREEN", "METADATA_SCREEN")},
    "ip-06": {"fn": check_ip_06, "types": ("PROMPT_SCREEN", "ASSET_SCREEN", "METADATA_SCREEN")},
    "ip-07": {"fn": check_ip_07, "types": ("PROMPT_SCREEN", "ASSET_SCREEN", "METADATA_SCREEN")},
    "ip-08": {"fn": check_ip_08, "types": ("PROMPT_SCREEN", "ASSET_SCREEN", "METADATA_SCREEN")},
    "tq-01": {"fn": check_tq_01, "types": ("ASSET_SCREEN",)},
    "mh-01": {"fn": check_mh_01, "types": ("METADATA_SCREEN", "ASSET_SCREEN")},
    "mh-02": {"fn": check_mh_02, "types": ("METADATA_SCREEN", "ASSET_SCREEN")},
    "mh-03": {"fn": check_mh_03, "types": ("METADATA_SCREEN", "ASSET_SCREEN")},
    "mh-04": {"fn": check_mh_04, "types": ("METADATA_SCREEN", "ASSET_SCREEN")},
    "mh-05": {"fn": check_mh_05, "types": ("METADATA_SCREEN", "ASSET_SCREEN")},
    "mh-06": {"fn": check_mh_06, "types": ("METADATA_SCREEN", "ASSET_SCREEN")},
}

# Rules that cannot run automatically: flagged REVIEW with an explanation.
NON_AUTOMATED_RULES = {
    "tq-02": "Noise/grain assessment requires pixel analysis of the rendered asset.",
    "tq-03": "Blur/focus assessment requires pixel analysis of the rendered asset.",
    "tq-04": "Compression artifact assessment requires pixel analysis of the rendered asset.",
    "tq-05": "Anatomical-error assessment requires visual inspection (model-assisted).",
    "tq-06": "Image artifact inspection requires visual inspection (model-assisted).",
    "tq-07": "Video artifact inspection requires keyframe analysis (model-assisted).",
    "tq-08": "Exposure/color assessment requires pixel analysis of the rendered asset.",
    "mh-07": "Commercial usefulness judgment requires human review.",
    "mh-08": "Release logic requires human review (recognizable people/property).",
}

SEVERITY_TO_RESULT = {
    RuleSeverity.INFO: "REVIEW",
    RuleSeverity.WARN: "REVIEW",
    RuleSeverity.BLOCK: "HIGH_RISK",
}


@dataclass(frozen=True)
class RuleSpec:
    rule_key: str
    severity: RuleSeverity  # INFO | WARN | BLOCK
    check_method: str  # automated | model_assisted | human_review
    applies_to: tuple[str, ...]


def run_screen(
    check_type: str,
    subject: ScreenSubject,
    rules: list[RuleSpec],
    existing_fingerprints: list[str] | None = None,
) -> ComplianceResult:
    """Run the compliance screen. Fail-closed: errors → REVIEW, never PASS."""
    findings: list[RuleFinding] = []

    for rule in rules:
        if check_type not in rule.applies_to:
            continue
        try:
            if rule.check_method == "automated" and rule.rule_key in AUTOMATED_CHECKS:
                impl = AUTOMATED_CHECKS[rule.rule_key]["fn"]
                if rule.rule_key == "mh-06":
                    findings.append(impl(subject, existing_fingerprints))
                else:
                    findings.append(impl(subject))
            else:
                reason = NON_AUTOMATED_RULES.get(
                    rule.rule_key, "This rule requires human or model-assisted review."
                )
                findings.append(
                    _finding(
                        rule.rule_key,
                        rule.severity,
                        False,
                        f"Not evaluated automatically: {reason} Fail-closed — flagged for human review.",
                        remediation="Complete this check manually before proceeding.",
                    )
                )
        except Exception as exc:  # fail closed per docs/26 §4.7
            findings.append(
                _finding(
                    rule.rule_key,
                    rule.severity,
                    False,
                    f"Check could not run ({type(exc).__name__}); fail-closed — flagged for review.",
                    remediation="Re-run the check or complete it manually.",
                )
            )

    triggered = [f for f in findings if f.triggered]
    high_risk = [f for f in triggered if f.severity == RuleSeverity.BLOCK]
    minor_triggered = [f for f in triggered if f.severity == RuleSeverity.INFO]

    # 3 minors escalate to HIGH_RISK (SEED_PLAN.md §4)
    escalated = len(minor_triggered) >= MINORS_ESCALATE_THRESHOLD
    if high_risk or escalated:
        result = "HIGH_RISK"
    elif triggered or any(
        "Fail-closed" in f.explanation or "Not evaluated automatically" in f.explanation
        for f in findings
    ):
        result = "REVIEW"
    else:
        result = "PASS"

    if result == "HIGH_RISK":
        risk_level = "CRITICAL" if len(high_risk) >= 2 else "HIGH"
        explanation = (
            "Assessed as HIGH_RISK: "
            + "; ".join(f"{f.rule_key}: {f.explanation}" for f in triggered[:3])
            + ". Strongly recommended not to proceed without changes. "
            "This is a risk assessment, not a prediction of Adobe Stock acceptance."
        )
    elif result == "REVIEW":
        risk_level = "HIGH" if len(triggered) >= 3 else "MEDIUM"
        explanation = (
            "Assessed as REVIEW: "
            + (
                "; ".join(f"{f.rule_key}: {f.explanation}" for f in triggered[:3])
                if triggered
                else "one or more checks require human completion."
            )
            + " Human review is required before proceeding."
        )
    else:
        risk_level = "LOW"
        explanation = (
            "Assessed as PASS: no rule triggered. This is a risk assessment of the "
            "text fields screened; it does not guarantee Adobe Stock acceptance."
        )

    return ComplianceResult(
        result=result,
        risk_level=risk_level,
        findings=tuple(findings),
        explanation=explanation,
    )
