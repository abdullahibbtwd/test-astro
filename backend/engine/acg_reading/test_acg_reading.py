#!/usr/bin/env python3
"""test_acg_reading.py — ACG spec 04 §8 (AR1–AR5), the validator (AV1–AV12, one
positive + one negative case each), change order 07 §9 (V3-1 … V3-5) and the
orchestrator checks of spec 05 §6 (O1–O5). No model calls anywhere: llm_client is
patched to raise.

    python -m pytest -q acg_reading/test_acg_reading.py
"""

from __future__ import annotations

import copy
import json
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, _ROOT, os.path.join(_ROOT, "d_layer"), os.path.join(_ROOT, "Astrocartography"),
           os.path.join(_ROOT, "principles_grounding"), os.path.join(_ROOT, "Interpretation_layer")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from compute_chart import BirthData, compute_chart  # noqa: E402

import acg_goals as ag  # noqa: E402
import acg_locate as al  # noqa: E402
import compute_acg as ca  # noqa: E402
import ground_acg as ga  # noqa: E402
import ar_generate  # noqa: E402
import ar_render  # noqa: E402
import ar_routing  # noqa: E402
import ar_validate as V  # noqa: E402
from ar_sections import BANDS, CARD_ORDER, NO_EMPHASIS_ID  # noqa: E402

BD = BirthData(year=1985, month=3, day=14, hour=11, minute=30,
               latitude=41.0082, longitude=28.9784, time_precision="exact")
BIRTH = {"year": 1985, "month": 3, "day": 14, "hour": 11, "minute": 30,
         "latitude": 41.0082, "longitude": 28.9784, "time_precision": "exact"}


@pytest.fixture(autouse=True)
def no_model_calls(monkeypatch):
    import llm_client

    def boom(*_a, **_k):
        raise AssertionError("a model call was made")
    monkeypatch.setattr(llm_client, "complete", boom)


@pytest.fixture(scope="module")
def natal():
    return compute_chart(BD)


@pytest.fixture(scope="module")
def acg(natal):
    return ca.compute_acg(natal)


@pytest.fixture(scope="module")
def corpora():
    return ga.load_json(ga.ACG_CORPUS_PATH), ga.load_json(ga.MAIN_CORPUS_PATH)


def _payload(natal, acg, corpora, lat, lon, name="Test"):
    place = {"query": name, "name": name, "name_tr": name, "lat": lat, "lon": lon,
             "country_code": None, "source": "manual"}
    loc, reloc = al.build_locate(acg, natal, place)
    pay, _ = ga.ground_acg(natal, reloc, loc, corpora[0], corpora[1], acg=acg,
                           affinity=ag.load_affinity())
    return pay


@pytest.fixture(scope="module")
def ny(natal, acg, corpora):
    return _payload(natal, acg, corpora, 40.7128, -74.006, "New York")


# ---------------------------------------------------------------------------
# AR1–AR3, AR5, V3-1, V3-2, V3-4
# ---------------------------------------------------------------------------

def test_ar1_routing_deterministic(ny):
    a = json.dumps(ar_routing.build_plan(ny), sort_keys=True, ensure_ascii=False)
    b = json.dumps(ar_routing.build_plan(ny), sort_keys=True, ensure_ascii=False)
    assert a == b


def _lines_order(plan):
    sec = next(s for s in plan["sections"] if s["key"] == "lines_here")
    return [s["slot_id"] for s in sec["slots"]]


def _pool_ids(plan):
    return {r["id"] for s in plan["sections"] for sl in s.get("slots", []) for r in sl["records"]}


def test_v3_4_focus_goal_reorders_never_filters(ny):
    base = ar_routing.build_plan(ny)
    for goal in ag.GOAL_ORDER:
        p = ar_routing.build_plan(ny, focus_goal=goal)
        assert sorted(_lines_order(p)) == sorted(_lines_order(base))
        assert _pool_ids(p) == _pool_ids(base)
        cards = next(s for s in p["sections"] if s["key"] == "suitability")["cards"]
        keys = [c["card"] for c in cards]
        if goal in {c[2] for c in __import__("ar_sections").CARDS.values()}:
            assert len(keys) == 6 and cards[0]["goal"] == goal
        else:
            assert len(keys) == 7 and keys[-1] == goal
        ov = next(s for s in p["sections"] if s["key"] == "place_overview")
        assert ov["focus_goal"]["goal"] == goal


