#!/usr/bin/env python3
"""
s3_generate.py — the LLM runner for S3 (SYNASTRY_READING_SPEC.md §5).

Mirrors L4's generator: parallel section calls + one synthesis pass, plus a
statements-extraction pass (§11). The shared contract block is sent once with
``cache_control`` so every call reuses it (§5 prompt caching); only the
per-section record list varies.

Calls:
  - section_all: the seven axes + the opener, in parallel (§5).
  - synthesize: one global pass -> final tr+en per section (§5, §6).
  - extract_statements: atomic statements with source ids (§11).

Model default is ``claude-sonnet-4-6`` (matches natal). Requires ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional

from s3_prompts import (
    build_opener_user,
    build_section_user,
    build_statements_system,
    build_statements_user,
    build_synthesis_system,
    build_synthesis_user,
)
from s3_sections import WHAT_EACH_BRINGS, RoutedRecord

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 8192
DEFAULT_SYNTHESIS_MAX_TOKENS = 48000
DEFAULT_STATEMENTS_MAX_TOKENS = 32000
_HARD_TOKEN_CAP = 64000
DEFAULT_SECTION_TEMPERATURE = 0.7
DEFAULT_SYNTHESIS_TEMPERATURE = 0.4
DEFAULT_STATEMENTS_TEMPERATURE = 0.2
_MAX_RETRIES = 3
_RETRY_BACKOFF_S = 2.0
_STREAM_STALL_TIMEOUT_S = 120.0


def _log(msg: str) -> None:
    print(f"[s3] {msg}", file=sys.stderr, flush=True)


# JSON Schemas for constrained decoding (guarantee valid, schema-conforming JSON).
SECTION_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"key": {"type": "string"}, "text_tr": {"type": "string"}},
    "required": ["key", "text_tr"],
}
SYNTHESIS_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "sections": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
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
STATEMENTS_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "statements": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "section": {"type": "string"},
                    "text_tr": {"type": "string"},
                    "text_en": {"type": "string"},
                    "source_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["section", "text_tr", "text_en", "source_ids"],
            },
        },
    },
    "required": ["statements"],
}


@dataclass
class SectionDraft:
    key: str
    text_tr: str

    def as_dict(self) -> dict:
        return {"key": self.key, "text_tr": self.text_tr}


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


class AnthropicGenerator:
    """Drives the model half of S3. ``contract`` is the shared, cacheable system
    block (built once by the driver from the framing stance + labels)."""

    def __init__(self, contract: str, *,
                 model: str = DEFAULT_MODEL,
                 synthesis_model: Optional[str] = None,
                 max_tokens: int = DEFAULT_MAX_TOKENS,
                 synthesis_max_tokens: int = DEFAULT_SYNTHESIS_MAX_TOKENS,
                 statements_max_tokens: int = DEFAULT_STATEMENTS_MAX_TOKENS,
                 section_temperature: float = DEFAULT_SECTION_TEMPERATURE,
                 synthesis_temperature: float = DEFAULT_SYNTHESIS_TEMPERATURE,
                 max_workers: int = 8,
                 label_a: str = "sen", label_b: str = "partnerin"):
        import anthropic
        import httpx
        self._anthropic = anthropic
        self._client = anthropic.Anthropic(
            timeout=httpx.Timeout(
                _STREAM_STALL_TIMEOUT_S, connect=15.0, write=60.0, pool=15.0)
        )
        self.contract = contract
        self.model = model
        self.synthesis_model = synthesis_model or model
        self.max_tokens = max_tokens
        self.synthesis_max_tokens = synthesis_max_tokens
        self.statements_max_tokens = statements_max_tokens
        self.section_temperature = section_temperature
        self.synthesis_temperature = synthesis_temperature
        self.max_workers = max_workers
        self.label_a = label_a
        self.label_b = label_b
        self.usage = {"input_tokens": 0, "output_tokens": 0,
                      "cache_read_input_tokens": 0,
                      "cache_creation_input_tokens": 0, "calls": 0}

    # -- shared system block, marked cacheable (§5 prompt caching) -------------
    def _system_blocks(self, extra: str = "") -> list[dict]:
        blocks = [{
            "type": "text",
            "text": self.contract,
            "cache_control": {"type": "ephemeral"},
        }]
        if extra:
            blocks.append({"type": "text", "text": extra})
        return blocks

    def _call_json(self, model: str, system, user: str, *,
                   temperature: float, max_tokens: int, label: str,
                   schema: Optional[dict] = None) -> dict:
        transient = (
            self._anthropic.RateLimitError,
            self._anthropic.APIConnectionError,
            self._anthropic.APITimeoutError,
            self._anthropic.InternalServerError,
        )
        budget = max_tokens
        last_err: Optional[Exception] = None
        for attempt in range(1, _MAX_RETRIES + 1):
            t0 = time.time()
            _log(f"{label} start (attempt {attempt}, max_tokens={budget})")
            try:
                kwargs = dict(
                    model=model, max_tokens=budget, temperature=temperature,
                    system=system, messages=[{"role": "user", "content": user}],
                )
                if schema is not None:
                    kwargs["output_config"] = {
                        "format": {"type": "json_schema", "schema": schema}}
                with self._client.messages.stream(**kwargs) as stream:
                    resp = stream.get_final_message()
                _log(f"{label} done in {time.time()-t0:.0f}s "
                     f"(out={getattr(getattr(resp,'usage',None),'output_tokens',0)} tok, "
                     f"stop={getattr(resp,'stop_reason',None)})")
                u = getattr(resp, "usage", None)
                if u is not None:
                    self.usage["input_tokens"] += getattr(u, "input_tokens", 0) or 0
                    self.usage["output_tokens"] += getattr(u, "output_tokens", 0) or 0
                    self.usage["cache_read_input_tokens"] += \
                        getattr(u, "cache_read_input_tokens", 0) or 0
                    self.usage["cache_creation_input_tokens"] += \
                        getattr(u, "cache_creation_input_tokens", 0) or 0
                    self.usage["calls"] += 1
                text = "".join(
                    b.text for b in resp.content
                    if getattr(b, "type", None) == "text"
                )
                if getattr(resp, "stop_reason", None) == "max_tokens":
                    if budget >= _HARD_TOKEN_CAP:
                        raise RuntimeError(
                            f"{label}: output hit the {_HARD_TOKEN_CAP}-token "
                            f"ceiling and is still truncated. Reduce scope or use "
                            f"a larger-output model."
                        )
                    last_err = RuntimeError(
                        f"output truncated at {budget} tokens (max_tokens)")
                    if attempt < _MAX_RETRIES:
                        budget = min(budget * 2, _HARD_TOKEN_CAP)
                        continue
                    raise last_err
                return _extract_json(text)
            except transient as err:
                last_err = err
                _log(f"{label} {type(err).__name__} after {time.time()-t0:.0f}s "
                     + ("- retrying" if attempt < _MAX_RETRIES else "- giving up"))
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_BACKOFF_S * attempt)
            except json.JSONDecodeError as err:
                last_err = err
                _log(f"{label} unparseable JSON - retrying")
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_BACKOFF_S)
        raise RuntimeError(
            f"S3 generation failed for {label} after {_MAX_RETRIES} attempts: "
            f"{last_err}"
        ) from last_err

    # -- one section (§5) -----------------------------------------------------
    def section(self, key: str, routed: list[RoutedRecord], *,
                houses_valid: bool) -> SectionDraft:
        if key == WHAT_EACH_BRINGS:
            user = build_opener_user(routed, label_a=self.label_a,
                                     label_b=self.label_b)
        else:
            user = build_section_user(key, routed, houses_valid=houses_valid,
                                      label_a=self.label_a, label_b=self.label_b)
        data = self._call_json(
            self.model, self._system_blocks(), user,
            temperature=self.section_temperature, max_tokens=self.max_tokens,
            label=f"section[{key}]", schema=SECTION_SCHEMA)
        return SectionDraft(key=data.get("key", key),
                            text_tr=data.get("text_tr", ""))

    def section_all(self, routed_by_section: dict[str, list[RoutedRecord]], *,
                    houses_valid: bool) -> list[SectionDraft]:
        keys = list(routed_by_section.keys())
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            return list(pool.map(
                lambda k: self.section(k, routed_by_section[k],
                                       houses_valid=houses_valid),
                keys))

    # -- synthesis (§5) -------------------------------------------------------
    def synthesize(self, drafts: list[SectionDraft]) -> list[dict]:
        system = self._system_blocks(build_synthesis_system("").strip())
        user = build_synthesis_user([d.as_dict() for d in drafts])
        data = self._call_json(
            self.synthesis_model, system, user,
            temperature=self.synthesis_temperature,
            max_tokens=self.synthesis_max_tokens,
            label="synthesis", schema=SYNTHESIS_SCHEMA)
        return data.get("sections", [])

    # -- statements (§11) -----------------------------------------------------
    def extract_statements(self, final_sections: list[dict],
                           allowed_ids_by_section: dict[str, list[str]]
                           ) -> list[dict]:
        system = self._system_blocks(build_statements_system("").strip())
        user = build_statements_user(final_sections, allowed_ids_by_section)
        data = self._call_json(
            self.synthesis_model, system, user,
            temperature=DEFAULT_STATEMENTS_TEMPERATURE,
            max_tokens=self.statements_max_tokens,
            label="statements", schema=STATEMENTS_SCHEMA)
        return data.get("statements", [])


def make_generator(contract: str, **kwargs) -> AnthropicGenerator:
    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set - S3 generation needs it. Export the "
            "key and re-run."
        )
    return AnthropicGenerator(contract, **kwargs)
