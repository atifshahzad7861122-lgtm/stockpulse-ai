"""originality agent — similarity scans vs market clusters."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agents import _base
from app.engines.similarity import scan_concept
from app.models.compliance import SimilarityRecord
from app.models.platform import AgentRun
from app.schemas.enums import DataProvenance, RiskLevel


def run(db: Session, run: AgentRun, input: dict[str, Any]) -> dict[str, Any]:
    subject_kind: str = input.get("subject_kind", "image_idea")
    subject_id: str = input["subject_id"]
    concept_text: str = input.get("concept_text", "")

    if not concept_text:
        from app.models.ideation import ImageIdea, VideoIdea
        from app.models.prompts import Prompt, PromptVersion

        if subject_kind == "image_idea":
            idea = db.query(ImageIdea).filter_by(id=subject_id).one_or_none()
            concept_text = f"{idea.title} {idea.concept}" if idea else ""
        elif subject_kind == "video_idea":
            idea = db.query(VideoIdea).filter_by(id=subject_id).one_or_none()
            concept_text = f"{idea.title} {idea.concept}" if idea else ""
        elif subject_kind == "prompt":
            pv = (
                db.query(PromptVersion)
                .join(Prompt, Prompt.id == PromptVersion.prompt_id)
                .filter(Prompt.id == subject_id)
                .order_by(PromptVersion.version_number.desc())
                .first()
            )
            concept_text = pv.prompt_text if pv else ""
        elif subject_kind == "asset":
            from app.models.production import Asset

            asset = db.query(Asset).filter_by(id=subject_id).one_or_none()
            concept_text = (
                f"{asset.title} {asset.asset_type.value if asset.asset_type else ''}"
                if asset
                else ""
            )

    # Market cluster corpus: descriptive labels only, never individual artists.
    corpus = [
        (
            "warm documentary workspace cluster",
            "person working at a wooden desk with warm window light, laptop, coffee",
            120,
        ),
        (
            "abstract technology background cluster",
            "flowing blue digital particles and network lines on dark background",
            200,
        ),
        (
            "golden hour landscape cluster",
            "mountain valley at sunset with dramatic clouds and river",
            150,
        ),
        (
            "clinical healthcare concept cluster",
            "doctor holding a digital tablet with medical interface overlays",
            90,
        ),
        (
            "minimal food flat lay cluster",
            "overhead arrangement of fresh vegetables on white background",
            110,
        ),
    ]
    verdict = scan_concept(concept_text or subject_id, corpus)

    fk = {
        "image_idea": {"image_idea_id": subject_id},
        "video_idea": {"video_idea_id": subject_id},
        "prompt": {"prompt_id": subject_id},
        "asset": {"asset_id": subject_id},
    }.get(subject_kind, {})
    record = SimilarityRecord(
        subject_kind=subject_kind,
        compared_cluster_label=(
            verdict.matches[0].compared_cluster_label if verdict.matches else "none"
        ),
        similarity_score=verdict.max_score,
        risk_level=RiskLevel(verdict.matches[0].risk_level) if verdict.matches else RiskLevel.LOW,
        cluster_sample_count=verdict.matches[0].cluster_sample_count if verdict.matches else None,
        differentiators=verdict.matches[0].differentiators if verdict.matches else None,
        data_provenance=DataProvenance.MOCK,
        agent_run_id=run.id,
        **fk,
    )
    db.add(record)
    db.commit()
    _base.info(db, run, f"Originality scan: {verdict.verdict} (max {verdict.max_score})")
    return {
        "similarity_record_id": record.id,
        "verdict": verdict.verdict,
        "max_score": verdict.max_score,
        "matches": [
            {
                "compared_cluster_label": m.compared_cluster_label,
                "similarity_score": m.similarity_score,
                "risk_level": m.risk_level,
                "cluster_sample_count": m.cluster_sample_count,
                "differentiators": m.differentiators,
            }
            for m in verdict.matches
        ],
        "embedding_status": verdict.embedding_status,
        "explanation": verdict.explanation,
        "note": "Embedding service unavailable in v1 — REVIEW band widened to 0.55–0.80. "
        + _base.MOCK_NOTE,
    }