def test_ar3_zero_line_and_wide_only(natal, acg, corpora):
    loc = {"schema_version": "acg-locate-1",
           "place": {"name": "X", "name_tr": "X", "lat": 0.0, "lon": 0.0},
           "status": "ok", "absence": None, "lines_near": [],
           "relocation": {"status": "absent", "absence": {"reason": "x"}, "chart_path": None},
           "house_diff": []}
    pay, _ = ga.ground_acg(natal, None, loc, *corpora)
    plan = ar_routing.build_plan(pay)
    assert "lines_here" not in [s["key"] for s in plan["sections"]]
    ov = plan["sections"][0]
    assert NO_EMPHASIS_ID in {r["id"] for r in ov["slots"][0]["records"]}
    loc["lines_near"] = [{"body": "saturn", "angle": "DSC", "distance_km": 700.0,
                          "tier": "wide", "read_in_v1": True, "nearest_point": [0, 0],
                          "side": "east"}]
    pay, _ = ga.ground_acg(natal, None, loc, *corpora)
    plan = ar_routing.build_plan(pay)
    sec = next(s for s in plan["sections"] if s["key"] == "lines_here")
    assert len(sec["slots"]) == 1 and sec["slots"][0]["wording_tr"] == "hafif ve arka planda"


def test_ar5_dry_run_prompts_no_calls(ny):
    plan = ar_routing.build_plan(ny, focus_goal="career")
    d = ar_generate.dry_run_prompts(plan)
    assert d["model_calls"] == 0 and "place_overview" in d["prompts"]
    for p in d["prompts"].values():
        assert not re.search(r"\b\d+(\.\d+)?\s*km\b", p["user"])       # no distances leak


def test_v3_1_cards_scores_lines(ny):
    plan = ar_routing.build_plan(ny)
    cards = next(s for s in plan["sections"] if s["key"] == "suitability")["cards"]
    assert [c["card"] for c in cards] == list(CARD_ORDER)
    assert list(plan["goal_scores"]) == list(ag.GOAL_ORDER)
    disp = plan["lines_display"]
    assert disp and all(d["body"] != "north_node" for d in disp)
    dists = [(0 if d["distance_km_rounded"] == "<10" else d["distance_km_rounded"])
             for d in disp]
    assert dists == sorted(dists)
    assert all(d == "<10" or d % 10 == 0 for d in (x["distance_km_rounded"] for x in disp))


def test_v3_2_no_emphasis_cards_make_no_calls(ny):
    pay = copy.deepcopy(ny)
    for blk in pay["goal_contributors"].values():
        blk["band"] = "no_emphasis"
    plan = ar_routing.build_plan(pay)
    assert "suitability" not in ar_generate.draft_prompts(plan)
    cards = next(s for s in plan["sections"] if s["key"] == "suitability")["cards"]
    outs = [ar_generate._card_output(c, {}, {}) for c in cards]      # no generator involved
    for o in outs:
        assert o["template"] and o["trace"] == [NO_EMPHASIS_ID]
        assert o["text_tr"].startswith(BANDS["no_emphasis"][0])


# ---------------------------------------------------------------------------
# AR4: validator — one positive and one negative case per rule
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,lang,rule", [
    ("Bu çizgi 120 km uzakta.", "tr", "AV1"),
    ("The line is 3° away.", "en", "AV1"),
    ("MC çizginiz burada.", "tr", "AV1"),
    ("Venüs 10. ev temalarını öne çıkarır.", "tr", "AV1"),
    ("Buraya kesinlikle taşınmalısınız.", "tr", "AV2"),
    ("You should move here.", "en", "AV2"),
    ("Burada ölüm teması var.", "tr", "AV8"),
    ("An accident may happen.", "en", "AV8"),
    ("Evet, burası uygun değil.", "tr", "AV10"),
    ("Yes, it is not suitable.", "en", "AV10"),
    ("A classical reading says so.", "en", "forbidden"),
    ("İlişkiler bi%cimde öne çıkar.", "tr", "ENC"),
    ("Neptün iliřkilerde belirir.", "tr", "ENC"),
])
def test_ar4_text_rules_negative(text, lang, rule):
    probs = V.text_problems(text, lang)
    assert any(p.startswith(rule) for p in probs), probs


@pytest.mark.parametrize("text,lang", [
    ("Venüs burada ilişkilerde belirgin biçimde uyum getirir.", "tr"),
    ("Venus brings noticeable harmony to relationships here.", "en"),
    ("Bölüm bölüm açılan yeni bir hayırlı dönem.", "tr"),      # 'bölüm' and 'hayırlı' are fine
    ("Ay bu alanda duygusal derinlik katar.", "tr"),
])
def test_ar4_text_rules_positive(text, lang):
    assert V.text_problems(text, lang) == []


def _mini(plan, sentences_by_key, cards=None):
    tr = {}
    for sec in plan["sections"]:
        if sec["key"] == "suitability":
            continue
        tr[sec["key"]] = {sl["slot_id"]: {"unit_id": sl["slot_id"],
                                          "sentences": sentences_by_key(sec, sl)}
                          for sl in sec["slots"]}
    return {"tr": tr, "en": copy.deepcopy(tr), "cards": cards or []}


