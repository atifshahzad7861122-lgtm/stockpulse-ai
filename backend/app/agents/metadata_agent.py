"""metadata agent — draft titles/descriptions/keywords with spam enforcement."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agents import _base
from app.engines.metadata import draft_metadata
from app.models.platform import AgentRun
from app.models.production import Asset, MetadataRecord


def run(db: Session, run: AgentRun, input: dict[str, Any]) -> dict[str, Any]:
    asset_id: str = input["asset_id"]
    asset = db.query(Asset).filter_by(id=asset_id).one_or_none()
    if asset is None:
        raise ValueError(f"Asset not found: {asset_id}")

    title_hint = asset.title or "commercial concept"
    words = [w for w in title_hint.lower().split() if len(w) > 3][:6]
    draft = draft_metadata(
        subject=title_hint,
        descriptor="in a clean commercial setting",
        use_case_hint="for editorial and advertising use",
        literal_sentence=f"A commercial stock concept: {title_hint}.",
        mood_sentence="Clean composition with natural light and authentic detail.",
        use_case_sentence="Suitable for editorial, advertising, and corporate communications.",
        keyword_groups={
            "primary": words[:3],
            "secondary": ["commercial", "stock photo", "concept"],
            "style_mood": ["authentic", "modern", "professional", "minimal"],
            "broad": ["business", "lifestyle", "editorial", "creative"],
        },
        adobe_category=input.get("adobe_category"),
        generation_tool="mock-generation-provider",
        generation_date="2026-09-18",
        descriptor_set=set(words),
    )

    # New version; flip is_current.
    existing = db.query(MetadataRecord).filter_by(asset_id=asset_id).all()
    for row in existing:
        row.is_current = False
    version_number = max([r.version_number for r in existing], default=0) + 1
    record = MetadataRecord(
        asset_id=asset_id,
        version_number=version_number,
        title=draft.title,
        description=draft.description,
        keywords=list(draft.keywords),
        adobe_category=draft.adobe_category,
        language=draft.language,
        is_current=True,
        created_by="agent",
        agent_run_id=run.id,
    )
    db.add(record)
    db.commit()
    _base.info(
        db,
        run,
        f"Drafted metadata v{version_number} (quality {draft.quality_score}, "
        f"{len(draft.spam_violations)} spam violations)",
    )
    return {
        "metadata_id": record.id,
        "version_number": version_number,
        "title": draft.title,
        "keyword_count": len(draft.keywords),
        "quality_score": draft.quality_score,
        "spam_violations": [
            {"rule_id": v.rule_id, "message": v.message, "fix": v.fix}
            for v in draft.spam_violations
        ],
        "ai_disclosure": draft.ai_disclosure,
        "provenance": "MOCK",
        "note": "Draft requires human review before submission. " + _base.MOCK_NOTE,
    }
