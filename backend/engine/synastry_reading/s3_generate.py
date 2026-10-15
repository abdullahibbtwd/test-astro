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

Model default is ``llm_client.DEFAULT_MODEL`` (gemini-3.7-flash, matches natal). Provider follows the model id
via ``llm_client`` (claude-* -> ANTHROPIC_API_KEY, gemini-* -> GEMINI_API_KEY).
"""

from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional

import os as _os
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
import llm_client  # provider-agnostic completion (Anthropic / Gemini)

from s3_prompts import (
    build_opener_user,
    build_section_user,
    build_statements_system,
    build_translation_system,
    build_translation_user,
    build_statements_user,
    build_synthesis_system,
    build_synthesis_user,
)
from s3_sections import RoutedRecord

DEFAULT_MODEL = llm_client.DEFAULT_MODEL  # gemini-3.7-flash
# The §11 statements extraction is extraction-shaped work the reader never sees
# as prose, so it runs on the cheap model by default (falls back to the
# synthesis model if that provider is unavailable).
DEFAULT_STATEMENTS_MODEL = llm_client.DEFAULT_CHEAP_MODEL  # gpt-6-luna
# The English is a faithful per-section translation of the final Turkish (§5,
# split out of synthesis on 2026-09-24, as in the natal pipeline): mechanical,
# bounded, so it runs on the cheap model by default with the same fallback.
DEFAULT_TRANSLATION_MODEL = llm_client.DEFAULT_CHEAP_MODEL  # gpt-6-luna
DEFAULT_TRANSLATION_MAX_TOKENS = 16384
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


# Sampling parameters are removed on the Claude 5 / Opus 4.7+ family; sending `temperature`
# there returns a 400. The default model is claude-sonnet-5, so temperature is only sent to
# older models (Sonnet 4.6, Opus 4.6, …) that still accept it.
_NO_SAMPLING_PREFIXES = llm_client.NO_SAMPLING_PREFIXES


_supports_temperature = llm_client.supports_temperature


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
                },
                "required": ["key", "text_tr"],
            },
        },
    },
    "required": ["sections"],
}
TRANSLATION_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"key": {"type": "string"}, "text_en": {"type": "string"}},
    "required": ["key", "text_en"],
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


class LLMGenerator:
    """Drives the model half of S3 through llm_client (provider follows the model id). ``contract`` is the shared, cacheable system
    block (built once by the driver from the framing stance + labels)."""

    def __init__(self, contract: str, profile, *,
                 model: str = DEFAULT_MODEL,
                 synthesis_model: Optional[str] = None,
                 statements_model: Optional[str] = DEFAULT_STATEMENTS_MODEL,
                 translation_model: Optional[str] = DEFAULT_TRANSLATION_MODEL,
                 translation_max_tokens: int = DEFAULT_TRANSLATION_MAX_TOKENS,
                 max_tokens: int = DEFAULT_MAX_TOKENS,
                 synthesis_max_tokens: int = DEFAULT_SYNTHESIS_MAX_TOKENS,
                 statements_max_tokens: int = DEFAULT_STATEMENTS_MAX_TOKENS,
                 section_temperature: float = DEFAULT_SECTION_TEMPERATURE,
                 synthesis_temperature: float = DEFAULT_SYNTHESIS_TEMPERATURE,
                 max_workers: int = 8,
                 label_a: str = "sen", label_b: str = "partnerin"):
        self.contract = contract
        self.profile = profile
        self.model = model
        self.synthesis_model = synthesis_model or model
        self.statements_model = statements_model or self.synthesis_model
        self.translation_model = translation_model or self.synthesis_model
        self.translation_max_tokens = translation_max_tokens
        self.fallbacks = 0   # cheap-model calls that fell back to the synthesis model
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
        transient = llm_client.transient_errors(model)
        hard_cap = min(_HARD_TOKEN_CAP, llm_client.output_cap(model))
        budget = min(max_tokens, hard_cap)
        last_err: Optional[Exception] = None
        for attempt in range(1, _MAX_RETRIES + 1):
            t0 = time.time()
            _log(f"{label} start (attempt {attempt}, max_tokens={budget})")
            try:
                resp = llm_client.complete(
                    model, system, user, max_tokens=budget,
                    temperature=temperature if _supports_temperature(model) else None,
                    schema=schema, timeout_s=_STREAM_STALL_TIMEOUT_S, label=label)
                _log(f"{label} done in {time.time()-t0:.0f}s "
                     f"(out={resp.usage['output_tokens']} tok, stop={resp.stop_reason})")
                for k in llm_client.USAGE_KEYS:
                    self.usage[k] += resp.usage.get(k, 0)
                self.usage["calls"] += 1
                text = resp.text
                if resp.stop_reason == "max_tokens":
                    if budget >= hard_cap:
                        raise RuntimeError(
                            f"{label}: output hit the {hard_cap}-token "
                            f"ceiling and is still truncated. Reduce scope or use "
                            f"a larger-output model."
                        )
                    last_err = RuntimeError(
                        f"output truncated at {budget} tokens (max_tokens)")
                    if attempt < _MAX_RETRIES:
                        budget = min(budget * 2, hard_cap)
                        continue
                    raise last_err
                return _extract_json(text)
            except llm_client.ProviderQuotaError:
                raise                                  # not transient: fail fast
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
        p = self.profile
        if key == p.opener_key:
            user = build_opener_user(
                routed, theme=p.themes.get(key, ""), opener_key=key,
                label_a=self.label_a, label_b=self.label_b)
        else:
            degrade = (not houses_valid) and key in p.house_dependent_axes
            user = build_section_user(
                key, routed, theme=p.themes.get(key, ""),
                position=p.movement.get(key, 0), lens=p.lens.get(key, ""),
                degrade=degrade, label_a=self.label_a, label_b=self.label_b)
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

    # -- cheap-model call with fallback (translation / statements) -------------
    def _call_cheap(self, model: str, system, user: str, *, temperature: float,
                    max_tokens: int, label: str, schema: dict) -> dict:
        """Run a mechanical pass on the cheap model; if it is unavailable (no
        credits, exhausted retries) fall back ONCE to the synthesis model so a
        finished Turkish reading is never lost over its English or its statements."""
        try:
            return self._call_json(model, system, user, temperature=temperature,
                                   max_tokens=max_tokens, label=label, schema=schema)
        except (llm_client.ProviderQuotaError, RuntimeError) as err:
            if model == self.synthesis_model:
                raise
            _log(f"{label} failed on {model} ({type(err).__name__}); "
                 f"falling back to {self.synthesis_model}")
            self.fallbacks += 1
            return self._call_json(self.synthesis_model, system, user,
                                   temperature=temperature, max_tokens=max_tokens,
                                   label=f"{label}/fallback", schema=schema)

    # -- per-section English translation (§5) ---------------------------------
    def translate(self, key: str, text_tr: str) -> str:
        """Faithful English rendering of one final Turkish section."""
        if not (text_tr or "").strip():
            return ""
        system = self._system_blocks(build_translation_system("").strip())
        user = build_translation_user(key, text_tr)
        data = self._call_cheap(self.translation_model, system, user,
                                temperature=self.synthesis_temperature,
                                max_tokens=self.translation_max_tokens,
                                label=f"translate[{key}]", schema=TRANSLATION_SCHEMA)
        return data.get("text_en", "")

    # -- synthesis (§5): Turkish weave, then parallel per-section translation --
    def synthesize(self, drafts: list[SectionDraft]) -> list[dict]:
        """One Turkish synthesis pass over all drafts (one job, one language), then
        one bounded English translation per section in parallel. Returns dicts
        with key / text_tr / text_en — the same shape callers always consumed."""
        system = self._system_blocks(build_synthesis_system("").strip())
        user = build_synthesis_user([d.as_dict() for d in drafts])
        data = self._call_json(
            self.synthesis_model, system, user,
            temperature=self.synthesis_temperature,
            max_tokens=self.synthesis_max_tokens,
            label="synthesis", schema=SYNTHESIS_SCHEMA)
        sections = [{"key": sec.get("key", ""), "text_tr": sec.get("text_tr", "")}
                    for sec in data.get("sections", [])]
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            en_texts = list(pool.map(
                lambda sec: self.translate(sec["key"], sec["text_tr"]), sections))
        for sec, text_en in zip(sections, en_texts):
            sec["text_en"] = text_en
        return sections

    # -- statements (§11) -----------------------------------------------------
    def extract_statements(self, final_sections: list[dict],
                           allowed_ids_by_section: dict[str, list[str]]
                           ) -> list[dict]:
        system = self._system_blocks(build_statements_system("").strip())
        user = build_statements_user(final_sections, allowed_ids_by_section)
        data = self._call_cheap(self.statements_model, system, user,
                                temperature=DEFAULT_STATEMENTS_TEMPERATURE,
                                max_tokens=self.statements_max_tokens,
                                label="statements", schema=STATEMENTS_SCHEMA)
        return data.get("statements", [])


def make_generator(contract: str, profile, **kwargs) -> LLMGenerator:
    """Construct the runner; fail early if the chosen model's provider has no key."""
    model = kwargs.get("model") or DEFAULT_MODEL
    synth = kwargs.get("synthesis_model") or model
    statements = kwargs.get("statements_model", DEFAULT_STATEMENTS_MODEL) or synth
    translation = kwargs.get("translation_model", DEFAULT_TRANSLATION_MODEL) or synth
    for m in {model, synth, statements, translation}:
        llm_client.require_api_key(m, "S3 generation")
    return LLMGenerator(contract, profile, **kwargs)


AnthropicGenerator = LLMGenerator  # backwards-compatible name
