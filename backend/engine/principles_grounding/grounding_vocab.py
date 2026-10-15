#!/usr/bin/env python3
"""
grounding_vocab.py — the canonical foreign-key vocabularies for the grounding
layer, plus the small derivation maps the gate needs.

Every value field in an ``about`` block is a foreign key into the chart object
emitted by ``../d_layer/compute_chart.py``. The strings here must match what the
engine emits verbatim (see ``d_layer/chart_types.py``); they are duplicated rather
than imported because ``d_layer`` is not an installable package (same rationale as
``retrival_contract/retrieval.py``).

These sets are the single source of truth shared by the schema generator
(``grounding_schema.json``), the backfill cascade (``backfill.py``) and the
grounding gate (``ground.py``).
"""

from __future__ import annotations

# --- Signs (FK: chart points[*].sign, axes.*.sign) --------------------------
SIGNS: tuple[str, ...] = (
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
)

# --- Points (FK: chart points[*].name) --------------------------------------
# Superset of the classical seven: includes outers and the lunar nodes, since
# `about.point` may name any charted body. Sector rulers / dignities still use
# the classical seven only — that is enforced where it matters, not here.
POINTS: tuple[str, ...] = (
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
    "Uranus", "Neptune", "Pluto", "North Node", "South Node",
)

# --- Aspect types (FK: chart relations[*].type) -----------------------------
ASPECT_TYPES: tuple[str, ...] = (
    "conjunction", "sextile", "square", "trine", "opposition",
)

# --- Elements (derived from sign) -------------------------------------------
ELEMENTS: tuple[str, ...] = ("fire", "earth", "air", "water")

# --- Essential-dignity states (FK to chart classifications, normalized) -----
# Each maps to the boolean field in `point.classifications` that confirms it.
DIGNITIES: tuple[str, ...] = (
    "domicile", "detriment", "exaltation", "fall",
    "triplicity", "bound", "face",
)
DIGNITY_TO_CLASSIFICATION: dict[str, str] = {
    "domicile": "in_domicile",
    "detriment": "in_detriment",
    "exaltation": "in_exaltation",
    "fall": "in_fall",
    "triplicity": "in_triplicity",
    "bound": "in_own_bound",
    "face": "in_own_face",
}

# --- House systems (FK: keys of point.sector / chart.sector_rulers) ----------
HOUSE_SYSTEMS: tuple[str, ...] = ("placidus", "whole_sign")

# --- factor_type and extraction enums ---------------------------------------
# rev 2 added house_domain (general significations) and house_lord_relative
# (chart-relative lordship) to fix the null-required-field defect.
# `element` was RETIRED: element-of-sign is not a chart-reconcilable factor (a
# principle "the element of Mars's sign" has no fixed element), so every such
# record is house_domain (single planet) or general (relational). See
# reclassify._route_element_violation.
FACTOR_TYPES: tuple[str, ...] = (
    "planet_in_sign", "planet_in_house", "planet_in_sign_and_house", "aspect",
    "dignity", "node", "ascendant", "house_ruler",
    "house_domain", "house_lord_relative",
    "general", "unclassified",
)

# The reconciliation fields each factor_type REQUIRES to be present (non-null).
# A factor_type whose required fields are not all present is a build-blocking
# invariant violation (spec §1 CRITICAL, §2.3). Tuples-of-tuples mean "one of":
# at least one option group must be fully satisfied.
FACTOR_REQUIRED_FIELDS: dict[str, tuple] = {
    "planet_in_sign": ("point", "sign"),
    "planet_in_house": ("point", "house", "house_system"),
    "planet_in_sign_and_house": ("point", "sign", "house", "house_system"),
    "aspect": ("aspect",),
    "dignity": ("point", "dignity"),
    # element retired — see FACTOR_TYPES note.
    # node needs the point and at least one of sign / (house+house_system);
    # handled specially in the validator.
    "node": ("point",),
    "ascendant": ("ascendant_sign",),
    "house_ruler": ("point", "house", "house_system"),
    # house_domain needs point OR (house+house_system); handled specially.
    "house_domain": (),
    "house_lord_relative": ("subject_house", "subject_house_system",
                            "placement_house", "placement_house_system"),
    "general": (),
    "unclassified": (),
}

