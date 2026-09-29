#!/usr/bin/env python3
"""test_ground_acg.py — ACG spec 03 invariants GA1–GA12 (+ v3 goal block).

    python -m pytest -q principles_grounding/test_ground_acg.py
"""

from __future__ import annotations

import copy
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, os.path.join(_ROOT, "d_layer"), os.path.join(_ROOT, "Astrocartography")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from compute_chart import BirthData, compute_chart  # noqa: E402

import acg_locate as al  # noqa: E402
import compute_acg as ca  # noqa: E402
import ground_acg as ga  # noqa: E402
from ground import ground  # noqa: E402

BD = BirthData(year=1985, month=3, day=14, hour=11, minute=30,
               latitude=41.0082, longitude=28.9784, time_precision="exact")


@pytest.fixture(scope="module")
def natal():
    return compute_chart(BD)


@pytest.fixture(scope="module")
def acg(natal):
    return ca.compute_acg(natal)


@pytest.fixture(scope="module")
def acg_corpus():
    return ga.load_json(ga.ACG_CORPUS_PATH)


@pytest.fixture(scope="module")
def main_corpus():
    return ga.load_json(ga.MAIN_CORPUS_PATH)


def _place(lat, lon, name="Test"):
    return {"query": None, "name": name, "name_tr": name, "lat": lat, "lon": lon,
            "country_code": None, "source": "manual"}


def _line(body, angle, d, tier, read=True):
    return {"body": body, "angle": angle, "distance_km": d, "tier": tier, "read_in_v1": read,
            "nearest_point": [0.0, 0.0], "side": "east"}


def _locate(lines, house_diff=(), reloc_status="ok"):
    return {"schema_version": "acg-locate-1", "place": _place(38.42, 27.14, "İzmir"),
            "status": "ok", "absence": None, "lines_near": list(lines),
            "relocation": {"status": reloc_status,
                           "absence": None if reloc_status == "ok" else
                           {"reason": "placidus_undefined_high_latitude", "detail": None},
                           "chart_path": None},
            "house_diff": list(house_diff)}


FIVE = [_line("venus", "DSC", 20, "tight"), _line("mars", "MC", 60, "tight"),
        _line("sun", "ASC", 180, "strong"), _line("moon", "IC", 250, "strong"),
        _line("jupiter", "MC", 390, "strong"), _line("saturn", "DSC", 700, "wide")]
WIDE_ONLY = [_line("saturn", "DSC", 700, "wide"), _line("pluto", "ASC", 900, "wide")]
NOTHING: list = []


def _run(natal, locate, acg_corpus, main_corpus, relocated=None):
    return ga.ground_acg(natal, relocated, locate, acg_corpus, main_corpus)


def _source_of(rec):
    return rec["acg_evidence"].get("source")


def test_ga1_sources_consistent_with_about(natal, acg_corpus, main_corpus):
    pay, _ = _run(natal, _locate(FIVE), acg_corpus, main_corpus, relocated=natal)
    for b in pay["bundles"]:
        if not b["factor"].startswith("line:"):
            continue
        body, angle = b["factor"][5:].split("|")
        for r in b["records"]:
            about, src = r["about"], _source_of(r)
            if src == "A1":
                assert about["factor_type"] == "planet_on_angle"
                assert about["planet"].lower() == body and about["angle"] == angle
            elif src == "A2":
                assert about["factor_type"] == "acg_planet_general"
                assert about["planet"].lower() == body
            elif src == "A3":
                assert r["principle_id"] == f"acg-angle-{angle.lower()}"
            elif src == "A4":
                assert about["factor_type"] == "planet_in_house"
                assert about["house"] == ga.ANGLE_HOUSE[angle]
                assert r["domain"] == "natal" and r["tradition"] == "modern"
            else:
                pytest.fail(f"unknown source {src}")


def test_ga2_selection_rules(natal, acg_corpus, main_corpus):
    pay, rep = _run(natal, _locate(FIVE), acg_corpus, main_corpus)
    assert pay["selection"]["rule"] == "tight_strong"
    assert pay["selection"]["lines"] == ["venus|DSC", "mars|MC", "sun|ASC", "moon|IC"]
    dropped = {d["principle_id"]: d["reason"] for d in rep["drop_log"]}
    assert dropped["line:jupiter|MC"] == "line_budget_exceeded"
    assert dropped["line:saturn|DSC"] == "tier_wide_not_selected"

    pay, _ = _run(natal, _locate(WIDE_ONLY), acg_corpus, main_corpus)
    assert pay["selection"] == {"rule": "nearest_wide", "lines": ["saturn|DSC"]}

    pay, _ = _run(natal, _locate(NOTHING), acg_corpus, main_corpus)
    assert pay["selection"]["rule"] == "none"
    assert not [b for b in pay["bundles"] if b["factor"].startswith("line:")]
    method = next(b for b in pay["bundles"] if b["factor"] == "method")
    assert "acg-method-no-influence" in [r["principle_id"] for r in method["records"]]


