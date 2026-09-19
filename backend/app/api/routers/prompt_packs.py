"""Prompt packs (Phase 3).

POST /prompt-packs — build a pack from a screened concept variation.
GET /prompt-packs — list; GET /prompt-packs/{id} — detail.
POST /prompt-packs/{id}/export — export via the selected generation
provider. The "muse" provider is EXPORT-ONLY: it writes the prompt pack to
a local file and returns its URI honestly labeled
"export only — asset not auto-generated". No asset is ever rendered here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    audit_log,
    bad_request,
    get_db,
    not_found,
    paginate,
    pagination_params,
)
from app.models.planning import ConceptVariation, PromptPack
from app.providers.providers import (
    MUSE_EXPORT_LABEL,
    GenerationRequest,
    get_generation_provider,
)
from app.schemas.common import Page, apply_labels
from app.schemas.planning import (
    PromptPackExportOut,
    PromptPackGenerateRequest,
    PromptPackOut,
)
from app.services.prompt_packs import generate_prompt_pack, pack_document

router = APIRouter(prefix="/prompt-packs", tags=["prompt-packs"])


def _out(row: PromptPack) -> PromptPackOut:
    return apply_labels(PromptPackOut.model_validate(row), row)


@router.post("", response_model=PromptPackOut, status_code=201)
def create_pack(
    concept_id: Annotated[str, Query()],
    body: PromptPackGenerateRequest,
    db: Annotated[Session, Depends(get_db)],
):
    concept = db.query(ConceptVariation).filter_by(id=concept_id).one_or_none()
    if concept is None:
        raise not_found("CONCEPT_NOT_FOUND", f"Concept {concept_id} not found.")
    pack = generate_prompt_pack(
        db, concept, target_tool=body.target_tool, format_version=body.format_version
    )
    db.commit()
    db.refresh(pack)
    audit_log(
        db,
        action="generate_prompt_pack",
        entity_kind="prompt_pack",
        entity_id=pack.id,
        after={"concept_id": concept_id, "target_tool": pack.target_tool},
        note="Deterministic prompt pack built from a screened concept.",
    )
    db.commit()
    return _out(pack)


@router.get("", response_model=Page[PromptPackOut])
def list_packs(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[dict, Depends(pagination_params)],
    concept_id: Annotated[str | None, Query()] = None,
    target_tool: Annotated[str | None, Query()] = None,
):
    q = db.query(PromptPack).order_by(PromptPack.created_at.desc())
    if concept_id:
        q = q.filter_by(concept_id=concept_id)
    if target_tool:
        q = q.filter_by(target_tool=target_tool)
    total = q.count()
    page, page_size = paging["page"], paging["page_size"]
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    return paginate([_out(r) for r in rows], page=page, page_size=page_size, total=total)


@router.get("/{pack_id}", response_model=PromptPackOut)
def get_pack(pack_id: str, db: Annotated[Session, Depends(get_db)]):
    row = db.query(PromptPack).filter_by(id=pack_id).one_or_none()
    if row is None:
        raise not_found("PROMPT_PACK_NOT_FOUND", f"Prompt pack {pack_id} not found.")
    return _out(row)


@router.post("/{pack_id}/export", response_model=PromptPackExportOut)
def export_pack(
    pack_id: str,
    provider: Annotated[str | None, Query()] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Export the prompt pack through the selected generation provider.

    ?provider=muse forces the export-only muse provider. Export never
    renders or claims an asset — it hands the user a local file to paste
    into their own generation tool.
    """
    row = db.query(PromptPack).filter_by(id=pack_id).one_or_none()
    if row is None:
        raise not_found("PROMPT_PACK_NOT_FOUND", f"Prompt pack {pack_id} not found.")
    concept = db.query(ConceptVariation).filter_by(id=row.concept_id).one_or_none()
    document = pack_document(row, concept.title if concept else "prompt-pack")

    try:
        if provider:
            # Explicit per-request override: only the known export-only
            # providers are selectable this way.
            from app.providers.providers import MockGenerationProvider, MuseGenerationProvider

            providers_by_name = {
                "mock": MockGenerationProvider,
                "muse": MuseGenerationProvider,
            }
            cls = providers_by_name.get(provider.lower())
            if cls is None:
                raise ValueError(
                    f"Unknown generation provider '{provider}' "
                    "(supported: 'mock', 'muse')"
                )
            provider = cls()
        else:
            provider = get_generation_provider()
    except ValueError as exc:
        raise bad_request("UNKNOWN_PROVIDER", str(exc))
    request = GenerationRequest(
        prompt_id=row.id,
        prompt_text=row.primary_prompt,
        asset_type=(concept.asset_type.value if concept else "IMAGE"),
        parameters={"prompt_pack": document},
    )
    response = provider.generate_asset(request)
    row.exported_at = datetime.now(UTC)
    row.export_uri = response.storage_uri
    db.commit()
    audit_log(
        db,
        action="export_prompt_pack",
        entity_kind="prompt_pack",
        entity_id=row.id,
        after={"export_uri": response.storage_uri, "provider": provider.name},
        note=f"Export via '{provider.name}' provider — {MUSE_EXPORT_LABEL}.",
    )
    db.commit()
    return PromptPackExportOut(
        prompt_pack_id=row.id,
        export_uri=response.storage_uri,
        provider=provider.name,
        provenance=response.provenance,
        note=MUSE_EXPORT_LABEL,
    )
