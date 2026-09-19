"""WHY-paragraph rendering for opportunity fusion (Phase 3).

DEFAULT: a deterministic, evidence-based template (``engines.fusion``) —
always available, never fakes text.

OPTIONAL: when ``STOCKPULSE_LLM_PROVIDER=ollama``, the local Ollama model
rewrites the evidence + components into a natural-language WHY paragraph.
Private data stays on localhost (Ollama's API is 127.0.0.1 only); the helper
refuses to use any non-local provider for this task. If Ollama is unreachable
or returns anything unusable, the deterministic template is the fallback —
the endpoint NEVER fails or fakes text because the LLM is down.
"""

from __future__ import annotations

import os
from typing import Any


def _ollama_rewrite(*, title: str, components: dict[str, Any], evidence: dict[str, Any]) -> str:
    """Ask the LOCAL Ollama model to phrase the WHY paragraph. Raises on any
    failure so the caller can fall back to the deterministic template."""
    from app.providers.providers import LLMRequest, get_llm_provider

    provider = get_llm_provider()
    if provider.name != "ollama":
        # Safety: only a localhost provider may see private-derived inputs.
        raise RuntimeError(
            f"refusing to send fusion evidence to non-local provider '{provider.name}'"
        )
    lines = [f"Opportunity: {title or 'untitled'}"]
    for name, value in components.items():
        lines.append(f"- {name}: {value if value is not None else 'no private data'}")
    for kind, notes in evidence.items():
        for note in notes:
            lines.append(f"- {kind}: {note}")
    response = provider.generate(
        LLMRequest(
            task="fusion_explain",
            context={"evidence_lines": lines},
            max_tokens=400,
        )
    )
    text = (response.text or "").strip()
    if not text:
        raise RuntimeError("Ollama returned empty text")
    return text


def render_explanation(
    *,
    deterministic_text: str,
    title: str = "",
    components: dict[str, Any] | None = None,
    demand_evidence_notes: tuple[str, ...] | list[str] = (),
    personal_evidence_notes: tuple[str, ...] | list[str] = (),
) -> tuple[str, str]:
    """Return (explanation_text, renderer).

    ``renderer`` is "deterministic-template", "ollama/<model>", or
    "deterministic-template (ollama fallback)". Never raises.
    """
    if os.environ.get("STOCKPULSE_LLM_PROVIDER", "mock").lower() != "ollama":
        return deterministic_text, "deterministic-template"
    try:
        text = _ollama_rewrite(
            title=title,
            components=dict(components or {}),
            evidence={
                "market evidence": list(demand_evidence_notes or ()),
                "personal evidence": list(personal_evidence_notes or ()),
            },
        )
        # Never let the LLM introduce guarantee language: fall back instead.
        from app.engines.fusion import explanation_has_banned_language

        if explanation_has_banned_language(text):
            raise RuntimeError("Ollama output contained guarantee-style language")
        return text, "ollama"
    except Exception:
        # LLM down/unusable → deterministic evidence-based fallback. The
        # endpoint must never fail or fake text because the LLM is down.
        return deterministic_text, "deterministic-template (ollama fallback)"
