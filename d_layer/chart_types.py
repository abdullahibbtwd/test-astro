#!/usr/bin/env python3
"""
chart_types.py  —  formal in-process typing of the LAYER 1 chart object.

These TypedDicts are the authoritative Python-side description of the structure
emitted by ``compute_chart()`` (after the RENAME_SPEC key renames). They make
the engine/interpretation boundary machine-checkable: ``mypy`` catches typos and
wrong-type accesses before runtime, and a new engineer learns the exact shape by
reading this one file. The language-agnostic twin is ``chart_schema.json``.

The most important distinction encoded here (the no-hallucination contract):

  * Required field  -> always present for that chart kind.
  * ``X | None``    -> the concept EXISTS for this chart but is UNDEFINED here
                       (e.g. ``placidus`` sector above the polar circle;
                       ``classifications`` for a non-classical point).
  * ``NotRequired[X]`` -> the concept DOES NOT EXIST for this chart at all
                       (e.g. ``axes``/``is_diurnal``/``derived_points`` when
                       there is no birth time).

Absent and null are NOT interchangeable.
"""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

# ---------------------------------------------------------------------------
# Closed domain-value sets (Literal). Spelling matches the engine's emitted
# values verbatim — these strings are foreign keys into all_principles.json,
# so they must never drift from what compute_chart.py emits.
# ---------------------------------------------------------------------------
Sign = Literal[
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
# Planet is the set used for *dignity rulers* — the classical seven only.
Planet = Literal["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
AspectType = Literal["conjunction", "sextile", "square", "trine", "opposition"]
Scheme = Literal["modern", "whole_sign"]
Precision = Literal["exact", "approximate", "unknown"]


# ---------------------------------------------------------------------------
# Leaf types
# ---------------------------------------------------------------------------
class Position(TypedDict):
    longitude: float
    sign: Sign
    sign_index: int                 # 0..11
    degree_in_sign: float


class Sector(TypedDict):
    """Per-point house placement, both systems."""
    placidus: int | None            # 1..12, or None above the polar circle
    whole_sign: int                 # 1..12


class TriplicityRulers(TypedDict):
    day: Planet
    night: Planet
    participating: Planet


class Classifications(TypedDict):
    """Essential dignities; only for the classical seven."""
    sign_ruler: Planet
    in_domicile: bool
    in_detriment: bool
    in_exaltation: bool
    in_fall: bool
    triplicity_ruler: Planet | None   # None when sect is unknown (no birth time)
    triplicity_rulers_all: TriplicityRulers
    in_triplicity: bool | None        # None when sect is unknown
    bound_ruler: Planet
    in_own_bound: bool
    face_ruler: Planet
    in_own_face: bool


# ---------------------------------------------------------------------------
# Point types
# ---------------------------------------------------------------------------
class MoonRange(TypedDict):
    """Only present on the Moon, only in the unknown tier."""
    start: Position
    end: Position
    note: str


class Point(TypedDict):
    name: str                       # domain value (planet/point name); kept open
    traditional: bool
    longitude: float
    sign: Sign
    sign_index: int
    degree_in_sign: float
    speed: float
    retrograde: bool
    sector: NotRequired[Sector]               # absent in the unknown tier
    classifications: Classifications | None    # null for non-classical points
    range: NotRequired[MoonRange]             # present only on Moon, unknown tier


# ---------------------------------------------------------------------------
# Relation type (edge in the aspect graph)
# ---------------------------------------------------------------------------
class Relation(TypedDict):
    source: str                     # point name
    target: str                     # point name
    type: AspectType
    scheme: Scheme
    orb: NotRequired[float]         # present only for modern relations
    applying: NotRequired[bool]     # present only for modern relations


# ---------------------------------------------------------------------------
# Container types
# ---------------------------------------------------------------------------
class Axes(TypedDict):
    ascendant: Position
    mc: Position


class Sectors(TypedDict):
    placidus_cusps: list[float] | None        # null above the polar circle
    whole_sign_cusps: list[float]


class DerivedPoints(TypedDict):
    """Points computed by formula, not observed. Open to more named lots later."""
    fortune: Position
    spirit: Position


class SectorRuler(TypedDict):
    """Rulership of one sector (house): sign on its cusp, that sign's domicile
    ruler, and where the ruler sits. ruler_sector is in this block's own house
    system (self-containment, CHART_SECTOR_RULERS_SPEC.md §4)."""
    sign_on_cusp: Sign      # sign FK
    ruler: Planet           # planet FK (domicile ruler of sign_on_cusp)
    ruler_sign: Sign        # sign FK — the ruler's own point.sign
    ruler_sector: int       # 1..12, in this block's house system


class SectorRulers(TypedDict):
    """Precomputed sector rulership per house system. Keys are the string house
    numbers "1".."12"; every house is always present (every sign has a domicile
    ruler under the traditional map)."""
    placidus: dict[str, SectorRuler]
    whole_sign: dict[str, SectorRuler]


class Meta(TypedDict):
    time_precision: Precision
    zodiac: str
    ephemeris: str
    pyswisseph_version: int | str
    house_systems: list[str]
    node_type: str
    timezone: str
    utc: str
    approx_bucket: NotRequired[str]   # only when approximate
    note: NotRequired[str]            # only when unknown


class UnstableFields(TypedDict):
    """Only when approximate."""
    asc_sign: NotRequired[bool]
    mc_sign: NotRequired[bool]
    is_diurnal: NotRequired[bool]
    moon_sign: NotRequired[bool]
    house_placements: NotRequired[list[str]]


# ---------------------------------------------------------------------------
# Top-level type
# ---------------------------------------------------------------------------
class Chart(TypedDict):
    meta: Meta
    confidence: Precision
    points: list[Point]
    relations: list[Relation]
    axes: NotRequired[Axes]                       # absent in the unknown tier
    sectors: NotRequired[Sectors]                 # absent in the unknown tier
    sector_rulers: NotRequired[SectorRulers]      # absent in the unknown tier
    is_diurnal: NotRequired[bool]                 # absent in the unknown tier
    derived_points: NotRequired[DerivedPoints]    # absent in the unknown tier
    planetary_day: NotRequired[str | None]        # absent unknown; null if circumpolar
    planetary_hour: NotRequired[str | None]       # absent unknown; null if circumpolar
    unstable_fields: NotRequired[UnstableFields]  # only when approximate
