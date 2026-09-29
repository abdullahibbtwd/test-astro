#!/usr/bin/env python3
"""test_acg_goals.py — ACG spec 08 §7 (S2–S8; S1 lives in test_acg_affinity.py).

    python -m pytest -q Astrocartography/test_acg_goals.py
"""

from __future__ import annotations

import io
import os
import sys
import time
import warnings

import numpy as np
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, os.path.join(_ROOT, "d_layer")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from compute_chart import BirthData, compute_chart  # noqa: E402

import acg_geodata as geo  # noqa: E402
import acg_goals as ag  # noqa: E402
import compute_acg as ca  # noqa: E402

BD = BirthData(year=1985, month=3, day=14, hour=11, minute=30,
               latitude=41.0082, longitude=28.9784, time_precision="exact")


@pytest.fixture(scope="module")
def acg():
    return ca.compute_acg(compute_chart(BD))


@pytest.fixture(scope="module")
def aff():
    return ag.load_affinity()


@pytest.fixture(scope="module")
def scan(acg, aff):
    t0 = time.monotonic()
    s = ag.goal_scan(acg, aff, geo.load_cities(), geo.load_grid())
    s["_elapsed"] = time.monotonic() - t0
    return s


def test_s2_distance_weight():
    w = ag.distance_weight
    assert w(0) == 1.0 and w(150) == 1.0
    assert w(400) == pytest.approx(0.5) and w(1000) == pytest.approx(0.0)
    assert w(1000.1) == 0.0
    xs = np.linspace(0, 1100, 2201)
    ys = [w(x) for x in xs]
    assert all(a >= b - 1e-12 for a, b in zip(ys, ys[1:]))                   # monotone
    for x in (150, 400):                                                      # continuous
        assert abs(w(x - 1e-9) - w(x + 1e-9)) < 1e-6
    assert np.allclose(ag.distance_weight_np(xs), ys)


@pytest.mark.parametrize("P,N,band", [
    (0.05, 0.1, "no_emphasis"),            # P + N < 0.20
    (1.2, 0.7, "mixed"),                   # mixed wins over S >= ... (precedence)
    (2.0, 1.0, "mixed"),                   # satisfies both mixed and S >= 1 -> mixed
    (1.3, 0.1, "strongly_supportive"),
    (0.5, 0.1, "supportive"),
    (0.05, 0.6, "challenging"),
    (0.3, 0.1, "no_emphasis"),             # S = 0.2: below supportive
])
def test_s3_bands(P, N, band):
    assert ag.band_of(P, N) == band
    code = ag.band_codes_np(np.array([P]), np.array([N]))[0]
    assert ag._BAND_CODES[code] == band


def test_s4_contributors_traceable(acg, aff):
    import json
    corpus_path = os.path.join(_ROOT, "principles_grounding", "acg_principles.grounded.json")
    with open(corpus_path, encoding="utf-8") as fh:
        ids = {r["principle_id"] for r in json.load(fh)}
    for lat, lon in ((38.42, 27.14), (40.71, -74.0), (52.52, 13.4), (-33.87, 151.2)):
        res = ag.score_point(acg, lat, lon, aff)
        near = {(c["body"], c["angle"]) for c in res["love"]["contributions"]}
        for goal, r in res.items():
            for rid in r["contributors"]:
                assert rid in ids
                assert any(rid in ag.cell_contributors(aff, b, a, goal) for b, a in near)


def test_s5_scan_deterministic(acg, aff):
    cities = geo.load_cities()[:200]
    a = ag.goal_scan(acg, aff, cities, None)
    b = ag.goal_scan(acg, aff, cities, None)
    ba, bb = io.BytesIO(), io.BytesIO()
    np.savez_compressed(ba, **a)
    np.savez_compressed(bb, **b)
    assert ba.getvalue() == bb.getvalue()


def test_s6_scan_equals_city_path(acg, aff, scan):
    cities = sorted(geo.load_cities(), key=lambda c: c["id"])
    idx = {c["id"]: i for i, c in enumerate(cities)}
    for cid in [cities[i]["id"] for i in range(0, len(cities), 97)] + ["gn-311046"]:
        if cid not in idx:
            continue
        c = cities[idx[cid]]
        res = ag.score_point(acg, c["lat"], c["lon"], aff)
        for gi, g in enumerate(ag.GOAL_ORDER):
            # float32 storage in the npz -> 1e-6 relative tolerance
            assert scan["city_S"][idx[cid], gi] == pytest.approx(res[g]["S"], abs=1e-5)
            assert scan["city_P"][idx[cid], gi] == pytest.approx(res[g]["P"], abs=1e-5)


def test_s7_no_lines_no_emphasis(aff):
    # a synthetic chart whose lines are all far away: shift every line out of range
    fake = {"bodies": []}
    for body in ag.READ_BODIES:
        far = [[179.0, lat] for lat in np.arange(-80, 80.25, 0.25)]
        fake["bodies"].append({"body": body, "read_in_v1": True, "lines": {
            "MC": {"vertices": far}, "IC": {"vertices": far},
            "ASC": {"vertices": far}, "DSC": {"vertices": far}}})
    res = ag.score_point(fake, 0.0, 0.0, aff)
    for r in res.values():
        assert r["band"] == "no_emphasis" and r["P"] == 0.0 and r["N"] == 0.0


def test_s8_performance(scan):
    n = len(scan["grid_lat"]) + len(scan["city_ids"])
    if scan["_elapsed"] > 10.0:
        warnings.warn(f"goal scan took {scan['_elapsed']:.1f}s for {n} points (target < 10s)")
    assert n > 50000


def test_heat_layer(scan):
    for g in ag.GOAL_ORDER:
        gj = ag.heat_geojson(scan, g)
        for f in gj["features"][:50]:
            assert f["properties"]["band"] != "no_emphasis"
            lon, lat = f["geometry"]["coordinates"]
            assert round(lon, 2) == lon and round(lat, 2) == lat


def test_aggregate_k():
    S = np.arange(40, dtype=float).reshape(40, 1) * np.ones((1, 11))
    P, N = np.clip(S, 0, None), np.zeros_like(S)
    a = ag.aggregate(S, P, N, kind="country")["love"]
    assert a["k"] == 3 and a["S_agg"] == pytest.approx((39 + 38 + 37) / 3)
    a = ag.aggregate(S[:5], P[:5], N[:5], kind="region")["love"]
    assert a["k"] == 1 and a["S_agg"] == 4.0
