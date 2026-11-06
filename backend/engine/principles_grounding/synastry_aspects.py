#!/usr/bin/env python3
"""
synastry_aspects.py — cross-chart aspect *math* for Match / Family.

Enumerates modern synastry aspects between two natal charts using the Match
gate's ``aspect_holds`` (ground_relationship). No interpretation text and no
family weighting — those arrive later from the astrologer.

``relationship_type`` only selects which aspects are returned:
  * romantic (default) — full modern planet×planet set (today's Match math)
  * parent_child / sibling — selection rules are empty for now, so the result
    is an empty subset (callers must not crash; weighting comes later)
"""

from __future__ import annotations

import os
import sys
from typing import Iterable, Literal, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_DLAYER = os.path.normpath(os.path.join(_HERE, "..", "d_layer"))
_RULES = os.path.normpath(os.path.join(_HERE, "..", "rules"))
for _p in (_HERE, _DLAYER, _RULES):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from compute_chart import _orb_now_and_later  # noqa: E402
from ground_relationship import MODERN_ASPECTS, aspect_holds  # noqa: E402
from load_rules import family_aspect_selection, load_family_rules  # noqa: E402

RelationshipType = Literal["romantic", "parent_child", "sibling"]
RELATIONSHIP_TYPES: tuple[str, ...] = ("romantic", "parent_child", "sibling")

# Ten read planets (nodes excluded) — same non-node set as L1 modern aspects.
SYN_PLANETS: tuple[str, ...] = (
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
)


def _planet_index(chart: dict) -> dict[str, dict]:
    return {
        p["name"]: p
        for p in (chart.get("points") or [])
        if p.get("name") in SYN_PLANETS
    }


def _row(a_point: str, b_point: str, aspect: str, fact: dict, applying: bool) -> dict:
    return {
        "a_point": a_point,
        "b_point": b_point,
        "type": aspect,
        "scheme": "modern",
        "orb": fact["orb"],
        "separation": fact["separation"],
        "applying": applying,
    }


def iter_match_synastry_aspects(chart_a: dict, chart_b: dict) -> Iterable[dict]:
    """
    Yield every modern synastry aspect between chart_a and chart_b using Match
    ``aspect_holds`` orbs. One aspect type per planet pair (MODERN_ASPECTS order).
    Applying/separating uses L1 ``_orb_now_and_later`` (speed-based), unchanged.
    """
    pa = _planet_index(chart_a)
    pb = _planet_index(chart_b)
    missing_a = [n for n in SYN_PLANETS if n not in pa]
    missing_b = [n for n in SYN_PLANETS if n not in pb]
    if missing_a or missing_b:
        raise ValueError(
            f"chart missing planets: A={missing_a or None} B={missing_b or None}"
        )

    for a_name in SYN_PLANETS:
        for b_name in SYN_PLANETS:
            a_pt, b_pt = pa[a_name], pb[b_name]
            for aspect, (angle, _orb_allow) in MODERN_ASPECTS.items():
                ok, fact = aspect_holds(a_pt, b_pt, aspect, "modern")
                if not ok:
                    continue
                _orb_now, applying = _orb_now_and_later(
                    a_pt["longitude"], a_pt["speed"],
                    b_pt["longitude"], b_pt["speed"],
                    angle,
                )
                yield _row(a_name, b_name, aspect, fact, applying)
                break  # one aspect per pair (same rule as L1 modern aspects)


def compute_synastry_aspects(
    chart_a: dict,
    chart_b: dict,
    relationship_type: RelationshipType = "romantic",
) -> list[dict]:
    """
    Synastry aspects from chart_a planets to chart_b planets.

    Parameters
    ----------
    chart_a, chart_b:
        Natal charts in the L1 ``compute_chart`` shape.
    relationship_type:
        ``romantic`` (default) | ``parent_child`` | ``sibling``.
        Default preserves today's Match aspect set. Family types currently have
        no selection rules, so they return an empty subset.

    Returns
    -------
    list[dict]
        Stable-ordered rows: a_point, b_point, type, scheme, orb, separation,
        applying. Orb/hold rules come from Match ``aspect_holds``.
    """
    if relationship_type not in RELATIONSHIP_TYPES:
        raise ValueError(
            f"relationship_type must be one of {RELATIONSHIP_TYPES}, "
            f"got {relationship_type!r}"
        )
    rows = list(iter_match_synastry_aspects(chart_a, chart_b))
    # Data-driven selection from family_rules.json (empty → safe defaults).
    selection = family_aspect_selection(relationship_type, load_family_rules())
    if selection is None:
        return rows
    if not selection:
        # No family selection rules yet — empty subset, not a crash.
        return []
    return [
        r for r in rows
        if (r["a_point"], r["b_point"], r["type"]) in selection
    ]
