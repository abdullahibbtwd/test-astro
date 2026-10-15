#!/usr/bin/env python3
"""
l4_generate.py — the LLM runner for Layer 4 (L4_INTERPRETATION_SPEC.md §4-§5).

``LLMGenerator`` drives the model half of the pipeline using the prompts in
``l4_prompts.py``:

  - one API call per non-empty section (§4), run in parallel — no section call
    depends on another's output;
  - one global synthesis call (§5) over all section drafts together.

Each call returns strict JSON (the prompts demand it); this module parses it into
the §6 shape. Assembly into l4_output.json and contract validation live in
``l4_interpret.py``.

The default model is ``llm_client.DEFAULT_MODEL`` (gemini-3.7-flash). The provider follows the model
id via ``llm_client`` (claude-* -> ANTHROPIC_API_KEY, gemini-* -> GEMINI_API_KEY).
"""

from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional, Protocol

import os as _os
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
import llm_client  # provider-agnostic completion (Anthropic / Gemini)

from l4_prompts import (
    FORBIDDEN_READER_TOKENS, build_detox_prompt, build_section_prompt,
    build_section_synthesis_prompt, build_translation_prompt,
)
from l4_sections import RoutedPrinciple

# Whole-word, case-insensitive tradition-label detector — MUST match l4_validate's
# regex exactly, so the detox pass clears precisely what the validator would flag.
_FORBIDDEN_RE = re.compile(
    r"(?<![\wçğıöşü])(" + "|".join(FORBIDDEN_READER_TOKENS) + r")(?![\wçğıöşü])",
    re.IGNORECASE,
)


def _find_forbidden(text: str) -> list[str]:
    return [m.group(0) for m in _FORBIDDEN_RE.finditer(text or "")]

DEFAULT_MODEL = llm_client.DEFAULT_MODEL  # gemini-3.7-flash
# Faithful English translation + forbidden-word detox: mechanical, bounded
# passes whose output the reader sees only as a translation, so they run on
# the cheap model by default.
DEFAULT_TRANSLATION_MODEL = llm_client.DEFAULT_CHEAP_MODEL  # gpt-6-luna
# A single section is one slice of the reading. Synthesis re-emits ALL sections
# in one call, so it needs a far larger budget or its JSON truncates mid-structure.
DEFAULT_MAX_TOKENS = 8192
# Synthesis now emits BOTH languages, so its output is ~2x a single-language pass.
DEFAULT_SYNTHESIS_MAX_TOKENS = 48000
# Per-model output ceiling. The auto-grow-on-truncation logic must respect the
# ACTUAL ceiling of the model in use — hardcoding Sonnet's 64K made the "use
# Opus 4.8 (128K)" remedy impossible, because the grow loop capped at 64K for
# every model. Longest-prefix match; default is the conservative Sonnet ceiling.
_output_cap = llm_client.output_cap
DEFAULT_SECTION_TEMPERATURE = 0.7   # warm, varied Turkish prose
DEFAULT_SYNTHESIS_TEMPERATURE = 0.4  # tighter: rewrite/prune, not invent
# Per-section English translation starting budget. One section in one language is
# small; _call_json auto-grows it on the rare long section, so it never truncates.
DEFAULT_TRANSLATION_MAX_TOKENS = 16384
# Per-section synthesis starting budget. A synthesized section is <= its draft
# (synthesis prunes), and drafts run up to ~15K on dense sections; start generous
# so big sections finish in one pass (you pay only for tokens actually generated).
# Still auto-grows within the model cap if ever exceeded — but never monolithic.
DEFAULT_SECTION_SYNTHESIS_MAX_TOKENS = 20000
_MAX_RETRIES = 3
_RETRY_BACKOFF_S = 2.0
# Per-chunk read timeout: a streaming call that produces NO token for this long
# is treated as wedged and raised (then retried), so it can never hang forever.
# Slow-but-progressing generation keeps resetting it, so this doesn't cut healthy
# long outputs short.
_STREAM_STALL_TIMEOUT_S = 120.0


