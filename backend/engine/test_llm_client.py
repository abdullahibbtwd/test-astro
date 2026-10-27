"""Offline tests for llm_client: provider routing, key handling, and the
Gemini/Anthropic response normalisation (SDKs are stubbed, no network)."""
from __future__ import annotations

import os
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llm_client as lc  # noqa: E402


# --- routing -----------------------------------------------------------------

@pytest.mark.parametrize("model,prov,bare", [
    ("claude-sonnet-5", "anthropic", "claude-sonnet-5"),
    ("gemini-2.5-pro", "gemini", "gemini-2.5-pro"),
    ("gemini:custom-tuned", "gemini", "custom-tuned"),
    ("anthropic:claude-opus-4-8", "anthropic", "claude-opus-4-8"),
])
def test_split_model(model, prov, bare):
    assert lc.split_model(model) == (prov, bare)


def test_unknown_model_raises():
    with pytest.raises(ValueError):
        lc.split_model("llama-4-maverick")


def test_output_cap_and_temperature():
    assert lc.output_cap("claude-opus-4-8") == 128000
    assert lc.output_cap("claude-sonnet-5") == 64000
    assert lc.output_cap("gemini-2.5-flash") == 65536
    assert not lc.supports_temperature("claude-sonnet-5")
    assert lc.supports_temperature("gemini-2.5-pro")


# --- keys --------------------------------------------------------------------

def test_key_from_file(tmp_path, monkeypatch):
    for n in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(n, raising=False)
    monkeypatch.setattr(lc, "_KEY_FILES", {
        "gemini": (("GEMINI_API_KEY", "GOOGLE_API_KEY"), str(tmp_path / "k")),
        "anthropic": lc._KEY_FILES["anthropic"],
    })
    assert lc.load_api_key("gemini") is False
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        lc.require_api_key("gemini-2.5-pro", "test")
    (tmp_path / "k").write_text("abc\n")
    assert lc.load_api_key("gemini") is True
    assert os.environ["GEMINI_API_KEY"] == "abc"
    assert lc.missing_key_message(["gemini-2.5-pro"], "x") is None


def test_google_api_key_alias(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "zzz")
    assert lc.get_api_key("gemini") == "zzz"


# --- Gemini normalisation (stubbed SDK) ----------------------------------------

class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _fake_gemini(monkeypatch, finish="STOP", text='{"a":1}', cached=0):
    captured = {}

    class FakeModels:
        def generate_content(self, *, model, contents, config):
            captured.update(model=model, contents=contents, config=config)
            part = _Obj(text=text, thought=False)
            cand = _Obj(finish_reason=_Obj(name=finish),
                        content=_Obj(parts=[part]))
            return _Obj(candidates=[cand],
                        usage_metadata=_Obj(prompt_token_count=100,
                                            candidates_token_count=20,
                                            thoughts_token_count=5,
                                            cached_content_token_count=cached),
                        prompt_feedback=None)

    class FakeClient:
        def __init__(self, **kw):
            captured["client_kwargs"] = kw
            self.models = FakeModels()

    class GenerateContentConfig(dict):
        def __init__(self, **kw):
            super().__init__(**kw)

    types_mod = types.SimpleNamespace(
        GenerateContentConfig=GenerateContentConfig,
        HttpOptions=lambda **kw: kw, HttpRetryOptions=lambda **kw: kw,
        AutomaticFunctionCallingConfig=lambda **kw: kw,
        ThinkingConfig=lambda **kw: kw)
    errors_mod = types.SimpleNamespace(
        APIError=Exception, ClientError=type("ClientError", (Exception,), {}),
        ServerError=type("ServerError", (Exception,), {}))
    genai_mod = types.SimpleNamespace(Client=FakeClient, types=types_mod,
                                      errors=errors_mod)
    google_mod = types.ModuleType("google")
    google_mod.genai = genai_mod
    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.genai", genai_mod)
    monkeypatch.setitem(sys.modules, "google.genai.types", types_mod)
    monkeypatch.setitem(sys.modules, "google.genai.errors", errors_mod)
    monkeypatch.setattr(lc, "_gemini_clients", {})
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    return captured


def test_gemini_complete_normalises(monkeypatch):
    cap = _fake_gemini(monkeypatch, cached=30)
    system = [{"type": "text", "text": "A", "cache_control": {"type": "ephemeral"}},
              {"type": "text", "text": "B"}]
    resp = lc.complete("gemini-2.5-pro", system, "hi", max_tokens=123,
                       temperature=0.7, schema={"type": "object"})
    assert resp.text == '{"a":1}'
    assert resp.stop_reason == "end_turn"
    assert resp.usage["input_tokens"] == 70
    assert resp.usage["output_tokens"] == 25
    assert resp.usage["cache_read_input_tokens"] == 30
    cfg = cap["config"]
    assert cfg["system_instruction"] == "A\n\nB"
    assert cfg["max_output_tokens"] == 123
    assert cfg["temperature"] == 0.7
    assert cfg["response_mime_type"] == "application/json"
    assert cfg["response_json_schema"] == {"type": "object"}
    assert cap["model"] == "gemini-2.5-pro"
    assert cap["client_kwargs"]["api_key"] == "k"


