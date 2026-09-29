#!/usr/bin/env python3
"""
s3_validate.py — the contract enforcer for S3 (SYNASTRY_READING_SPEC.md §10).

``validate(output, statements, routed_ids)`` returns a list of error strings. An
empty list means the reading may ship; a non-empty list must stop it (§10: a
failing call is regenerated, and the driver never writes a violating artifact).

Invariants enforced here:
  - §10.3 MASK: no banned classical vocabulary (tr or en). Hard-banned terms are
    unambiguous machinery; context-banned patterns catch the technical usage of
    words that are otherwise ordinary romantic English.
  - §10.4 NO SCORE: no numeric/letter compatibility rating.
  - §10.6 STATEMENTS TRACEABLE: every statement links to ≥1 grounded record id
    that was actually routed to its section (this also covers §10.1 traceability
    and §10.2 attribution, since routed ids carry the correct `bound`).
  - Structural: locked section keys, movement, non-empty bilingual text.

The floor (§10.5) is enforced by construction in ``s3_routing`` (floored records
never reach a section); this module additionally asserts no floored id resurfaced.
"""

from __future__ import annotations

import re
from typing import Optional

from s3_prompts import CONTEXT_BANNED_PATTERNS, HARD_BANNED_TERMS
from s3_profiles import get_profile

SCHEMA_VERSION = "s3.v1"

# Hard-banned whole words, case-insensitive, Turkish-letter aware on the borders
# so "traditional" is caught but a longer innocuous word is not split wrongly.
_HARD_RE = re.compile(
    r"(?<![\wçğıöşü])(" + "|".join(re.escape(t) for t in HARD_BANNED_TERMS)
    + r")(?![\wçğıöşü])",
    re.IGNORECASE,
)
_CONTEXT_RES = [re.compile(p, re.IGNORECASE) for p in CONTEXT_BANNED_PATTERNS]

# §10.4 — a compatibility score/grade. Percentages, "N/100", "N out of 10",
# "score: N", or an isolated letter grade (A+/B-/…) used as a rating.
_SCORE_RES = [
    re.compile(r"\b\d{1,3}\s*%"),
    re.compile(r"\b\d{1,3}\s*/\s*(?:100|10|5)\b"),
    re.compile(r"\b\d{1,2}\s+(?:out of|üzerinden|/)\s*\d{1,3}\b"),
    re.compile(r"\b(?:score|puan|skor|rating|grade|not)\s*[:=]\s*\w+", re.IGNORECASE),
    re.compile(r"(?<![\w])[A-F][+\-]?\s+(?:grade|rating)\b", re.IGNORECASE),
]


def find_mask_violations(text: str) -> list[str]:
    text = text or ""
    hits = [m.group(0) for m in _HARD_RE.finditer(text)]
    for rx in _CONTEXT_RES:
        hits += [m.group(0) for m in rx.finditer(text)]
    return hits


def find_score_violations(text: str) -> list[str]:
    text = text or ""
    out: list[str] = []
    for rx in _SCORE_RES:
        out += [m.group(0) for m in rx.finditer(text)]
    return out


def clean_statements(statements: list[dict],
                     routed_ids: dict[str, set[str]]) -> tuple[list[dict], dict]:
    """Enforce §10.6 by CLEANING rather than failing the whole reading: drop any
    source_id not routed to the statement's section, drop statements left with no
    valid source, and drop statements that leak banned vocabulary or a score. The
    (expensive) tr/en reading is the primary artifact and is validated strictly on
    its own; statements are for the eval harness, so a stray model-cited id must
    degrade gracefully, not sink the run. Returns (kept, drop_report)."""
    kept: list[dict] = []
    report = {"input": len(statements), "dropped_no_source": 0,
              "dropped_mask_or_score": 0, "trimmed_stray_ids": 0}
    for st in statements:
        skey = st.get("section")
        allowed = routed_ids.get(skey, set())
        raw = st.get("source_ids") or []
        good = [p for p in raw if p in allowed]
        if len(good) != len(raw):
            report["trimmed_stray_ids"] += 1
        if not good:
            report["dropped_no_source"] += 1
            continue
        if (find_mask_violations(st.get("text_tr", ""))
                or find_mask_violations(st.get("text_en", ""))
                or find_score_violations(st.get("text_tr", ""))
                or find_score_violations(st.get("text_en", ""))):
            report["dropped_mask_or_score"] += 1
            continue
        kept.append({**st, "source_ids": good})
    report["kept"] = len(kept)
    return kept, report


