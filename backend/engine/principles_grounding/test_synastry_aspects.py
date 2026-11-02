#!/usr/bin/env python3
"""Family / Match synastry aspect-math tests (no interpretation).

Run: python -m pytest backend/engine/principles_grounding/test_synastry_aspects.py -q
"""

from __future__ import annotations

import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_DLAYER = os.path.normpath(os.path.join(_HERE, "..", "d_layer"))
for _p in (_HERE, _DLAYER):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from compute_chart import BirthData, compute_chart, _orb_now_and_later  # noqa: E402
from ground_relationship import MODERN_ASPECTS, aspect_holds  # noqa: E402
from synastry_aspects import (  # noqa: E402
    SYN_PLANETS,
    compute_synastry_aspects,
    iter_match_synastry_aspects,
)

_FIXTURE = os.path.join(_HERE, "fixtures", "synastry_aspects_sofia_ayse.json")


def _chart_from_birth(birth: dict) -> dict:
    y, m, d = (int(x) for x in birth["date"].split("-"))
    hh, mm = (int(x) for x in birth["time"].split(":"))
    return compute_chart(BirthData(
        year=y, month=m, day=d, hour=hh, minute=mm,
        latitude=birth["latitude"], longitude=birth["longitude"],
        time_precision="exact",
    ))


def _load_pair():
    with open(_FIXTURE, encoding="utf-8") as fh:
        data = json.load(fh)
    chart_a = _chart_from_birth(data["person_a"]["birth"])
    chart_b = _chart_from_birth(data["person_b"]["birth"])
    return data, chart_a, chart_b


def _match_baseline(chart_a: dict, chart_b: dict) -> list[dict]:
    """Today's Match aspect math: aspect_holds + L1 applying flag, no filters."""
    pa = {p["name"]: p for p in chart_a["points"] if p["name"] in SYN_PLANETS}
    pb = {p["name"]: p for p in chart_b["points"] if p["name"] in SYN_PLANETS}
    out = []
    for a_name in SYN_PLANETS:
        for b_name in SYN_PLANETS:
            a_pt, b_pt = pa[a_name], pb[b_name]
            for aspect, (angle, _) in MODERN_ASPECTS.items():
                ok, fact = aspect_holds(a_pt, b_pt, aspect, "modern")
                if not ok:
                    continue
                _, applying = _orb_now_and_later(
                    a_pt["longitude"], a_pt["speed"],
                    b_pt["longitude"], b_pt["speed"],
                    angle,
                )
                out.append({
                    "a_point": a_name,
                    "b_point": b_name,
                    "type": aspect,
                    "scheme": "modern",
                    "orb": fact["orb"],
                    "separation": fact["separation"],
                    "applying": applying,
                })
                break
    return out


def test_known_pair_returns_expected_aspects() -> None:
    data, chart_a, chart_b = _load_pair()
    got = compute_synastry_aspects(chart_a, chart_b, "romantic")
    assert got == data["expected_aspects"]
    # Spot-check tight luminaries from the Sofia × Ayşe pair.
    by_pair = {(r["a_point"], r["b_point"]): r for r in got}
    moon_sun = by_pair[("Moon", "Sun")]
    assert moon_sun["type"] == "trine"
    assert moon_sun["orb"] == pytest.approx(0.559, abs=0.001)
    assert moon_sun["applying"] is True
    sun_sun = by_pair[("Sun", "Sun")]
    assert sun_sun["type"] == "square"
    assert sun_sun["orb"] == pytest.approx(1.943, abs=0.001)


def test_romantic_byte_identical_to_match_baseline() -> None:
    _data, chart_a, chart_b = _load_pair()
    romantic = compute_synastry_aspects(chart_a, chart_b, "romantic")
    baseline = _match_baseline(chart_a, chart_b)
    assert romantic == baseline
    # Default argument must be romantic (Match unchanged).
    assert compute_synastry_aspects(chart_a, chart_b) == baseline
    assert list(iter_match_synastry_aspects(chart_a, chart_b)) == baseline
    # Strict byte identity of the JSON form Match callers would persist.
    assert json.dumps(romantic, sort_keys=True, separators=(",", ":")) == (
        json.dumps(baseline, sort_keys=True, separators=(",", ":"))
    )


def test_family_types_return_subset_without_crash() -> None:
    _data, chart_a, chart_b = _load_pair()
    romantic = compute_synastry_aspects(chart_a, chart_b, "romantic")
    romantic_keys = {(r["a_point"], r["b_point"], r["type"]) for r in romantic}

    for kind in ("parent_child", "sibling"):
        family = compute_synastry_aspects(chart_a, chart_b, kind)
        assert isinstance(family, list)
        family_keys = {(r["a_point"], r["b_point"], r["type"]) for r in family}
        assert family_keys <= romantic_keys
        # No selection rules yet → empty subset.
        assert family == []


def test_invalid_relationship_type_raises() -> None:
    _data, chart_a, chart_b = _load_pair()
    with pytest.raises(ValueError, match="relationship_type"):
        compute_synastry_aspects(chart_a, chart_b, "cousins")  # type: ignore[arg-type]
