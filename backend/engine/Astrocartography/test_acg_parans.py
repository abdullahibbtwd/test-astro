#!/usr/bin/env python3
"""test_acg_parans.py — ACG spec 10 §8 (PA1–PA8).

    python -m pytest -q Astrocartography/test_acg_parans.py
"""

from __future__ import annotations

import copy
import os
import sys

import numpy as np
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, _ROOT, os.path.join(_ROOT, "d_layer"), os.path.join(_ROOT, "principles_grounding"),
           os.path.join(_ROOT, "acg_reading"), os.path.join(_ROOT, "Interpretation_layer")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from compute_chart import BirthData, compute_chart  # noqa: E402

import acg_goals as ag  # noqa: E402
import acg_locate as al  # noqa: E402
import compute_acg as ca  # noqa: E402
import compute_parans as cp  # noqa: E402
from acg_geo import n180  # noqa: E402

SOFIA = BirthData(year=1979, month=3, day=30, hour=6, minute=30,
                  latitude=42.690019, longitude=23.314641, time_precision="exact")


@pytest.fixture(scope="module")
def natal():
    return compute_chart(SOFIA)


@pytest.fixture(scope="module")
def acg(natal):
    return ca.compute_acg(natal)


@pytest.fixture(scope="module")
def parans(acg):
    return cp.compute_parans(acg)


def _eq(acg):
    return {b["body"]: b["equatorial"] for b in acg["bodies"]}


def test_pa1_hour_angles(acg, parans):
    eq = _eq(acg)
    for p in parans["parans"]:
        A, B = p["a"], p["b"]
        lst = eq[A["body"]]["ra"] + cp.hour_angle(A["angle"], p["lat"], eq[A["body"]]["dec"])
        h_b = n180(lst - eq[B["body"]]["ra"])
        want = cp.hour_angle(B["angle"], p["lat"], eq[B["body"]]["dec"])
        assert abs(n180(h_b - want)) < 1e-6, p["id"]


def _interp_lon(verts, lat):
    for (l1, p1), (l2, p2) in zip(verts, verts[1:]):
        if p1 <= lat <= p2:
            d = n180(l2 - l1)
            t = 0.0 if p2 == p1 else (lat - p1) / (p2 - p1)
            return n180(l1 + t * d)
    return None


def test_pa2_lines_cross_at_paran_latitude(acg, parans):
    bodies = {b["body"]: b for b in acg["bodies"]}
    checked = 0
    for p in parans["parans"]:
        la = _interp_lon(bodies[p["a"]["body"]]["lines"][p["a"]["angle"]]["vertices"], p["lat"])
        lb = _interp_lon(bodies[p["b"]["body"]]["lines"][p["b"]["angle"]]["vertices"], p["lat"])
        assert la is not None and lb is not None, p["id"]
        # every paran, including those next to the circumpolar joins (compute_acg
        # densifies the curves there by hour angle, so the polylines hold)
        assert abs(n180(la - lb)) < 0.01, p["id"]
        assert abs(n180(la - p["crossing_lon"])) < 0.01, p["id"]
        checked += 1
    assert checked == len(parans["parans"])


def test_pa3_scope(parans, acg):
    eq = _eq(acg)
    for p in parans["parans"]:
        angles = {p["a"]["angle"], p["b"]["angle"]}
        assert not angles <= {"MC", "IC"}
        assert "north_node" not in (p["a"]["body"], p["b"]["body"])
        for side in ("a", "b"):
            if p[side]["angle"] in ("ASC", "DSC"):
                assert abs(p["lat"]) <= 90 - abs(eq[p[side]["body"]]["dec"]) + 1e-9
        assert -80 <= p["lat"] <= 80


def test_pa4_determinism_and_count(acg, parans):
    assert cp.dumps(cp.compute_parans(acg)) == cp.dumps(parans)
    assert 200 <= len(parans["parans"]) <= 230
    lats = [p["lat"] for p in parans["parans"]]
    assert lats == sorted(lats)
    assert len({p["id"] for p in parans["parans"]}) == len(parans["parans"])


def test_pa5_orb_and_weight(parans):
    p = parans["parans"][100]
    near = cp.parans_near({"parans": [p]}, p["lat"] + 0.5)
    assert len(near) == 1 and near[0]["weight"] == pytest.approx(0.2)
    assert cp.parans_near({"parans": [p]}, p["lat"] + 1.01) == []