def _log(msg: str) -> None:
    print(f"[l4] {msg}", file=sys.stderr, flush=True)


# Sampling parameters are removed on the Claude 5 / Opus 4.7+ family; sending `temperature`
# there returns a 400. The default model is claude-sonnet-5, so temperature is only sent to
# older models (Sonnet 4.6, Opus 4.6, …) that still accept it.
_NO_SAMPLING_PREFIXES = llm_client.NO_SAMPLING_PREFIXES


_supports_temperature = llm_client.supports_temperature


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
# Synthesis is now Turkish-only (English is a separate per-section pass), so its
# single-call output is ~halved and no longer risks the ceiling for large charts.
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
                },
                "required": ["key", "text_tr"],
            },
        },
    },
    "required": ["sections"],
}
# One section, one language — bounded output, can never hit the ceiling.
TRANSLATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "key": {"type": "string"},
        "text_en": {"type": "string"},
    },
    "required": ["key", "text_en"],
}
DETOX_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"text": {"type": "string"}},
    "required": ["text"],
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
# LLM runner (provider chosen per model id by llm_client)
# ---------------------------------------------------------------------------

class LLMGenerator:
    """Drives the model half of L4 through llm_client; the provider follows the
    model id (claude-* -> Anthropic, gemini-* -> Google)."""

    def __init__(self, model: str = DEFAULT_MODEL,
                 synthesis_model: Optional[str] = None,
                 translation_model: Optional[str] = DEFAULT_TRANSLATION_MODEL,
                 max_tokens: int = DEFAULT_MAX_TOKENS,
                 synthesis_max_tokens: int = DEFAULT_SYNTHESIS_MAX_TOKENS,
                 translation_max_tokens: int = DEFAULT_TRANSLATION_MAX_TOKENS,
                 section_temperature: float = DEFAULT_SECTION_TEMPERATURE,
                 synthesis_temperature: float = DEFAULT_SYNTHESIS_TEMPERATURE,
                 max_workers: int = 6):
        self.model = model
        self.synthesis_model = synthesis_model or model
        # translation/detox model: explicit > cheap default > synthesis model
        self.translation_model = translation_model or self.synthesis_model
        self.max_tokens = max_tokens
        self.synthesis_max_tokens = synthesis_max_tokens
        self.translation_max_tokens = translation_max_tokens
        self.section_temperature = section_temperature
        self.synthesis_temperature = synthesis_temperature
        self.max_workers = max_workers
        # Real token accounting, summed across every call (thread-safe-ish: the
        # GIL makes += on ints atomic enough for this reporting use).
        self.usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
        self.fallbacks = 0   # cheap-model calls that had to fall back to the synthesis model

    # -- one call, with retry on transient errors / truncation / bad JSON -----
    def _call_json(self, model: str, system: str, user: str, *,
                   temperature: float, max_tokens: int, label: str,
                   schema: Optional[dict] = None) -> dict:
        # Stream every call: inputs are large (the full chart rides in each one)
        # and synthesis sets a high max_tokens. The SDK refuses / times out
        # non-streaming requests above ~16K max_tokens, so streaming is required,
        # not optional. Sonnet 4.6 caps output at 64K (= _HARD_TOKEN_CAP).
        transient = llm_client.transient_errors(model)
        hard_cap = _output_cap(model)
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
                for k in ("input_tokens", "output_tokens"):
                    self.usage[k] += resp.usage.get(k, 0)
                self.usage["calls"] += 1
                text = resp.text
                # A max_tokens stop means the JSON is cut off mid-structure;
                # parsing it would raise a misleading "delimiter" error. Grow the
                # budget and retry — but Sonnet 4.6 cannot emit beyond 64K, so if
                # we are already at the cap, fail with a clear message.
                if resp.stop_reason == "max_tokens":
                    if budget >= hard_cap:
                        bigger = ("" if hard_cap >= 128000 else
                                  " Reduce scope or use a larger-output model "
                                  "(e.g. --synthesis-model claude-opus-4-8, 128K).")
                        raise RuntimeError(
                            f"{label}: output hit {model}'s {hard_cap}-token ceiling "
                            f"and is still truncated.{bigger}"
                        )
                    last_err = RuntimeError(
                        f"output truncated at {budget} tokens (stop_reason=max_tokens)")
                    if attempt < _MAX_RETRIES:
                        budget = min(budget * 2, hard_cap)
                        continue
                    raise last_err
                return _extract_json(text)
            except llm_client.ProviderQuotaError:
                raise                                  # not transient: fail fast
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

    def progressive_section(self, key, routed, chart):
        """Same grounded draft pipeline, with ONB's longer opening chapter."""
        system, user = build_section_prompt(key, routed, chart)
        if key == 'core_identity':
            system += "\nONBOARDING LENGTH: Write about 450 Turkish words (400-500), in 4-6 paragraphs. Fully develop the supplied Sun-sign, Moon-sign, Ascendant and chart-ruler principles. Keep house references brief. Do not invent claims or pad with generic advice."
        data = self._call_json(self.model, system, user, temperature=self.section_temperature,
                               max_tokens=self.max_tokens, label=f'progressive_draft[{key}]', schema=SECTION_SCHEMA)
        return SectionDraft(key=data.get('key', key), text_tr=data.get('text_tr', ''))

    def section_all(self, routed_by_section: dict[str, list[RoutedPrinciple]],
                    chart: dict) -> list[SectionDraft]:
        """Run every section call in parallel (§4: no cross-dependencies)."""
        keys = list(routed_by_section.keys())
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            return list(pool.map(
                lambda k: self.section(k, routed_by_section[k], chart), keys
            ))

    # -- cheap-model call with fallback --------------------------------------
    def _call_cheap(self, system: str, user: str, *, max_tokens: int,
                    label: str, schema: dict) -> dict:
        """Run a mechanical pass (translation / detox) on the cheap translation
        model; if that model is unavailable (no credits, exhausted retries), fall
        back ONCE to the synthesis model so a finished Turkish reading is never
        lost over its English rendering."""
        try:
            return self._call_json(self.translation_model, system, user,
                                   temperature=self.synthesis_temperature,
                                   max_tokens=max_tokens, label=label, schema=schema)
        except (llm_client.ProviderQuotaError, RuntimeError) as err:
            if self.translation_model == self.synthesis_model:
                raise
            _log(f"{label} failed on {self.translation_model} ({type(err).__name__}); "
                 f"falling back to {self.synthesis_model}")
            self.fallbacks += 1
            return self._call_json(self.synthesis_model, system, user,
                                   temperature=self.synthesis_temperature,
                                   max_tokens=max_tokens, label=f"{label}/fallback",
                                   schema=schema)

    # -- per-section English translation (§5, split out of synthesis) ---------
    def translate(self, key: str, text_tr: str) -> str:
        """Faithful English rendering of one already-synthesized Turkish section.
        Bounded output (one section, one language) — never risks the ceiling."""
        if not (text_tr or "").strip():
            return ""
        system, user = build_translation_prompt(key, text_tr)
        data = self._call_cheap(system, user, max_tokens=self.translation_max_tokens,
                                label=f"translate[{key}]", schema=TRANSLATION_SCHEMA)
        return data.get("text_en", "")

    # -- one section's Turkish synthesis (§5), with all drafts as context ------
    def synthesize_section(self, key: str, own_text_tr: str,
                           all_drafts: list[dict], chart: dict,
                           low_salience_ids: list[str] | None = None) -> dict:
        system, user = build_section_synthesis_prompt(
            key, own_text_tr, all_drafts, chart, low_salience_ids)
        data = self._call_json(self.synthesis_model, system, user,
                               temperature=self.synthesis_temperature,
                               max_tokens=DEFAULT_SECTION_SYNTHESIS_MAX_TOKENS,
                               label=f"synthesis[{key}]",
                               schema=SECTION_SCHEMA)   # {key, text_tr} — same shape
        return {"key": data.get("key", key), "text_tr": data.get("text_tr", "")}

    # -- synthesis (§5): per-section (ceiling-proof), then parallel translation -
    def synthesize(self, drafts: list[SectionDraft], chart: dict,
                   low_salience_ids: list[str] | None = None) -> list[dict]:
        """Synthesize each section in its OWN bounded, parallel call — one section
        can never approach the output ceiling no matter how large the whole reading
        is. Every other section's draft rides along as read-only context, so the
        cross-section jobs (dedup / callbacks / contradiction) still hold. Then one
        bounded English translation per section, also in parallel.

        This replaces the single global synthesis call, which re-emitted all 12
        sections at once and truncated at the model's output ceiling on long charts.
        """
        as_dicts = [d.as_dict() for d in drafts]

        # Phase 1: per-section Turkish synthesis, in parallel.
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            sections = list(pool.map(
                lambda d: self.synthesize_section(
                    d.key, d.text_tr, as_dicts, chart, low_salience_ids),
                drafts))

        # Phase 2: translate each section to English, in parallel.
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            en_texts = list(pool.map(
                lambda s: self.translate(s.get("key", ""), s.get("text_tr", "")),
                sections))
        for s, text_en in zip(sections, en_texts):
            s["text_en"] = text_en

        # Phase 3: scrub any leaked tradition-label words (§7.3) that the prompts
        # failed to keep out. The validator hard-fails on these; a targeted re-ask
        # per offending (section, language) removes them before assembly.
        self._detox_sections(sections)
        return sections

    # -- §7.3 detox: remove leaked tradition labels from reader-facing text ----
    def _detox_text(self, key: str, text: str, lang: str, tries: int = 2) -> str:
        """Re-ask to strip forbidden tradition-label words from one section's text
        while preserving meaning. Bounded output; retries until clean or exhausted
        (the validator remains the backstop if a stubborn leak survives)."""
        for _ in range(tries):
            found = sorted(set(_find_forbidden(text)))
            if not found:
                return text
            system, user = build_detox_prompt(key, text, lang, found)
            data = self._call_cheap(system, user,
                                    max_tokens=DEFAULT_SECTION_SYNTHESIS_MAX_TOKENS,
                                    label=f"detox[{key}/{lang}]", schema=DETOX_SCHEMA)
            new = data.get("text", "")
            text = new if new.strip() else text
        return text

    def _detox_sections(self, sections: list[dict]) -> None:
        """Clean every (section, language) that leaks a forbidden token, in
        parallel. Mutates ``sections`` in place. No-op when nothing leaks."""
        jobs = []
        for i, s in enumerate(sections):
            if _find_forbidden(s.get("text_tr", "")):
                jobs.append((i, "text_tr", "tr"))
            if _find_forbidden(s.get("text_en", "")):
                jobs.append((i, "text_en", "en"))
        if not jobs:
            return
        _log(f"detox: {len(jobs)} section/language block(s) leak a tradition label")
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            cleaned = list(pool.map(
                lambda j: self._detox_text(sections[j[0]].get("key", ""),
                                           sections[j[0]][j[1]], j[2]),
                jobs))
        for (i, field, _lang), text in zip(jobs, cleaned):
            sections[i][field] = text


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_generator(**kwargs) -> LLMGenerator:
    """Construct the runner. Raises a clear error if the provider of the chosen
    model(s) has no API key configured."""
    model = kwargs.get("model") or DEFAULT_MODEL
    synth = kwargs.get("synthesis_model") or model
    translation = kwargs.get("translation_model", DEFAULT_TRANSLATION_MODEL) or synth
    for m in {model, synth, translation}:
        llm_client.require_api_key(m, "L4 generation")
    return LLMGenerator(**kwargs)


AnthropicGenerator = LLMGenerator  # backwards-compatible name