def test_gemini_max_tokens_maps(monkeypatch):
    _fake_gemini(monkeypatch, finish="MAX_TOKENS")
    resp = lc.complete("gemini-2.5-flash", "s", "u", max_tokens=10)
    assert resp.stop_reason == "max_tokens"


def test_gemini_429_is_transient(monkeypatch):
    _fake_gemini(monkeypatch)
    monkeypatch.setattr(lc, "GEMINI_429_MAX_WAITS", 0)  # no sleeping in tests
    from google.genai import errors

    def boom(*a, **kw):
        exc = errors.ClientError("rate")
        exc.code = 429
        raise exc
    monkeypatch.setattr(lc, "_gemini_complete", lc._wrap_gemini(boom))
    with pytest.raises(lc.transient_errors("gemini-2.5-pro")):
        lc._gemini_complete("m", None, "u", max_tokens=1, temperature=None,
                            schema=None, timeout_s=1)


def test_all_transient_errors_union(monkeypatch):
    _fake_gemini(monkeypatch)
    both = lc.all_transient_errors("claude-sonnet-5", "gemini-2.5-pro")
    import anthropic
    assert anthropic.RateLimitError in both
    assert lc._GeminiTooManyRequests in both


def test_gemini_429_waits_then_succeeds(monkeypatch):
    _fake_gemini(monkeypatch)
    from google.genai import errors
    slept = []
    monkeypatch.setattr(lc.time, "sleep", lambda s: slept.append(s))
    monkeypatch.setattr(lc, "GEMINI_429_MAX_WAITS", 2)
    calls = {"n": 0}

    def flaky(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            exc = errors.ClientError('{"retryDelay": "7s"}')
            exc.code = 429
            raise exc
        return "ok"
    assert lc._wrap_gemini(flaky)() == "ok"
    assert slept == [8.0]


def test_retry_delay_parse():
    assert lc._retry_delay_s(Exception("x retryDelay: '23s'"), 10) == 24.0
    assert lc._retry_delay_s(Exception("nope"), 10) == 10


# --- OpenAI normalisation (stubbed SDK) ----------------------------------------

def _fake_openai(monkeypatch, status="completed", reason=None, text='{"b":2}'):
    captured = {}

    class FakeResponses:
        def create(self, **kw):
            captured.update(kw)
            return _Obj(status=status, output_text=text,
                        incomplete_details=_Obj(reason=reason) if reason else None,
                        usage=_Obj(input_tokens=100, output_tokens=40,
                                   input_tokens_details=_Obj(cached_tokens=25)))

    class FakeClient:
        def __init__(self, **kw):
            captured["client_kwargs"] = kw
            self.responses = FakeResponses()

    class _E(Exception):
        pass
    mod = types.SimpleNamespace(OpenAI=FakeClient, RateLimitError=_E, APIConnectionError=_E,
                                APITimeoutError=_E, InternalServerError=_E)
    monkeypatch.setitem(sys.modules, "openai", mod)
    monkeypatch.setattr(lc, "_openai_clients", {})
    monkeypatch.setenv("OPENAI_API_KEY", "ok")
    return captured


def test_openai_routing():
    assert lc.split_model("gpt-6-luna") == ("openai", "gpt-6-luna")
    assert lc.split_model("openai:gpt-6-sol") == ("openai", "gpt-6-sol")
    assert lc.output_cap("gpt-6-luna") == 128000
    assert not lc.supports_temperature("gpt-6-luna")   # reasoning family: no temperature


def test_openai_complete_normalises(monkeypatch):
    cap = _fake_openai(monkeypatch)
    resp = lc.complete("gpt-6-luna", "SYS", "hi", max_tokens=99, temperature=0.7,
                       schema={"type": "object"})
    assert resp.text == '{"b":2}' and resp.stop_reason == "end_turn"
    assert resp.usage["input_tokens"] == 75 and resp.usage["output_tokens"] == 40
    assert resp.usage["cache_read_input_tokens"] == 25
    assert cap["model"] == "gpt-6-luna" and cap["instructions"] == "SYS" and cap["input"] == "hi"
    assert cap["max_output_tokens"] == 99
    assert "temperature" not in cap                    # dropped for reasoning models
    assert cap["text"]["format"]["schema"] == {"type": "object"}
    assert cap["reasoning"]["effort"] == lc.OPENAI_REASONING_EFFORT
    assert cap["client_kwargs"]["api_key"] == "ok" and cap["client_kwargs"]["max_retries"] == 0


def test_openai_truncation_maps(monkeypatch):
    _fake_openai(monkeypatch, status="incomplete", reason="max_output_tokens")
    assert lc.complete("gpt-6-luna", None, "u", max_tokens=5).stop_reason == "max_tokens"


def test_gemini_thinking_level_default_minimal(monkeypatch):
    cap = _fake_gemini(monkeypatch)
    lc.complete("gemini-3.7-flash", "s", "u", max_tokens=10)
    assert cap["config"]["thinking_config"] == {"thinking_level": "MINIMAL"}
    cap = _fake_gemini(monkeypatch)
    lc.complete("gemini-3.7-flash", "s", "u", max_tokens=10, thinking="medium")
    assert cap["config"]["thinking_config"] == {"thinking_level": "MEDIUM"}
