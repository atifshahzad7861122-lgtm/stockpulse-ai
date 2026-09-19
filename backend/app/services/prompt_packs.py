"""Prompt pack generation (Phase 3, backend only).

Builds a generation prompt pack from one screened concept variation:
primary + alternative prompt, negative prompt, technical requirements,
originality instructions, and compliance instructions — for image and
video variants.

Deterministic template assembly; never claims model inference. The pack is
EXPORT-ONLY: StockPulse never auto-generates assets from it. The user
copies the prompt into their own generation tool (e.g. muse AI).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.planning import ConceptVariation, ProductionRecommendation, PromptPack
from app.providers.providers import GenerationRequest

PROMPT_PACK_FORMAT_VERSION = "1.0"

_IMAGE_TECHNICAL_REQUIREMENTS = """Technical requirements (verify in your generation tool):
- Resolution: export at 6000px on the long edge or larger (≥ 4 megapixels minimum)
- Orientation: match the concept's orientation and aspect ratio
- Color: Adobe RGB or sRGB; avoid crushed blacks and clipped highlights
- Clean frame: no watermarks, signatures, borders, or overlaid text
- Keep model release / property release needs in mind while composing the scene"""

_VIDEO_TECHNICAL_REQUIREMENTS = """Technical requirements (verify in your generation tool):
- Resolution: 3840×2160 (4K) or at minimum 1920×1080
- Frame rate: 24 or 30 fps; duration as specified in the concept
- Orientation: match the concept's orientation (landscape or vertical)
- Stable exposure and white balance across the whole clip
- No burned-in text, logos, watermarks, or audio with rights issues"""

_IMAGE_NEGATIVE_PROMPT = (
    "watermark, logo, brand name, text overlay, signature, border, frame, "
    "blurry, out of focus, low resolution, pixelated, jpeg artifacts, noise, "
    "grain, distorted anatomy, extra limbs, deformed hands, deformed face, "
    "copyrighted character, celebrity likeness, stock photo cliché"
)

_VIDEO_NEGATIVE_PROMPT = (
    "watermark, logo, text overlay, subtitles, flicker, jitter, warping, "
    "morphing faces, extra limbs, distorted anatomy, low resolution, "
    "compression artifacts, abrupt cuts, shaky camera, copyrighted character, "
    "celebrity likeness"
)

_ORIGINALITY_TEMPLATE = """Originality instructions (mandatory):
- Create an original work. Do NOT copy, trace, or closely recreate any
  existing photograph, artwork, advertisement, or film frame — this includes
  another contributor's work (never TREND → COPY → RECREATE).
- Concept differentiators to preserve: {differentiators}
- If the output starts resembling a known reference, change the subject
  arrangement, viewpoint, or styling until it reads as new.
- Originality notes for this concept: {originality_notes}"""

_COMPLIANCE_TEMPLATE = """Compliance instructions (mandatory human checks before production):
- No recognizable real people without a signed model release; no celebrity
  likenesses at all.
