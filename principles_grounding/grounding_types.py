#!/usr/bin/env python3
"""
grounding_types.py — Python-side typing of the grounding additions to a
principle record (PRINCIPLE_GROUNDING_SPEC.md §6).

These mirror ``d_layer/chart_types.py`` in spirit: the authoritative in-process
shape, machine-checkable with mypy. The language-agnostic twin is
``grounding_schema.json``.

The contract on field presence follows the chart engine's absent-vs-null rule:
unused ``about`` value fields are **structurally omitted**, never set to null.
Only ``factor_type``, ``extraction_confidence`` and ``extraction_source`` are
always present.
"""

from __future__ import annotations

from typing import List, Literal, TypedDict

FactorType = Literal[
    "planet_in_sign", "planet_in_house", "planet_in_sign_and_house", "aspect",
    "dignity", "node", "ascendant", "house_ruler",   # `element` retired
    "house_domain", "house_lord_relative",            # added in rev 2
    "general", "unclassified",
]

HouseSystem = Literal["placidus", "whole_sign"]


class AspectSubject(TypedDict):
    source: str
    target: str
    type: str


class About(TypedDict, total=False):
    factor_type: FactorType                                   # required
    point: str
    sign: str
    house: int
    house_system: HouseSystem
    aspect: AspectSubject
    dignity: str
    ascendant_sign: str
    # house_lord_relative fields (rev 2): the ruling planet is chart-derived,
    # never stored — the principle names the relationship, not the planet.
    subject_house: int
    subject_house_system: HouseSystem
    placement_house: int
    placement_house_system: HouseSystem
    generational: bool
    extraction_confidence: Literal["high", "medium", "low"]   # required
    extraction_source: Literal[
        "id_parse", "conditions_crosscheck", "llm", "manual"
    ]                                                         # required


class Requirement(TypedDict, total=False):
    kind: Literal[
        "point_sign", "point_house", "point_aspects", "point_dignity",
        "sign_element", "ascendant", "house_ruler", "native_gender",
        "birth_time", "other",
    ]                                                         # required
    point: str


class GroundedPrinciple(TypedDict, total=False):
    """A principle record after backfill: the original fields are unchanged and
    ``about`` / ``requires`` are added. Only the grounding additions are typed
    here; the original content fields stay open (str/list as in the corpus)."""
    principle_id: str
    domain: str
    tradition: str
    rule: str
    judgment: str
    conditions: object          # preserved verbatim for provenance (poly-typed)
    about: About                # added by backfill
    requires: List[Requirement]  # added by backfill
