"""compliance agent — screen subjects against the 28 seeded rules."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agents import _base
from app.engines.compliance import RuleSpec, ScreenSubject, run_screen
from app.models.compliance import ComplianceCheck, ComplianceRule
from app.models.platform import AgentRun
from app.schemas.enums import ComplianceCheckType, ComplianceResult, RiskLevel, RuleSeverity


def _build_subject(
    db: Session, subject_kind: str, subject_id: str, subject_version_id: str | None
) -> ScreenSubject:
    from app.models.ideation import ImageIdea, VideoIdea
    from app.models.production import Asset, MetadataRecord
    from app.models.prompts import Prompt, PromptVersion

    s = ScreenSubject()
    if subject_kind == "prompt":
        prompt = db.query(Prompt).filter_by(id=subject_id).one_or_none()
        pv = None
        if subject_version_id:
            pv = db.query(PromptVersion).filter_by(id=subject_version_id).one_or_none()
        elif prompt and prompt.current_version_id:
            pv = db.query(PromptVersion).filter_by(id=prompt.current_version_id).one_or_none()
        if pv:
            s = ScreenSubject(
                prompt_text=pv.prompt_text or "",
                negative_prompt_text=pv.negative_prompt_text or "",
                generation_tool=(pv.parameters or {}).get("provenance_note")
                and "mock-generation-provider",
            )
    elif subject_kind in ("image_idea", "video_idea"):
        model = ImageIdea if subject_kind == "image_idea" else VideoIdea
        idea = db.query(model).filter_by(id=subject_id).one_or_none()
        if idea:
            s = ScreenSubject(
                concept=idea.concept or "",
                originality_notes=idea.originality_notes or "",
                title=idea.title or "",
            )
    elif subject_kind == "asset":
        asset = db.query(Asset).filter_by(id=subject_id).one_or_none()
        if asset:
            s = ScreenSubject(
                title=asset.title or "",
                width_px=asset.width_px,
                height_px=asset.height_px,
                asset_type=asset.asset_type.value if asset.asset_type else "IMAGE",
                ai_disclosure=True,
                generation_tool="mock-generation-provider",
                generation_date="2026-09-18",
            )
    elif subject_kind == "metadata":
        md = db.query(MetadataRecord).filter_by(id=subject_id).one_or_none()
        if md:
            s = ScreenSubject(
                title=md.title or "",
                description=md.description or "",
                keywords=tuple(md.keywords or []),
                adobe_category=md.adobe_category,
            )
    elif subject_kind == "production_queue":
        from app.models.production import ProductionQueue

        item = db.query(ProductionQueue).filter_by(id=subject_id).one_or_none()
        if item:
            s = ScreenSubject(
                title=item.title or "",
                asset_type=item.asset_type.value if item.asset_type else "IMAGE",
                generation_tool=item.generation_tool,
            )
    return s


def run(db: Session, run: AgentRun, input: dict[str, Any]) -> dict[str, Any]:
    check_type = ComplianceCheckType(input.get("check_type", "PROMPT_SCREEN"))
    subject_kind: str = input.get("subject_kind", "prompt")
    subject_id: str = input["subject_id"]
    subject_version_id: str | None = input.get("subject_version_id")

    rules = db.query(ComplianceRule).filter_by(is_enabled=True).all()
    specs = [
        RuleSpec(
            rule_key=r.rule_key,
            severity=r.severity,
            check_method=(r.rule_config or {}).get("check_method", "automated"),
            applies_to=tuple(r.applies_to or []),
        )
        for r in rules
    ]
    subject = _build_subject(db, subject_kind, subject_id, subject_version_id)
    result = run_screen(check_type.value, subject, specs)

    # Map subject_kind → check FK columns.
    fk = {
        "prompt": {"prompt_id": subject_id, "prompt_version_id": subject_version_id},
        "asset": {"asset_id": subject_id},
        "image_idea": {"image_idea_id": subject_id},
        "video_idea": {"video_idea_id": subject_id},
        "metadata": {"metadata_id": subject_id},
        "production_queue": {"production_queue_id": subject_id},
    }.get(subject_kind, {})

    check = ComplianceCheck(
        check_type=check_type,
        result=ComplianceResult(result.result),
        risk_level=RiskLevel(result.risk_level),
        findings=[
            {
                "check_id": f.rule_key.upper(),
                "rule_key": f.rule_key,
                "rule_version": f.rule_version,
                "severity": (
                    f.severity.value if isinstance(f.severity, RuleSeverity) else f.severity
                ),
                "triggered": f.triggered,
                "explanation": f.explanation,
                "matched_excerpt": f.matched_excerpt,
                "remediation": f.remediation,
            }
            for f in result.findings
        ],
        explanation=result.explanation,
        agent_run_id=run.id,
        **fk,
    )
    db.add(check)
    db.commit()
    _base.info(db, run, f"Compliance screen: {result.result} ({result.risk_level})")
    return {
        "check_id": check.id,
        "result": result.result,
        "risk_level": result.risk_level,
        "rules_version": result.rules_version,
        "finding_count": len(result.findings),
        "note": f"Assessed as {result.result} — never a guarantee of acceptance.",
    }
