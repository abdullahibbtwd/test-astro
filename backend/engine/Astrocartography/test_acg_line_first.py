#!/usr/bin/env python3
"""test_acg_line_first.py — ACG spec 11 §9, the recommender half (DV4–DV8).
DV1–DV3 (policy + filters) live in test_acg_destinations.py.

Destinations are not reviewed yet (spec 11: no auto-approval), so these tests run the
ranking with ``include_unreviewed=True`` — the same code path, a wider candidate set.

    python -m pytest -q Astrocartography/test_acg_line_first.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, _ROOT, os.path.join(_ROOT, "d_layer")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pytest.importorskip("acg_destinations")
if not os.path.exists(os.path.join(_HERE, "destinations.json")):
    pytest.skip("destinations.json not built", allow_module_level=True)

from compute_chart import BirthData, compute_chart  # noqa: E402

import acg_destinations as dst  # noqa: E402
import acg_geodata as geo  # noqa: E402
import acg_goals as ag  # noqa: E402
import acg_line_first as lf  # noqa: E402
import acg_recommend as rec  # noqa: E402
import compute_acg as ca  # noqa: E402
import compute_parans as cp  # noqa: E402
from acg_geo import gc_distance_km  # noqa: E402

BD = BirthData(year=1985, month=3, day=14, hour=11, minute=30,
               latitude=41.0082, longitude=28.9784, time_precision="exact")
HOME = (41.0082, 28.9784)


@pytest.fixture(scope="module")
def ctx():
    acg = ca.compute_acg(compute_chart(BD))
    parans = cp.compute_parans(acg)
    aff = ag.load_affinity()
    rec.set_parans(parans)
    scan = ag.goal_scan(acg, aff, geo.load_cities(), geo.load_grid(), parans)
    return {"acg": acg, "parans": parans, "aff": aff, "scan": scan}


def _rank(ctx, goal, scope="world", **filters):
    f = dst.resolve_filters(goal, home_latlon=HOME, **filters)
    return lf.rank_line_first(goal, scope, ctx["acg"], ctx["scan"], ctx["aff"], f,
                              include_unreviewed=True)


@pytest.fixture(scope="module")
def career(ctx):
    return _rank(ctx, "career")


def _all_dest_ids(r):
    ids = {d["id"] for g in r["by_line"] for d in g["destinations"]} | {c["id"] for c in r["cities"]}
    if r.get("turkey"):
        ids |= {d["id"] for g in r["turkey"]["by_line"] for d in g["destinations"]}
    return ids


def test_dv4_groups(ctx, career):
    assert career["by_line"], "expected at least one line group"
    assert len(career["by_line"]) <= 4
    bodies = {b["body"]: b for b in ctx["acg"]["bodies"]}
    for g in career["by_line"]:
        ds = g["destinations"]
        assert 1 <= len(ds) <= 5
        countries = [d["country"] for d in ds]
        assert all(countries.count(c) <= 2 for c in countries)
        for i, a in enumerate(ds):
            assert a["band"] in rec.ELIGIBLE
            for b in ds[i + 1:]:
                assert gc_distance_km(a["lon"], a["lat"], b["lon"], b["lat"]) >= 150.0
            ln = g["line"]
            if ln["kind"] == "line":
                D = ag.line_distances(ctx["acg"], [a["lat"]], [a["lon"]])[0]
                j = ag.LINE_KEYS.index((ln["body"], ln["angle"]))
                assert D[j] <= 400.0 + 1e-6
            else:
                p = next(x for x in ctx["parans"]["parans"] if x["id"] == ln["id"])
                assert abs(a["lat"] - p["lat"]) <= 1.0
    real = [g for g in career["by_line"] if g["kind"] == "line"]
    assert len(real) >= min(3, len(career["by_line"]))
    assert [g["affinity"] for g in career["by_line"]] == sorted(
        (g["affinity"] for g in career["by_line"]), reverse=True)


def test_dv5_lines_without_destinations(ctx):
    # a filter that leaves almost nothing makes strong lines come up empty
    r = _rank(ctx, "career", regions=["oceania"], city_size=["big"])
    empty = {f"{x['line']['body']}|{x['line']['angle']}" for x in r["lines_without_destinations"]}
    grouped = {f"{g['line'].get('body')}|{g['line'].get('angle')}" for g in r["by_line"]}
    assert empty, "expected at least one strong line without destinations"
    assert not (empty & grouped)
    strong = {f"{x['body']}|{x['angle']}" for x in lf.strong_lines(ctx["aff"], "career", None)}
    assert empty <= strong


def test_dv6_no_excluded_areas(career):
    by_id = {d["id"]: d for d in dst.load_destinations()}
    for did in _all_dest_ids(career):
        d = by_id[did]
        ok, rule = dst.policy_verdict(d)
        assert ok and not d["exclude"], (d["name"], rule)
        assert d["country"] not in ("KP", "MN")


def test_dv7_turkey_block_small_places(ctx, career):
    by_id = {d["id"]: d for d in dst.load_destinations()}
    world_sizes = {by_id[d["id"]]["size"] for g in career["by_line"] for d in g["destinations"]}
    assert world_sizes <= {"big"}                           # default city_size = big
    # the Turkey block ignores the size default: small TR destinations are candidates
    f = dst.resolve_filters("career", home_latlon=HOME)
    tr_small = [d for d in dst.candidates(f, include_unreviewed=True, ignore_size=True,
                                          country="TR") if d["size"] == "small"]
    assert tr_small, "expected small Turkish destinations (e.g. Bodrum) as candidates"
    assert "turkey" in career


def test_dv8_filters_never_change_scores(ctx):
    base = _rank(ctx, "career")
    narrowed = _rank(ctx, "career", regions=["europe"], climate=["warm", "mild"])
    s_base = {d["id"]: d["S"] for g in base["by_line"] for d in g["destinations"]}
    for g in narrowed["by_line"]:
        for d in g["destinations"]:
            if d["id"] in s_base:
                assert d["S"] == s_base[d["id"]]
            full = rec.item_honesty(ctx["acg"], d["lat"], d["lon"], ctx["aff"], "career")
            assert full["S"] == d["S"]


def test_filters_echoed(career):
    f = career["filters_applied"]
    assert f["regions"] == ["all"] and f["city_size"] == ["big"]
    assert f["climate"] is None and f["policy"] == "viable_world_v1"
    assert f["purpose"] == ["living"]
    assert career["include_unreviewed"] is True


def test_flat_list(career):
    cities = career["cities"]
    assert len(cities) <= 10
    cs = [c["country"] for c in cities]
    assert all(cs.count(c) <= 3 for c in cs)
    assert [c["S"] for c in cities] == sorted((c["S"] for c in cities), reverse=True)
    ids = {d["id"] for g in career["by_line"] for d in g["destinations"]}
    assert {c["id"] for c in cities} <= ids


def test_reviewed_only_by_default(ctx):
    f = dst.resolve_filters("career", home_latlon=HOME)
    r = lf.rank_line_first("career", "world", ctx["acg"], ctx["scan"], ctx["aff"], f)
    by_id = {d["id"]: d for d in dst.load_destinations()}
    assert all(by_id[i]["reviewed"] for i in _all_dest_ids(r))
