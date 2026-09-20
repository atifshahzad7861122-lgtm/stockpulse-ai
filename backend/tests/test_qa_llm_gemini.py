"""Gemini LLM provider tests.

Covers the new GeminiLLMProvider in app/providers/providers.py:
- provider selection via STOCKPULSE_LLM_PROVIDER=gemini
- request shape (URL, x-goog-api-key header, systemInstruction/contents body)
- response parsing (candidates -> text, usageMetadata -> tokens)
- honesty contract: missing key / API error / malformed / empty -> RuntimeError,
  NEVER fake text
- health() never raises; validates the key with a free models.list call

No real Google API needed: all HTTP is faked through httpx.MockTransport, so
these tests never touch the network. Selection/import/init must also never
touch the network.
"""

from __future__ import annotations

import httpx
import pytest

from app.providers.providers import (
    LLMRequest,
    GeminiLLMProvider,
    MockLLMProvider,
    PROVENANCE_MOCK,
    PROVENANCE_THIRD_PARTY,
    get_llm_provider,
)


@pytest.fixture()
def provider(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
    return GeminiLLMProvider()


def _install_mock_transport(monkeypatch, handler):
    """Route every httpx.Client created by the provider through MockTransport."""
    real_client = httpx.Client

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", factory)


def _ok_response(text: str = "Concept one: rooftop garden at dawn.") -> dict:
    return {
        "candidates": [
            {"content": {"parts": [{"text": text}], "role": "model"}},
        ],
        "usageMetadata": {
            "promptTokenCount": 40,
            "candidatesTokenCount": 12,
            "totalTokenCount": 52,
        },
    }


def test_selection_gemini_via_env(monkeypatch):
    monkeypatch.setenv("STOCKPULSE_LLM_PROVIDER", "gemini")
    provider = get_llm_provider()
    assert isinstance(provider, GeminiLLMProvider)
    assert provider.name == "gemini"
    assert provider.provenance == PROVENANCE_THIRD_PARTY


def test_selection_defaults_to_mock(monkeypatch):
    monkeypatch.delenv("STOCKPULSE_LLM_PROVIDER", raising=False)
    assert isinstance(get_llm_provider(), MockLLMProvider)


def test_selection_unknown_still_raises(monkeypatch):
    monkeypatch.setenv("STOCKPULSE_LLM_PROVIDER", "gpt-99")
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_llm_provider()


def test_env_config_respected(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-pro")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "45")
    provider = GeminiLLMProvider()
    assert provider.model == "gemini-2.5-pro"
    assert provider.timeout == 45.0


def test_init_does_not_touch_network(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("network touched during init")

    monkeypatch.setattr(httpx, "Client", boom)
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    provider = GeminiLLMProvider()
    assert provider.model == "gemini-2.0-flash"


def test_generate_request_shape_and_parsing(provider, monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["api_key_header"] = request.headers.get("x-goog-api-key")
        import json as _json

        seen["body"] = _json.loads(request.content.decode())
        return httpx.Response(200, json=_ok_response())

    _install_mock_transport(monkeypatch, handler)
    resp = provider.generate(LLMRequest(task="ideate", context={"micro_niche": "x"}, max_tokens=500))

    assert seen["url"].endswith("/models/gemini-2.0-flash:generateContent")
    assert seen["api_key_header"] == "test-key-123"
    body = seen["body"]
    assert "systemInstruction" in body
    assert body["contents"][0]["role"] == "user"
    assert body["generationConfig"]["maxOutputTokens"] == 500
    assert resp.text == "Concept one: rooftop garden at dawn."
    assert resp.model == "gemini/gemini-2.0-flash"
    assert resp.provenance == PROVENANCE_THIRD_PARTY
    assert resp.tokens_used == 52


def test_generate_joins_multi_part_text(provider, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "Hello "}, {"text": "world"}]}},
                ],
                "usageMetadata": {},
            },
        )

    _install_mock_transport(monkeypatch, handler)
    resp = provider.generate(LLMRequest(task="summarize", context={}))
    assert resp.text == "Hello world"
    assert resp.tokens_used == 0


def test_generate_without_key_raises_not_fakes(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    provider = GeminiLLMProvider()
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY is not set"):
        provider.generate(LLMRequest(task="ideate", context={}))


def test_generate_api_error_raises(provider, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "API key not valid"}})

    _install_mock_transport(monkeypatch, handler)
    with pytest.raises(RuntimeError, match="Gemini API call failed"):
        provider.generate(LLMRequest(task="ideate", context={}))


def test_generate_malformed_response_raises(provider, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    _install_mock_transport(monkeypatch, handler)
    with pytest.raises(RuntimeError, match="unexpected response shape"):
        provider.generate(LLMRequest(task="ideate", context={}))


def test_generate_empty_text_raises(provider, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": "  "}]}}]}
        )

    _install_mock_transport(monkeypatch, handler)
    with pytest.raises(RuntimeError, match="empty response"):
        provider.generate(LLMRequest(task="ideate", context={}))


def test_health_without_key_is_failed_not_raise(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    provider = GeminiLLMProvider()
    result = provider.health()
    assert result["status"] == "FAILED"
    assert "GEMINI_API_KEY" in result["detail"]


def test_health_validates_key_with_free_models_list(provider, monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["api_key_header"] = request.headers.get("x-goog-api-key")
        return httpx.Response(200, json={"models": [{"name": "models/gemini-2.0-flash"}]})

    _install_mock_transport(monkeypatch, handler)
    result = provider.health()
    assert result["status"] == "OK"
    assert "/models" in seen["url"]
    assert ":generateContent" not in seen["url"]
    assert seen["api_key_header"] == "test-key-123"


def test_health_api_down_is_failed_not_raise(provider, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"message": "bad key"}})

    _install_mock_transport(monkeypatch, handler)
    result = provider.health()
    assert result["status"] == "FAILED"


def test_mock_path_labels_unchanged(monkeypatch):
    """With the default mock provider, ideation notes keep their exact old text."""
    from app.providers.providers import LLMResponse, MockLLMProvider

    monkeypatch.delenv("STOCKPULSE_LLM_PROVIDER", raising=False)
    llm = get_llm_provider()
    assert isinstance(llm, MockLLMProvider)
    resp = llm.generate(LLMRequest(task="ideate", context={"micro_niche": "n", "count": 1}))
    assert isinstance(resp, LLMResponse)
    assert resp.provenance == PROVENANCE_MOCK
