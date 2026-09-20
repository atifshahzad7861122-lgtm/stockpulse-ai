"""Provider abstractions (docs: 15_TREND_INTELLIGENCE §2, 31_INTEGRATION_SPECIFICATION).


Env-var-driven selection with MOCK default:
    STOCKPULSE_TREND_PROVIDER=mock   (mock | <future real adapter>)
    STOCKPULSE_LLM_PROVIDER=mock     (mock | ollama)
    STOCKPULSE_GENERATION_PROVIDER=mock   (mock | muse)


v1 ships mock providers (deterministic, labeled MOCK, no network calls, no
credentials) plus OllamaLLMProvider — a LOCAL LLM via the Ollama REST API.


The "muse" generation provider is EXPORT-ONLY: it writes the prompt pack to
a local export file and returns its URI honestly labeled "export only —
asset not auto-generated". It makes NO undocumented API calls and renders
no media: muse AI has no public generation API that this backend may call,
so the provider's job is to hand the user a copy-paste-ready prompt pack.
The user generates the asset themselves in muse AI (or any tool).
Real adapters beyond these are a future integration (docs/31).
"""


from __future__ import annotations


import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime


PROVENANCE_MOCK = "MOCK"
PROVENANCE_LOCAL = "LOCAL"  # Ollama: inference ran on this machine, not a vendor API
PROVENANCE_THIRD_PARTY = "THIRD_PARTY"  # vendor API inference (e.g. Gemini): real model, external service




# ---------------------------------------------------------------------------
# Abstract bases
# ---------------------------------------------------------------------------




@dataclass(frozen=True)
class TrendSnapshotPayload:
    """Normalized provider output for one topic (docs/15 §3)."""


    topic: str
    value_w0: float
    value_w1: float
    value_baseline: float
    keyword_tvs: tuple[float, ...] = ()
    source_z_scores: tuple[float, ...] = ()
    source_id: str = "mock"




class TrendProvider(ABC):
    """Source adapter: pull and normalize trend data (docs/13 §3, 15 §2)."""


    name: str = "base"
    provenance: str = PROVENANCE_MOCK


    @abstractmethod
    def fetch_topics(self, topics: list[str], window_days: int = 7) -> list[TrendSnapshotPayload]:
        """Return normalized per-topic snapshot payloads for the given window."""
        raise NotImplementedError


    @abstractmethod
    def health(self) -> dict:
        """Source health: {status: OK|DEGRADED|FAILED, detail: str}."""
        raise NotImplementedError


@dataclass(frozen=True)
class LLMRequest:
    task: str  # e.g. "ideate", "draft_prompt", "draft_metadata", "summarize"
    context: dict
    max_tokens: int = 1000


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    provenance: str = PROVENANCE_MOCK
    tokens_used: int = 0


class LLMProvider(ABC):
    """Text generation provider (docs/13 §7–§10, 14)."""

    name: str = "base"

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError

    @abstractmethod
    def health(self) -> dict:
        raise NotImplementedError


@dataclass(frozen=True)
class GenerationRequest:
    prompt_id: str
    prompt_text: str
    asset_type: str
    parameters: dict = field(default_factory=dict)


@dataclass(frozen=True)
class GenerationResponse:
    storage_uri: str
    width_px: int | None
    height_px: int | None
    duration_seconds: float | None
    provenance: str = PROVENANCE_MOCK


class GenerationProvider(ABC):
    """Media generation provider (docs/20). v1: mock only — no media is rendered."""

    name: str = "base"

    @abstractmethod
    def generate_asset(self, request: GenerationRequest) -> GenerationResponse:
        raise NotImplementedError

    @abstractmethod
    def health(self) -> dict:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Mock implementations — deterministic, labeled MOCK, no network
# ---------------------------------------------------------------------------


