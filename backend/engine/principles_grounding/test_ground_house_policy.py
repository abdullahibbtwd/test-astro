"""Tests for the grounding house policy (ground.py, added 2026-09-21).

The reading is Placidus-only: every house claim is verified against the
placidus sector / rulers whatever system the source record declares. A
whole-sign record survives only when its house is also the Placidus house.

Run:  python -m pytest principles_grounding/test_ground_house_policy.py -q
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ground import ground  # noqa: E402

# Synthetic chart: only the fields the gate reads. The Sun straddles a cusp so
# its Placidus (9) and whole-sign (8) houses differ; the Moon agrees (5/5).
_POINTS = [
    ("Sun", "Gemini", 9, 8),
    ("Moon", "Pisces", 5, 5),
    ("Mercury", "Gemini", 8, 8),
    ("Venus", "Taurus", 7, 7),
    ("Mars", "Aries", 6, 6),
    ("Jupiter", "Cancer", 9, 9),
    ("Saturn", "Capricorn", 3, 3),
    ("Uranus", "Capricorn", 3, 3),
    ("Neptune", "Capricorn", 3, 3),
    ("Pluto", "Scorpio", 1, 1),
    ("North Node", "Aquarius", 4, 4),
    ("South Node", "Leo", 10, 10),
]
_CUSP_SIGNS = ["Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces", "Aries",
               "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra"]
_RULER = {"Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon",
          "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars",
          "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn",
          "Pisces": "Jupiter"}
_MODERN = {**_RULER, "Scorpio": "Pluto", "Aquarius": "Uranus", "Pisces": "Neptune"}


def _chart(*, lord_of_1_placidus_house: int = 6) -> dict:
    pts = {n: {"name": n, "sign": sg, "traditional": n not in ("Uranus", "Neptune", "Pluto"),
               "sector": {"placidus": pl, "whole_sign": ws}, "classifications": None}
           for n, sg, pl, ws in _POINTS}
    # Mars (lord of 1) sits in Placidus 6 by default; the whole-sign block puts
    # it in 7 so the two systems disagree about the lord's placement.
    pts["Mars"]["sector"] = {"placidus": lord_of_1_placidus_house, "whole_sign": 7}

    def rulers(system):
        out = {}
        for i, sign in enumerate(_CUSP_SIGNS):
            r, m = _RULER[sign], _MODERN[sign]
            out[str(i + 1)] = {
                "sign_on_cusp": sign, "ruler": r, "ruler_sign": pts[r]["sign"],
                "ruler_sector": pts[r]["sector"][system],
                "modern_ruler": m, "modern_ruler_sign": pts[m]["sign"],
                "modern_ruler_sector": pts[m]["sector"][system]}
        return out

    return {
        "confidence": "exact",
        "points": list(pts.values()),
        "axes": {"ascendant": {"sign": "Scorpio"}, "mc": {"sign": "Leo"}},
        "sector_rulers": {"placidus": rulers("placidus"), "whole_sign": rulers("whole_sign")},
        "relations": [],
    }


def _rec(pid, factor_type, tradition="traditional", **about):
    return {"principle_id": pid, "domain": "natal", "tradition": tradition,
            "rule": "r", "topic_tags": [], "requires": [],
            "about": {"factor_type": factor_type, "extraction_confidence": "high",
                      "extraction_source": "deterministic", **about}}


def _kept_ids(res):
    return {r["principle_id"] for r in res.kept}


def test_whole_sign_record_verified_against_placidus():
    ws8 = _rec("sun-ws-8", "planet_in_house", point="Sun", house=8, house_system="whole_sign")
    ws9 = _rec("sun-ws-9", "planet_in_house", point="Sun", house=9, house_system="whole_sign")
    res = ground([ws8, ws9], _chart())          # default policy: placidus
    assert _kept_ids(res) == {"sun-ws-9"}       # the Placidus house, not the declared one
    assert res.house_policy == "placidus"
    assert "Sun in placidus house 9" in res.bundles   # label shows the verified system
    drop = next(d for d in res.drops if d.principle_id == "sun-ws-8")
    assert drop.gate == "B" and "placidus" in drop.reason


def test_record_policy_honours_declared_system():
    ws8 = _rec("sun-ws-8", "planet_in_house", point="Sun", house=8, house_system="whole_sign")
    ws9 = _rec("sun-ws-9", "planet_in_house", point="Sun", house=9, house_system="whole_sign")
    res = ground([ws8, ws9], _chart(), house_policy=None)
    assert _kept_ids(res) == {"sun-ws-8"}
    assert res.house_policy is None
    assert "Sun in whole_sign house 8" in res.bundles


def test_agreeing_houses_survive_either_way():
    moon = _rec("moon-ws-5", "planet_in_house", point="Moon", house=5, house_system="whole_sign")
    assert _kept_ids(ground([moon], _chart())) == {"moon-ws-5"}
    assert _kept_ids(ground([moon], _chart(), house_policy=None)) == {"moon-ws-5"}


def test_node_house_uses_policy():
    nn = _rec("nn-4", "node", point="North Node", house=4, house_system="whole_sign")
    assert _kept_ids(ground([nn], _chart())) == {"nn-4"}


def test_house_lord_relative_resolved_in_placidus():
    # lord of 1 (Mars) is in Placidus 6 but whole-sign 7: the WS-declared record
    # claiming "lord of 1 in 7" fails under the Placidus policy; "in 6" passes.
    in7 = _rec("lord1-in-7", "house_lord_relative", subject_house=1,
               subject_house_system="whole_sign", placement_house=7,
               placement_house_system="whole_sign")
    in6 = _rec("lord1-in-6", "house_lord_relative", subject_house=1,
               subject_house_system="whole_sign", placement_house=6,
               placement_house_system="whole_sign")
    res = ground([in7, in6], _chart())
    assert _kept_ids(res) == {"lord1-in-6"}
    assert "lord of placidus house 1 in house 6" in res.bundles
    res_record = ground([in7, in6], _chart(), house_policy=None)
    assert _kept_ids(res_record) == {"lord1-in-7"}


def test_payload_and_report_carry_policy():
    res = ground([], _chart())
    assert res.kept_payload()["house_policy"] == "placidus"
    assert res.report()["house_policy"] == "placidus"


def test_bad_policy_rejected():
    with pytest.raises(ValueError):
        ground([], _chart(), house_policy="koch")
