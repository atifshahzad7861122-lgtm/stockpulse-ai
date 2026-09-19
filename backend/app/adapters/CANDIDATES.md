# Adapter candidates (documented, NOT implemented)

Phase 2 backend-core scope note: these integrations are researched and parked
here for a future phase. Nothing below is wired into the registry, the
scheduler, or the seed — this file is the whole deliverable.

Standing guardrails apply to every future implementation: automate repetition,
not judgment. The human keeps final decisions on originality, rights, quality,
metadata truthfulness and submission. Provenance is recorded honestly
(`DataProvenance`: real public → `THIRD_PARTY`, official APIs → `VERIFIED`,
private real → `USER_PROVIDED`); mock/demo data must never appear live.

---

## EXIFTOOL — metadata preflight for Metadata Studio

**What it is:** ExifTool (Phil Harvey, free for any use) — the reference
command-line tool for reading/writing image metadata (EXIF, IPTC, XMP).

**Candidate role:** a future `exiftool_adapter.py` (or library call inside
Metadata Studio) for metadata preflight: read embedded title/description/
keywords from local files, and write back the human-approved metadata before
submission. It is a *mechanical* check — "does this file carry complete,
well-formed IPTC/XMP?" — not a judgment.

**Hard limits (must be baked into any implementation):**
- ExifTool can verify metadata *presence and syntax*; it **cannot judge**
  image quality, originality, or legality.
- It cannot tell whether keywords truthfully describe the image, whether the
  asset infringes someone else's work, or whether a model/property release is
  actually required. Those stay human decisions (review gates in docs/21).
- Writing metadata never fixes a bad asset — preflight passes files through,
  it does not approve them.

**Provenance note:** metadata written locally from the user's own approved
drafts would be `USER_PROVIDED`; ExifTool itself adds no provenance signal.

---

## COMFYUI — local image-generation tool (generation-tool list candidate)

**What it is:** ComfyUI — a node-based, locally-run image/video generation
frontend (commonly used with Stable Diffusion / Flux-family checkpoints).

**Candidate role:** a future entry on the *generation-tool list* (docs/20
"Generation Tools") — i.e. StockPulse would record "asset drafted with
ComfyUI, checkpoint X, LoRA Y" as the tool of record for a generated asset,
alongside the generation prompt that was used. It is a *tool*, not a data
source; it emits no trend signals.

**Hard limits (must be resolved before any implementation):**
- **Licence:** ComfyUI core is GPLv3. Linking/integrating it into StockPulse
  has licence implications for distribution — legal review required before
  anything beyond "user runs ComfyUI separately" is built.
- **Checkpoint/LoRA rights:** every checkpoint and LoRA a user loads carries
  its own licence and training-data provenance. Rights need *separate review
  per model file* — StockPulse must never assume "local generation = clean
  rights".
- **Adobe disclosure:** Adobe Stock requires generative-AI disclosure for AI
  content. Any ComfyUI-generated asset must carry that flag through the
  submission queue (docs/21 review gates), or the contributor risks account
  action. The tool adapter must record — never silently drop — the AI-generated
  flag.
- **Originality:** local generation does not guarantee originality; outputs
  can still resemble training data. Human review stays the gate.

---

## KDENLIVE — no action

Kdenlive is a video editor, not a data source and not a generation tool in
StockPulse's pipeline. **Not an integration target.** No adapter planned.
