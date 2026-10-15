#!/usr/bin/env python3
"""
pr_validate.py — the deterministic contract enforcer for the predictive reading
(PREDICTIVE_READING_SPEC §8, §11).

``validate(reading, ctx)`` returns a list of error strings; empty means the reading may
ship. The mask lint is split so the caller can honor §11.2: a Tier-A hit is
build-blocking, a Tier-B hit is a violation to fix. Word-count checks assume the §8
re-ask has already run (the orchestrator owns that loop); this module reports whatever
is still out of range.

Shares its ban vocabulary with the prompt (``pr_prompts``) so the two never drift.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Optional

from pr_events import HORIZON_KEYS, WORD_TARGETS
from pr_prompts import (
    MODERN_CONTEXT, MODERN_HARD, TECH_CONTEXT, TECH_HARD,
    TIER_A_CONTEXT, TIER_A_HARD,
)

WORD_TOLERANCE = 0.15           # §11.3 ±15%
SPARSE_FLOOR_FRAC = 0.60        # §9 shorter output allowed to 60% of the word minimum


# ---------------------------------------------------------------------------
# Ban regexes (built once). Whole-word, Turkish-letter aware on the borders.
# Three buckets, each un-banned at a different astro_detail level (see pr_prompts).
# ---------------------------------------------------------------------------
def _hard_re(terms: list[str]) -> re.Pattern:
    return re.compile(
        r"(?<![\wçğıöşüÇĞİÖŞÜ])(" + "|".join(re.escape(t) for t in terms)
        + r")(?![\wçğıöşüÇĞİÖŞÜ])", re.IGNORECASE)


def _finder(hard_terms: list[str], ctx_patterns: list[str]):
    hard_re = _hard_re(hard_terms)
    ctx_res = [re.compile(p, re.IGNORECASE) for p in ctx_patterns]

    def find(text: str) -> list[str]:
        text = text or ""
        hits = [m.group(0) for m in hard_re.finditer(text)]
        for rx in ctx_res:
            hits += [m.group(0) for m in rx.finditer(text)]
        return hits
    return find


find_tier_a = _finder(TIER_A_HARD, TIER_A_CONTEXT)   # classical machinery
find_modern = _finder(MODERN_HARD, MODERN_CONTEXT)   # aspect names, retrograde, transit-driver
find_tech = _finder(TECH_HARD, TECH_CONTEXT)         # house numbers, phase words, house systems


# ---------------------------------------------------------------------------
# Planet lint (§11.5). Map Turkish + English planet words to a canonical name so
# "no planet may appear that is not in the input event list" can be checked.
# ---------------------------------------------------------------------------
_PLANET_WORDS = {
    "sun": "Sun", "güneş": "Sun", "gunes": "Sun",
    "moon": "Moon", "ay": "Moon",
    "mercury": "Mercury", "merkür": "Mercury", "merkur": "Mercury",
    "venus": "Venus", "venüs": "Venus",
    "mars": "Mars",
    "jupiter": "Jupiter", "jüpiter": "Jupiter",
    "saturn": "Saturn", "satürn": "Saturn", "saturn": "Saturn",
    "uranus": "Uranus", "uranüs": "Uranus",
    "neptune": "Neptune", "neptün": "Neptune", "neptun": "Neptune",
    "pluto": "Pluto", "plüton": "Pluto", "pluton": "Pluto",
}
# "ay" (Moon) is also the Turkish word for "month" — too ambiguous to lint, so it is
# excluded from the leak scan (the prompt still forbids naming mechanics around it).
_PLANET_SCAN = {k: v for k, v in _PLANET_WORDS.items() if k not in ("ay",)}
_PLANET_RE = re.compile(
    r"(?<![\wçğıöşüÇĞİÖŞÜ])(" + "|".join(re.escape(w) for w in _PLANET_SCAN)
    + r")(?![\wçğıöşüÇĞİÖŞÜ])", re.IGNORECASE)


def find_planet_mentions(text: str) -> set[str]:
    return {_PLANET_SCAN[m.group(1).lower()] for m in _PLANET_RE.finditer(text or "")}


# A 4-digit year that is outside the forecast window is a fabricated date (§11.5).
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


# ---------------------------------------------------------------------------
# Word counting
# ---------------------------------------------------------------------------
def word_count(text: str) -> int:
    return len((text or "").split())


def bounds(horizon: str, key: str, *, sparse: bool) -> tuple[int, int]:
    lo, hi = WORD_TARGETS[horizon][key]
    floor = lo * (SPARSE_FLOOR_FRAC if sparse else (1 - WORD_TOLERANCE))
    ceil = hi * (1 + WORD_TOLERANCE)
    return math.floor(floor), math.ceil(ceil)


# ---------------------------------------------------------------------------
# Validation context
# ---------------------------------------------------------------------------
@dataclass
class ValidationContext:
    horizon: str
    profile: object                       # pr_profiles.Profile
    surface_planets: bool = True
    sparse: bool = False
    astro_detail: str = "plain"           # plain | modern | technical (which mask applies)
    allowed_planets: set[str] = field(default_factory=set)   # planets present in input
    allowed_years: set[int] = field(default_factory=set)     # years spanned by the window


def _prose_values(reading: dict, horizon: str) -> list[tuple[str, str]]:
    return [(k, reading[k]) for k in HORIZON_KEYS[horizon] if isinstance(reading.get(k), str)]


def validate(reading: dict, ctx: ValidationContext) -> list[str]:
    errors: list[str] = []
    horizon = ctx.horizon
    expected = set(HORIZON_KEYS[horizon]) | {"meta"}

    # §11.1 — EXACTLY the horizon's section keys + meta, nothing else, nothing missing.
    got = set(reading.keys())
    missing, extra = expected - got, got - expected
    if missing:
        errors.append(f"§11.1 missing keys: {sorted(missing)}")
    if extra:
        errors.append(f"§11.1 unexpected keys: {sorted(extra)}")

    # Which buckets are enforced at this detail level (see pr_prompts):
    #   plain     → classical + modern + technique  (hide everything)
    #   modern    → classical + technique           (modern astrology vocab allowed)
    #   technical → nothing                          (full reasoning allowed)
    # Classical (TIER-A) stays build-blocking wherever it is enforced.
    detail = ctx.astro_detail
    enforce_tier_a = detail != "technical"
    enforce_modern = detail == "plain"
    enforce_tech = detail in ("plain", "modern")
    # Planets are surfaced (and so leak-checked against the event list) whenever the audience
    # is astrology-literate, regardless of the surface_planets toggle.
    planets_allowed = ctx.surface_planets or detail in ("modern", "technical")

    for key, text in _prose_values(reading, horizon):
        if not text.strip():
            errors.append(f"§11.1 section {key!r} is empty")
            continue

        # §11.2 — mask lint, gated by astro_detail. TIER-A is build-blocking.
        if enforce_tier_a:
            for tok in find_tier_a(text):
                errors.append(f"§11.2 TIER-A classical term {tok!r} in {key!r} (build-blocking)")
        if enforce_modern:
            for tok in find_modern(text):
                errors.append(f"§11.2 MODERN machinery {tok!r} in {key!r} (astro_detail=plain)")
        if enforce_tech:
            for tok in find_tech(text):
                errors.append(f"§11.2 TECH machinery {tok!r} in {key!r} (astro_detail={detail})")

        # §11.3 — word count within tolerance (after the §8 re-ask).
        lo, hi = bounds(horizon, key, sparse=ctx.sparse)
        wc = word_count(text)
        if not (lo <= wc <= hi):
            errors.append(f"§11.3 section {key!r} is {wc} words, want {lo}–{hi}")

        # §11.5 — no fabricated planet / date.
        if planets_allowed:
            stray = find_planet_mentions(text) - ctx.allowed_planets
            if stray:
                errors.append(f"§11.5 planet(s) {sorted(stray)} in {key!r} not in the event list")
        else:
            named = find_planet_mentions(text)
            if named:
                errors.append(f"§11.5 planet(s) {sorted(named)} named in {key!r} "
                              f"but surface_planets is OFF")
        for m in _YEAR_RE.finditer(text):
            yr = int(m.group(0))
            if yr not in ctx.allowed_years:
                errors.append(f"§11.5 year {yr} in {key!r} is outside the forecast window")

    # §11.4 — focus present where the horizon has it, and on-domain for non-general.
    if "focus" in HORIZON_KEYS[horizon]:
        focus = reading.get("focus")
        if not isinstance(focus, str) or not focus.strip():
            errors.append("§11.4 focus paragraph missing")
        elif ctx.profile.name != "general" and ctx.profile.domain_keywords:
            low = focus.lower()
            if not any(kw in low for kw in ctx.profile.domain_keywords):
                errors.append(
                    f"§11.4 {ctx.profile.name} focus does not mention its domain "
                    f"({ctx.profile.domain_phrase})")

    return errors


def is_build_blocking(errors: list[str]) -> bool:
    """Tier-A leaks are absolute (§11.2); the driver must never ship them."""
    return any("TIER-A" in e for e in errors)
