"""Metadata engine — title/description/keyword generator with anti-spam rules
(docs: 19_METADATA_ENGINE_SPECIFICATION).

The 7 anti-spam rules (SPAM-01…SPAM-07, docs/19 §5) are enforced on every
draft. Quality score formula: docs/19 §8.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Named constants (docs/19 §3–§4)
TITLE_MAX_CHARS = 200
TITLE_TARGET_MIN_CHARS = 70
TITLE_TARGET_MAX_CHARS = 140
DESCRIPTION_MAX_CHARS = 1000
DESCRIPTION_TARGET_MIN_CHARS = 200
DESCRIPTION_TARGET_MAX_CHARS = 500
KEYWORDS_MAX = 25
KEYWORDS_MIN = 10
KEYWORDS_TARGET_MIN = 15
KEYWORDS_TARGET_MAX = 20
DESCRIPTION_KEYWORD_DENSITY_MAX = 0.30

# Quality score weights (docs/19 §8)
Q_W_RELEVANCE = 0.30
Q_W_ORDERING = 0.15
Q_W_TITLE = 0.15
Q_W_DESCRIPTION = 0.15
Q_W_SPAM = 0.15
Q_W_DISCLOSURE = 0.10

# Quality bars (docs/19 §8)
QUALITY_REGENERATE_BELOW = 70
QUALITY_POLISH_MAX = 84

AI_DISCLOSURE_TEMPLATE = "This asset was created with the assistance of AI using {tool} on {date}."


@dataclass(frozen=True)
class SpamViolation:
    rule_id: str
    message: str
    offending_terms: tuple[str, ...]
    fix: str


_MISLEADING_CLAIMS = (
    "bestselling",
    "best-selling",
    "viral",
    "trending now",
    "award-winning",
    "guaranteed",
    "number one",
    "#1 bestseller",
)
_BAIT_TERMS = ("free download", "click here", "100% free", "wallpaper")
_PROHIBITED_NAME_HINTS = (
    "apple",
    "nike",
    "disney",
    "tesla",
    "taylor swift",
    "elon musk",
    "picasso",
    "mickey mouse",
)


def _stem(word: str) -> str:
    word = word.lower()
    for suffix in ("ing", "ies", "es", "s"):
        if word.endswith(suffix) and len(word) > len(suffix) + 2:
            if suffix == "ies":
                return word[:-3] + "y"
            return word[: -len(suffix)]
    return word


def _word_counts(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        stem = _stem(word)
        counts[stem] = counts.get(stem, 0) + 1
    return counts


def spam_check(title: str, description: str, keywords: list[str]) -> list[SpamViolation]:
    """Apply SPAM-01…SPAM-07 (docs/19 §5). Returns violations (empty = clean)."""
    violations: list[SpamViolation] = []
    combined = f"{title} {' '.join(keywords)}"

    # SPAM-01: keyword stuffing — no term (or stem) more than twice across title + keywords
    counts = _word_counts(combined)
    stuffed = sorted(s for s, c in counts.items() if c > 2 and len(s) > 2)
    if stuffed:
        violations.append(
            SpamViolation(
                rule_id="SPAM-01",
                message="Keyword stuffing: a term (or its stem) appears more than twice across title + keywords.",
                offending_terms=tuple(stuffed[:8]),
                fix="Remove repetitions; use each term at most twice.",
            )
        )

    # SPAM-02: irrelevant trending terms — heuristic: flagged trend-bait words not in content
    content_words = set(_word_counts(f"{title} {description}").keys())
    trend_bait = ("taylor swift", "crypto", "bitcoin", "world cup", "olympics")
    irrelevant = [
        t for t in trend_bait if t in combined.lower() and _stem(t.split()[0]) not in content_words
    ]
    if irrelevant:
        violations.append(
            SpamViolation(
                rule_id="SPAM-02",
                message="Irrelevant trending terms detected.",
                offending_terms=tuple(irrelevant),
                fix="Remove trending terms unrelated to the actual content.",
            )
        )

    # SPAM-03: misleading claims
    misleading = [t for t in _MISLEADING_CLAIMS if t in combined.lower()]
    if misleading:
        violations.append(
            SpamViolation(
                rule_id="SPAM-03",
                message="Misleading performance/quality claims presented as fact.",
                offending_terms=tuple(misleading),
                fix="Remove superlatives; describe only what is verifiable in the asset.",
            )
        )

    # SPAM-04: bait terms
    bait = [t for t in _BAIT_TERMS if t in combined.lower()]
    if bait:
        violations.append(
            SpamViolation(
                rule_id="SPAM-04",
                message="Generic high-traffic bait terms unrelated to content.",
                offending_terms=tuple(bait),
                fix="Remove bait terms unless the asset genuinely is that thing.",
            )
        )

    # SPAM-05: prohibited names (brands/artists/celebrities)
    names = [t for t in _PROHIBITED_NAME_HINTS if t in combined.lower()]
    if names:
        violations.append(
            SpamViolation(
                rule_id="SPAM-05",
                message="Brand/artist/celebrity names in metadata.",
                offending_terms=tuple(names),
                fix="Remove all brand, artist, and celebrity names from metadata.",
            )
        )

    # SPAM-06: title-keyword echo — keyword list must not be a comma-split copy of title
    title_tokens = set(_word_counts(title).keys())
    keyword_tokens = set(_word_counts(" ".join(keywords)).keys())
    if (
        title_tokens
        and keyword_tokens
        and title_tokens <= keyword_tokens
        and len(keywords) <= len(title.split()) + 2
    ):
        violations.append(
            SpamViolation(
                rule_id="SPAM-06",
                message="Keyword list echoes the title instead of adding discoverability terms.",
                offending_terms=tuple(sorted(title_tokens)[:8]),
                fix="Add specific secondary terms (environment, objects, style, use case) beyond the title words.",
            )
        )

    # SPAM-07: description stuffing — keyword density ≤ 30% of description tokens
    if description:
        desc_tokens = re.findall(r"[a-z0-9]+", description.lower())
        kw_stems = {_stem(w) for k in keywords for w in re.findall(r"[a-z0-9]+", k.lower())}
        if desc_tokens:
            density = sum(1 for t in desc_tokens if _stem(t) in kw_stems) / len(desc_tokens)
            if density > DESCRIPTION_KEYWORD_DENSITY_MAX:
                violations.append(
                    SpamViolation(
                        rule_id="SPAM-07",
                        message=f"Description reads as a keyword list (density {density:.0%} > 30%).",
                        offending_terms=(),
                        fix="Rewrite the description as prose: 1–3 sentences about content, mood, and use case.",
                    )
                )

    return violations


@dataclass(frozen=True)
class MetadataDraft:
    title: str
    description: str
    keywords: tuple[str, ...]
    adobe_category: str | None
    language: str
    ai_disclosure: str
    quality_score: float
    spam_violations: tuple[SpamViolation, ...]
    provenance: str = "MOCK"


def build_title(subject: str, descriptor: str, use_case_hint: str) -> str:
    """[Primary subject] + [key visual descriptor] + [context/use-case hint] (§3.1)."""
    title = f"{subject} {descriptor} {use_case_hint}".strip()
    title = re.sub(r"\s+", " ", title)
    return title[:TITLE_MAX_CHARS]


def build_description(literal: str, mood: str, use_case: str) -> str:
    """Sentence 1: literal content. Sentence 2: mood/style. Sentence 3: use case (§3.2)."""
    parts = [literal.strip()]
    if mood.strip():
        parts.append(mood.strip())
    if use_case.strip():
        parts.append(use_case.strip())
    description = " ".join(p for p in parts if p)
    return description[:DESCRIPTION_MAX_CHARS]


def order_keywords(
    primary: list[str], secondary: list[str], style_mood: list[str], broad: list[str]
) -> list[str]:
    """Ordering strategy §4.2: specific → general; dedupe; cap at 25."""
    ordered: list[str] = []
    seen: set[str] = set()
    for group in (primary, secondary, style_mood, broad):
        for kw in group:
            key = kw.strip().lower()
            if key and key not in seen:
                seen.add(key)
                ordered.append(kw.strip())
    return ordered[:KEYWORDS_MAX]


def quality_score(
    relevance: float,
    ordering: float,
    title_quality: float,
    description_quality: float,
    spam_clean: float,
    disclosure_complete: float,
) -> float:
    """metadata_quality_score 0–100 (docs/19 §8)."""
    return round(
        Q_W_RELEVANCE * relevance * 100
        + Q_W_ORDERING * ordering * 100
        + Q_W_TITLE * title_quality * 100
        + Q_W_DESCRIPTION * description_quality * 100
        + Q_W_SPAM * spam_clean * 100
        + Q_W_DISCLOSURE * disclosure_complete * 100,
        2,
    )


def draft_metadata(
    subject: str,
    descriptor: str,
    use_case_hint: str,
    literal_sentence: str,
    mood_sentence: str,
    use_case_sentence: str,
    keyword_groups: dict[str, list[str]],
    adobe_category: str | None,
    generation_tool: str | None,
    generation_date: str | None,
    descriptor_set: set[str] | None = None,
) -> MetadataDraft:
    """Generate a metadata draft with spam checks + quality score."""
    title = build_title(subject, descriptor, use_case_hint)
    description = build_description(literal_sentence, mood_sentence, use_case_sentence)
    keywords = tuple(
        order_keywords(
            keyword_groups.get("primary", []),
            keyword_groups.get("secondary", []),
            keyword_groups.get("style_mood", []),
            keyword_groups.get("broad", []),
        )
    )
    violations = tuple(spam_check(title, description, list(keywords)))

    descriptor_set = descriptor_set or set()
    if descriptor_set and keywords:
        relevance = sum(1 for k in keywords if any(d in k.lower() for d in descriptor_set)) / len(
            keywords
        )
    else:
        relevance = 0.8  # heuristic when no descriptor set supplied
    ordering = 1.0  # order_keywords() always emits specific → general
    title_quality = (
        1.0
        if TITLE_TARGET_MIN_CHARS <= len(title) <= TITLE_TARGET_MAX_CHARS
        else 0.8 if len(title) <= TITLE_MAX_CHARS and len(title) > 0 else 0.0
    )
    description_quality = (
        1.0
        if DESCRIPTION_TARGET_MIN_CHARS <= len(description) <= DESCRIPTION_TARGET_MAX_CHARS
        else 0.8 if len(description) <= DESCRIPTION_MAX_CHARS and len(description) > 0 else 0.0
    )
    spam_clean = 1.0 if not violations else 0.0
    disclosure_complete = 1.0 if (generation_tool and generation_date) else 0.0

    score = quality_score(
        relevance, ordering, title_quality, description_quality, spam_clean, disclosure_complete
    )
    disclosure = AI_DISCLOSURE_TEMPLATE.format(
        tool=generation_tool or "unknown tool", date=generation_date or "unknown date"
    )
    return MetadataDraft(
        title=title,
        description=description,
        keywords=keywords,
        adobe_category=adobe_category,
        language="en",
        ai_disclosure=disclosure,
        quality_score=score,
        spam_violations=violations,
    )


def validate_bundle(title: str, description: str | None, keywords: list[str]) -> list[dict]:
    """Validate a metadata bundle → issues list for POST /metadata/{id}/validate."""
    issues: list[dict] = []
    if not title.strip():
        issues.append(
            {"code": "TITLE_MISSING", "message": "Title is required.", "severity": "error"}
        )
    elif len(title) > TITLE_MAX_CHARS:
        issues.append(
            {
                "code": "TITLE_TOO_LONG",
                "message": f"Title exceeds {TITLE_MAX_CHARS} characters.",
                "severity": "error",
            }
        )
    if len(keywords) > KEYWORDS_MAX:
        issues.append(
            {
                "code": "KEYWORD_COUNT_EXCEEDED",
                "message": f"Keyword count {len(keywords)} exceeds {KEYWORDS_MAX}.",
                "severity": "error",
            }
        )
    if len(keywords) < KEYWORDS_MIN:
        issues.append(
            {
                "code": "KEYWORD_COUNT_LOW",
                "message": f"Keyword count {len(keywords)} below minimum {KEYWORDS_MIN}.",
                "severity": "warning",
            }
        )
    lowered = [k.lower() for k in keywords]
    if len(set(lowered)) != len(lowered):
        issues.append(
            {
                "code": "KEYWORD_DUPLICATES",
                "message": "Duplicate keywords detected.",
                "severity": "warning",
            }
        )
    for v in spam_check(title, description or "", keywords):
        issues.append(
            {"code": v.rule_id, "message": f"{v.message} Fix: {v.fix}", "severity": "error"}
        )
    return issues