# factor_types whose required field being null is the v1 defect: they reconcile
# against a concrete chart value, so a null field would compare against None.
RECONCILABLE_FACTOR_TYPES: frozenset = frozenset({
    "planet_in_sign", "planet_in_house", "planet_in_sign_and_house", "aspect",
    "dignity", "node", "ascendant", "house_ruler",
    "house_lord_relative",
})
EXTRACTION_CONFIDENCES: tuple[str, ...] = ("high", "medium", "low")
# rev 3: closed, meaningful enum. `deterministic` = Tier-1 template capture,
# `llm` = Tier-2 extraction, `manual` = a NAMED human reviewed it (requires
# reviewer + reviewed_at). `manual` is NEVER an auto-assigned discard channel.
EXTRACTION_SOURCES: tuple[str, ...] = ("deterministic", "llm", "manual")

# rev 3 §2.1: `unclassified` is earned, never a default. Every unclassified
# record must carry one of these reasons. There is deliberately no
# hard/unclear/declined member ("the extractor found it difficult" is invalid).
UNCLASSIFIED_REASONS: tuple[str, ...] = (
    "no_subject_in_text", "multi_subject_unsplittable",
    "dependency_unsatisfiable", "non_configurational",
)

# --- requires.kind enum -----------------------------------------------------
REQUIRE_KINDS: tuple[str, ...] = (
    "point_sign", "point_house", "point_aspects", "point_dignity",
    "sign_element", "ascendant", "house_ruler", "native_gender",
    "birth_time", "other",
)

# --- Derivation: sign -> element --------------------------------------------
SIGN_ELEMENT: dict[str, str] = {
    "Aries": "fire", "Leo": "fire", "Sagittarius": "fire",
    "Taurus": "earth", "Virgo": "earth", "Capricorn": "earth",
    "Gemini": "air", "Libra": "air", "Aquarius": "air",
    "Cancer": "water", "Scorpio": "water", "Pisces": "water",
}

# Case-insensitive lookup helpers (canonicalize loosely-cased source tokens to
# the exact FK casing; used by the backfill, never to relax gate-B matching).
_SIGN_LOWER = {s.lower(): s for s in SIGNS}
_POINT_LOWER = {p.lower(): p for p in POINTS}
# common single-word aliases seen in the corpus
_POINT_ALIASES = {
    "north node": "North Node", "south node": "South Node",
    "nn": "North Node", "sn": "South Node",
    "rahu": "North Node", "ketu": "South Node",
    "ascendant": None,  # handled by factor_type=ascendant, not a point
}


def canon_sign(token: str | None) -> str | None:
    if not token:
        return None
    return _SIGN_LOWER.get(token.strip().lower())


def canon_point(token: str | None) -> str | None:
    if not token:
        return None
    t = token.strip().lower()
    if t in _POINT_ALIASES:
        return _POINT_ALIASES[t]
    return _POINT_LOWER.get(t)


def canon_aspect(token: str | None) -> str | None:
    if not token:
        return None
    t = token.strip().lower()
    return t if t in ASPECT_TYPES else None


def canon_element(token: str | None) -> str | None:
    if not token:
        return None
    t = token.strip().lower()
    return t if t in ELEMENTS else None


def element_of_sign(sign: str | None) -> str | None:
    if not sign:
        return None
    return SIGN_ELEMENT.get(sign)


# Ordinal house words -> int, for ID / prose parsing.
HOUSE_WORDS: dict[str, int] = {
    "first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3,
    "fourth": 4, "4th": 4, "fifth": 5, "5th": 5, "sixth": 6, "6th": 6,
    "seventh": 7, "7th": 7, "eighth": 8, "8th": 8, "ninth": 9, "9th": 9,
    "tenth": 10, "10th": 10, "eleventh": 11, "11th": 11,
    "twelfth": 12, "12th": 12,
}
