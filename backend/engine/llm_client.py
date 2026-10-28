"""Provider-agnostic LLM client for the reading pipelines.

Every stage that talks to a model (natal L4, synastry S3, predictive reading,
L5 distiller, the predictive translator) goes through :func:`complete` instead
of importing a vendor SDK directly. The provider is chosen from the model id:

    claude-*           -> Anthropic   (ANTHROPIC_API_KEY, or ~/.anthropic_key)
    gemini-*           -> Google      (GEMINI_API_KEY / GOOGLE_API_KEY, or ~/.gemini_key)
    gpt-* / o*-        -> OpenAI      (OPENAI_API_KEY, or ~/.openai_key)
    anthropic:<model>  -> force Anthropic
    gemini:<model>     -> force Google
    openai:<model>     -> force OpenAI

So ``--model gemini-2.5-pro`` on any orchestrator is enough to switch vendors;
no other flag changes. Key files live in the HOME directory on purpose - this
project folder is Drive-synced and must never hold a secret.

The contract every provider satisfies:

    resp = complete(model, system, user, max_tokens=..., temperature=...,
                    schema=..., label=...)
    resp.text          # concatenated text output
    resp.stop_reason   # "end_turn" | "max_tokens" | other vendor string
    resp.usage         # dict with the keys in USAGE_KEYS (0 when unknown)

``system`` may be a plain string or an Anthropic-style list of text blocks
(with ``cache_control``); non-Anthropic providers flatten it to one string.
``schema`` is a JSON Schema dict: Anthropic gets constrained decoding, Gemini
gets ``response_json_schema`` + JSON mime type. Vendor exceptions that are
worth retrying are exposed via :func:`transient_errors` so callers keep their
own retry/backoff loops unchanged.
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Sequence, Union

# Project-wide default model. Every pipeline's DEFAULT_MODEL points here.
# Override with ASTRO_LLM_MODEL (e.g. gemini-3.8-flash or a Pro id). The default
# is a free-tier Flash model so local testing works with a Gemini free key.
# Free-tier default: gemini-2.5-flash is closed to new keys; 3.5 Flash-Lite is
# the recommended free Flash model for new Gemini API projects.
DEFAULT_MODEL = os.environ.get("ASTRO_LLM_MODEL", "gemini-3.5-flash-lite")
# Cheap model for the mechanical stages (faithful translation, forbidden-word
# detox, the L5 distiller): bounded, extraction-shaped work where the reader
# never sees the model's own prose. Defaults to the same free Flash model so a
# Gemini-only key can finish readings; set ASTRO_CHEAP_MODEL=gpt-6-luna for the
# prior OpenAI translation path. Reasoning effort for OpenAI models comes from
# OPENAI_REASONING_EFFORT (default "low"; "none" = non-reasoning mode).
DEFAULT_CHEAP_MODEL = os.environ.get("ASTRO_CHEAP_MODEL", DEFAULT_MODEL)
OPENAI_REASONING_EFFORT = os.environ.get("OPENAI_REASONING_EFFORT", "low")
# Gemini thinking level for every Gemini call (minimal | low | medium | high).
# Thinking tokens are billed at the output rate and were ~60% of billed output
# at the model default (medium). Project default is MINIMAL so free-tier
# Flash-Lite does not spend the whole output budget on thoughts. Override per
# process with GEMINI_THINKING_LEVEL, or per call via complete(thinking=...).
# Set GEMINI_THINKING_LEVEL=low|medium for heavier models.
GEMINI_THINKING_LEVEL = os.environ.get("GEMINI_THINKING_LEVEL", "minimal").lower()

USAGE_KEYS = ("input_tokens", "output_tokens",
              "cache_read_input_tokens", "cache_creation_input_tokens")

# Per-model output ceiling (longest-prefix match). The auto-grow-on-truncation
# loops in the generators must not exceed the real ceiling of the model in use.
DEFAULT_OUTPUT_CAP = 64000
MODEL_OUTPUT_CAP = {
    "claude-opus-4-8": 128000,
    "gemini-2.5": 65536,
    "gemini-3": 65536,
    "gpt-6": 128000,
    "gpt-5": 128000,
}

# Models that reject a sampling temperature (reasoning models: Anthropic's
# current line and OpenAI's gpt-5/gpt-6 families).
NO_SAMPLING_PREFIXES = (
    "claude-sonnet-5", "claude-opus-4-7", "claude-opus-4-8",
    "claude-fable-5", "claude-mythos-5",
    "gpt-5", "gpt-6", "o3", "o4",
)

# Gemini rate limiting. Google returns 429/503 with a suggested retryDelay; we
# sleep that long (or an exponential backoff with jitter) INSIDE the client
# before surfacing the error. Each wait is capped. Concurrency is also capped
# per process: extra calls wait on the gate instead of hitting the quota together.
GEMINI_MAX_CONCURRENCY = int(os.environ.get("GEMINI_MAX_CONCURRENCY", "8"))
GEMINI_429_MAX_WAITS = int(os.environ.get("GEMINI_429_MAX_WAITS", "6"))
GEMINI_RETRY_BASE_S = float(os.environ.get("GEMINI_RETRY_BASE_S", "1"))
GEMINI_RETRY_MAX_WAIT_S = float(os.environ.get("GEMINI_RETRY_MAX_WAIT_S", "60"))

_KEY_FILES = {
    "anthropic": (("ANTHROPIC_API_KEY",), "~/.anthropic_key"),
    "gemini": (("GEMINI_API_KEY", "GOOGLE_API_KEY"), "~/.gemini_key"),
    "openai": (("OPENAI_API_KEY",), "~/.openai_key"),
}


@dataclass
class LLMResponse:
    text: str
    stop_reason: str
    usage: dict = field(default_factory=lambda: {k: 0 for k in USAGE_KEYS})
    raw: object = None


# ---------------------------------------------------------------------------
# Model-id helpers
# ---------------------------------------------------------------------------

def split_model(model: str) -> tuple[str, str]:
    """Return (provider, bare_model_id). Accepts 'gemini:foo' / 'anthropic:foo'
    overrides, otherwise infers from the id prefix."""
    if ":" in model:
        prov, bare = model.split(":", 1)
        prov = prov.strip().lower()
        if prov in ("anthropic", "claude"):
            return "anthropic", bare
        if prov in ("gemini", "google"):
            return "gemini", bare
        if prov == "openai":
            return "openai", bare
        raise ValueError(f"unknown provider prefix {prov!r} in model {model!r}")
    low = model.lower()
    if low.startswith("gemini") or low.startswith("gemma"):
        return "gemini", model
    if low.startswith("claude"):
        return "anthropic", model
    if low.startswith("gpt-") or low.startswith(("o1", "o3", "o4")):
        return "openai", model
    raise ValueError(
        f"cannot infer provider from model {model!r}; use 'anthropic:<id>', "
        f"'gemini:<id>' or 'openai:<id>'")


def provider_of(model: str) -> str:
    return split_model(model)[0]


def output_cap(model: str) -> int:
    _, bare = split_model(model)
    best, best_len = DEFAULT_OUTPUT_CAP, -1
    for prefix, cap in MODEL_OUTPUT_CAP.items():
        if bare.startswith(prefix) and len(prefix) > best_len:
            best, best_len = cap, len(prefix)
    return best


def supports_temperature(model: str) -> bool:
    _, bare = split_model(model)
    return not any(bare.startswith(p) for p in NO_SAMPLING_PREFIXES)


# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------

def load_api_key(provider: str, api_key_file: Optional[str] = None) -> bool:
    """Make sure the provider's key is in os.environ. Order: existing env var,
    explicit file, then the default ~/.<provider>_key file. Returns True if a
    key is now available."""
    env_names, default_file = _KEY_FILES[provider]
    if any(os.environ.get(n) for n in env_names):
        return True
    for path in filter(None, [api_key_file, os.path.expanduser(default_file)]):
        try:
            with open(path, encoding="utf-8") as fh:
                key = fh.read().strip()
        except OSError:
            continue
        if key:
            os.environ[env_names[0]] = key
            return True
    return False


def get_api_key(provider: str) -> Optional[str]:
    load_api_key(provider)
    for n in _KEY_FILES[provider][0]:
        if os.environ.get(n):
            return os.environ[n]
    return None


def require_api_key(model: str, stage: str = "this stage") -> None:
    """Raise RuntimeError with a clear message if the model's provider has no key."""
    provider = provider_of(model)
    if load_api_key(provider):
        return
    env_names, default_file = _KEY_FILES[provider]
    raise RuntimeError(
        f"{env_names[0]} is not set - {stage} uses {model!r} via {provider} and "
        f"needs it. Export it (set {env_names[0]}=...) or put the key in "
        f"{default_file}, then retry.")


