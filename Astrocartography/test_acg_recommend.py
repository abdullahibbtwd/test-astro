#!/usr/bin/env python3
"""test_acg_recommend.py — ACG spec 09 §6 (W1–W8).

W6 (free-text classification) needs the live cheap model: it runs only with
ACG_LIVE=1. Everything else makes zero model calls.

    python -m pytest -q Astrocartography/test_acg_recommend.py
    ACG_LIVE=1 python -m pytest -q Astrocartography/test_acg_recommend.py -k w6
"""

from __future__ import annotations

import copy
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, _ROOT, os.path.join(_ROOT, "d_layer"), os.path.join(_ROOT, "acg_reading"),
           os.path.join(_ROOT, "principles_grounding"),
           os.path.join(_ROOT, "Interpretation_layer")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from compute_chart import BirthData, compute_chart  # noqa: E402

import acg_geodata as geo  # noqa: E402
import acg_goals as ag  # noqa: E402
import acg_recommend as rec  # noqa: E402
import compute_acg as ca  # noqa: E402
from acg_geo import gc_distance_km  # noqa: E402

BD = BirthData(year=1985, month=3, day=14, hour=11, minute=30,
               latitude=41.0082, longitude=28.9784, time_precision="exact")


@pytest.fixture(scope="module", autouse=True)
def lines_only_context():
    """These v3 tests score lines only: pin the recommender's paran context (another
    module may have set it) so the scan and the honesty fields agree."""
    rec.set_parans(None)
    yield
    rec.set_parans(None)


@pytest.fixture(scope="module")
def natal():
    return compute_chart(BD)


@pytest.fixture(scope="module")
def acg(natal):
    return ca.compute_acg(natal)


@pytest.fixture(scope="module")
def aff():
    return ag.load_affinity()


@pytest.fixture(scope="module")
def scan(acg, aff):
    return ag.goal_scan(acg, aff, geo.load_cities(), geo.load_grid())


@pytest.fixture(scope="module")
def zero_aff(aff):
    z = copy.deepcopy(aff)
    for cell in z["cells"].values():
        for g in cell.values():
            g["A"] = 0.0
    return z


@pytest.fixture(scope="module")
def zero_scan(acg, zero_aff):
    return ag.goal_scan(acg, zero_aff, geo.load_cities(), geo.load_grid())


@pytest.fixture(scope="module")
def career(acg, scan, aff):
    return rec.rank("career", "world", acg, scan, aff)


def test_w1_deterministic(acg, scan, aff, career):
    again = rec.rank("career", "world", acg, scan, aff)
    assert json.dumps(again, sort_keys=True) == json.dumps(career, sort_keys=True)


def test_w2_diversity(career):
    cities = career["cities"]
    assert 0 < len(cities) <= 10
    lines = [rec.line_key_of(c["dominant_line"]) for c in cities]
    assert max(lines.count(x) for x in lines) <= 2
    countries = [c["country"] for c in cities]
    assert max(countries.count(x) for x in countries) <= 3
    for i, a in enumerate(cities):
        for b in cities[i + 1:]:
            assert gc_distance_km(a["lon"], a["lat"], b["lon"], b["lat"]) >= 150.0
    assert [c["S"] for c in cities] == sorted((c["S"] for c in cities), reverse=True)
    assert len(career["regions"]) <= 5 and len(career["countries"]) <= 5
    rl = [rec.line_key_of(r["dominant_line"]) for r in career["regions"]]
    assert all(rl.count(x) <= 2 for x in rl)


def test_w3_only_eligible_and_thin(acg, zero_scan, zero_aff, career):
    for key in ("cities", "regions", "countries"):
        assert all(i["band"] in rec.ELIGIBLE for i in career[key])
    empty = rec.rank("love", "world", acg, zero_scan, zero_aff)
    assert empty["cities"] == [] and empty["thin_result"] is True
    assert empty["regions"] == [] and empty["countries"] == []


def test_w4_turkey_block_always(acg, zero_scan, zero_aff, career):
    assert "turkey" in career
    assert all(c["country"] == "TR" for c in career["turkey"]["cities"])
    empty = rec.rank("love", "world", acg, zero_scan, zero_aff)
    t = empty["turkey"]
    assert t["none_eligible"] is True and t["cities"] == []
    assert t["best_available"]["country"] == "TR"                 # honest best, band as-is


def test_w5_scope_country(acg, scan, aff):
    r = rec.rank("career", "DE", acg, scan, aff)
    assert all(c["country"] == "DE" for c in r["cities"])
    assert all(x["country"] == "DE" for x in r["regions"])
    assert r["countries"] == [] and "turkey" not in r


def test_honesty_fields(career):
    for c in career["cities"]:
        assert c["has_tradeoff"] == (c["N"] >= 0.25)
        assert all(ln["contribution"] > 0.05 for ln in c["supporting_lines"])
        assert all(ln["contribution"] < -0.05 for ln in c["challenging_lines"])
        assert c["contributors"]


# ---------------------------------------------------------------------------
# W7: RV1–RV4 (one positive + one negative each)
# ---------------------------------------------------------------------------

