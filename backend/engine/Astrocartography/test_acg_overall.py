#!/usr/bin/env python3
"""test_acg_overall.py — the "overall improvement" recommendation (acg_overall.py)."""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, _ROOT, os.path.join(_ROOT, "d_layer"), os.path.join(_ROOT, "acg_reading"),
           os.path.join(_ROOT, "principles_grounding"), os.path.join(_ROOT, "Interpretation_layer")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from compute_chart import BirthData, compute_chart  # noqa: E402

import acg_destinations as dst  # noqa: E402
import acg_goals as ag  # noqa: E402
import acg_overall as ov  # noqa: E402
import acg_recommend as rec  # noqa: E402
import compute_acg as ca  # noqa: E402
import compute_parans as cp  # noqa: E402
from acg_geo import gc_distance_km  # noqa: E402

BD = BirthData(year=1979, month=3, day=30, hour=6, minute=30,
               latitude=42.690019, longitude=23.314641, time_precision="exact")


@pytest.fixture(scope="module")
def result():
    acg = ca.compute_acg(compute_chart(BD))
    rec.set_parans(cp.compute_parans(acg))
    aff = ag.load_affinity()
    f = dst.resolve_filters("love", home_latlon=(42.69, 23.31), purpose="both")
    r = ov.recommend_overall(acg, aff, f)
    yield acg, aff, r
    rec.set_parans(None)


def test_eligibility_and_order(result):
    _, _, r = result
    places = r["places"]
    assert 0 < len(places) <= ov.MAX_PLACES
    assert all(p["overall"] >= ov.OVERALL_MIN and p["breadth"] >= ov.BREADTH_MIN for p in places)
    assert [p["overall"] for p in places] == sorted((p["overall"] for p in places), reverse=True)


def test_overall_is_mean_of_goal_scores(result):
    acg, aff, r = result
    for p in r["places"][:4]:
        sc = ag.score_point(acg, p["lat"], p["lon"], aff, rec.PARANS)
        assert p["overall"] == pytest.approx(np.mean([s["S"] for s in sc.values()]), abs=1e-5)
        assert p["breadth"] == sum(s["band"] in ov.ELIGIBLE for s in sc.values())
        assert p["strain"] == sum(s["band"] == "challenging" for s in sc.values())


def test_diversity(result):
    _, _, r = result
    places = r["places"]
    cs = [p["country"] for p in places]
    assert all(cs.count(c) <= ov.PER_COUNTRY for c in cs)
    for i, a in enumerate(places):
        for b in places[i + 1:]:
            assert gc_distance_km(a["lon"], a["lat"], b["lon"], b["lat"]) >= ov.MIN_SEP_KM
    lines = [rec.line_key_of(p["dominant_line"]) for p in places]
    assert all(lines.count(x) <= ov.PER_LINE for x in lines)


def test_only_viable_reviewed(result):
    _, _, r = result
    by_id = {d["id"]: d for d in dst.load_destinations()}
    for p in r["places"] + r["turkey"]["places"]:
        d = by_id[p["id"]]
        assert d["reviewed"] and not d["exclude"] and dst.policy_verdict(d)[0]
    assert all(p["country"] == "TR" for p in r["turkey"]["places"])


def test_tradeoff_flag(result):
    _, _, r = result
    for p in r["places"]:
        assert p["has_tradeoff"] == bool(p["challenged"])


def test_dry_run_no_calls(tmp_path, monkeypatch):
    import llm_client
    import run_acg

    def boom(*_a, **_k):
        raise AssertionError("model call in dry run")
    monkeypatch.setattr(llm_client, "complete", boom)
    birth = {"year": 1979, "month": 3, "day": 30, "hour": 6, "minute": 30,
             "latitude": 42.690019, "longitude": 23.314641, "time_precision": "exact"}
    m = run_acg.run_acg({"birth": birth, "recommend": "overall"}, dry_run=True,
                        runs_dir=str(tmp_path / "r"), cache_root=str(tmp_path / "c"))
    assert m["status"] == "ok" and m["goal"] == "overall"
    f = next(a for a in m["artifacts"] if a.startswith("recommend_overall_world"))
    with open(os.path.join(m["run_dir"], f), encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["places"] and data["dry_run_units"]
    for p in data["places"]:
        assert p["text_en"].startswith(p["label_en"])
    rec.set_parans(None)
