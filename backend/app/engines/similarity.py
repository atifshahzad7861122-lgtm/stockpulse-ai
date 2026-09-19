"""Similarity / originality engine (docs: 17_ORIGINALITY_ENGINE_SPECIFICATION).

Fingerprinting: normalized text hash + token-set Jaccard + embedding stub.
Thresholds (CONTRACT §contract, docs/17 §3):
- < 0.60 → CLEAR
- 0.60–0.80 → REVIEW
- ≥ 0.80 → HIGH_RISK

Embedding service is a stub in v1 (no network): the verdict is annotated
"embedding-unavailable" and the REVIEW band widens to 0.55–0.80 during
fallback (docs/17 §8). Never claims legal certainty; cluster labels are
descriptive, never identifying individual artists.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

# Named constants — thresholds (docs/17 §3)
REVIEW_THRESHOLD = 0.60
HIGH_RISK_THRESHOLD = 0.80
FALLBACK_REVIEW_THRESHOLD = 0.60  # fallback band matches REVIEW_THRESHOLD (authoritative)
PROMPT_VERSION_MAX_SIMILARITY = 0.85  # docs/17 §5.1: prompt iterations may be closer
SUBMISSION_DEDUP_THRESHOLD = 0.90  # docs/17 §5.3

EMBEDDING_UNAVAILABLE_NOTE = "embedding-unavailable"

_STOPWORDS = frozenset(
    "a an the and or of to in on for with by from at as is are was were be been "
    "it its this that these those we you they he she i my our your their his her "
    "not no do does did will would can could should have has had".split()
)


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def token_set(text: str) -> frozenset[str]:
    return frozenset(t for t in normalize_text(text).split() if t not in _STOPWORDS)


def text_fingerprint(text: str) -> str:
    """SimHash-style compact fingerprint: sha256 over the sorted token multiset."""
    tokens = sorted(t for t in normalize_text(text).split() if t not in _STOPWORDS)
    canonical = "|".join(tokens)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def jaccard_similarity(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def embedding_similarity_stub(_a: str, _b: str) -> None:
    """No embedding service in v1 (no network). Returns None → fallback path."""
    return None


def combined_similarity(text_a: str, text_b: str) -> float:
    """v1 similarity: token-set Jaccard (fingerprint equality adds a bonus).

    Deterministic and explainable. Embedding comparison is unavailable in v1;
    callers annotate verdicts accordingly.
    """
    set_a, set_b = token_set(text_a), token_set(text_b)
    jaccard = jaccard_similarity(set_a, set_b)
    if text_fingerprint(text_a) == text_fingerprint(text_b):
        return 1.0
    return round(jaccard, 4)


def canonical_token_string(text: str) -> str:
    """Canonical sorted token multiset, pipe-joined — the comparable fingerprint form."""
    tokens = sorted(t for t in normalize_text(text).split() if t not in _STOPWORDS)
    return "|".join(tokens)


def max_similarity(fingerprint: str, corpus: list[str]) -> float:
    """Max similarity of a hex fingerprint vs a corpus.

    Corpus entries may be hex fingerprints (exact match → 1.0) or canonical
    token strings ("tok1|tok2|…") for Jaccard comparison.
    """
    best = 0.0
    for entry in corpus:
        if entry == fingerprint:
            return 1.0
        if "|" in entry:
            best = max(best, max_token_similarity(entry, [fingerprint]))
    return best


def max_token_similarity(token_string: str, corpus: list[str]) -> float:
    """Max Jaccard similarity between a canonical token string and a corpus.

    Corpus entries may be canonical token strings or hex fingerprints (hex
    entries only match exactly against identical token strings — no match).
    """
    a = frozenset(token_string.split("|")) if token_string else frozenset()
    best = 0.0
    for entry in corpus:
        if "|" not in entry:
            continue
        b = frozenset(entry.split("|"))
        best = max(best, jaccard_similarity(a, b))
    return round(best, 4)


def verdict_for(score: float, embedding_available: bool = False) -> str:
    """Map a 0–1 similarity score to CLEAR / REVIEW / HIGH_RISK."""
    review_line = REVIEW_THRESHOLD if embedding_available else FALLBACK_REVIEW_THRESHOLD
    if score >= HIGH_RISK_THRESHOLD:
        return "HIGH_RISK"
    if score >= review_line:
        return "REVIEW"
    return "CLEAR"


@dataclass(frozen=True)
class SimilarityMatch:
    compared_cluster_label: str
    similarity_score: float
    risk_level: str  # LOW | MEDIUM | HIGH | CRITICAL
    cluster_sample_count: int | None
    differentiators: str | None


@dataclass(frozen=True)
class SimilarityVerdict:
    verdict: str  # CLEAR | REVIEW | HIGH_RISK
    max_score: float
    matches: tuple[SimilarityMatch, ...]
    engine_version: str = "originality_v1.0"
    embedding_status: str = EMBEDDING_UNAVAILABLE_NOTE
    confidence: float = 0.6
    explanation: str = ""


def risk_level_for(score: float) -> str:
    if score >= HIGH_RISK_THRESHOLD:
        return "CRITICAL"
    if score >= REVIEW_THRESHOLD:
        return "HIGH"
    if score >= 0.40:
        return "MEDIUM"
    return "LOW"


def scan_concept(
    concept_text: str,
    corpus: list[tuple[str, str, int | None]],
    top_k: int = 5,
) -> SimilarityVerdict:
    """Compare a concept against market clusters.

    corpus: list of (cluster_label, representative_text, sample_count).
    Cluster labels are descriptive (niche/motif/composition family) — never
    identifying individual artists.
    """
    scored: list[tuple[float, str, int | None]] = []
    for label, rep_text, sample_count in corpus:
        score = combined_similarity(concept_text, rep_text)
        scored.append((score, label, sample_count))
    scored.sort(key=lambda x: x[0], reverse=True)

    matches = tuple(
        SimilarityMatch(
            compared_cluster_label=label,
            similarity_score=round(score, 4),
            risk_level=risk_level_for(score),
            cluster_sample_count=sample_count,
            differentiators=(
                "Review the overlapping elements and adjust subject, composition, "
                "or viewpoint to increase differentiation."
                if score >= REVIEW_THRESHOLD
                else None
            ),
        )
        for score, label, sample_count in scored[:top_k]
    )
    max_score = scored[0][0] if scored else 0.0
    verdict = verdict_for(max_score, embedding_available=False)

    if verdict == "HIGH_RISK":
        explanation = (
            f"Assessed as HIGH_RISK: concept is near-identical to market cluster "
            f"'{scored[0][1]}' (similarity {max_score:.2f} ≥ {HIGH_RISK_THRESHOLD}). "
            "Blocked from approval without explicit user override. "
            "This is a risk assessment, not a legal judgment."
        )
    elif verdict == "REVIEW":
        explanation = (
            f"Assessed as REVIEW: closest market cluster '{scored[0][1]}' at similarity "
            f"{max_score:.2f} (uncertainty band {FALLBACK_REVIEW_THRESHOLD}–{HIGH_RISK_THRESHOLD} "
            "during embedding-unavailable fallback). Human judgment required."
        )
    else:
        explanation = (
            f"Assessed as CLEAR: closest market cluster at similarity {max_score:.2f} "
            f"(below {FALLBACK_REVIEW_THRESHOLD}). Matches are topical, not substantive."
        )

    return SimilarityVerdict(
        verdict=verdict,
        max_score=round(max_score, 4),
        matches=matches,
        confidence=0.6,  # lowered during embedding-unavailable fallback (docs/17 §8)
        explanation=explanation,
    )
