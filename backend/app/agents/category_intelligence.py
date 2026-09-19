"""category_intelligence agent — propose taxonomy additions for USER approval.

Never auto-creates categories/subcategories/micro-niches. Output is a proposal
list the user reviews; approved proposals are applied via the taxonomy API.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agents import _base
from app.models.platform import AgentRun
from app.models.taxonomy import Category
from app.providers.providers import LLMRequest, get_llm_provider


def run(db: Session, run: AgentRun, input: dict[str, Any]) -> dict[str, Any]:
    category_id: str | None = input.get("category_id")
    q = db.query(Category)
    if category_id:
        q = q.filter(Category.id == category_id)
    categories = q.order_by(Category.sort_order).limit(10).all()

    llm = get_llm_provider()
    proposals: list[dict[str, Any]] = []
    for cat in categories:
        response = llm.generate(
            LLMRequest(
                task="ideate",
                context={
                    "micro_niche": f"subcategories of {cat.name}",
                    "count": 3,
                    "subject_hint": "commercial stock subcategories",
                    "mood": "buyer-searchable",
                },
            )
        )
        proposals.append(
            {
                "category_id": cat.id,
                "category_name": cat.name,
                "proposed_subcategories": response.text,
                "model": response.model,
                "provenance": "MOCK",
                "status": "proposed — awaiting user approval (never auto-applied)",
            }
        )
    _base.info(
        db, run, f"Proposed taxonomy additions for {len(proposals)} categories (approval required)"
    )
    return {
        "proposals": proposals,
        "proposal_count": len(proposals),
        "note": "Proposals only — the agent never modifies taxonomy without user approval. "
        + _base.MOCK_NOTE,
    }
