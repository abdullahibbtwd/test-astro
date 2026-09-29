"""
test_acg_affinity.py — the goal-affinity table (ACG/ACG_08_GOAL_SCORING_SPEC.md §2, §7 S1).

    python -m pytest -q Astrocartography/test_acg_affinity.py
"""
from __future__ import annotations

import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import build_affinity as ba  # noqa: E402
from acg_constants import AFFINITY_LOW_EVIDENCE, ANGLES, GOAL_ORDER  # noqa: E402

needs_table = pytest.mark.skipif(not os.path.exists(ba.OUT) or not os.path.exists(ba.CORPUS),
                                 reason="affinity table / corpus not built")


def _line(pid, planet, angle, cit, ge):
    return {"principle_id": pid, "acg_scope": "line", "citation_count": cit, "goal_effects": ge,
            "about": {"factor_type": "planet_on_angle", "planet": planet, "angle": angle}}


def _general(pid, planet, cit, ge):
    return {"principle_id": pid, "acg_scope": "planet_general", "citation_count": cit,
            "goal_effects": ge, "about": {"factor_type": "acg_planet_general", "planet": planet}}


# --- S1 --------------------------------------------------------------------------

def test_s1_five_supportive_citations():
    corpus = [_line("acg-venus-dsc-01", "Venus", "DSC", 3, {"love": "supportive"}),
              _line("acg-venus-dsc-02", "Venus", "DSC", 2, {"love": "supportive"}),
              _line("acg-venus-dsc-03", "Venus", "DSC", 4, {"career": "challenging"})]
    cell = ba.build(corpus, "x")["cells"]["venus|DSC"]["love"]
    assert abs(cell["A"] - 5 / 7) < 1e-9
    assert abs(cell["A"] - 0.714285714) < 1e-9
    assert (cell["s"], cell["c"], cell["m"], cell["volume"]) == (5.0, 0.0, 0.0, 5.0)
    assert cell["low_evidence"] is False
    assert cell["contributors"] == ["acg-venus-dsc-01", "acg-venus-dsc-02"]


def test_formula_weights_mixed_and_general():
    corpus = [_line("acg-saturn-mc-01", "Saturn", "MC", 0, {"career": "mixed"}),     # cit -> 1
              _line("acg-saturn-mc-02", "Saturn", "MC", 2, {"career": "challenging"}),
              _general("acg-general-saturn-01", "Saturn", 4, {"career": "supportive"}),
              {"principle_id": "acg-angle-mc", "acg_scope": "angle_frame", "citation_count": 9,
               "goal_effects": {"career": "supportive"},
               "about": {"factor_type": "acg_angle_frame", "angle": "MC"}}]          # A3: excluded
    doc = ba.build(corpus, "x")
    cell = doc["cells"]["saturn|MC"]["career"]
    s, c, m = 0.5 * 4, 2.0, 1.0
    sp, cp = s + m / 2, c + m / 2
    want = (sp - cp) / (sp + cp + 2.0) * min(1.0, (sp + cp) / 5.0)
    assert (cell["s"], cell["c"], cell["m"]) == (s, c, m)
    assert abs(cell["A"] - want) < 1e-9
    assert "acg-angle-mc" not in cell["contributors"]
    # planet_general reaches every angle of its planet, and no other planet
    assert doc["cells"]["saturn|IC"]["career"]["contributors"] == ["acg-general-saturn-01"]
    assert doc["cells"]["venus|MC"]["career"]["contributors"] == []
    assert doc["cells"]["venus|MC"]["career"]["A"] == 0.0


def test_low_evidence_threshold_synthetic():
    corpus = [_line("acg-mars-asc-01", "Mars", "ASC", 1, {"rest": "challenging"}),
              _line("acg-mars-asc-02", "Mars", "ASC", 1, {"love": "challenging"}),
              _line("acg-mars-asc-03", "Mars", "ASC", 1, {"love": "mixed"})]
    cells = ba.build(corpus, "x")["cells"]["mars|ASC"]
    assert cells["rest"]["volume"] == 1.0 and cells["rest"]["low_evidence"] is True
    assert cells["love"]["volume"] == 2.0 and cells["love"]["low_evidence"] is False


# --- the real table ------------------------------------------------------------------

@pytest.fixture(scope="module")
def table() -> dict:
    return json.load(open(ba.OUT, encoding="utf-8"))


@pytest.fixture(scope="module")
def corpus() -> list[dict]:
    return json.load(open(ba.CORPUS, encoding="utf-8"))


@needs_table
def test_table_shape_and_range(table):
    assert table["schema_version"] == "acg-affinity-1"
    assert table["corpus_sha256"] == ba.file_sha256(ba.CORPUS)
    assert set(table["cells"]) == {f"{p}|{a}" for p in ba.PLANETS for a in ANGLES}
    assert len(table["cells"]) == 40
    for cell in table["cells"].values():
        assert list(cell) == sorted(GOAL_ORDER)
        for v in cell.values():
            assert -1.0 <= v["A"] <= 1.0


