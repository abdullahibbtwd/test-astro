#!/usr/bin/env python3
"""
grounding_schema.py — JSON Schema (Draft 2020-12) for the ``about`` / ``requires``
additions, built from the canonical vocabularies in ``grounding_vocab.py`` so the
schema can never drift from the enums the gate uses.

Two roles:

  1. ``ABOUT_SCHEMA`` / ``REQUIRES_SCHEMA`` — Draft 2020-12 documents with
     ``additionalProperties: false`` and ``enum``-constrained value fields. This
     is what enforces FK discipline on LLM output: off-vocabulary values (e.g.
     ``"sign": "taurus"`` lowercase) fail validation (spec §6, test 7).

  2. ``validate_about()`` — a self-contained validator used by the backfill's LLM
     pass to reject-and-retry. It prefers the ``jsonschema`` package when
     installed and otherwise applies an equivalent built-in check, so the
     pipeline runs with no third-party dependency.

Run ``python grounding_schema.py`` to (re)emit ``grounding_schema.json``.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from grounding_vocab import (
    RECONCILABLE_FACTOR_TYPES,
    ASPECT_TYPES,
    DIGNITIES,
    EXTRACTION_CONFIDENCES,
    EXTRACTION_SOURCES,
    FACTOR_TYPES,
    HOUSE_SYSTEMS,
    POINTS,
    REQUIRE_KINDS,
    SIGNS,
    UNCLASSIFIED_REASONS,
)

_DRAFT = "https://json-schema.org/draft/2020-12/schema"

ASPECT_SUBJECT_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["source", "target", "type"],
    "properties": {
        "source": {"enum": list(POINTS)},
        "target": {"enum": list(POINTS)},
        "type": {"enum": list(ASPECT_TYPES)},
    },
}

ABOUT_SCHEMA: dict = {
    "$schema": _DRAFT,
    "$id": "about.schema.json",
    "title": "About",
    "type": "object",
    "additionalProperties": False,
    "required": ["factor_type", "extraction_confidence", "extraction_source"],
    "properties": {
        "factor_type": {"enum": list(FACTOR_TYPES)},
        "point": {"enum": list(POINTS)},
        "sign": {"enum": list(SIGNS)},
        "house": {"type": "integer", "minimum": 1, "maximum": 12},
        "house_system": {"enum": list(HOUSE_SYSTEMS)},
        "aspect": ASPECT_SUBJECT_SCHEMA,
        "dignity": {"enum": list(DIGNITIES)},
        # dignity_ruler (rev 3): for "{planet} in {other}'s domicile/bound/..."
        # reception records — the planet whose dignity-rulership the subject sits
        # in. Reconciled via classifications.{sign,bound,face,triplicity}_ruler.
        "dignity_ruler": {"enum": list(POINTS)},
        "ascendant_sign": {"enum": list(SIGNS)},
        # house_lord_relative fields (rev 2) — chart-relative lordship.
        "subject_house": {"type": "integer", "minimum": 1, "maximum": 12},
        "subject_house_system": {"enum": list(HOUSE_SYSTEMS)},
        "placement_house": {"type": "integer", "minimum": 1, "maximum": 12},
        "placement_house_system": {"enum": list(HOUSE_SYSTEMS)},
        "generational": {"type": "boolean"},
        # rev 3 provenance / earned-verdict fields.
        "unclassified_reason": {"enum": list(UNCLASSIFIED_REASONS)},
        "reviewer": {"type": "string", "minLength": 1},
        "reviewed_at": {"type": "string", "minLength": 1},
        "extraction_confidence": {"enum": list(EXTRACTION_CONFIDENCES)},
        "extraction_source": {"enum": list(EXTRACTION_SOURCES)},
    },
    # Conditional subschemas encode the factor_type ⇒ required-field invariant
    # (spec §1 CRITICAL, §2.3, §6): a reconcilable type whose required field is
    # absent fails validation here, structurally — not just at runtime.
    "allOf": [
        # house_system mandatory whenever house is present (spec §1).
        {"if": {"required": ["house"]},
         "then": {"required": ["house_system"]}},
        {"if": {"properties": {"factor_type": {"const": "planet_in_sign"}},
                "required": ["factor_type"]},
         "then": {"required": ["point", "sign"]}},
        {"if": {"properties": {"factor_type": {"const": "planet_in_house"}},
                "required": ["factor_type"]},
         "then": {"required": ["point", "house", "house_system"]}},
        {"if": {"properties": {"factor_type": {"const": "planet_in_sign_and_house"}},
                "required": ["factor_type"]},
         "then": {"required": ["point", "sign", "house", "house_system"]}},
        {"if": {"properties": {"factor_type": {"const": "aspect"}},
                "required": ["factor_type"]},
         "then": {"required": ["aspect"]}},
        {"if": {"properties": {"factor_type": {"const": "dignity"}},
                "required": ["factor_type"]},
         "then": {"required": ["point", "dignity"]}},
        {"if": {"properties": {"factor_type": {"const": "node"}},
                "required": ["factor_type"]},
         "then": {"required": ["point"],
                  "anyOf": [{"required": ["sign"]}, {"required": ["house"]}]}},
        {"if": {"properties": {"factor_type": {"const": "ascendant"}},
                "required": ["factor_type"]},
         "then": {"required": ["ascendant_sign"]}},
        {"if": {"properties": {"factor_type": {"const": "house_ruler"}},
                "required": ["factor_type"]},
         "then": {"required": ["point", "house", "house_system"]}},
        # house_domain: point OR (house+house_system); forbids occupancy claims
        # (no sign, and not both point AND house — that would be a placement).
        {"if": {"properties": {"factor_type": {"const": "house_domain"}},
                "required": ["factor_type"]},
         "then": {"anyOf": [{"required": ["point"]},
                            {"required": ["house", "house_system"]}],
                  "not": {"required": ["sign"]}}},
        {"if": {"properties": {"factor_type": {"const": "house_lord_relative"}},
                "required": ["factor_type"]},
         "then": {"required": ["subject_house", "subject_house_system",
                               "placement_house", "placement_house_system"],
                  "not": {"required": ["point"]}}},
        # rev 3 §2.1: unclassified must carry an enum reason.
        {"if": {"properties": {"factor_type": {"const": "unclassified"}},
                "required": ["factor_type"]},
         "then": {"required": ["unclassified_reason"]}},
        # rev 3 §2: manual source means a named human reviewed it.
        {"if": {"properties": {"extraction_source": {"const": "manual"}},
                "required": ["extraction_source"]},
         "then": {"required": ["reviewer", "reviewed_at"]}},
    ],
}

REQUIREMENT_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["kind"],
    "properties": {
        "kind": {"enum": list(REQUIRE_KINDS)},
        "point": {"enum": list(POINTS)},
    },
}

REQUIRES_SCHEMA: dict = {
    "$schema": _DRAFT,
    "$id": "requires.schema.json",
    "title": "Requires",
    "type": "array",
    "items": REQUIREMENT_SCHEMA,
}

# Fields each factor_type is allowed to carry (beyond the always-present three).
# Used by the built-in validator to mirror the spec's "emit only the fields the
# factor_type uses" rule. Permissive supersets where a type has variants.
_FACTOR_FIELDS: dict[str, set[str]] = {
    "planet_in_sign": {"point", "sign", "generational"},
    "planet_in_house": {"point", "house", "house_system", "generational"},
    "planet_in_sign_and_house": {
        "point", "sign", "house", "house_system", "generational",
    },
    "aspect": {"aspect", "generational"},
    "dignity": {"point", "dignity", "dignity_ruler", "generational"},
    "node": {"point", "sign", "house", "house_system", "generational"},
    "ascendant": {"ascendant_sign"},
    "house_ruler": {"house", "house_system", "point", "generational"},
    "house_domain": {"point", "house", "house_system", "generational"},
    "house_lord_relative": {
        "subject_house", "subject_house_system",
        "placement_house", "placement_house_system", "generational",
    },
    "general": set(),
    "unclassified": {"unclassified_reason"},
}
# Provenance fields permitted on any factor_type (orthogonal to the subject).
_PROVENANCE_FIELDS = {"reviewer", "reviewed_at"}

# Required (non-null) fields per factor_type — the invariant of spec §1/§2.3.
# Lists-of-tuples = "any one of these groups must be fully present".
_FACTOR_REQUIRED: dict[str, list[tuple[str, ...]]] = {
    "planet_in_sign": [("point", "sign")],
    "planet_in_house": [("point", "house", "house_system")],
    "planet_in_sign_and_house": [("point", "sign", "house", "house_system")],
    "aspect": [("aspect",)],
    "dignity": [("point", "dignity")],
    "node": [("point", "sign"), ("point", "house", "house_system")],
    "ascendant": [("ascendant_sign",)],
    "house_ruler": [("point", "house", "house_system")],
    "house_domain": [("point",), ("house", "house_system")],
    "house_lord_relative": [("subject_house", "subject_house_system",
                             "placement_house", "placement_house_system")],
    "general": [()],
    "unclassified": [()],
}
_ALWAYS = {"factor_type", "extraction_confidence", "extraction_source"}
_ALL_VALUE_FIELDS = {
    "point", "sign", "house", "house_system", "aspect",
    "dignity", "dignity_ruler", "ascendant_sign",
    "subject_house", "subject_house_system",
    "placement_house", "placement_house_system", "generational",
    "unclassified_reason", "reviewer", "reviewed_at",
}


def _enum_ok(value, allowed) -> bool:
    return value in allowed


def _builtin_validate_about(obj) -> list[str]:
    """Equivalent of jsonschema validation for the about block. Returns a list
    of human-readable errors ([] == valid)."""
    errs: list[str] = []
    if not isinstance(obj, dict):
        return ["about must be an object"]

    for k in _ALWAYS:
        if k not in obj:
            errs.append(f"missing required field: {k}")

    ft = obj.get("factor_type")
    if not _enum_ok(ft, FACTOR_TYPES):
        errs.append(f"factor_type off-vocabulary: {ft!r}")
    if not _enum_ok(obj.get("extraction_confidence"), EXTRACTION_CONFIDENCES):
        errs.append(
            f"extraction_confidence off-vocabulary: "
            f"{obj.get('extraction_confidence')!r}"
        )
    if not _enum_ok(obj.get("extraction_source"), EXTRACTION_SOURCES):
        errs.append(
            f"extraction_source off-vocabulary: "
            f"{obj.get('extraction_source')!r}"
        )

    # Per-field FK enum checks (strict casing — this is what catches "taurus").
    if "point" in obj and not _enum_ok(obj["point"], POINTS):
        errs.append(f"point off-vocabulary: {obj['point']!r}")
    if "sign" in obj and not _enum_ok(obj["sign"], SIGNS):
        errs.append(f"sign off-vocabulary: {obj['sign']!r}")
    if "ascendant_sign" in obj and not _enum_ok(obj["ascendant_sign"], SIGNS):
        errs.append(f"ascendant_sign off-vocabulary: {obj['ascendant_sign']!r}")
    if "dignity" in obj and not _enum_ok(obj["dignity"], DIGNITIES):
        errs.append(f"dignity off-vocabulary: {obj['dignity']!r}")
    if "dignity_ruler" in obj and not _enum_ok(obj["dignity_ruler"], POINTS):
        errs.append(f"dignity_ruler off-vocabulary: {obj['dignity_ruler']!r}")
    if "unclassified_reason" in obj and not _enum_ok(
            obj["unclassified_reason"], UNCLASSIFIED_REASONS):
        errs.append(f"unclassified_reason off-vocabulary: "
                    f"{obj['unclassified_reason']!r}")
    if "house_system" in obj and not _enum_ok(obj["house_system"], HOUSE_SYSTEMS):
        errs.append(f"house_system off-vocabulary: {obj['house_system']!r}")
    for hf in ("house", "subject_house", "placement_house"):
        if hf in obj:
            h = obj[hf]
            if not (isinstance(h, int) and not isinstance(h, bool) and 1 <= h <= 12):
                errs.append(f"{hf} out of range: {h!r}")
    for hsf in ("subject_house_system", "placement_house_system"):
        if hsf in obj and not _enum_ok(obj[hsf], HOUSE_SYSTEMS):
            errs.append(f"{hsf} off-vocabulary: {obj[hsf]!r}")
    if "house" in obj and "house_system" not in obj:
        errs.append("house present but house_system missing")
    if "generational" in obj and not isinstance(obj["generational"], bool):
        errs.append("generational must be boolean")
    if "aspect" in obj:
        a = obj["aspect"]
        if not isinstance(a, dict) or set(a) != {"source", "target", "type"}:
            errs.append("aspect must have exactly {source,target,type}")
        else:
            if not _enum_ok(a["source"], POINTS):
                errs.append(f"aspect.source off-vocabulary: {a['source']!r}")
            if not _enum_ok(a["target"], POINTS):
                errs.append(f"aspect.target off-vocabulary: {a['target']!r}")
            if not _enum_ok(a["type"], ASPECT_TYPES):
                errs.append(f"aspect.type off-vocabulary: {a['type']!r}")

    # additionalProperties:false + factor_type-appropriate fields. Provenance
    # fields (reviewer/reviewed_at) are allowed on any factor_type.
    allowed = (
        _ALWAYS | _PROVENANCE_FIELDS | _FACTOR_FIELDS.get(ft, set())
        if ft in _FACTOR_FIELDS else None
    )
    known = _ALWAYS | _ALL_VALUE_FIELDS
    for k in obj:
        if k not in known:
            errs.append(f"unknown field: {k}")
        elif allowed is not None and k not in allowed:
            errs.append(f"field {k!r} not valid for factor_type {ft!r}")

    # rev 3: manual source requires a named reviewer + timestamp (no auto-manual).
    if obj.get("extraction_source") == "manual":
        for f in ("reviewer", "reviewed_at"):
            if not obj.get(f):
                errs.append(f"extraction_source 'manual' requires {f}")

    # Required-field invariant (spec §1 CRITICAL / §2.3): at least one required
    # group must be fully present. A reconcilable type with a missing required
    # field is the v1 defect and must fail validation.
    groups = _FACTOR_REQUIRED.get(ft)
    if groups is not None and groups != [()]:
        if not any(all(f in obj for f in grp) for grp in groups):
            need = " OR ".join("(" + ", ".join(g) + ")" for g in groups)
            errs.append(f"factor_type {ft!r} requires {need} (invariant violation)")

    # rev 3 §2.1: unclassified is earned — must carry an enum reason.
    if ft == "unclassified" and not obj.get("unclassified_reason"):
        errs.append("unclassified requires an unclassified_reason (§2.1)")

    # house_domain must not assert a specific occupancy (no sign; not point+house).
    if ft == "house_domain":
        if "sign" in obj:
            errs.append("house_domain must not carry a sign (no occupancy claim)")
        if "point" in obj and "house" in obj:
            errs.append("house_domain must not carry both point and house "
                        "(that is a specific placement)")
    return errs


def validate_about(obj) -> tuple[bool, list[str]]:
    """Validate an about block against ABOUT_SCHEMA. Uses jsonschema if present,
    else the equivalent built-in. Returns (ok, errors)."""
    try:
        import jsonschema  # type: ignore

        validator = jsonschema.Draft202012Validator(ABOUT_SCHEMA)
        errs = [e.message for e in validator.iter_errors(obj)]
        # jsonschema alone won't enforce per-factor_type field sets; layer it on.
        errs += [
            e for e in _builtin_validate_about(obj)
            if e.startswith("field ") or e.startswith("unknown field")
        ]
        return (not errs, errs)
    except ImportError:
        errs = _builtin_validate_about(obj)
        return (not errs, errs)


def invariant_violation(about) -> Optional[str]:
    """Return a reason string if `about` is a RECONCILABLE factor_type missing a
    required reconciliation field (the v1 defect), else None. This is the §2.3 /
    gate-B precondition check, isolated from general schema validity so callers
    can treat it as a fatal data error rather than a drop (spec §4 precondition).
    """
    if not isinstance(about, dict):
        return "about is not an object"
    ft = about.get("factor_type")
    if ft not in RECONCILABLE_FACTOR_TYPES:
        return None
    groups = _FACTOR_REQUIRED.get(ft, [()])
    if groups == [()]:
        return None
    if any(all(f in about and about[f] is not None for f in grp) for grp in groups):
        return None
    need = " OR ".join("(" + ", ".join(g) + ")" for g in groups)
    return f"factor_type {ft!r} missing required field; needs {need}"


def validate_requires(obj) -> tuple[bool, list[str]]:
    errs: list[str] = []
    if not isinstance(obj, list):
        return False, ["requires must be a list"]
    for i, item in enumerate(obj):
        if not isinstance(item, dict):
            errs.append(f"requires[{i}] must be an object")
            continue
        if not _enum_ok(item.get("kind"), REQUIRE_KINDS):
            errs.append(f"requires[{i}].kind off-vocabulary: {item.get('kind')!r}")
        if "point" in item and not _enum_ok(item["point"], POINTS):
            errs.append(f"requires[{i}].point off-vocabulary: {item['point']!r}")
        for k in item:
            if k not in ("kind", "point"):
                errs.append(f"requires[{i}] unknown field: {k}")
    return (not errs, errs)


def _emit() -> str:
    doc = {
        "$schema": _DRAFT,
        "$id": "grounding.schema.json",
        "title": "Principle grounding additions (about + requires)",
        "$defs": {
            "about": ABOUT_SCHEMA,
            "requires": REQUIRES_SCHEMA,
            "aspectSubject": ASPECT_SUBJECT_SCHEMA,
            "requirement": REQUIREMENT_SCHEMA,
        },
        "type": "object",
        "properties": {
            "about": {"$ref": "#/$defs/about"},
            "requires": {"$ref": "#/$defs/requires"},
        },
    }
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "grounding_schema.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return path


if __name__ == "__main__":
    print("wrote", _emit())