class MockTrendProvider(TrendProvider):
    """Deterministic mock trend source.

    Values are derived from a stable hash of the topic name so runs are
    reproducible. Every payload is labeled provenance=MOCK and must never be
    presented as real Adobe Stock data.
    """

    name = "mock_trend_provider"

    def _seed(self, topic: str, window: str) -> float:
        import hashlib

        digest = hashlib.sha256(f"{topic}|{window}".encode()).hexdigest()
        return int(digest[:8], 16) / 0xFFFFFFFF  # 0–1 deterministic

    def fetch_topics(self, topics: list[str], window_days: int = 7) -> list[TrendSnapshotPayload]:
        payloads: list[TrendSnapshotPayload] = []
        for topic in topics:
            base = 50.0 + 40.0 * self._seed(topic, "base")
            w0 = base * (1.0 + 0.3 * self._seed(topic, "w0"))
            w1 = base * (1.0 + 0.3 * self._seed(topic, "w1"))
            baseline = base
            keyword_tvs = tuple(
                round(-1.0 + 4.0 * self._seed(f"{topic}|kw{i}", "tv"), 3) for i in range(5)
            )
            z_scores = tuple(
                round(-2.0 + 4.0 * self._seed(f"{topic}|src{i}", "z"), 3) for i in range(3)
            )
            payloads.append(
                TrendSnapshotPayload(
                    topic=topic,
                    value_w0=round(w0, 2),
                    value_w1=round(w1, 2),
                    value_baseline=round(baseline, 2),
                    keyword_tvs=keyword_tvs,
                    source_z_scores=z_scores,
                    source_id=self.name,
                )
            )
        return payloads

    def health(self) -> dict:
        return {
            "status": "OK",
            "detail": "Mock provider always available (deterministic, no network).",
            "checked_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }


class MockLLMProvider(LLMProvider):
    """Template-based deterministic LLM stub, labeled MOCK.

    Produces structured, deterministic text for agent tasks. Template outputs
    are clearly synthetic; the provider never claims real model inference.
    """

    name = "mock_llm"
    model = "mock-llm-template-v1"

    def generate(self, request: LLMRequest) -> LLMResponse:
        ctx = request.context
        task = request.task
        if task == "ideate":
            text = self._ideate(ctx)
        elif task == "draft_prompt":
            text = self._draft_prompt(ctx)
        elif task == "draft_metadata":
            text = self._draft_metadata(ctx)
        elif task == "summarize":
            text = self._summarize(ctx)
        elif task == "briefing":
            text = self._briefing(ctx)
        else:
            text = f"[MOCK {task}] " + "; ".join(f"{k}={v}" for k, v in list(ctx.items())[:6])
        return LLMResponse(
            text=text, model=self.model, provenance=PROVENANCE_MOCK, tokens_used=len(text.split())
        )

    def _ideate(self, ctx: dict) -> str:
        niche = ctx.get("micro_niche", "the niche")
        n = int(ctx.get("count", 3))
        lines = [f"CONCEPT {i+1} for {niche}:" for i in range(n)]
        angles = [
            "a fresh viewpoint avoiding the niche cliché",
            "an unexpected human-scale interaction",
            "a minimal composition with strong negative space",
            "a macro detail revealing texture and craft",
            "a wide environmental establishing shot",
        ]
        out = []
        for i, line in enumerate(lines):
            angle = angles[i % len(angles)]
            out.append(
                f"{line} {ctx.get('subject_hint', 'subject')} shown through {angle}; "
                f"mood {ctx.get('mood', 'clean commercial')}; "
                f"differentiator: distinctive composition, not a reskin of existing stock."
            )
        return "\n".join(out)

    def _draft_prompt(self, ctx: dict) -> str:
        return (
            f"[MOCK prompt draft] Primary: {ctx.get('subject', 'subject')} in "
            f"{ctx.get('environment', 'environment')}, {ctx.get('style', 'photorealistic')}, "
            f"{ctx.get('composition', 'rule of thirds')}. Alternative: reworked viewpoint. "
            f"Negative: watermark, logo, text, blurry, low resolution, deformed, distorted."
        )

    def _draft_metadata(self, ctx: dict) -> str:
        subject = ctx.get("subject", "subject")
        return (
            f"[MOCK metadata draft] Title: {subject} in commercial setting. "
            f"Keywords: {subject}, commercial, stock, concept, minimal, editorial."
        )

    def _summarize(self, ctx: dict) -> str:
        items = ctx.get("items", [])
        return f"[MOCK summary] {len(items)} items: " + "; ".join(str(i)[:80] for i in items[:5])

    def _briefing(self, ctx: dict) -> str:
        return (
            f"[MOCK daily briefing] {ctx.get('opportunity_count', 0)} opportunities, "
            f"{ctx.get('trend_count', 0)} trends analyzed, "
            f"{ctx.get('alert_count', 0)} alerts. Review gates pending: "
            f"{ctx.get('pending_gates', 'opportunities')}."
        )

    def health(self) -> dict:
        return {
            "status": "OK",
            "detail": "Mock LLM always available (template-based, no network).",
            "checked_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }


class OllamaLLMProvider(LLMProvider):
    """Local LLM via Ollama's REST API (default http://localhost:11434).

    KEY PRIVACY WIN: private earnings/performance data stays on this machine —
    prompts go to localhost only, never to an external service. Prefer this
    provider for any agent task whose context includes USER_PROVIDED data.

    Selection:
        STOCKPULSE_LLM_PROVIDER=ollama
        OLLAMA_BASE_URL=http://localhost:11434   (default)
        OLLAMA_MODEL=llama3.1                    (any model pulled locally;
                                                `ollama pull <model>` first)
        LLM_TIMEOUT_SECONDS=120                  (default; generation timeout)

    Guardrails (research report — automate repetition, not judgment): the
    model DRAFTS (ideation angles, prompt text, metadata suggestions); the
    human keeps final decisions on originality, rights, quality, metadata
    truthfulness and submission.

    Guarded: selecting/importing this provider never touches the network.
    health() reports FAILED (never raises) when Ollama isn't running, so app
    startup is never blocked. generate() raises a clear RuntimeError when the
    server is down — it NEVER returns fake text as if a model had answered.

    Uses plain httpx POSTs to /api/chat with format:"json" for structured
    outputs (the official ollama python lib is optional). ``trust_env=False``
    is deliberate: it ignores proxy env vars (localhost needs no proxy) and
    avoids URL-parse failures from malformed NO_PROXY entries.
    """

    name = "ollama"
    provenance = PROVENANCE_LOCAL

    _TASK_INSTRUCTIONS = {
        "ideate": (
            "Brainstorm original commercial-stock concept angles from the given niche. "
            "Each concept must be a genuinely new composition, not a reskin of existing "
            "stock; flag any angle that risks copying another contributor's work."
        ),
        "draft_prompt": (
            "Draft an original image-generation prompt (primary + one alternative "
            "viewpoint + negative terms). It must describe an original scene — never "
            "instruct recreating a specific existing artwork or photograph."
        ),
        "draft_metadata": (
            "Draft title and keywords for a stock asset. Keywords must truthfully "
            "describe what is actually in the image; never invent subjects, locations "
            "or properties not present."
        ),
        "summarize": "Summarize the provided items concisely and factually.",
        "briefing": (
            "Write a short daily briefing from the provided counts. Do not invent "
            "numbers; report only what the context contains."
        ),
    }

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.environ.get("OLLAMA_MODEL", "llama3.1")
        self.timeout = timeout if timeout is not None else float(os.environ.get("LLM_TIMEOUT_SECONDS", "120"))

    def _client(self):
        import httpx  # project dependency (requirements.txt); local import keeps module import cheap

        return httpx.Client(base_url=self.base_url, trust_env=False, timeout=self.timeout)

    def _system_prompt(self, task: str) -> str:
        instruction = self._TASK_INSTRUCTIONS.get(task, f"Perform the task '{task}' helpfully.")
        return (
            "You are StockPulse's local drafting assistant for an Adobe Stock contributor. "
            "Automate repetition, never judgment: you draft, the human keeps final decisions "
            "on originality, rights, quality, metadata truthfulness and submission. "
            "Respond with a single valid JSON object: {\"result\": \"<your draft text>\"}. "
            f"Task instruction: {instruction}"
        )

    def generate(self, request: LLMRequest) -> LLMResponse:
        import json as _json

        context_json = _json.dumps(request.context, default=str)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._system_prompt(request.task)},
                {
                    "role": "user",
                    "content": (
                        f"Task: {request.task}\nContext (JSON):\n{context_json}\n"
                        f"Respond with a single valid JSON object: {{\"result\": \"...\"}}."
                    ),
                },
            ],
            "format": "json",
            "stream": False,
            "options": {"num_predict": request.max_tokens},
        }
        try:
            with self._client() as client:
                resp = client.post("/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            raise RuntimeError(
                f"Ollama unavailable at {self.base_url} (model '{self.model}'): {exc}. "
                "Is `ollama serve` running, and is the model pulled (`ollama pull <model>`)?"
            ) from exc
        try:
            content = data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise RuntimeError(f"Ollama returned an unexpected response shape: {exc}") from exc
        # Honest extraction: prefer the structured "result" field, fall back to raw text.
        text = content
        try:
            parsed = _json.loads(content)
            if isinstance(parsed, dict) and isinstance(parsed.get("result"), str):
                text = parsed["result"]
        except ValueError:
            pass
        tokens = int(data.get("prompt_eval_count") or 0) + int(data.get("eval_count") or 0)
        return LLMResponse(
            text=text,
            model=f"ollama/{self.model}",
            provenance=self.provenance,
            tokens_used=tokens,
        )

    def health(self) -> dict:
        checked_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        try:
            with self._client() as client:
                # /api/tags is Ollama's standard liveness check (short timeout).
                resp = client.get("/api/tags", timeout=5.0)
                resp.raise_for_status()
                models = [m.get("name", "") for m in resp.json().get("models", [])]
        except Exception as exc:
            return {
                "status": "FAILED",
                "detail": (
                    f"Ollama not reachable at {self.base_url}: {exc}. "
                    "Start it with `ollama serve` (never blocks app startup)."
                ),
                "checked_at": checked_at,
            }
        if not any(self.model in name or name in self.model for name in models):
            return {
                "status": "DEGRADED",
                "detail": (
                    f"Ollama is up at {self.base_url} but model '{self.model}' is not pulled "
                    f"(available: {', '.join(models) or 'none'}). Run `ollama pull {self.model}`."
                ),
                "checked_at": checked_at,
            }
        return {
            "status": "OK",
            "detail": f"Ollama reachable at {self.base_url}; model '{self.model}' ready (local inference).",
            "checked_at": checked_at,
        }