@needs_table
def test_contributors_are_matching_corpus_records(table, corpus):
    by_id = {r["principle_id"]: r for r in corpus}
    for key, cell in table["cells"].items():
        p, a = key.split("|")
        for g, v in cell.items():
            assert v["contributors"] == sorted(set(v["contributors"]))
            for rid in v["contributors"]:
                r = by_id[rid]
                about = r["about"]
                assert about["planet"].lower() == p
                if r["acg_scope"] == "line":
                    assert about["factor_type"] == "planet_on_angle" and about["angle"] == a
                else:
                    assert r["acg_scope"] == "planet_general"
                    assert about["factor_type"] == "acg_planet_general"
                assert g in r["goal_effects"]


@needs_table
def test_low_evidence_flag(table):
    for cell in table["cells"].values():
        for v in cell.values():
            assert v["low_evidence"] is (v["volume"] < AFFINITY_LOW_EVIDENCE)
            assert v["volume"] == pytest.approx(v["s"] + v["c"] + v["m"], abs=1e-9)


@needs_table
def test_table_matches_a_fresh_build_and_is_deterministic(table, corpus):
    sha = ba.file_sha256(ba.CORPUS)
    one, two = ba.dumps(ba.build(corpus, sha)), ba.dumps(ba.build(corpus, sha))
    assert one == two
    assert one == open(ba.OUT, encoding="utf-8").read()
    if not os.path.exists(ba.OUT + ".sha256"):      # local build artifact, not tracked in git
        pytest.skip("no local .sha256 sidecar (not tracked in git)")
    side = open(ba.OUT + ".sha256", encoding="utf-8").readline().split()
    import hashlib
    assert side == [hashlib.sha256(open(ba.OUT, "rb").read()).hexdigest(),
                    "acg_goal_affinity.json"]


def test_build_is_byte_identical_on_synthetic_corpus():
    corpus = [_line("acg-venus-dsc-01", "Venus", "DSC", 3, {"love": "supportive"}),
              _general("acg-general-venus-01", "Venus", 2, {"creativity": "mixed"})]
    assert ba.dumps(ba.build(corpus, "x")) == ba.dumps(ba.build(list(reversed(corpus)), "x"))


# --- parans (spec 10 §6) -----------------------------------------------------------

def _paran(pid, p1, p2, cit, ge):
    return {"principle_id": pid, "acg_scope": "paran", "citation_count": cit, "goal_effects": ge,
            "about": {"factor_type": "acg_paran", "planets": sorted([p1, p2])}}


def _fallback_want(cells, pair, g):
    p1, p2 = pair.split("-")
    mean = lambda p: sum(cells[f"{p}|{a}"][g]["A"] for a in ANGLES) / 4  # noqa: E731
    return 0.5 * (mean(p1) + mean(p2))


def test_pairs_are_45_alphabetical():
    assert len(ba.PAIRS) == 45 and len(set(ba.PAIRS)) == 45
    for k in ba.PAIRS:
        a, b = k.split("-")
        assert a < b and a in ba.PLANETS and b in ba.PLANETS
    assert "neptune-sun" in ba.PAIRS


def test_paran_sourced_when_volume_reaches_threshold():
    corpus = [_line("acg-sun-mc-01", "Sun", "MC", 1, {"career": "supportive"}),
              _paran("acg-paran-neptune-sun-01", "Sun", "Neptune", 1, {"spirituality": "supportive"}),
              _paran("acg-paran-neptune-sun-02", "Neptune", "Sun", 0, {"spirituality": "mixed",
                                                                        "rest": "challenging"}),
              _paran("acg-paran-neptune-sun-03", "Neptune", "Sun", 3, {"spirituality": "challenging"}),
              {"principle_id": "acg-method-crossings", "acg_scope": "paran", "citation_count": 9,
               "goal_effects": {"spirituality": "supportive"},
               "about": {"factor_type": "acg_method", "slug": "crossings"}}]   # not a pair
    doc = ba.build(corpus, "x")
    v = doc["parans"]["neptune-sun"]["spirituality"]
    s, c, m = 1.0, 3.0, 1.0
    sp, cp = s + m / 2, c + m / 2
    want = (sp - cp) / (sp + cp + 2.0) * min(1.0, (sp + cp) / 5.0)
    assert v["source"] == "paran"
    assert (v["s"], v["c"], v["m"], v["volume"]) == (s, c, m, 5.0)
    assert abs(v["A"] - want) < 1e-12
    assert v["low_evidence"] is False
    assert v["contributors"] == ["acg-paran-neptune-sun-01", "acg-paran-neptune-sun-02",
                                 "acg-paran-neptune-sun-03"]
    # volume 1 < 2 -> fallback, but s/c/m/volume still report the thin paran evidence
    r = doc["parans"]["neptune-sun"]["rest"]
    assert r["source"] == "fallback" and r["c"] == 1.0 and r["volume"] == 1.0
    assert r["low_evidence"] is True
    # the fallback of career picks up the sun line cell
    fc = doc["parans"]["neptune-sun"]["career"]
    assert fc["source"] == "fallback" and fc["contributors"] == ["acg-sun-mc-01"]
    assert abs(fc["A"] - _fallback_want(doc["cells"], "neptune-sun", "career")) < 1e-12
    assert fc["A"] > 0
    # the method record never enters any pair
    assert all("acg-method-crossings" not in v["contributors"]
               for blk in doc["parans"].values() for v in blk.values())


