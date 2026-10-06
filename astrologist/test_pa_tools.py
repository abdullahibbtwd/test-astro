"""PA_01 §8 T1-T13 (T10 is in test_pa_cards.py).  Run: python -m pytest astrologist/test_pa_tools.py -q"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import re
from datetime import date, timedelta

import pytest
from jsonschema import Draft202012Validator

import _paths
import pa_tools as T
import subjects as S
from conftest import make_ctx

TODAY = date.fromisoformat(S.FIXTURE_TODAY)
ALL_CALLS = [
    ("chart_facts", {}), ("chart_facts", {"bodies": ["venus", "saturn"], "angles": ["mc"]}),
    ("natal_topics", {"goals": ["love"]}), ("natal_topics", {"topics": ["core_identity", "inner_drives", "identity"]}),
    ("natal_section", {"section_key": "partnerships"}),
    ("day", {"date": "2026-10-12", "lens": "general"}),
    ("span", {"from": "2026-10-05", "to": "2027-01-02", "goal": "love"}),
    ("span", {"from": "2026-11-01", "to": "2026-11-30"}),
    ("best_days", {"activities": ["contract", "project_start"]}),
    ("calendar_item", {"item_id": "tr:saturn:conjunction:sun:2026a"}),
    ("place", {"place_text": "İzmir", "goals": ["career"]}), ("place", {"place_text": "London"}),
    ("recommend", {"goal": "career", "scope": "world"}),
    ("compatibility", {"other": "p1"}), ("compatibility", {"other": "p2"}),
    ("astro_basics", {"kind": "retrograde", "key": "mercury"}), ("astro_basics", {"kind": "life_area", "key": "partnerships"}),
]

PACK_SCHEMA = {
    "type": "object",
    "required": ["call_id", "tool", "args", "forced", "status", "absence", "clamped", "source_kinds", "facts", "records",
                 "items", "prose", "card_candidates", "link_candidates", "needs_input"],
    "properties": {
        "status": {"enum": ["ok", "absent", "out_of_range", "needs_input", "not_ready"]},
        "tool": {"enum": T.TOOLS},
        "source_kinds": {"type": "array", "items": {"enum": ["chart", "natal_reading", "forecast", "calendar", "best_days",
                                                             "acg", "compatibility"]}},
        "facts": {"type": "array", "items": {"type": "object", "required": ["id", "label"], "additionalProperties": False,
                                             "properties": {"id": {"pattern": "^f:"}, "label": {"type": "string"}}}},
        "records": {"type": "array", "items": {"type": "object", "required": ["id", "render", "polarity", "sensitivity"],
                                               "additionalProperties": False,
                                               "properties": {"id": {"pattern": "^r:(natal|forecast|cal|bd|acg|syn|basics):"},
                                                              "render": {"type": "string", "minLength": 1},
                                                              "polarity": {"enum": ["supportive", "challenging", "mixed", None]},
                                                              "sensitivity": {"enum": ["normal", "high", None]}}}},
        "items": {"type": "array", "items": {"type": "object", "required": ["id", "label", "dates", "band", "grade", "band_label"],
                                             "additionalProperties": False, "properties": {"id": {"pattern": "^i:"}, "label": {"type": "string"}, "dates": {"type": "array", "items": {"type": "string", "format": "date"}}, "band": {"type": ["string", "null"]}, "grade": {"type": ["string", "null"]}, "band_label": {"type": ["string", "null"]}}}},
        "prose": {"type": "array", "items": {"type": "object", "required": ["id", "text"], "additionalProperties": False,
                                             "properties": {"id": {"pattern": "^p:"}, "text": {"type": "string"}}}},
        "card_candidates": {"type": "array", "items": {"required": ["id", "card", "desc"], "properties": {"id": {"pattern": "^k:"}}}},
        "link_candidates": {"type": "array", "items": {"required": ["id", "label", "route"], "properties": {"id": {"pattern": "^l:"}}}},
    },
}


@pytest.fixture(scope="module")
def packs(ctx):
    return [T.run_tool(ctx, f"c{i}", tool, args) for i, (tool, args) in enumerate(ALL_CALLS)]


def test_t1_packs_validate(packs):
    v = Draft202012Validator(PACK_SCHEMA)
    for p in packs:
        errs = list(v.iter_errors(p))
        assert not errs, (p["tool"], [e.message for e in errs[:3]])


def test_t2_caps_deterministic(ctx):
    calls = [("natal_topics", {"goals": ["love", "career"]}), ("span", {"from": "2026-10-05", "to": "2027-09-27"}),
             ("best_days", {"activities": ["contract", "love"]}), ("compatibility", {"other": "p1"})]
    a = T.apply_caps([T.run_tool(ctx, f"c{i}", t, x) for i, (t, x) in enumerate(calls)])
    b = T.apply_caps([T.run_tool(ctx, f"c{i}", t, x) for i, (t, x) in enumerate(calls)])
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert sum(len(p["records"]) for p in a) <= 40
    assert sum(len(p["items"]) for p in a) <= 30
    assert sum(len(p["prose"]) for p in a) <= 3
    for p in a:
        if p["records"]:
            assert len(p["records"]) >= 4


def test_t3_time_layers_modern_only(packs):
    import cal_corpus
    _, modern = cal_corpus.load()
    for p in packs:
        if p["tool"] in ("day", "span", "best_days", "calendar_item"):
            for r in p["records"]:
                pid = r["id"].split(":", 2)[2]
                assert pid in modern, r["id"]                    # cal_corpus.load keeps tradition == modern only


_DATE = re.compile(r"\b(?:\d{1,2} )?(Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık|January|"
                   r"February|March|April|May|June|July|August|September|October|November|December) \d{4}\b|\b\d{4}-\d{2}-\d{2}\b")
_HOUSE = re.compile(r"\b\d{1,2}\.\s?ev|\b\d{1,2}(st|nd|rd|th) house", re.IGNORECASE)


def test_t4_no_digits_except_dates(packs):
    for p in packs:
        texts = [f["label"] for f in p["facts"]] + [r["render"] for r in p["records"]] + \
                [i["label"] for i in p["items"]] + [x["text"] for x in p["prose"]] + \
                [lk["label"] for lk in p["link_candidates"]]
        for t in texts:
            assert not _HOUSE.search(t), t
            assert not re.search(r"\d", _DATE.sub("", t)), (p["tool"], t[:120])


def test_t5_horizons(ctx):
    far = (TODAY + timedelta(days=400)).isoformat()
    assert T.run_tool(ctx, "c0", "day", {"date": far})["status"] == "out_of_range"
    bd = (TODAY + timedelta(days=120)).isoformat()
    assert T.run_tool(ctx, "c0", "best_days", {"activities": ["contract"], "from": bd, "to": bd})["status"] == "out_of_range"
    sp = T.run_tool(ctx, "c0", "span", {"from": "2027-08-01", "to": "2028-02-01"})
    assert sp["status"] == "ok" and sp["clamped"]["used"]["to"] < "2028-02-01"


def test_t6_instanbul_never_antwerp(ctx):
    p = T.run_tool(ctx, "c0", "place", {"place_text": "Instanbul"})
    assert p["status"] in ("ok", "needs_input")
    if p["status"] == "ok":
        assert p["_internal"]["place"]["place_id"] == "gn-745044"
        assert "Antwerp" not in json.dumps(p, ensure_ascii=False)
    assert p["resolved_by"] is None                             # the chat never geocodes (Phase 0 G2)
    assert T.search_places("Londra")["place"]["id"] == "gn-2643743"
    assert T.search_places("Qwxzzy")["status"] == "not_found"


def test_t7_recommend_order_equals_ranking(ctx, packs):
    import acg_destinations as dst
    import acg_line_first as lf
    import acg_recommend as rec
    prod = ctx.acg()
    rec.set_parans(prod.get("parans"))
    b = S.SUBJECT["birth"]["place"]
    f = dst.resolve_filters("career", regions=None, city_size=None, max_distance_km=None, home_latlon=(b["lat"], b["lon"]),
                            climate=None, purpose=None)
    rk = lf.rank_line_first("career", "world", prod["acg"], prod["goal_scan"], prod["aff"], f)
    p = next(x for x in packs if x["tool"] == "recommend")
    assert [i["id"] for i in p["items"] if i["id"].startswith("i:rec:")] == [f"i:rec:{c['id']}" for c in rk["cities"][:5]]


def test_t8_compatibility_types_and_unknown(ctx):
    assert set(T.REL_TYPE) >= {"partner", "colleague", "business_partner", "parent", "child", "family", "friend", "other"}
    assert [T.REL_TYPE[r] for r in ("partner", "colleague", "business_partner", "parent", "child", "family", "friend", "other")] == \
        ["love", "work", "work", "family", "family", "family", "general", "general"]
    p = T.run_tool(ctx, "c0", "compatibility", {"other": "p9"})
    assert p["status"] == "needs_input" and p["needs_input"]["kind"] == "person_unknown"


def test_t9_no_model_and_no_reading_stage(pa_cache, monkeypatch):
    import cr_generate
    import llm_client

    def boom(*a, **k):
        raise AssertionError("a tool called a model or started a reading stage")
    monkeypatch.setattr(llm_client, "complete", boom)
    monkeypatch.setattr(cr_generate, "ensure_texts", boom)
    monkeypatch.setattr(cr_generate, "make_generator", boom)
    c = make_ctx("en", pa_cache)
    for i, (tool, args) in enumerate(ALL_CALLS):
        T.run_tool(c, f"c{i}", tool, args)


def test_t11_forced_calls(ctx):
    rows = {"date": ({"date": "2026-10-12"}, [("day", {"date": "2026-10-12", "lens": "general"})]),
            "month": ({"month": "2026-11"}, [("span", {"from": "2026-11-01", "to": "2026-11-30", "lens": "general"})]),
            "place_id": ({"place_id": "gn-745044"}, [("place", {"place_id": "gn-745044"})]),
            "other_profile_id": ({"other_profile_id": "prof-ayse"}, [("compatibility", {"other": "p1"})]),
            "compatibility_id": ({"compatibility_id": "cmp-1"}, [("compatibility", {"compatibility_id": "cmp-1"})]),
            "item_id": ({"item_id": "per:x"}, [("calendar_item", {"item_id": "per:x"})]),
            "activity": ({"activity": "contract"}, [("best_days", {"activities": ["contract"]})]),
            "activity+date": ({"activity": "contract", "date": "2026-10-14"},
                              [("best_days", {"activities": ["contract"], "from": "2026-10-14", "to": "2026-10-14"})]),
            "section_key": ({"section_key": "partnerships"}, [("natal_section", {"section_key": "partnerships"})])}
    for name, (context, want) in rows.items():
        assert T.forced_calls(context, ctx) == want, name


def test_t12_byte_identical(ctx):
    for i, (tool, args) in enumerate(ALL_CALLS):
        a = T.run_tool(ctx, f"c{i}", tool, args)
        b = T.run_tool(ctx, f"c{i}", tool, args)
        assert json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(b, sort_keys=True, ensure_ascii=False), tool


def _snapshot() -> dict:
    out = {}
    for pat in ("cal_run/_cache/*/*/*.json", "cal_run/_collective/*.json", "acg_run/_cache/*/*.json",
                "runs/*/*.json", "prediction_run/*/*.json"):
        for f in glob.glob(os.path.join(_paths.ROOT, pat)):
            with open(f, "rb") as fh:
                out[f] = hashlib.sha256(fh.read()).hexdigest()
    return out


def test_t13_other_layers_untouched(pa_cache):
    before = _snapshot()
    c = make_ctx("tr", pa_cache)
    for i, (tool, args) in enumerate(ALL_CALLS):
        T.run_tool(c, f"c{i}", tool, args)
    after = _snapshot()
    changed = [f for f in before if after.get(f) != before[f]]
    assert not changed, changed[:5]