def _unit(uid="cities:0", kind="city", tradeoff=False, pool=("a-1", "a-2")):
    return {"unit_id": uid, "kind": kind, "has_tradeoff": tradeoff,
            "allowed_planets": ["jupiter"], "must_name": "Berlin",
            "principles": [{"id": i} for i in pool]}


def _text(ids, words=48, lead="Berlin'de Jüpiter"):
    body = " ".join(["bu alanda görünürlük ve mesleki büyüme teması öne çıkar"] * 6).split()
    text = lead + " " + " ".join(body[: words - 2]) + "."
    return {"cities:0": {"unit_id": "cities:0", "sentences": [{"text": text, "ids": ids}]}}


def test_w7_rv_rules():
    import acg_views as vw
    pol = {"a-1": "supportive", "a-2": "challenging"}
    ok = vw.validate_units([_unit()], _text(["a-1"]), _text(["a-1"]), pol)
    assert ok == [], ok
    bad = vw.validate_units([_unit()], _text(["zzz"]), _text(["zzz"]), pol)          # RV1
    assert any(e.startswith("RV1") for e in bad)
    u = _unit(tradeoff=True)
    assert any(e.startswith("RV2") for e in vw.validate_units([u], _text(["a-1"]),
                                                               _text(["a-1"]), pol))
    assert not [e for e in vw.validate_units([u], _text(["a-1", "a-2"]),
                                             _text(["a-1", "a-2"]), pol) if e.startswith("RV2")]
    t = _text(["a-1"])
    t["cities:0"]["sentences"][0]["text"] += " Bu en iyi yer kesinlikle burası."
    assert any("RV4" in e for e in vw.validate_units([_unit()], t, _text(["a-1"]), pol))


def test_rv3_order_is_ranking(career):
    import acg_views as vw
    out = vw.assemble_recommendation(career, {}, {})
    assert [c["id"] for c in out["cities"]] == [c["id"] for c in career["cities"]]
    assert [c["id"] for c in out["regions"]] == [c["id"] for c in career["regions"]]
    for c in out["cities"]:
        assert c["text_tr"].startswith(c["band_label_tr"])


def test_w8_dry_run_no_calls(tmp_path, monkeypatch):
    import llm_client
    import run_acg

    def boom(*_a, **_k):
        raise AssertionError("model call in dry run")
    monkeypatch.setattr(llm_client, "complete", boom)
    birth = {"year": 1985, "month": 3, "day": 14, "hour": 11, "minute": 30,
             "latitude": 41.0082, "longitude": 28.9784, "time_precision": "exact"}
    m = run_acg.run_acg({"birth": birth, "recommend": "career", "scope": "world"},
                        dry_run=True, runs_dir=str(tmp_path / "r"), cache_root=str(tmp_path / "c"))
    assert m["status"] == "ok" and m["stage_status"]["reading"] == "dry_run"
    rec_file = next(a for a in m["artifacts"] if a.startswith("recommend_career_world"))
    with open(os.path.join(m["run_dir"], rec_file), encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["dry_run_units"] and data["cities"]


# ---------------------------------------------------------------------------
# W6: free text -> goal (live model; opt-in)
# ---------------------------------------------------------------------------

PHRASES = {
    "love": ["Aşkı bulmak için nereye gitmeliyim?", "Where could I find love?"],
    "career": ["Kariyer için en iyi yer neresi?", "Where is best for my career?"],
    "business": ["Şirket kurmak için hangi şehir?", "Where should I start a business?"],
    "money": ["Daha çok para kazanabileceğim yer?", "Where can I earn more money?"],
    "family": ["Çocuklarımla aile hayatı için nerede yaşayalım?",
               "Where is good for raising a family?"],
    "education": ["Yüksek lisans için hangi şehre gideyim?", "Where should I go to study?"],
    "creativity": ["Sanatımı geliştirmek için nereye gideyim?",
                   "Where would my creativity flourish?"],
    "spirituality": ["Ruhsal gelişim için bir inziva yeri?",
                     "Where can I grow spiritually?"],
    "rest": ["Dinlenip kafa dinlemek için nereye gideyim?",
             "Where can I rest and recharge?"],
    "travel": ["Tatilde gezmek için nereye gideyim?", "Where should I travel on holiday?"],
    "relocation": ["Kalıcı olarak taşınıp yerleşmek için neresi?",
                   "Where should I settle down permanently?"],
}
OFF_TOPIC = ["Bugün hava nasıl?", "What is 2 plus 2?", "Kedimin adı ne olmalı?",
             "Tell me a joke.", "Satürn kaç yaşında?"]


@pytest.mark.skipif(os.environ.get("ACG_LIVE") != "1", reason="live model test (ACG_LIVE=1)")
def test_w6_free_text_classification():
    import acg_views as vw
    import run_acg
    import argparse
    models = run_acg.resolve_models(argparse.Namespace(model=None, synthesis_model=None,
                                                       translation_model=None))
    gen = run_acg.make_generator(models)
    wrong = []
    for goal, phrases in PHRASES.items():
        for p in phrases:
            r = vw.classify_goal(p, gen)
            if r["goal"] != goal:
                wrong.append((p, goal, r))
    for p in OFF_TOPIC:
        r = vw.classify_goal(p, gen)
        if r["status"] != "needs_goal":
            wrong.append((p, None, r))
    assert not wrong, wrong