def missing_key_message(models: Sequence[str], stage: str) -> Optional[str]:
    """None if every provider used by ``models`` has a key, else the error text."""
    for m in models:
        try:
            require_api_key(m, stage)
        except RuntimeError as exc:
            return str(exc)
    return None


# ---------------------------------------------------------------------------
# System-prompt normalisation
# ---------------------------------------------------------------------------

SystemT = Union[str, Sequence[dict], None]


def _system_text(system: SystemT) -> str:
    if system is None:
        return ""
    if isinstance(system, str):
        return system
    return "\n\n".join(b.get("text", "") for b in system if b.get("type", "text") == "text")


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

_anthropic_clients: dict = {}


def _anthropic_client(timeout_s: float):
    import anthropic
    import httpx
    key = round(timeout_s, 3)
    cli = _anthropic_clients.get(key)
    if cli is None:
        cli = anthropic.Anthropic(
            timeout=httpx.Timeout(timeout_s, connect=15.0, write=60.0, pool=15.0))
        _anthropic_clients[key] = cli
    return cli


def _anthropic_complete(model: str, system: SystemT, user: str, *,
                        max_tokens: int, temperature: Optional[float],
                        schema: Optional[dict], timeout_s: float,
                        thinking: Optional[str] = None) -> LLMResponse:
    client = _anthropic_client(timeout_s)
    kwargs = dict(model=model, max_tokens=max_tokens,
                  messages=[{"role": "user", "content": user}])
    if system:
        kwargs["system"] = system
    if temperature is not None and supports_temperature(model):
        kwargs["temperature"] = temperature
    if schema is not None:
        kwargs["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
    # Stream every call: the SDK refuses non-streaming requests with large
    # max_tokens, and the finite read timeout doubles as a wedged-stream guard.
    with client.messages.stream(**kwargs) as stream:
        resp = stream.get_final_message()
    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    u = getattr(resp, "usage", None)
    usage = {k: (getattr(u, k, 0) or 0) if u is not None else 0 for k in USAGE_KEYS}
    return LLMResponse(text=text, stop_reason=str(getattr(resp, "stop_reason", "") or ""),
                       usage=usage, raw=resp)


def _anthropic_transient() -> tuple:
    import anthropic
    return (anthropic.RateLimitError, anthropic.APIConnectionError,
            anthropic.APITimeoutError, anthropic.InternalServerError)


# ---------------------------------------------------------------------------
# Gemini (google-genai)
# ---------------------------------------------------------------------------

_gemini_clients: dict = {}
_RETRY_DELAY_RE = re.compile(r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s")


class _GeminiGate:
    """Process-wide cap. Callers past the limit wait; they are not dropped."""

    def __init__(self):
        self._cv = threading.Condition()
        self._inflight = 0

    def limit(self) -> int:
        try:
            return max(1, int(os.environ.get("GEMINI_MAX_CONCURRENCY", "8")))
        except ValueError:
            return 8

    def __enter__(self):
        with self._cv:
            while self._inflight >= self.limit():
                self._cv.wait()
            self._inflight += 1
        return self

    def __exit__(self, *_exc):
        with self._cv:
            self._inflight -= 1
            self._cv.notify()


_gemini_gate = _GeminiGate()


def _provider_status(exc) -> Optional[int]:
    for attr in ("code", "status_code", "status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    return None


def _parse_retry_after(exc) -> Optional[float]:
    """Google's 429/503 body carries a RetryInfo.retryDelay like '23s'."""
    match = _RETRY_DELAY_RE.search(str(exc))
    if not match:
        return None
    return float(match.group(1))


def _retry_wait_s(exc, attempt: int) -> float:
    """Honor retry-after when present. Otherwise exponential backoff.
    Jitter spreads retries. Neither path waits longer than the max."""
    max_wait = max(0.0, GEMINI_RETRY_MAX_WAIT_S)
    parsed = _parse_retry_after(exc)
    if parsed is not None:
        base = max(0.0, parsed)
    else:
        base = max(0.0, GEMINI_RETRY_BASE_S) * (2 ** attempt)
    spread = min(base, max_wait) * 0.2
    jitter = random.uniform(0, spread) if spread else 0.0
    return min(max_wait, base + jitter)


def _retry_delay_s(exc, fallback: float) -> float:
    """Back-compat helper. Prefer _retry_wait_s for new call sites."""
    parsed = _parse_retry_after(exc)
    if parsed is not None:
        return min(parsed, max(0.0, GEMINI_RETRY_MAX_WAIT_S))
    return fallback


def _gemini_client(timeout_s: float):
    from google import genai
    from google.genai import types
    key = round(timeout_s, 3)
    cli = _gemini_clients.get(key)
    if cli is None:
        api_key = get_api_key("gemini")
        if not api_key:
            require_api_key("gemini:x", "Gemini generation")
        cli = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=int(timeout_s * 1000),
                # The SDK's own retry is disabled: the generators run their own
                # backoff loop and log each attempt.
                retry_options=types.HttpRetryOptions(attempts=1)),
        )
        _gemini_clients[key] = cli
    return cli


def _gemini_complete(model: str, system: SystemT, user: str, *,
                     max_tokens: int, temperature: Optional[float],
                     schema: Optional[dict], timeout_s: float,
                     thinking: Optional[str] = None) -> LLMResponse:
    from google.genai import types
    client = _gemini_client(timeout_s)
    cfg = dict(
        max_output_tokens=max_tokens,
        # No tools are ever passed; disabling AFC silences the SDK's per-call
        # "direct use of automatic function calling" warning.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    level = (thinking or GEMINI_THINKING_LEVEL or "").upper()
    if level and level != "DEFAULT":
        cfg["thinking_config"] = types.ThinkingConfig(thinking_level=level)
    sys_text = _system_text(system)
    if sys_text:
        cfg["system_instruction"] = sys_text
    if temperature is not None:
        cfg["temperature"] = temperature
    if schema is not None:
        cfg["response_mime_type"] = "application/json"
        cfg["response_json_schema"] = schema
    with _gemini_gate:
        resp = client.models.generate_content(
            model=model, contents=user, config=types.GenerateContentConfig(**cfg))

    cands = getattr(resp, "candidates", None) or []
    finish = None
    if cands:
        finish = getattr(cands[0], "finish_reason", None)
        finish = getattr(finish, "name", None) or (str(finish) if finish else None)
    if finish == "MAX_TOKENS":
        stop = "max_tokens"
    elif finish in (None, "STOP", "FINISH_REASON_UNSPECIFIED"):
        stop = "end_turn"
    else:
        stop = finish.lower()

    text = ""
    if cands and getattr(cands[0], "content", None) and cands[0].content.parts:
        text = "".join(
            p.text for p in cands[0].content.parts
            if getattr(p, "text", None) and not getattr(p, "thought", False))
    if not text and not cands:
        # Prompt-level block: surface the reason instead of an empty string.
        pf = getattr(resp, "prompt_feedback", None)
        reason = getattr(getattr(pf, "block_reason", None), "name", None)
        raise RuntimeError(f"Gemini returned no candidates (block_reason={reason!r})")

    um = getattr(resp, "usage_metadata", None)
    usage = {k: 0 for k in USAGE_KEYS}
    if um is not None:
        cached = getattr(um, "cached_content_token_count", 0) or 0
        usage["input_tokens"] = (getattr(um, "prompt_token_count", 0) or 0) - cached
        usage["output_tokens"] = ((getattr(um, "candidates_token_count", 0) or 0)
                                  + (getattr(um, "thoughts_token_count", 0) or 0))
        usage["cache_read_input_tokens"] = cached
    return LLMResponse(text=text, stop_reason=stop, usage=usage, raw=resp)


def _gemini_transient() -> tuple:
    import httpx
    from google.genai import errors
    return (errors.ServerError, _GeminiTooManyRequests,
            httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError)


class ProviderQuotaError(RuntimeError):
    """The provider refused for a non-transient billing/quota reason (e.g. OpenAI
    ``insufficient_quota``: no credits). Retrying cannot help; callers may fall
    back to another model."""


class _GeminiTooManyRequests(Exception):
    pass


def _log_retry(status: Optional[int], delay: float, attempt: int) -> None:
    """Optional smoke/ops log. Status and wait only — never a prompt or key."""
    path = os.environ.get("ASTRO_BUDGET_LOG")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(json.dumps({
                "retry": True,
                "status": status,
                "wait_s": round(delay, 3),
                "attempt": attempt,
            }) + "\n")
    except OSError:
        return


def _wrap_gemini(fn):
    """On 429 or 503, sleep for retry-after or exponential backoff with jitter,
    then retry, up to GEMINI_429_MAX_WAITS times. Each sleep is at most
    GEMINI_RETRY_MAX_WAIT_S. The concurrency gate is inside the call, so a wait
    does not hold a slot. Only then re-raise as the transient marker."""
    def inner(*a, **kw):
        waits = 0
        while True:
            try:
                return fn(*a, **kw)
            except Exception as exc:
                if _provider_status(exc) not in (429, 503):
                    raise
                if waits >= GEMINI_429_MAX_WAITS:
                    raise _GeminiTooManyRequests(str(exc)) from exc
                delay = _retry_wait_s(exc, waits)
                status = _provider_status(exc)
                print(f"[llm] gemini {status} - waiting {delay:.0f}s "
                      f"({waits + 1}/{GEMINI_429_MAX_WAITS})",
                      file=sys.stderr, flush=True)
                _log_retry(status, delay, waits + 1)
                time.sleep(delay)
                waits += 1
    return inner


_gemini_complete = _wrap_gemini(_gemini_complete)


# ---------------------------------------------------------------------------
# OpenAI (Responses API)
# ---------------------------------------------------------------------------

_openai_clients: dict = {}


def _openai_client(timeout_s: float, api_key: Optional[str] = None):
    """One cached client per (timeout, key). ``api_key`` = a per-request key (e.g. a
    user's own OpenAI key, PA_04 llm_route); None = the platform key."""
    import openai
    key = (round(timeout_s, 3), api_key or "")
    cli = _openai_clients.get(key)
    if cli is None:
        if not api_key:
            api_key = get_api_key("openai")
        if not api_key:
            require_api_key("openai:x", "OpenAI generation")
        # The generators run their own retry/backoff loop and log each attempt.
        cli = openai.OpenAI(api_key=api_key, timeout=timeout_s, max_retries=0)
        _openai_clients[key] = cli
    return cli


def _openai_complete(model: str, system: SystemT, user: str, *,
                     max_tokens: int, temperature: Optional[float],
                     schema: Optional[dict], timeout_s: float,
                     thinking: Optional[str] = None, strict: bool = False,
                     api_key: Optional[str] = None) -> LLMResponse:
    client = _openai_client(timeout_s, api_key)
    kwargs: dict = dict(model=model, input=user, max_output_tokens=max_tokens)
    sys_text = _system_text(system)
    if sys_text:
        kwargs["instructions"] = sys_text
    if temperature is not None and supports_temperature(model):
        kwargs["temperature"] = temperature
    if schema is not None:
        # Non-strict by default: the corpus schemas use features strict mode forbids
        # (optional keys); the callers parse and validate the JSON anyway. Callers whose
        # schemas are strict-compatible (PA planner/composer) pass strict=True.
        kwargs["text"] = {"format": {"type": "json_schema", "name": "result",
                                     "schema": schema, "strict": bool(strict)}}
    effort = thinking or OPENAI_REASONING_EFFORT
    if effort:
        kwargs["reasoning"] = {"effort": effort}
    import openai
    try:
        resp = client.responses.create(**kwargs)
    except openai.RateLimitError as exc:
        # OpenAI reports "no credits" as a 429 too. That one is not transient.
        body = str(getattr(exc, "body", None) or exc)
        if "insufficient_quota" in body or "credit_balance_exhausted" in body:
            raise ProviderQuotaError(
                f"OpenAI account has no credits for {model!r} (insufficient_quota). "
                f"Add credits at platform.openai.com/settings/organization/billing, or "
                f"run with another model.") from exc
        raise

    status = getattr(resp, "status", None)
    reason = getattr(getattr(resp, "incomplete_details", None), "reason", None)
    if status == "incomplete" and reason == "max_output_tokens":
        stop = "max_tokens"
    elif status in (None, "completed"):
        stop = "end_turn"
    else:
        stop = str(reason or status).lower()
    text = getattr(resp, "output_text", None) or ""
    u = getattr(resp, "usage", None)
    usage = {k: 0 for k in USAGE_KEYS}
    if u is not None:
        cached = getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0
        usage["input_tokens"] = (getattr(u, "input_tokens", 0) or 0) - cached
        usage["output_tokens"] = getattr(u, "output_tokens", 0) or 0
        usage["cache_read_input_tokens"] = cached
    return LLMResponse(text=text, stop_reason=stop, usage=usage, raw=resp)


def _openai_transient() -> tuple:
    import openai
    return (openai.RateLimitError, openai.APIConnectionError,
            openai.APITimeoutError, openai.InternalServerError)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_PROVIDERS = {
    "anthropic": (_anthropic_complete, _anthropic_transient),
    "gemini": (_gemini_complete, _gemini_transient),
    "openai": (_openai_complete, _openai_transient),
}


def complete(model: str, system: SystemT, user: str, *,
             max_tokens: int, temperature: Optional[float] = None,
             schema: Optional[dict] = None, timeout_s: float = 120.0,
             label: str = "", thinking: Optional[str] = None,
             strict: bool = False, route: Optional[dict] = None) -> LLMResponse:
    """One completion on whichever provider ``model`` belongs to. ``thinking``
    is the reasoning level (Gemini thinking_level / OpenAI reasoning effort);
    None = the provider default from the environment (GEMINI_THINKING_LEVEL /
    OPENAI_REASONING_EFFORT). Ignored by Anthropic (adaptive thinking).

    ``strict`` (OpenAI only): strict Structured Outputs for ``schema``.
    ``route`` (OpenAI only): per-request routing, e.g. ``{"openai_api_key": ...}`` for a
    user's own key; absent -> the platform key. Other providers ignore both."""
    provider, bare = split_model(model)
    fn, _ = _PROVIDERS[provider]
    extra: dict = {}
    if provider == "openai":
        extra = {"strict": strict, "api_key": (route or {}).get("openai_api_key")}
    return fn(bare, system, user, max_tokens=max_tokens, temperature=temperature,
              schema=schema, timeout_s=timeout_s, thinking=thinking, **extra)


def transient_errors(model: str) -> tuple:
    """Exception classes worth a backoff-and-retry for this model's provider."""
    provider, _ = split_model(model)
    return _PROVIDERS[provider][1]()


def all_transient_errors(*models: str) -> tuple:
    """Union of transient classes across the given models (section + synthesis
    model may sit on different providers)."""
    seen: list = []
    for m in models:
        for cls in transient_errors(m):
            if cls not in seen:
                seen.append(cls)
    return tuple(seen)
