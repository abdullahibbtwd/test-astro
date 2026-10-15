#!/usr/bin/env python3
"""
forecast_types.py  —  formal in-process typing of the PREDICTIVE forecast object.

These TypedDicts are the authoritative Python-side description of the structure
emitted by ``compute_forecast()`` (SPEC §11). They make the compute/grounding
boundary machine-checkable the same way ``chart_types.py`` does for LAYER 1: a
new engineer learns the exact shape from this one file, and mypy catches typos.
The language-agnostic twin is ``forecast_schema.json``.

Naming reuses the chart object wherever fields overlap (SPEC §11): ``sign`` and
the dignity flags match ``chart_types.py``; aspect names are the full
``AspectType`` strings from ``chart_schema.json`` (conjunction/sextile/square/
trine/opposition), NOT abbreviations.

Absent-vs-null contract (as in the chart):
  * Required field  -> always present.
  * ``X | None``    -> the concept EXISTS for this event but does not apply here
                       (e.g. ``cycle_stage`` on an ingress; ``house_placidus``
                       on a circumpolar natal).
"""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

# ---------------------------------------------------------------------------
# Closed domain-value sets. Spellings are foreign keys — into chart_schema.json
# (sign/aspect) and into the corpus `requires` vocabulary (grounding kind).
# ---------------------------------------------------------------------------
Sign = Literal[
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
Element = Literal["fire", "earth", "air", "water"]
AspectType = Literal["conjunction", "sextile", "square", "trine", "opposition"]
Horizon = Literal["day", "month", "year"]
Precision = Literal["exact", "approximate", "unknown"]
Family = Literal[
    "transit_aspect", "ingress_sign", "ingress_house",
    "lunation", "eclipse", "profection",
]
Phase = Literal["applying", "separating", "perfecting"]
SpeedClass = Literal["fast", "slow"]
Segment = Literal["early", "mid", "late", "q1", "q2", "q3", "q4"]
# The grounding.kind vocabulary is exactly the corpus `requires.kind` set the
# forecast-grounding step matches against (SPEC §9). "midheaven" is deliberately
# absent — the corpus has no such kind, so MC/IC contacts ground as "other".
GroundingKind = Literal[
    "point_aspects", "point_house", "point_sign", "point_dignity",
    "sign_element", "ascendant", "house_ruler", "birth_time",
    "native_gender", "other",
]


# ---------------------------------------------------------------------------
# Leaf types
# ---------------------------------------------------------------------------
class Bodies(TypedDict):
    transiting: str | None          # the moving body (null for pure-sky events)
    natal: str | None               # the natal target (null for sky/ingress)


class Dignity(TypedDict):
    """Compact essential dignity used to modulate aspect valence (SPEC §9).
    ``sign`` is null on the natal side (it lives on the natal chart point)."""
    sign: Sign | None
    sign_ruler: str
    in_domicile: bool
    in_detriment: bool
    in_exaltation: bool
    in_fall: bool


class DignityPair(TypedDict):
    transiting: Dignity | None      # null for a non-classical transiting body
    natal: Dignity | None           # null for an angle target / non-classical


class Grounding(TypedDict):
    """The §9 structured signature. ``kind`` + ``topic_tags`` are always present;
    the remaining keys appear only for the kinds that carry them, so the
    grounding step can match by structure before falling back to embeddings."""
    kind: GroundingKind
    topic_tags: list[str]
    transiting_point: NotRequired[str]
    natal_point: NotRequired[str]
    point: NotRequired[str]
    aspect: NotRequired[AspectType]
    phase: NotRequired[Phase]
    cycle_stage: NotRequired[int]
    house_placidus: NotRequired[int | None]
    house_wholesign: NotRequired[int | None]
    sign: NotRequired[Sign]
    element: NotRequired[Element]
    angle: NotRequired[str]


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------
class Event(TypedDict):
    event_id: str
    family: Family
    datetime: str                   # ISO-8601, birth-location tz (or window-start)
    standing: bool                  # in-orb-at-start vs perfecting-in-window
    bodies: Bodies
    aspect: AspectType | None
    phase: Phase | None
    cycle_stage: int | None         # 1..8
    speed_class: SpeedClass | None
    house_placidus: int | None      # domain routing
    house_wholesign: int | None     # classical texture
    sign: Sign | None
    dignity: DignityPair | None
    segment: Segment | None
    grounding: Grounding


# ---------------------------------------------------------------------------
# Container types
# ---------------------------------------------------------------------------
class Window(TypedDict):
    start: str
    end: str
    tz: str


class ConfigFlags(TypedDict):
    enable_profections: bool
    enable_lots_targets: bool


class Meta(TypedDict):
    natal_ref: str
    target_date: str
    horizon: Horizon
    generated_at: str
    run_id: str
    precision_tier: Precision
    degraded: bool
    suppressed_families: list[str]
    ephemeris: str
    config: ConfigFlags


class Counts(TypedDict):
    by_family: dict[str, int]
    by_segment: dict[str, int]


class Rulers(TypedDict):
    """Target-date planetary day/hour ruler; present only on the DAY horizon
    (invariant 5). Null when birth coordinates were not supplied / circumpolar."""
    planetary_day: str | None
    planetary_hour: str | None


class Forecast(TypedDict):
    meta: Meta
    window: Window
    events: list[Event]
    counts: Counts
    rulers: NotRequired[Rulers]     # DAY horizon only