class GeminiLLMProvider(LLMProvider):
    """Real LLM via Google's Gemini API (v1beta generateContent).

    Selection:
        STOCKPULSE_LLM_PROVIDER=gemini
        GEMINI_API_KEY=<key from https://aistudio.google.com/apikey>  (required)
        GEMINI_MODEL=gemini-2.0-flash    (default; any generateContent-capable model)
        LLM_TIMEOUT_SECONDS=120          (default; generation timeout)

    This is the first REAL (non-mock, non-local) LLM provider: agent drafts
    (ideation angles, prompt text, metadata, summaries, briefings) are produced
    by the vendor model instead of deterministic templates. Responses are
    labeled THIRD_PARTY so downstream code never mistakes them for verified
    data.

    Honesty contract (same as Ollama):
    - generate() RAISES a clear RuntimeError when the key is missing, the API
      errors, or the response shape is unexpected — it NEVER returns fake text
      as if the model had answered. Callers fall back to deterministic text.
    - health() NEVER raises (never blocks app startup); it performs a free
      `models.list` call that validates the key without spending tokens.
    - The model DRAFTS; the human keeps final decisions on originality,
      rights, quality, metadata truthfulness and submission. Task instructions
      forbid guarantee language ("will sell", rankings, sales numbers).

    Privacy note: unlike Ollama, prompts DO leave the machine (Google's API).
    Prefer the ollama provider for contexts containing private USER_PROVIDED
    data; the ideation/fusion callers already keep prompts to market-level
    context.
    """

    name = "gemini"
    provenance = PROVENANCE_THIRD_PARTY
    _BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    _TASK_INSTRUCTIONS = {
        "ideate": (
            "Brainstorm original commercial-stock concept angles from the given niche. "
            "Each concept must be a genuinely new composition, not a reskin of existing "
            "stock; flag any angle that risks copying another contributor's work."
        ),
        "draft_prompt": (
            "Draft an original image-generation prompt (primary + one alternative "
            "viewpoint + negative terms). It must describe an original scene — never "
            "instruct recreating a specific existing artwork or photograph."
        ),
        "draft_metadata": (
            "Draft title and keywords for a stock asset. Keywords must truthfully "
            "describe what is actually in the image; never invent subjects, locations "
            "or properties not present."
        ),
        "summarize": "Summarize the provided items concisely and factually.",
        "briefing": (
            "Write a short daily briefing from the provided counts. Do not invent "
            "numbers; report only what the context contains."
        ),
        "explain": (
            "Explain in plain language why the given opportunity scored the way it "
            "did, citing only the evidence provided. Never promise sales, rankings, "
            "or any guaranteed outcome."
        ),
    }

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
        self.timeout = timeout if timeout is not None else float(os.environ.get("LLM_TIMEOUT_SECONDS", "120"))

    def _client(self):
        import httpx  # project dependency (requirements.txt); local import keeps module import cheap

        return httpx.Client(
            base_url=self._BASE_URL,
            headers={"x-goog-api-key": self.api_key},
            timeout=self.timeout,
        )

    def _system_prompt(self, task: str) -> str:
        instruction = self._TASK_INSTRUCTIONS.get(task, f"Perform the task '{task}' helpfully.")
        return (
            "You are StockPulse's drafting assistant for an Adobe Stock contributor. "
            "Automate repetition, never judgment: you draft, the human keeps final decisions "
            "on originality, rights, quality, metadata truthfulness and submission. "
            "Never promise sales, rankings, or guaranteed outcomes; predictions are "
            "probabilistic estimates, never certainties. "
            f"Task instruction: {instruction}"
        )

    def generate(self, request: LLMRequest) -> LLMResponse:
        import json as _json

        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Create a free key at "
                "https://aistudio.google.com/apikey and set STOCKPULSE_LLM_PROVIDER=gemini "
                "with GEMINI_API_KEY in the backend environment."
            )
        context_json = _json.dumps(request.context, default=str)
        payload = {
            "systemInstruction": {"parts": [{"text": self._system_prompt(request.task)}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                f"Task: {request.task}\nContext (JSON):\n{context_json}\n"
                                "Respond with plain text only (no markdown code fences)."
                            )
                        }
                    ],
                }
            ],
            "generationConfig": {
                "maxOutputTokens": request.max_tokens,
                "temperature": 0.7,
            },
        }
        try:
            with self._client() as client:
                resp = client.post(f"/models/{self.model}:generateContent", json=payload)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            raise RuntimeError(f"Gemini API call failed (model '{self.model}'): {exc}") from exc
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).strip()
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise RuntimeError(f"Gemini returned an unexpected response shape: {exc}") from exc
        if not text:
            # Empty candidate (e.g. all blocked by safety filters) is not a usable draft.
            raise RuntimeError(
                "Gemini returned an empty response (candidates present but no text). "
                "The prompt may have been blocked by safety filters."
            )
        usage = data.get("usageMetadata", {}) or {}
        tokens = int(usage.get("totalTokenCount") or 0)
        return LLMResponse(
            text=text,
            model=f"gemini/{self.model}",
            provenance=self.provenance,
            tokens_used=tokens,
        )

    def health(self) -> dict:
        checked_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        if not self.api_key:
            return {
                "status": "FAILED",
                "detail": "GEMINI_API_KEY is not set (never blocks app startup).",
                "checked_at": checked_at,
            }
        try:
            with self._client() as client:
                # models.list is free (no tokens) and validates the key.
                resp = client.get("/models", params={"pageSize": 1}, timeout=10.0)
                resp.raise_for_status()
        except Exception as exc:
            return {
                "status": "FAILED",
                "detail": f"Gemini API not reachable or key invalid: {exc}.",
                "checked_at": checked_at,
            }
        return {
            "status": "OK",
            "detail": f"Gemini API reachable; model '{self.model}' configured (vendor inference).",
            "checked_at": checked_at,
        }