def test_ga3_requires_natal_value_condition(natal, acg_corpus, main_corpus):
    venus_sign = next(p["sign"] for p in natal["points"] if p["name"] == "Venus")
    other = "Libra" if venus_sign != "Libra" else "Taurus"
    synthetic = copy.deepcopy(next(r for r in acg_corpus
                                   if r["principle_id"].startswith("acg-venus-dsc-")))
    synthetic["principle_id"] = "acg-venus-dsc-99"
    synthetic["requires"] = [{"kind": "natal_point_sign", "point": "Venus", "sign": other}]
    pay, rep = _run(natal, _locate([_line("venus", "DSC", 20, "tight")]),
                    acg_corpus + [synthetic], main_corpus)
    kept = {r["principle_id"] for b in pay["bundles"] for r in b["records"]}
    assert "acg-venus-dsc-99" not in kept
    assert {"principle_id": "acg-venus-dsc-99", "reason": "requires_unsatisfied_natal"}.items() \
        <= next(d for d in rep["drop_log"] if d["principle_id"] == "acg-venus-dsc-99").items()


def test_requires_unsupported_and_relocated(natal, acg_corpus, main_corpus):
    base = next(r for r in acg_corpus if r["principle_id"].startswith("acg-mars-mc-"))
    unsup = dict(copy.deepcopy(base), principle_id="acg-mars-mc-97",
                 requires=[{"kind": "unsupported", "text": "x"}])
    needs = dict(copy.deepcopy(base), principle_id="acg-mars-mc-98",
                 requires=[{"kind": "relocated_point_angular", "point": "Mars"}])
    pay, rep = _run(natal, _locate([_line("mars", "MC", 20, "tight")], reloc_status="absent"),
                    acg_corpus + [unsup, needs], main_corpus, relocated=None)
    reasons = {d["principle_id"]: d["reason"] for d in rep["drop_log"]}
    assert reasons["acg-mars-mc-97"] == "requires_unsupported_kind"
    assert reasons["acg-mars-mc-98"] == "requires_needs_relocated_chart"


def test_ga4_fallback_only_when_thin(natal, acg_corpus, main_corpus):
    pay, rep = _run(natal, _locate([_line("venus", "DSC", 20, "tight")]), acg_corpus, main_corpus)
    b = next(b for b in pay["bundles"] if b["factor"] == "line:venus|DSC")
    a1 = [r for r in b["records"] if _source_of(r) == "A1"]
    a4 = [r for r in b["records"] if _source_of(r) == "A4"]
    assert len(a1) >= 3 and a4 == []
    assert any(d["reason"] == "fallback_not_needed" for d in rep["drop_log"])

    thin = [r for r in acg_corpus if not r["principle_id"].startswith("acg-venus-dsc-")]
    thin += [r for r in acg_corpus if r["principle_id"].startswith("acg-venus-dsc-")][:1]
    pay, _ = _run(natal, _locate([_line("venus", "DSC", 20, "tight")]), thin, main_corpus)
    b = next(b for b in pay["bundles"] if b["factor"] == "line:venus|DSC")
    a1 = [r for r in b["records"] if _source_of(r) == "A1"]
    a4 = [r for r in b["records"] if _source_of(r) == "A4"]
    assert len(a1) == 1 and 1 <= len(a4) and len(a1) + len(a4) <= 3


def test_ga5_ga6_stream_b(natal, acg, acg_corpus, main_corpus):
    place, _ = al.resolve_place(lat=40.7128, lon=-74.006)
    loc, reloc = al.build_locate(acg, natal, place)
    pay, _ = _run(natal, loc, acg_corpus, main_corpus, relocated=reloc)
    rpts = {p["name"]: p for p in reloc["points"]}
    line_bodies = {f[5:].split("|")[0] for f in pay["selection"]["lines"] for f in [f"line:{f}"]}
    house_bodies = set()
    for b in pay["bundles"]:
        if not b["factor"].startswith("house:"):
            continue
        body = b["factor"][6:].split("|")[0]
        house_bodies.add(body)
        for r in b["records"]:
            about = r["about"]
            assert rpts[about["point"]]["sector"]["placidus"] == about["house"]      # GA5
    assert house_bodies and not (house_bodies & line_bodies)                          # GA6
    assert len(house_bodies) <= 5


