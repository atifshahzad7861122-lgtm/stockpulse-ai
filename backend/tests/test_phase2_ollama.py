"""Ollama LLM provider tests (user-supplied research report).

Covers the new OllamaLLMProvider in app/providers/providers.py:
- provider selection via STOCKPULSE_LLM_PROVIDER=ollama
- graceful degradation when the local endpoint is unreachable (mocked httpx)
- structured JSON output parsing (mocked /api/chat response)

No real Ollama needed: all HTTP is faked through httpx.MockTransport, so these
tests never touch the network. Selection/import/init of the provider must also
never touch the network.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.providers.providers import (
    LLMRequest,
    MockLLMProvider,
    OllamaLLMProvider,
    PROVENANCE_LOCAL,
    PROVENANCE_MOCK,
    get_llm_provider,
)


@pytest.fixture()
def provider(monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
    return OllamaLLMProvider()


def _install_mock_transport(monkeypatch, handler):
    """Route every httpx.Client created by the provider through MockTransport."""
    real_client = httpx.Client

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", factory)


def _chat_response(content: str, prompt_eval: int = 12, eval_count: int = 25) -> dict:
    return {
        "model": "llama3.1",
        "message": {"role": "assistant", "content": content},
        "done": True,
        "prompt_eval_count": prompt_eval,
        "eval_count": eval_count,
    }


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def test_selection_ollama_via_env(monkeypatch):
    monkeypatch.setenv("STOCKPULSE_LLM_PROVIDER", "ollama")
    provider = get_llm_provider()
    assert isinstance(provider, OllamaLLMProvider)
    assert provider.name == "ollama"


def test_selection_defaults_to_mock(monkeypatch):
    monkeypatch.delenv("STOCKPULSE_LLM_PROVIDER", raising=False)
    assert isinstance(get_llm_provider(), MockLLMProvider)


def test_selection_unknown_raises(monkeypatch):
    monkeypatch.setenv("STOCKPULSE_LLM_PROVIDER", "gpt-99")
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_llm_provider()


def test_env_config_respected_and_base_url_normalized(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/")
    monkeypatch.setenv("OLLAMA_MODEL", "mistral")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "30")
    provider = OllamaLLMProvider()
    assert provider.base_url == "http://localhost:11434"
    assert provider.model == "mistral"
    assert provider.timeout == 30.0


def test_init_does_not_touch_network(monkeypatch):
    """Constructing the provider must never open a connection."""

    def boom(*args, **kwargs):
        raise AssertionError("network touched during init")

    monkeypatch.setattr(httpx, "Client", boom)
    provider = OllamaLLMProvider()
    assert provider.model == "llama3.1"


# ---------------------------------------------------------------------------
# Structured JSON output parsing (mocked /api/chat)
# ---------------------------------------------------------------------------


def test_generate_parses_structured_json_result(provider, monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json=_chat_response('{"result": "concept A; concept B"}'))

    _install_mock_transport(monkeypatch, handler)
    resp = provider.generate(LLMRequest(task="ideate", context={"micro_niche": "vintage film"}))

    assert seen["path"] == "/api/chat"
    assert seen["body"]["format"] == "json"
    assert seen["body"]["stream"] is False
    assert seen["body"]["model"] == "llama3.1"
    assert resp.text == "concept A; concept B"
    assert resp.model == "ollama/llama3.1"
    assert resp.provenance == PROVENANCE_LOCAL
    assert resp.provenance != PROVENANCE_MOCK  # local inference is never labeled MOCK
    assert resp.tokens_used == 37


def test_generate_request_shape(provider, monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json=_chat_response('{"result": "ok"}'))

    _install_mock_transport(monkeypatch, handler)
    provider.generate(LLMRequest(task="draft_prompt", context={"subject": "lighthouse"}, max_tokens=500))

    body = seen["body"]
    assert body["options"]["num_predict"] == 500
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["system", "user"]
    assert "JSON" in body["messages"][0]["content"]
    assert "draft_prompt" in body["messages"][1]["content"]


def test_generate_falls_back_to_raw_text_when_not_json(provider, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_chat_response("plain text, no JSON here"))

    _install_mock_transport(monkeypatch, handler)
    resp = provider.generate(LLMRequest(task="summarize", context={}))
    assert resp.text == "plain text, no JSON here"


def test_generate_falls_back_when_result_field_missing(provider, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_chat_response('{"other": "field"}'))

    _install_mock_transport(monkeypatch, handler)
    resp = provider.generate(LLMRequest(task="summarize", context={}))
    assert resp.text == '{"other": "field"}'


def test_generate_unexpected_shape_raises(provider, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "envelope"})

    _install_mock_transport(monkeypatch, handler)
    with pytest.raises(RuntimeError, match="unexpected response shape"):
        provider.generate(LLMRequest(task="ideate", context={}))


# ---------------------------------------------------------------------------
# Graceful degradation when the local endpoint is unreachable
# ---------------------------------------------------------------------------


def test_generate_raises_clear_error_when_unreachable(provider, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    _install_mock_transport(monkeypatch, handler)
    with pytest.raises(RuntimeError) as excinfo:
        provider.generate(LLMRequest(task="ideate", context={}))
    msg = str(excinfo.value)
    assert "http://localhost:11434" in msg
    assert "ollama serve" in msg
    # Never returns fake text as if a model had answered.


def test_generate_http_error_raises(provider, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    _install_mock_transport(monkeypatch, handler)
    with pytest.raises(RuntimeError, match="Ollama unavailable"):
        provider.generate(LLMRequest(task="ideate", context={}))


def test_health_failed_when_unreachable(provider, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    _install_mock_transport(monkeypatch, handler)
    health = provider.health()  # must never raise — app startup must not block
    assert health["status"] == "FAILED"
    assert "ollama serve" in health["detail"]
    assert health["checked_at"]


def test_health_ok_when_model_pulled(provider, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": "llama3.1:latest"}]})

    _install_mock_transport(monkeypatch, handler)
    health = provider.health()
    assert health["status"] == "OK"
    assert "local inference" in health["detail"]


def test_health_degraded_when_model_not_pulled(provider, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "mistral:latest"}]})

    _install_mock_transport(monkeypatch, handler)
    health = provider.health()
    assert health["status"] == "DEGRADED"
    assert "ollama pull llama3.1" in health["detail"]