class MockGenerationProvider(GenerationProvider):
    """Mock media generator: registers a placeholder asset record, renders nothing."""

    name = "mock_generation_provider"

    def generate_asset(self, request: GenerationRequest) -> GenerationResponse:
        # No media is rendered; the URI is a clearly-labeled placeholder.
        return GenerationResponse(
            storage_uri=f"mock://generated/{request.prompt_id}.{ 'mp4' if request.asset_type == 'VIDEO' else 'png'}",
            width_px=6000 if request.asset_type == "IMAGE" else 3840,
            height_px=3376 if request.asset_type == "IMAGE" else 2160,
            duration_seconds=8.0 if request.asset_type == "VIDEO" else None,
            provenance=PROVENANCE_MOCK,
        )

    def health(self) -> dict:
        return {
            "status": "OK",
            "detail": "Mock generation provider (no media rendered).",
            "checked_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }


# ---------------------------------------------------------------------------
# Selection (env-driven, MOCK default)
# ---------------------------------------------------------------------------

PROVENANCE_MUSE_EXPORT = "MUSE_EXPORT"
MUSE_EXPORT_LABEL = "export only — asset not auto-generated"


class MuseGenerationProvider(GenerationProvider):
    """EXPORT-ONLY provider for muse AI (Meta AI's image generator).

    Honest by design: muse AI exposes no public generation API this backend
    may call, so this provider NEVER attempts to render media and NEVER
    claims it did. generate_asset() writes the prompt pack to a local export
    file (a copy-paste-ready document for the user) and returns its URI,
    labeled "export only — asset not auto-generated".

    The prompt pack must travel inside request.parameters["prompt_pack"] as
    the plain document produced by app.services.prompt_packs.pack_document().
    Missing pack → ValueError with a clear message (never silent garbage).
    """

    name = "muse"
    provenance = PROVENANCE_MUSE_EXPORT

    def __init__(self, export_dir: str | None = None) -> None:
        import os as _os

        self.export_dir = (
            export_dir
            or _os.environ.get("STOCKPULSE_MUSE_EXPORT_DIR")
            or _os.path.join(
                _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                "exports",
                "prompt_packs",
            )
        )

    def export_prompt_pack(self, pack_document: dict) -> str:
        """Write the prompt pack document to a local file; return its URI.

        No network, no generation — a local file the user can open and
        paste into muse AI themselves.
        """
        import json as _json
        import os as _os

        if not isinstance(pack_document, dict) or not pack_document.get("primary_prompt"):
            raise ValueError(
                "Muse export requires a prompt pack document with 'primary_prompt' "
                "(see app.services.prompt_packs.pack_document)."
            )
        _os.makedirs(self.export_dir, exist_ok=True)
        concept_title = pack_document.get("concept_title", "prompt-pack")
        safe = "".join(c if (c.isalnum() or c in "-_") else "-" for c in str(concept_title))[:60]
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        filename = f"{safe or 'prompt-pack'}_{stamp}.json"
        path = _os.path.join(self.export_dir, filename)
        document = dict(pack_document)
        document["provider"] = self.name
        document["provenance"] = PROVENANCE_MUSE_EXPORT
        document["generation_claim"] = MUSE_EXPORT_LABEL
        # Honest labeling is guaranteed by the export path itself, even for
        # a hand-built document: this file never represents a generated asset.
        document.setdefault("export_only", True)
        document.setdefault("asset_auto_generated", False)
        with open(path, "w", encoding="utf-8") as fh:
            _json.dump(document, fh, indent=2, ensure_ascii=False)
        return f"file://{path}"

    def generate_asset(self, request: GenerationRequest) -> GenerationResponse:
        pack = (request.parameters or {}).get("prompt_pack")
        uri = self.export_prompt_pack(pack or {})
        return GenerationResponse(
            storage_uri=uri,
            width_px=None,
            height_px=None,
            duration_seconds=None,
            provenance=self.provenance,
        )

    def health(self) -> dict:
        return {
            "status": "OK",
            "detail": (
                "Muse provider is export-only: it writes prompt packs to local "
                "files for manual use in muse AI. No media is generated, no "
                "network calls are made."
            ),
            "export_dir": self.export_dir,
            "checked_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }


def get_trend_provider() -> TrendProvider:
    name = os.environ.get("STOCKPULSE_TREND_PROVIDER", "mock").lower()
    if name == "mock":
        return MockTrendProvider()
    raise ValueError(f"Unknown trend provider '{name}' (v1 supports only 'mock')")


def get_llm_provider() -> LLMProvider:
    name = os.environ.get("STOCKPULSE_LLM_PROVIDER", "mock").lower()
    if name == "mock":
        return MockLLMProvider()
    if name == "ollama":
        return OllamaLLMProvider()
    if name == "gemini":
        return GeminiLLMProvider()
    raise ValueError(f"Unknown LLM provider '{name}' (supported: 'mock', 'ollama', 'gemini')")


def get_generation_provider() -> GenerationProvider:
    name = os.environ.get("STOCKPULSE_GENERATION_PROVIDER", "mock").lower()
    if name == "mock":
        return MockGenerationProvider()
    if name == "muse":
        return MuseGenerationProvider()
    raise ValueError(f"Unknown generation provider '{name}' (supported: 'mock', 'muse')")


def providers_health() -> dict:
    return {
        "trend": get_trend_provider().health(),
        "llm": get_llm_provider().health(),
        "generation": get_generation_provider().health(),
    }