- No trademarks, logos, brand packaging, or distinctive product designs.
- No copyrighted characters, artworks, or "in the style of" a living artist.
- Disclose AI generation when uploading to Adobe Stock (mandatory).
- Screened assessment: {compliance_result} — {compliance_explanation}
  This is a text-field risk assessment, not legal certainty and not a
  guarantee of Adobe Stock acceptance. Visual review of the rendered asset
  is still required."""

_EXPORT_ONLY_FOOTER = (
    "\n\n— Exported from StockPulse AI prompt pack (format {version}). "
    "Export only: this prompt pack does not generate any asset by itself. "
    "Copy the prompt above into your own generation tool (e.g. muse AI)."
)


def _primary_image_prompt(spec: dict, rec: ProductionRecommendation) -> str:
    return (
        f"Commercial stock photograph, {spec.get('orientation', 'landscape')} "
        f"{spec.get('aspect_ratio', '3:2')}: {spec.get('concept', '')} "
        f"Composition: {spec.get('composition', '')}. "
        f"Lighting: {spec.get('lighting', '')}. "
        f"Camera: {spec.get('camera', '')}, {spec.get('perspective', '')}. "
        f"Intended use: {spec.get('commercial_use', 'commercial stock')}. "
        "Photorealistic, clean commercial aesthetic, original arrangement."
    )


def _alternative_image_prompt(spec: dict) -> str:
    return (
        f"Alternative viewpoint of the same concept: {spec.get('subject', '')} "
        f"in {spec.get('environment', '')}, shot as "
        f"{spec.get('composition', '')} with {spec.get('lighting', '')}. "
        "Shift the camera angle and prop arrangement so this reads as a "
        "distinct frame, not a crop of the primary."
    )


def _primary_video_prompt(spec: dict) -> str:
    return (
        f"Commercial stock video clip, {spec.get('duration', 8)} seconds, "
        f"{spec.get('orientation', 'landscape')}: {spec.get('scene', '')} "
        f"Action: {spec.get('action', '')}. "
        f"Camera movement: {spec.get('camera_movement', '')}. "
        f"Visual direction: {spec.get('visual_direction', '')}. "
        f"Loop: {spec.get('loop_potential', '')}. "
        f"Intended use: {spec.get('commercial_use', 'commercial stock')}. "
        "Smooth, professional motion; original choreography."
    )


def _alternative_video_prompt(spec: dict) -> str:
    return (
        f"Alternative take of the same concept: {spec.get('subject', '')} "
        f"with {spec.get('action', '')}, {spec.get('visual_direction', '')}. "
        "Change the camera path and pacing so this reads as a distinct "
        "clip, not a re-cut of the primary."
    )


def generate_prompt_pack(
    db: Session,
    concept: ConceptVariation,
    target_tool: str = "muse",
    format_version: str = PROMPT_PACK_FORMAT_VERSION,
) -> PromptPack:
    """Build and persist a prompt pack from a screened concept variation."""
    spec = concept.concept_json or {}
    rec = db.query(ProductionRecommendation).filter_by(id=concept.recommendation_id).one_or_none()
    is_video = concept.asset_type.value == "VIDEO"

    if is_video:
        primary = _primary_video_prompt(spec)
        alternative = _alternative_video_prompt(spec)
        negative = _VIDEO_NEGATIVE_PROMPT
        technical = _VIDEO_TECHNICAL_REQUIREMENTS
    else:
        primary = _primary_image_prompt(spec, rec)
        alternative = _alternative_image_prompt(spec)
        negative = _IMAGE_NEGATIVE_PROMPT
        technical = _IMAGE_TECHNICAL_REQUIREMENTS

    differentiators = spec.get("composition") or spec.get("visual_direction") or "original staging"
    originality = _ORIGINALITY_TEMPLATE.format(
        differentiators=differentiators,
        originality_notes=concept.originality_notes or "see concept record",
    )
    comp = concept.compliance_result_json or {}
    compliance_instructions = _COMPLIANCE_TEMPLATE.format(
        compliance_result=concept.compliance_result or "not screened",
        compliance_explanation=comp.get("explanation", "no explanation recorded"),
    )

    pack = PromptPack(
        concept_id=concept.id,
        primary_prompt=primary,
        alternative_prompt=alternative,
        negative_prompt=negative,
        technical_requirements=technical,
        originality_instructions=originality,
        compliance_instructions=compliance_instructions,
        target_tool=target_tool,
        format_version=format_version,
    )
    db.add(pack)
    db.flush()
    return pack


def pack_document(pack: PromptPack, concept_title: str) -> dict:
    """The exportable document: the full prompt pack as plain data.

    This is what the muse export provider writes to disk. It contains only
    prompt text — no asset is ever rendered from it.
    """
    return {
        "format": "stockpulse-prompt-pack",
        "format_version": pack.format_version,
        "concept_title": concept_title,
        "target_tool": pack.target_tool,
        "primary_prompt": pack.primary_prompt,
        "alternative_prompt": pack.alternative_prompt,
        "negative_prompt": pack.negative_prompt,
        "technical_requirements": pack.technical_requirements,
        "originality_instructions": pack.originality_instructions,
        "compliance_instructions": pack.compliance_instructions,
        "export_only": True,
        "asset_auto_generated": False,
        "disclaimer": (
            "Export only — no asset was auto-generated from this prompt pack. "
            "Copy the prompts into your own generation tool (e.g. muse AI)."
        ),
    }


class PromptPackGenerator:
    """Object-oriented facade over prompt-pack generation and export.

    Export-only: generates prompt text documents for the user's own
    generation tool (muse). Never renders or claims an asset.
    """

    def __init__(self, db: Session):
        self.db = db

    def generate(
        self,
        concept: ConceptVariation,
        target_tool: str = "muse",
        format_version: str = PROMPT_PACK_FORMAT_VERSION,
    ) -> PromptPack:
        return generate_prompt_pack(
            self.db,
            concept,
            target_tool=target_tool,
            format_version=format_version,
        )

    def document(self, pack: PromptPack, concept_title: str) -> dict:
        return pack_document(pack, concept_title)

    def export(
        self, pack: PromptPack, concept_title: str, provider_name: str = "muse"
    ):
        """Export the pack document through the named provider.

        The muse provider writes a local JSON file (export-only); the mock
        provider returns a mock URI. Neither generates an asset.
        """
        from app.providers.providers import get_generation_provider

        if provider_name == "muse":
            from app.providers.providers import MuseGenerationProvider

            provider = MuseGenerationProvider()
        else:
            provider = get_generation_provider()
        document = pack_document(pack, concept_title)
        request = GenerationRequest(
            prompt_id=pack.id,
            prompt_text=pack.primary_prompt,
            asset_type="IMAGE",
            parameters={"prompt_pack": document},
        )
        return provider.generate_asset(request)