def validate(output: dict,
             statements: Optional[dict] = None,
             routed_ids: Optional[dict[str, set[str]]] = None,
             floored_ids: Optional[set[str]] = None) -> list[str]:
    errors: list[str] = []

    if output.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {SCHEMA_VERSION!r}, got "
            f"{output.get('schema_version')!r}"
        )

    # Section keys/movement are validated against the reading's own profile
    # (PROFILES §7.3: the reading's structure must match its type).
    profile = get_profile(output.get("reading_type", "general"))
    section_order = profile.section_order
    movement = profile.movement

    sections = output.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append("sections must be a non-empty list")
        return errors

    seen: list[str] = []
    for idx, sec in enumerate(sections):
        loc = f"sections[{idx}]"
        key = sec.get("key")
        if key not in section_order:
            errors.append(
                f"{loc}: key {key!r} is not a {profile.reading_type} section key")
        else:
            seen.append(key)
            if movement[key] != sec.get("movement"):
                errors.append(
                    f"{loc} ({key}): movement should be {movement[key]}, got "
                    f"{sec.get('movement')}"
                )

        for lang in ("text_tr", "text_en"):
            val = sec.get(lang)
            if not isinstance(val, str) or not val.strip():
                errors.append(f"{loc} ({key}): {lang} is empty")
                continue
            for tok in find_mask_violations(val):
                errors.append(
                    f"{loc} ({key}): banned term {tok!r} in {lang} (§10.3 mask)"
                )
            for tok in find_score_violations(val):
                errors.append(
                    f"{loc} ({key}): compatibility score {tok!r} in {lang} (§10.4)"
                )

        # §10.6 — an emitted section must carry the grounded ids it rests on.
        pids = sec.get("source_ids")
        if not isinstance(pids, list) or not pids:
            errors.append(f"{loc} ({key}): empty source_ids (§10.1/§10.6)")
        elif routed_ids is not None and key in routed_ids:
            stray = [p for p in pids if p not in routed_ids[key]]
            if stray:
                errors.append(
                    f"{loc} ({key}): source_ids {stray} not routed to this section "
                    f"(§10.1 traceability)"
                )

    dupes = {k for k in seen if seen.count(k) > 1}
    if dupes:
        errors.append(f"duplicate section keys: {sorted(dupes)}")

    # §10.5 — no floored record may resurface in a shipped section.
    if floored_ids:
        for sec in sections:
            for p in sec.get("source_ids") or []:
                if p in floored_ids:
                    errors.append(
                        f"sections[{sec.get('key')}]: floored record {p!r} "
                        f"resurfaced (§10.5)"
                    )

    # §10.6 — statements: every entry links to ≥1 routed record id for its section.
    if statements is not None:
        stmts = statements.get("statements")
        if not isinstance(stmts, list):
            errors.append("statements.statements must be a list (§10.6)")
        else:
            for j, st in enumerate(stmts):
                sloc = f"statements[{j}]"
                sids = st.get("source_ids")
                skey = st.get("section")
                if not isinstance(sids, list) or not sids:
                    errors.append(f"{sloc}: empty source_ids (§10.6)")
                    continue
                if routed_ids is not None and skey in routed_ids:
                    stray = [p for p in sids if p not in routed_ids[skey]]
                    if stray:
                        errors.append(
                            f"{sloc} ({skey}): source_ids {stray} not routed to "
                            f"this section (§10.6)"
                        )
                for lang in ("text_tr", "text_en"):
                    if find_mask_violations(st.get(lang, "")):
                        errors.append(f"{sloc}: banned term in {lang} (§10.3)")

    return errors