def test_pa6_max_two_closest(parans):
    lat = parans["parans"][100]["lat"]
    near = cp.parans_near(parans, lat)
    assert len(near) <= 2
    within = sorted(abs(lat - p["lat"]) for p in parans["parans"] if abs(lat - p["lat"]) <= 1.0)
    assert [r["dlat_deg"] for r in near] == within[:len(near)]


def test_pa7_zero_weight_regression(acg, parans, monkeypatch):
    aff = ag.load_affinity()
    base = ag.score_point(acg, 41.0, 29.0, aff)
    monkeypatch.setattr(ag, "W_PARAN", 0.0)
    with_zero = ag.score_point(acg, 41.0, 29.0, aff, parans)
    for g in ag.GOAL_ORDER:
        assert with_zero[g]["S"] == pytest.approx(base[g]["S"], abs=1e-12)
    import acg_geodata as geo
    cities = geo.load_cities()[:300]
    s0 = ag.goal_scan(acg, aff, cities, None)
    s1 = ag.goal_scan(acg, aff, cities, None, parans)
    assert np.allclose(s0["city_S"], s1["city_S"])


def test_scan_matches_city_path_with_parans(acg, parans):
    aff = ag.load_affinity()
    import acg_geodata as geo
    cities = sorted(geo.load_cities(), key=lambda c: c["id"])[:400]
    scan = ag.goal_scan(acg, aff, cities, None, parans)
    for i in range(0, 400, 37):
        c = cities[i]
        res = ag.score_point(acg, c["lat"], c["lon"], aff, parans)
        for gi, g in enumerate(ag.GOAL_ORDER):
            assert scan["city_S"][i, gi] == pytest.approx(res[g]["S"], abs=1e-5)


def test_geojson_layer(parans):
    gj = cp.to_geojson(parans)
    lines = [f for f in gj["features"] if f["properties"]["kind"] == "paran"]
    points = [f for f in gj["features"] if f["properties"]["kind"] == "paran_crossing"]
    assert len(lines) == len(points) == len(parans["parans"])
    for f in lines[:20]:
        xs = [c[0] for c in f["geometry"]["coordinates"]]
        assert xs[0] == -180 and xs[-1] == 180
        assert len({c[1] for c in f["geometry"]["coordinates"]}) == 1


def test_locate_blocks(acg, natal, parans):
    p = parans["parans"][120]
    place = {"query": None, "name": "X", "name_tr": "X", "lat": p["lat"] + 0.3, "lon": 10.0,
             "country_code": None, "source": "manual"}
    loc, _ = al.build_locate(acg, natal, place, parans=parans)
    assert 1 <= len(loc["parans_near"]) <= 2
    d = loc["parans_display"][0]
    assert d["label_tr"] == "Enlem kesişimi" and len(d["planets_tr"]) == 2
    assert d["north_south"] in ("north", "south")


def test_pa8_reading_section(acg, natal, parans):
    import ground_acg as ga
    import ar_routing
    corp = ga.load_json(ga.ACG_CORPUS_PATH), ga.load_json(ga.MAIN_CORPUS_PATH)
    lats = [q["lat"] for q in parans["parans"]]
    # a latitude with no paran within 1°
    far = next(x for x in np.arange(-60, 70, 0.1) if min(abs(x - l) for l in lats) > 1.05)
    for lat, expect in ((float(far), False), (parans["parans"][120]["lat"] + 0.2, True)):
        place = {"query": None, "name": "X", "name_tr": "X", "lat": lat, "lon": 10.0,
                 "country_code": None, "source": "manual"}
        loc, reloc = al.build_locate(acg, natal, place, parans=parans)
        pay, _ = ga.ground_acg(natal, reloc, loc, *corp)
        plan = ar_routing.build_plan(pay)
        keys = [s["key"] for s in plan["sections"]]
        assert ("background_influences" in keys) is expect
        if expect:
            sec = next(s for s in plan["sections"] if s["key"] == "background_influences")
            for slot in sec["slots"]:
                bundle = next(b for b in pay["bundles"] if b["factor"] == slot["slot_id"])
                ids = {r["principle_id"] for r in bundle["records"]}
                assert {r["id"] for r in slot["records"]} == ids
                for r in bundle["records"]:
                    src = r["acg_evidence"]["source"]
                    if src == "P1":
                        assert r["acg_scope"] == "paran"
                    elif src == "P2":
                        assert r["acg_scope"] == "planet_general"
                        assert r["about"]["planet"].lower() in slot["bodies"]
                    else:
                        assert r["principle_id"] == "acg-method-crossings"
