#!/usr/bin/env python3
"""
l4_generate.py — the LLM runner for Layer 4 (L4_INTERPRETATION_SPEC.md §4-§5).

``AnthropicGenerator`` drives the model half of the pipeline using the prompts in
``l4_prompts.py``:

  - one API call per non-empty section (§4), run in parallel — no section call
    depends on another's output;
  - one global synthesis call (§5) over all section drafts together.

Each call returns strict JSON (the prompts demand it); this module parses it into
the §6 shape. Assembly into l4_output.json and contract validation live in
``l4_interpret.py``.

The default model is Sonnet (``claude-sonnet-4-6``). Requires ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional, Protocol

from l4_prompts import build_section_prompt, build_synthesis_prompt
from l4_sections import RoutedPrinciple

DEFAULT_MODEL = "claude-sonnet-4-6"
# A single section is one slice of the reading. Synthesis re-emits ALL sections
# in one call, so it needs a far larger budget or its JSON truncates mid-structure.
DEFAULT_MAX_TOKENS = 8192
# Synthesis now emits BOTH languages, so its output is ~2x a single-language pass.
DEFAULT_SYNTHESIS_MAX_TOKENS = 48000
_HARD_TOKEN_CAP = 64000              # Sonnet 4.x output ceiling
DEFAULT_SECTION_TEMPERATURE = 0.7   # warm, varied Turkish prose
DEFAULT_SYNTHESIS_TEMPERATURE = 0.4  # tighter: rewrite/prune, not invent
_MAX_RETRIES = 3
_RETRY_BACKOFF_S = 2.0
# Per-chunk read timeout: a streaming call that produces NO token for this long
# is treated as wedged and raised (then retried), so it can never hang forever.
# Slow-but-progressing generation keeps resetting it, so this doesn't cut healthy
# long outputs short.
_STREAM_STALL_TIMEOUT_S = 120.0


def _log(msg: str) -> None:
    print(f"[l4] {msg}", file=sys.stderr, flush=True)


# JSON Schemas for structured outputs (constrained decoding). With these the API
# guarantees valid, schema-conforming JSON — no more unescaped-quote breakage in
# the prose. Grounding is structural (attached from routing, §3), so the model
# emits prose only — no claim trace to bloat or break the output.
SECTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "key": {"type": "string"},
        "text_tr": {"type": "string"},
    },
    "required": ["key", "text_tr"],
}
SYNTHESIS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "key": {"type": "string"},
                    "text_tr": {"type": "string"},
                    "text_en": {"type": "string"},
                },
                "required": ["key", "text_tr", "text_en"],
            },
        },
    },
    "required": ["sections"],
}


@dataclass
class SectionDraft:
    key: str
    text_tr: str

    def as_dict(self) -> dict:
        return {"key": self.key, "text_tr": self.text_tr}


class Generator(Protocol):
    def section_all(self, routed_by_section: dict[str, list[RoutedPrinciple]],
                    chart: dict) -> list[SectionDraft]: ...

    def synthesize(self, drafts: list[SectionDraft], chart: dict,
                   low_salience_ids: list[str] | None = None) -> list[dict]: ...


# ---------------------------------------------------------------------------
# JSON extraction — models occasionally wrap JSON in prose or code fences.
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    # strict=False tolerates raw control chars (e.g. literal newlines models
    # sometimes leave inside string values).
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start:end + 1], strict=False)
        raise


# ---------------------------------------------------------------------------
# Anthropic runner
# ---------------------------------------------------------------------------

class AnthropicGenerator:
    def __init__(self, model: str = DEFAULT_MODEL,
                 synthesis_model: Optional[str] = None,
                 max_tokens: int = DEFAULT_MAX_TOKENS,
                 synthesis_max_tokens: int = DEFAULT_SYNTHESIS_MAX_TOKENS,
                 section_temperature: float = DEFAULT_SECTION_TEMPERATURE,
                 synthesis_temperature: float = DEFAULT_SYNTHESIS_TEMPERATURE,
                 max_workers: int = 6):
        import anthropic  # lazy: only needed when actually generating
        import httpx
        self._anthropic = anthropic
        # Finite read timeout = stall guard. connect/write/pool are generous; the
        # read leg is the one that protects against a wedged stream.
        self._client = anthropic.Anthropic(
            timeout=httpx.Timeout(
                _STREAM_STALL_TIMEOUT_S, connect=15.0, write=60.0, pool=15.0)
        )
        self.model = model
        self.synthesis_model = synthesis_model or model
        self.max_tokens = max_tokens
        self.synthesis_max_tokens = synthesis_max_tokens
        self.section_temperature = section_temperature
        self.synthesis_temperature = synthesis_temperature
        self.max_workers = max_workers
        # Real token accounting, summed across every call (thread-safe-ish: the
        # GIL makes += on ints atomic enough for this reporting use).
        self.usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0}

    # -- one call, with retry on transient errors / truncation / bad JSON -----
    def _call_json(self, model: str, system: str, user: str, *,
                   temperature: float, max_tokens: int, label: str,
                   schema: Optional[dict] = None) -> dict:
        # Stream every call: inputs are large (the full chart rides in each one)
        # and synthesis sets a high max_tokens. The SDK refuses / times out
        # non-streaming requests above ~16K max_tokens, so streaming is required,
        # not optional. Sonnet 4.6 caps output at 64K (= _HARD_TOKEN_CAP).
        transient = (
            self._anthropic.RateLimitError,
            self._anthropic.APIConnectionError,
            self._anthropic.APITimeoutError,   # wedged-stream stall guard fires here
            self._anthropic.InternalServerError,
        )
        budget = max_tokens
        last_err: Optional[Exception] = None
        for attempt in range(1, _MAX_RETRIES + 1):
            t0 = time.time()
            _log(f"{label} start (attempt {attempt}, max_tokens={budget})")
            try:
                kwargs = dict(
                    model=model,
                    max_tokens=budget,
                    temperature=temperature,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                if schema is not None:
                    # Constrained decoding: guarantees valid, schema-conforming JSON.
                    kwargs["output_config"] = {
                        "format": {"type": "json_schema", "schema": schema}
                    }
                with self._client.messages.stream(**kwargs) as stream:
                    resp = stream.get_final_message()
                _log(f"{label} done in {time.time()-t0:.0f}s "
                     f"(out={getattr(getattr(resp,'usage',None),'output_tokens',0)} tok, "
                     f"stop={getattr(resp,'stop_reason',None)})")
                u = getattr(resp, "usage", None)
                if u is not None:
                    self.usage["input_tokens"] += getattr(u, "input_tokens", 0) or 0
                    self.usage["output_tokens"] += getattr(u, "output_tokens", 0) or 0
                    self.usage["calls"] += 1
                text = "".join(
                    b.text for b in resp.content
                    if getattr(b, "type", None) == "text"
                )
                # A max_tokens stop means the JSON is cut off mid-structure;
                # parsing it would raise a misleading "delimiter" error. Grow the
                # budget and retry — but Sonnet 4.6 cannot emit beyond 64K, so if
                # we are already at the cap, fail with a clear message.
                if getattr(resp, "stop_reason", None) == "max_tokens":
                    if budget >= _HARD_TOKEN_CAP:
                        raise RuntimeError(
                            f"{label}: output hit the model's {_HARD_TOKEN_CAP}-token "
                            f"ceiling and is still truncated. Reduce scope or use a "
                            f"larger-output model (e.g. Opus 4.8 supports 128K)."
                        )
                    last_err = RuntimeError(
                        f"output truncated at {budget} tokens (stop_reason=max_tokens)")
                    if attempt < _MAX_RETRIES:
                        budget = min(budget * 2, _HARD_TOKEN_CAP)
                        continue
                    raise last_err
                return _extract_json(text)
            except transient as err:               # backoff and retry
                last_err = err
                _log(f"{label} {type(err).__name__} after {time.time()-t0:.0f}s "
                     f"- retrying" if attempt < _MAX_RETRIES else
                     f"{label} {type(err).__name__} after {time.time()-t0:.0f}s "
                     f"- giving up")
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_BACKOFF_S * attempt)
            except json.JSONDecodeError as err:     # bad JSON: retry the call
                last_err = err
                _log(f"{label} unparseable JSON - retrying")
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_BACKOFF_S)
        raise RuntimeError(
            f"L4 generation failed for {label} after {_MAX_RETRIES} attempts: "
            f"{last_err}"
        ) from last_err

    # -- per-section call (§4) ------------------------------------------------
    def section(self, key: str, routed: list[RoutedPrinciple],
                chart: dict) -> SectionDraft:
        system, user = build_section_prompt(key, routed, chart)
        data = self._call_json(self.model, system, user,
                               temperature=self.section_temperature,
                               max_tokens=self.max_tokens,
                               label=f"section[{key}]",
                               schema=SECTION_SCHEMA)
        return SectionDraft(
            key=data.get("key", key),
            text_tr=data.get("text_tr", ""),
        )

    def section_all(self, routed_by_section: dict[str, list[RoutedPrinciple]],
                    chart: dict) -> list[SectionDraft]:
        """Run every section call in parallel (§4: no cross-dependencies)."""
        keys = list(routed_by_section.keys())
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            return list(pool.map(
                lambda k: self.section(k, routed_by_section[k], chart), keys
            ))

    # -- single global synthesis call (§5) ------------------------------------
    def synthesize(self, drafts: list[SectionDraft], chart: dict,
                   low_salience_ids: list[str] | None = None) -> list[dict]:
        system, user = build_synthesis_prompt(
            [d.as_dict() for d in drafts], chart, low_salience_ids)
        data = self._call_json(self.synthesis_model, system, user,
                               temperature=self.synthesis_temperature,
                               max_tokens=self.synthesis_max_tokens,
                               label="synthesis",
                               schema=SYNTHESIS_SCHEMA)
        return data.get("sections", [])


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_generator(**kwargs) -> AnthropicGenerator:
    """Construct the Anthropic runner. Raises a clear error if no API key is
    configured (the SDK reads ANTHROPIC_API_KEY from the environment)."""
    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set - L4 generation needs it. Export the "
            "key and re-run (e.g. set ANTHROPIC_API_KEY=sk-...)."
        )
    return AnthropicGenerator(**kwargs)
