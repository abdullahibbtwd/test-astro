#!/usr/bin/env python3
"""
pr_generate.py — the LLM runner for the predictive reading (PREDICTIVE_READING_SPEC §2, §7).

Mirrors the L4/S3 generators: the shared system block is sent once with ``cache_control``
so every call in a horizon reuses it (§2 prompt caching), and the beat calls fan out in
parallel. The orchestrator (``read_forecast.py``) owns the call GRAPH (how many beats, the
synthesis, the §8 re-ask); this module owns one call each, with retry/backoff, a stall
guard, and constrained-JSON decoding.

Model default is ``llm_client.DEFAULT_MODEL`` (gemini-3.7-flash); provider follows the model id via ``llm_client``
(claude-* -> ANTHROPIC_API_KEY, gemini-* -> GEMINI_API_KEY). Needs a key for real generation;
tests inject a fake generator instead.
"""

from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import os as _os
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
import llm_client  # provider-agnostic completion (Anthropic / Gemini)

DEFAULT_MODEL = llm_client.DEFAULT_MODEL  # gemini-3.7-flash
DEFAULT_MAX_TOKENS = 4096
_HARD_TOKEN_CAP = 64000
DEFAULT_TEMPERATURE = 0.7          # §7 — only sent to models that still accept it (see below)
_MAX_RETRIES = 3
_RETRY_BACKOFF_S = 2.0
_STREAM_STALL_TIMEOUT_S = 120.0

# Sampling parameters (temperature/top_p/top_k) are REMOVED on the Claude 5 / Opus 4.7+
# family — sending `temperature` there returns a 400 ("`temperature` is deprecated for this
# model"). The default model is claude-sonnet-5, so temperature is dropped by default and
# only forwarded to older models (Sonnet 4.6, Opus 4.6, Haiku 4.5, …) that still honor it.
_NO_SAMPLING_PREFIXES = llm_client.NO_SAMPLING_PREFIXES


_supports_temperature = llm_client.supports_temperature


def _log(msg: str) -> None:
    print(f"[pr] {msg}", file=sys.stderr, flush=True)


# Constrained-decoding schemas (guarantee valid JSON with exactly the requested keys).
DAY_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"reading": {"type": "string"}}, "required": ["reading"],
}
BEAT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"beat": {"type": "string"}}, "required": ["beat"],
}
SYNTHESIS_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"overview": {"type": "string"}, "focus": {"type": "string"}},
    "required": ["overview", "focus"],
}


def _one_key_schema(key: str) -> dict:
    return {"type": "object", "additionalProperties": False,
            "properties": {key: {"type": "string"}}, "required": [key]}


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start:end + 1], strict=False)
        raise


class LLMGenerator:
    """Drives the model half of the predictive reading through llm_client. ``system_block`` is the shared,
    cacheable prefix (built once by the driver from §7.1 + the surface-planets toggle)."""

    def __init__(self, system_block: str, *,
                 model: str = DEFAULT_MODEL,
                 synthesis_model: Optional[str] = None,
                 max_tokens: int = DEFAULT_MAX_TOKENS,
                 temperature: float = DEFAULT_TEMPERATURE,
                 max_workers: int = 4):
        self.system_block = system_block
        self.model = model
        self.synthesis_model = synthesis_model or model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_workers = max_workers
        self.usage = {"input_tokens": 0, "output_tokens": 0,
                      "cache_read_input_tokens": 0,
                      "cache_creation_input_tokens": 0, "calls": 0}

    # -- shared system block, marked cacheable (§2) ---------------------------
    def _system(self) -> list[dict]:
        return [{"type": "text", "text": self.system_block,
                 "cache_control": {"type": "ephemeral"}}]

    def _call_json(self, model: str, user: str, *, label: str,
                   schema: dict, max_tokens: Optional[int] = None) -> dict:
        transient = llm_client.transient_errors(model)
        hard_cap = min(_HARD_TOKEN_CAP, llm_client.output_cap(model))
        budget = min(max_tokens or self.max_tokens, hard_cap)
        last_err: Optional[Exception] = None
        for attempt in range(1, _MAX_RETRIES + 1):
            t0 = time.time()
            _log(f"{label} start (attempt {attempt}, max_tokens={budget})")
            try:
                resp = llm_client.complete(
                    model, self._system(), user, max_tokens=budget,
                    temperature=self.temperature if _supports_temperature(model) else None,
                    schema=schema, timeout_s=_STREAM_STALL_TIMEOUT_S, label=label)
                for k in llm_client.USAGE_KEYS:
                    self.usage[k] += resp.usage.get(k, 0)
                self.usage["calls"] += 1
                text = resp.text
                if resp.stop_reason == "max_tokens":
                    if budget >= hard_cap:
                        raise RuntimeError(
                            f"{label}: hit the {hard_cap}-token ceiling, still truncated.")
                    last_err = RuntimeError(f"truncated at {budget} tokens")
                    if attempt < _MAX_RETRIES:
                        budget = min(budget * 2, hard_cap)
                        continue
                    raise last_err
                _log(f"{label} done in {time.time()-t0:.0f}s")
                return _extract_json(text)
            except transient as err:
                last_err = err
                _log(f"{label} {type(err).__name__} - "
                     + ("retrying" if attempt < _MAX_RETRIES else "giving up"))
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_BACKOFF_S * attempt)
            except json.JSONDecodeError as err:
                last_err = err
                _log(f"{label} unparseable JSON - retrying")
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_BACKOFF_S)
        raise RuntimeError(
            f"predictive reading failed for {label} after {_MAX_RETRIES} attempts: "
            f"{last_err}") from last_err

    # -- the four call kinds --------------------------------------------------
    def day(self, user: str) -> dict:
        return self._call_json(self.model, user, label="day", schema=DAY_SCHEMA)

    def beat(self, user: str, label: str) -> str:
        data = self._call_json(self.model, user, label=f"beat[{label}]", schema=BEAT_SCHEMA)
        return data.get("beat", "")

    def beats(self, jobs: list[tuple[str, str]]) -> dict[str, str]:
        """Run beat calls in parallel. `jobs` = [(segment_key, user_prompt), ...].
        Returns {segment_key: beat_text}."""
        def _run(job):
            key, user = job
            return key, self.beat(user, key)
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            return dict(pool.map(_run, jobs))

    def synthesize(self, user: str) -> dict:
        return self._call_json(self.synthesis_model, user, label="synthesis",
                               schema=SYNTHESIS_SCHEMA)

    def reask(self, user: str, key: str) -> str:
        data = self._call_json(self.model, user, label=f"reask[{key}]",
                               schema=_one_key_schema(key))
        return data.get(key, "")


def make_generator(system_block: str, **kwargs) -> LLMGenerator:
    """Construct the runner; fail early if the chosen model's provider has no key."""
    model = kwargs.get("model") or DEFAULT_MODEL
    for m in {model, kwargs.get("synthesis_model") or model}:
        llm_client.require_api_key(m, "predictive reading generation")
    return LLMGenerator(system_block, **kwargs)


AnthropicGenerator = LLMGenerator  # backwards-compatible name