def _valid_sentences(plan):
    place = plan["place"]["name_tr"]

    def make(sec, sl):
        recs = sl["records"]
        planet = sl.get("planet_tr")
        n_words = {"place_overview": 100, "lines_here": 50, "positives": 90,
                   "challenges": 80, "life_areas_here": 90}[sec["key"]]
        out = []
        for i, r in enumerate((recs * 20)[: max(1, n_words // 10)]):
            if sec["key"] in ("positives", "challenges"):
                pol_ok = ("supportive", "mixed") if sec["key"] == "positives" else \
                    ("challenging", "mixed")
                r = next((x for x in recs if x.get("polarity") in pol_ok), r)
            words = "bu alanda sakin ve dengeli bir tema belirir gibi durur".split()
            head = (f"{place} " if sec["key"] == "place_overview" and i == 0 else "")
            head += (f"{planet} " if planet and i == 0 else "")
            out.append({"text": head + " ".join(words) + ".", "ids": [r["id"]]})
        return out
    return make


def test_ar4_validator_full_positive_and_negatives(ny):
    plan = ar_routing.build_plan(ny)
    pools = ar_generate.unit_pools(plan)
    pol = ar_generate.polarity_map(plan)
    allowed = ar_routing.traced_ids(plan)
    good = _mini(plan, _valid_sentences(plan))
    errs = V.validate(good, plan, pools, pol, allowed)
    # EN copies are Turkish text: only the EN planet coverage / place checks can fire
    assert not [e for e in errs if "[tr]" in e and not e.startswith("AV3")], errs

    bad = copy.deepcopy(good)                                    # AV4 unknown id
    uid = next(iter(bad["tr"]["lines_here"]))
    bad["tr"]["lines_here"][uid]["sentences"][0]["ids"] = ["acg-nonexistent-99"]
    assert any(e.startswith("AV4") for e in V.validate(bad, plan, pools, pol, allowed))

    bad = copy.deepcopy(good)                                    # AV5 overview misses place
    for u in bad["tr"]["place_overview"].values():
        for s in u["sentences"]:
            s["text"] = s["text"].replace(plan["place"]["name_tr"], "Orası")
    assert any(e.startswith("AV5 [tr]") for e in V.validate(bad, plan, pools, pol, allowed))

    bad = copy.deepcopy(good)                                    # AV6 too short
    uid = next(iter(bad["tr"]["lines_here"]))
    bad["tr"]["lines_here"][uid]["sentences"] = bad["tr"]["lines_here"][uid]["sentences"][:1]
    assert any(e.startswith("AV6") for e in V.validate(bad, plan, pools, pol, allowed))

    bad = copy.deepcopy(good)                                    # AV7 empty section
    bad["tr"]["positives"] = {}
    assert any(e.startswith("AV7") for e in V.validate(bad, plan, pools, pol, allowed))

    if "challenges" in bad["tr"]:                                # AV11 wrong polarity
        bad = copy.deepcopy(good)
        sup = next(i for i, p in pol.items() if p == "supportive")
        u = next(iter(bad["tr"]["challenges"].values()))
        u["sentences"][0]["ids"] = [sup]
        assert any(e.startswith("AV11") for e in V.validate(bad, plan, pools, pol, allowed))

    bad = copy.deepcopy(good)                                    # AV3 / AV12 wrong planet
    u = next(iter(bad["tr"]["positives"].values()))
    u["sentences"][0]["text"] += " Plüton da burada."
    assert any(e.startswith("AV12") for e in V.validate(bad, plan, pools, pol, allowed)) \
        or "pluto" in plan["line_bodies"]
    u = next(iter(bad["tr"]["lines_here"].values()))
    u["sentences"][0]["text"] += " Plüton da burada."
    assert any(e.startswith("AV3") for e in V.validate(bad, plan, pools, pol, allowed)) \
        or "pluto" in plan["line_bodies"]


def test_av9_card_label_and_trace(ny):
    plan = ar_routing.build_plan(ny)
    pools, pol = ar_generate.unit_pools(plan), ar_generate.polarity_map(plan)
    allowed = ar_routing.traced_ids(plan)
    good = _mini(plan, _valid_sentences(plan))
    card = {"card": "love", "goal": "love", "band": "supportive", "contributors": ["x-1"],
            "template": True, "trace": ["x-1"],
            "text_tr": "Destekleyici. Bu alanda sıcak bağlar kurulabilir.",
            "text_en": "Supportive. Warm bonds may form here."}
    errs = V.validate({**good, "cards": [card]}, plan, pools, pol, allowed)
    assert not [e for e in errs if "AV9" in e]
    bad = dict(card, text_tr="Uygun. Bu alanda sıcak bağlar.")               # wrong label
    assert any("AV9" in e for e in V.validate({**good, "cards": [bad]}, plan, pools, pol, allowed))
    bad = dict(card, trace=["acg-other-1"])                                  # outside contributors
    assert any("AV9" in e for e in V.validate({**good, "cards": [bad]}, plan, pools, pol, allowed))


def test_render_shapes(ny):
    plan = ar_routing.build_plan(ny)
    reading = _mini(plan, _valid_sentences(plan),
                    cards=[ar_generate._card_output(dict(c, band="no_emphasis"), {}, {})
                           for c in next(s for s in plan["sections"]
                                         if s["key"] == "suitability")["cards"]])
    tr = ar_render.reading_json(reading, plan, "tr")
    assert tr["footer"].startswith("Bu okuma sembolik")
    keys = [s["key"] for s in tr["sections"]]
    assert keys[0] == "place_overview" and keys[-1] == "suitability"
    assert all(s.get("text") or s.get("cards") for s in tr["sections"])       # AV7
    md = ar_render.reading_markdown(tr, ar_render.reading_json(reading, plan, "en"))
    assert "# New York" in md


# ---------------------------------------------------------------------------
# V3-3: country view picks cities inside the country
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def scan(acg):
    import acg_geodata as geo
    return ag.goal_scan(acg, ag.load_affinity(), geo.load_cities(), geo.load_grid())


@pytest.mark.parametrize("iso", ["TR", "DE"])
def test_v3_3_country_best_cities_inside(acg, scan, iso):
    import acg_geodata as geo
    import acg_recommend as rec
    view = rec.area_view("country", iso, acg, scan, ag.load_affinity())
    assert view["status"] == "ok"
    ids = {c["id"] for c in geo.cities_in(iso_a2=iso)}
    for goal, rows in view["best_cities"].items():
        assert rows and len(rows) <= 3
        assert {r["id"] for r in rows} <= ids
    assert set(view["bands"]) == set(ag.GOAL_ORDER)


# ---------------------------------------------------------------------------
# Orchestrator: O1–O5, V3-5
# ---------------------------------------------------------------------------

@pytest.fixture()
def dirs(tmp_path):
    return str(tmp_path / "runs"), str(tmp_path / "cache")


def _run(request, dirs, **kw):
    import run_acg
    return run_acg.run_acg(request, runs_dir=dirs[0], cache_root=dirs[1], **kw)


def test_o1_map_mode_no_calls(dirs):
    m = _run({"birth": BIRTH}, dirs)
    assert m["mode"] == "map" and m["status"] == "ok"
    names = set(m["artifacts"])
    assert any(n.startswith("acg_") and n.endswith(".json") for n in names)
    assert any(n.startswith("goal_scan") for n in names)
    assert sum(n.startswith("goal_heat_") for n in names) == 11
    assert not any(n.startswith(("locate", "reading")) for n in names)


def test_o2_city_dry_run(dirs):
    m = _run({"birth": BIRTH, "city": "İzmir"}, dirs, dry_run=True)
    assert m["status"] == "ok"
    names = set(m["artifacts"])
    assert any(n.startswith("dry_run_prompts") for n in names)
    assert not any(n.startswith("reading_") for n in names)


def test_o3_approximate_time_absent(dirs):
    m = _run({"birth": dict(BIRTH, time_precision="approximate", approx_bucket="morning"), "city": "İzmir"},
             dirs, dry_run=True)
    assert m["status"] == "absent"
    skipped = [s for s in m["stages"] if s["status"].startswith("skipped:birth_time_not_exact")]
    assert {s["name"] for s in skipped} >= {"locate", "relocate", "ground_acg", "reading"}


def test_o4_high_latitude(dirs):
    m = _run({"birth": BIRTH, "lat": 70.0, "lon": 25.0}, dirs, dry_run=True)
    assert m["stage_status"]["relocate"] == "absent:placidus_undefined_high_latitude"
    assert m["stage_status"]["reading"] == "dry_run"
    assert any(g.startswith("relocation_absent") for g in m["gaps"])


def test_o5_folder_pattern_and_gitignore(dirs):
    m = _run({"birth": BIRTH}, dirs)
    assert re.fullmatch(r"\d{8}-\d{6}_[a-z0-9]{3}", os.path.basename(m["run_dir"]))
    # Engines live under backend/engine/; acg_run/ is ignored at the repo root.
    repo = os.path.dirname(os.path.dirname(_ROOT))
    with open(os.path.join(repo, ".gitignore"), encoding="utf-8") as fh:
        assert "acg_run/" in fh.read().split()


def test_v3_5_cache_hit(dirs):
    _run({"birth": BIRTH}, dirs)
    m = _run({"birth": BIRTH}, dirs)
    hits = {s["name"]: s["cache_hit"] for s in m["stages"] if s["cache_hit"] is not None}
    assert hits.get("compute_acg") and hits.get("city_scan") and hits.get("goal_scan")