def test_paran_records_do_not_change_cells():
    base = [_line("acg-venus-dsc-01", "Venus", "DSC", 3, {"love": "supportive"}),
            _general("acg-general-pluto-01", "Pluto", 2, {"rest": "challenging"})]
    extra = [_paran("acg-paran-pluto-venus-01", "Pluto", "Venus", 2, {"love": "mixed"}),
             _paran("acg-paran-pluto-venus-02", "Pluto", "Venus", 2, {"love": "challenging"})]
    one, two = ba.build(base, "x"), ba.build(base + extra, "x")
    assert ba.dumps(one["cells"]) == ba.dumps(two["cells"])
    assert one["parans"]["pluto-venus"]["love"]["source"] == "fallback"
    assert two["parans"]["pluto-venus"]["love"]["source"] == "paran"


def test_parans_build_is_order_independent():
    corpus = [_line("acg-venus-dsc-01", "Venus", "DSC", 3, {"love": "supportive"}),
              _paran("acg-paran-moon-venus-01", "Moon", "Venus", 1, {"love": "supportive"}),
              _paran("acg-paran-moon-venus-02", "Moon", "Venus", 1, {"love": "supportive"})]
    assert ba.dumps(ba.build(corpus, "x")) == ba.dumps(ba.build(list(reversed(corpus)), "x"))


@needs_table
def test_table_parans_shape(table):
    par = table["parans"]
    assert list(par) == sorted(par) and set(par) == set(ba.PAIRS) and len(par) == 45
    for blk in par.values():
        assert list(blk) == sorted(GOAL_ORDER) and len(blk) == 11
        for v in blk.values():
            assert set(v) == {"A", "s", "c", "m", "volume", "low_evidence", "source",
                              "contributors"}
            assert -1.0 <= v["A"] <= 1.0
            assert v["source"] in ("paran", "fallback")
            assert (v["source"] == "paran") is (v["volume"] >= ba.PARAN_MIN_VOLUME)
            assert v["low_evidence"] is (v["volume"] < AFFINITY_LOW_EVIDENCE)
            assert v["contributors"] == sorted(set(v["contributors"]))


@needs_table
def test_table_parans_fallback_formula_exact(table):
    cells, par = table["cells"], table["parans"]
    checked = 0
    for pair in ("neptune-sun", "jupiter-venus", "mars-saturn", "mercury-pluto", "moon-uranus"):
        for g in GOAL_ORDER:
            v = par[pair][g]
            if v["source"] != "fallback":
                continue
            assert abs(v["A"] - _fallback_want(cells, pair, g)) < 1e-12, (pair, g)
            p1, p2 = pair.split("-")
            want = sorted({c for p in (p1, p2) for a in ANGLES
                           for c in cells[f"{p}|{a}"][g]["contributors"]})
            assert v["contributors"] == want
            checked += 1
    assert checked >= 40


@needs_table
def test_table_parans_contributors_in_corpus(table, corpus):
    by_id = {r["principle_id"]: r for r in corpus}
    for pair, blk in table["parans"].items():
        p1, p2 = pair.split("-")
        for g, v in blk.items():
            for rid in v["contributors"]:
                r = by_id[rid]
                assert g in r["goal_effects"]
                if v["source"] == "paran":
                    assert r["acg_scope"] == "paran" and ba.paran_pair(r) == pair
                else:
                    assert r["acg_scope"] in ("line", "planet_general")
                    assert r["about"]["planet"].lower() in (p1, p2)


@needs_table
def test_table_parans_sourced_entries_match_formula(table, corpus):
    for pair, blk in table["parans"].items():
        recs = [r for r in corpus if ba.paran_pair(r) == pair]
        for g, v in blk.items():
            acc = {"supportive": 0.0, "challenging": 0.0, "mixed": 0.0}
            for r in recs:
                pol = r["goal_effects"].get(g)
                if pol:
                    acc[pol] += max(1, int(r.get("citation_count") or 0))
            assert (v["s"], v["c"], v["m"]) == (acc["supportive"], acc["challenging"],
                                                acc["mixed"])
            if v["source"] == "paran":
                sp, cp = v["s"] + v["m"] / 2, v["c"] + v["m"] / 2
                want = (sp - cp) / (sp + cp + 2.0) * min(1.0, (sp + cp) / 5.0)
                assert abs(v["A"] - want) < 1e-12


@needs_table
def test_table_cells_unchanged_by_parans(table, corpus):
    """Regression: the line cells equal a build over the corpus with every paran record
    removed (the line affinity does not depend on parans)."""
    no_par = [r for r in corpus if r.get("acg_scope") != "paran"]
    assert ba.dumps(ba.build(no_par, "x")["cells"]) == ba.dumps(table["cells"])
