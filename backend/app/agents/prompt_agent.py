"""prompt agent — versioned prompt packages via the prompt engine."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agents import _base
from app.engines.prompts import PromptSelections, generate_package
from app.models.ideation import ImageIdea, VideoIdea
from app.models.platform import AgentRun
from app.models.prompts import Prompt, PromptVersion
from app.schemas.enums import AssetType, PromptStatus


def run(db: Session, run: AgentRun, input: dict[str, Any]) -> dict[str, Any]:
    idea_id: str | None = input.get("idea_id")
    kind: str = input.get("kind", "image")
    tool_family: str = input.get("tool", "midjourney")
    feedback: str | None = input.get("feedback")

    if kind == "video":
        idea = db.query(VideoIdea).filter_by(id=idea_id).one_or_none() if idea_id else None
    else:
        idea = db.query(ImageIdea).filter_by(id=idea_id).one_or_none() if idea_id else None
    if idea is None:
        # Fallback: first READY idea of the kind.
        idea = (
            db.query(ImageIdea if kind == "image" else VideoIdea).filter_by(status="READY").first()
        )
    if idea is None:
        _base.warn(db, run, "No idea available for prompt generation")
        return {"prompts_created": 0, "note": "Prompt generation needs a READY idea."}

    selections = PromptSelections(
        asset_type="VIDEO" if kind == "video" else "IMAGE",
        category="commercial",
        micro_niche=idea.title[:60],
        concept=idea.concept[:200],
        visual_style="photorealistic",
        aspect_ratio="16:9",
        orientation="landscape",
        camera="eye-level, rule of thirds",
        lighting="natural light",
        environment="clean commercial setting",
        subject=idea.title[:80],
        composition="rule of thirds with negative space",
        commercial_use_case="stock photography",
        tool_family=tool_family,
    )
    package = generate_package(
        selections,
        niche_slug=idea.title[:40].lower().replace(" ", "-"),
        compliance_rules=[],
        concept_risks=[idea.originality_notes[:200]] if idea.originality_notes else [],
    )
    prompt = Prompt(
        image_idea_id=idea.id if kind == "image" else None,
        video_idea_id=idea.id if kind == "video" else None,
        asset_type=AssetType.VIDEO if kind == "video" else AssetType.IMAGE,
        name=f"Prompt for {idea.title[:80]}",
        status=PromptStatus.DRAFT,
    )
    db.add(prompt)
    db.flush()
    pv = PromptVersion(
        prompt_id=prompt.id,
        version_number=1,
        prompt_text=package.primary_prompt,
        negative_prompt_text=package.negative_prompt,
        parameters={
            "tool_family": tool_family,
            "mock": True,
            "alternative_prompt": package.alternative_prompt,
            "technical_requirements": package.technical_requirements,
            "quality_requirements": package.quality_requirements,
            "originality_instructions": package.originality_instructions,
            "compliance_instructions": package.compliance_instructions,
            "quality_score": package.quality_score,
            "quality_criteria": package.quality_criteria,
            "template_version": package.template_version,
            "rules_version": package.rules_version,
            "provenance_note": "MOCK demo prompt — regenerate before real production.",
        },
        change_summary="Initial agent draft."
        + (f" Feedback addressed: {feedback}" if feedback else ""),
        created_by="agent",
        agent_run_id=run.id,
    )
    db.add(pv)
    db.flush()
    prompt.current_version_id = pv.id
    db.commit()
    _base.info(db, run, f"Created prompt package {prompt.id} (DRAFT — review required)")
    return {
        "prompt_id": prompt.id,
        "version_number": 1,
        "provenance": "MOCK",
        "note": "Draft prompt — compliance screen required before production. " + _base.MOCK_NOTE,
    }