def test_ga7_method_table(natal, acg_corpus, main_corpus):
    def methods(pay):
        return {r["principle_id"] for b in pay["bundles"] if b["factor"] == "method"
                for r in b["records"]}
    always = set(ga.METHOD_ALWAYS)
    m = methods(_run(natal, _locate(FIVE), acg_corpus, main_corpus)[0])
    assert m == always | {"acg-method-orb-distance"}
    m = methods(_run(natal, _locate(WIDE_ONLY), acg_corpus, main_corpus)[0])
    assert m == always | {"acg-method-orb-distance"}
    m = methods(_run(natal, _locate(NOTHING), acg_corpus, main_corpus)[0])
    assert m == always | {"acg-method-no-influence"}
    diff = [{"body": "saturn", "natal_house": 3, "relocated_house": 10, "angular_after": True}]
    reloc = copy.deepcopy(natal)
    for p in reloc["points"]:
        if p["name"] == "Saturn":
            p["sector"]["placidus"] = 10
    m = methods(_run(natal, _locate(NOTHING, diff), acg_corpus, main_corpus, relocated=reloc)[0])
    assert "acg-method-relocated-chart" in m


def test_ga8_ga9_scopes_and_ids(natal, acg_corpus, main_corpus):
    ids = {r["principle_id"] for r in acg_corpus} | {r["principle_id"] for r in main_corpus}
    pay, _ = _run(natal, _locate(FIVE), acg_corpus, main_corpus, relocated=natal)
    for b in pay["bundles"]:
        for r in b["records"]:
            assert r["principle_id"] in ids
            if r.get("domain") == "astrocartography":
                assert r["acg_scope"] in ga.V1_SCOPES


def test_ga10_other_grounding_untouched(natal, main_corpus):
    res = ground(main_corpus, natal, reading="natal", house_policy="placidus")
    assert not any(r["principle_id"].startswith("acg-") for r in res.kept)
    assert not any(r["principle_id"].startswith("acg-") for r in main_corpus)
    digest = ga.sha256_file(ga.MAIN_CORPUS_PATH)
    side = ga.MAIN_CORPUS_PATH + ".sha256"
    if os.path.exists(side):
        with open(side, encoding="utf-8") as fh:
            assert fh.read().split()[0] == digest


def test_ga11_determinism(natal, acg_corpus, main_corpus):
    a = json.dumps(_run(natal, _locate(FIVE), acg_corpus, main_corpus, relocated=natal),
                   ensure_ascii=False, sort_keys=True)
    b = json.dumps(_run(natal, _locate(FIVE), acg_corpus, main_corpus, relocated=natal),
                   ensure_ascii=False, sort_keys=True)
    assert a == b


def test_ga12_relocation_absent(natal, acg_corpus, main_corpus):
    pay, _ = _run(natal, _locate([_line("venus", "DSC", 20, "tight")], reloc_status="absent"),
                  acg_corpus, main_corpus, relocated=None)
    assert pay["status"] == "ok"
    assert any(b["factor"].startswith("line:") for b in pay["bundles"])
    assert not any(b["factor"].startswith("house:") for b in pay["bundles"])
    assert "relocation_absent:placidus_undefined_high_latitude" in pay["gaps"]


def test_absence_paths(natal, main_corpus):
    loc = _locate(FIVE)
    pay, _ = ga.ground_acg(natal, None, loc, None, main_corpus)
    assert pay["status"] == "absent" and pay["absence"]["reason"] == "acg_corpus_missing"
    loc = dict(loc, status="absent", absence={"reason": "birth_time_not_exact", "detail": None})
    pay, _ = ga.ground_acg(natal, None, loc, [], main_corpus)
    assert pay["absence"]["reason"] == "birth_time_not_exact"


def test_lines_display(natal, acg_corpus, main_corpus):
    lines = [_line("venus", "DSC", 4.2, "tight"), _line("mars", "MC", 86.0, "tight"),
             _line("north_node", "ASC", 90.0, "tight", read=False),
             _line("saturn", "DSC", 704.9, "wide")]
    pay, _ = _run(natal, _locate(lines), acg_corpus, main_corpus)
    disp = pay["lines_display"]
    assert [d["body"] for d in disp] == ["venus", "mars", "saturn"]            # no nodes
    assert [d["distance_km_rounded"] for d in disp] == ["<10", 90, 700]
    assert [d["read_in_prose"] for d in disp] == [True, True, False]
    assert disp[0]["angle_label_tr"] == "Alçalan çizgi" and disp[1]["tier_label_en"] == "Very close"


def test_goal_block(natal, acg, acg_corpus, main_corpus):
    import acg_goals
    if not os.path.exists(acg_goals.AFFINITY_PATH):
        pytest.skip("affinity table not built yet")
    aff = acg_goals.load_affinity()
    place, _ = al.resolve_place(lat=40.7128, lon=-74.006)
    loc, reloc = al.build_locate(acg, natal, place)
    pay, _ = ga.ground_acg(natal, reloc, loc, acg_corpus, main_corpus, acg=acg, affinity=aff)
    gc = pay["goal_contributors"]
    assert list(gc) == list(acg_goals.GOAL_ORDER)
    loaded = ({r["principle_id"] for b in pay["bundles"] for r in b["records"]}
              | {r["principle_id"] for r in pay["goal_records"]})
    for goal, blk in gc.items():
        assert set(blk["contributors"]) <= loaded
        assert blk["band"] in acg_goals.BANDS
