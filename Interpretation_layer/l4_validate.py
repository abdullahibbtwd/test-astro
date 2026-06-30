#!/usr/bin/env python3
"""
l4_validate.py — the contract enforcer (L4_INTERPRETATION_SPEC.md §7).

``validate(output, routed_ids)`` checks the invariants that hold the
no-hallucination contract and returns a list of error strings. An empty list
means the output may ship; a non-empty list MUST stop the output (§7.1: validate
before output). ``routed_ids`` maps each section key to the set of principle_ids
that were routed to it — needed to enforce §7.2 (synthesis adds nothing): no
claim may cite an id that was not available to that section.
"""

from __future__ import annotations

import re
from typing import Optional

from l4_prompts import FORBIDDEN_READER_TOKENS
from l4_sections import MOVEMENT, SECTION_ORDER

SCHEMA_VERSION = "l4.v1"
PRECISION_TIER = "exact"

# Whole-word, case-insensitive match for tradition labels (§7.3).
_FORBIDDEN_RE = re.compile(
    r"(?<![\wçğıöşü])(" + "|".join(FORBIDDEN_READER_TOKENS) + r")(?![\wçğıöşü])",
    re.IGNORECASE,
)


def _find_forbidden(text: str) -> list[str]:
    return [m.group(0) for m in _FORBIDDEN_RE.finditer(text or "")]


def validate(output: dict,
             routed_ids: Optional[dict[str, set[str]]] = None) -> list[str]:
    errors: list[str] = []

    # Top-level contract (§6, §7.7).
    if output.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {SCHEMA_VERSION!r}, got "
            f"{output.get('schema_version')!r}"
        )
    if output.get("precision_tier") != PRECISION_TIER:
        errors.append(
            f"precision_tier must be {PRECISION_TIER!r} (§7.7), got "
            f"{output.get('precision_tier')!r}"
        )

    sections = output.get("sections")
    if not isinstance(sections, list):
        errors.append("sections must be a list")
        return errors

    seen_keys: list[str] = []
    for idx, sec in enumerate(sections):
        loc = f"sections[{idx}]"
        key = sec.get("key")

        # §7.6 — section keys are locked.
        if key not in SECTION_ORDER:
            errors.append(f"{loc}: key {key!r} is not one of the twelve §2 keys")
        else:
            seen_keys.append(key)
            if MOVEMENT[key] != sec.get("movement"):
                errors.append(
                    f"{loc} ({key}): movement should be {MOVEMENT[key]}, got "
                    f"{sec.get('movement')}"
                )

        text_tr = sec.get("text_tr")
        if not isinstance(text_tr, str) or not text_tr.strip():
            # §7.4 — no empty sections (an emitted section must have text).
            errors.append(f"{loc} ({key}): text_tr is empty (§7.4)")
            text_tr = text_tr or ""

        text_en = sec.get("text_en")
        if not isinstance(text_en, str) or not text_en.strip():
            errors.append(f"{loc} ({key}): text_en is empty (§7.4)")
            text_en = text_en or ""

        # §7.3 — no tradition labels reach the reader, in either language.
        for field, val in (("text_tr", text_tr), ("text_en", text_en)):
            for tok in _find_forbidden(val):
                errors.append(
                    f"{loc} ({key}): forbidden tradition token {tok!r} in {field} (§7.3)"
                )

        # §7.1 — grounding is now section-level: every emitted section carries
        # the principle_ids it was built from (attached deterministically from
        # routing). A section with no grounding must not ship.
        pids = sec.get("principle_ids")
        if not isinstance(pids, list) or not pids:
            errors.append(f"{loc} ({key}): empty principle_ids (§7.1/§7.4)")
            pids = pids if isinstance(pids, list) else []
        elif not all(isinstance(p, str) and p for p in pids):
            errors.append(f"{loc} ({key}): non-string/empty principle_id")

        allowed = routed_ids.get(key) if routed_ids else None
        # §7.2 — a section that was never routed cannot appear (synthesis must
        # not invent a section).
        if routed_ids is not None and key in SECTION_ORDER and allowed is None:
            errors.append(
                f"{loc} ({key}): section was not routed any principles (§7.2/§7.4)"
            )
        # §7.2 — synthesis adds nothing: every listed id was routed to this section.
        if allowed is not None:
            stray = [p for p in pids if p not in allowed]
            if stray:
                errors.append(
                    f"{loc} ({key}): principle_ids {stray} were not routed to this "
                    f"section (§7.2 synthesis adds nothing)"
                )

    # §7.4 — no duplicate section keys, canonical order is informative only.
    dupes = {k for k in seen_keys if seen_keys.count(k) > 1}
    if dupes:
        errors.append(f"duplicate section keys: {sorted(dupes)}")

    return errors
