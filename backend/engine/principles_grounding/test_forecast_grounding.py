#!/usr/bin/env python3
"""
test_forecast_grounding.py — offline tests for ground_forecast.py
(FORECAST_GROUNDING_SPEC.md §6). No LLM, no network.

Synthetic mini-corpus + a fake retriever pin the invariants deterministically; the real
merged corpus is used for the existence/factor-type/determinism checks when present.

Run:  python test_forecast_grounding.py     (or: pytest test_forecast_grounding.py)
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ground_forecast import (
    NullRetriever, PREDICTIVE_DOMAINS, build_indices, ground_forecast,
)

_HERE = os.path.dirname(os.path.abspath(__file__))
_CORPUS = os.path.join(_HERE, "all_principles_grounded.with_predictive.json")


# ---------------------------------------------------------------------------
# builders
# ---------------------------------------------------------------------------
def _aspect_rec(pid, s, t, typ, *, domain="predictive", requires=None, judgment="j",
                tradition="modern"):
    return {"principle_id": pid, "domain": domain, "tradition": tradition,
            "judgment": judgment, "topic_tags": [typ],
            "about": {"factor_type": "aspect",
                      "aspect": {"source": s, "target": t, "type": typ}},
            "requires": requires if requires is not None else [{"kind": "other"}]}


def _house_rec(pid, point, house, *, domain="predictive"):
    return {"principle_id": pid, "domain": domain, "tradition": "modern",
            "judgment": "j", "topic_tags": [],
            "about": {"factor_type": "planet_in_house", "point": point,
                      "house": house, "house_system": "placidus"},
            "requires": [{"kind": "other"}]}


def _general_rec(pid, *, domain="predictive"):
    return {"principle_id": pid, "domain": domain, "tradition": "modern",
            "judgment": "general truth", "topic_tags": ["transit"],
            "about": {"factor_type": "general"}, "requires": [{"kind": "other"}]}


def _event(family="transit_aspect", *, transiting="Mars", natal="Venus", aspect="square",
           house=None, sign=None, eid=None):
    return {
        "event_id": eid or f"{family}-{transiting}-{natal}-{aspect}",
        "family": family, "standing": False,
        "bodies": {"transiting": transiting, "natal": natal},
        "aspect": aspect if family == "transit_aspect" else None,
        "phase": "applying" if family == "transit_aspect" else None,
        "cycle_stage": 3 if family == "transit_aspect" else None,
        "speed_class": "slow", "house_placidus": house, "house_wholesign": house,
        "sign": sign, "dignity": None,
        "grounding": {"kind": "point_aspects", "topic_tags": ["transit", aspect or ""]},
    }


def _forecast(events, horizon="month"):
    return {"meta": {"horizon": horizon, "target_date": "2026-07-01",
                     "natal_ref": "sha256:x", "run_id": "r"},
            "window": {"start": "2026-07-01T00:00:00+03:00",
                       "end": "2026-08-01T00:00:00+03:00", "tz": "Europe/Istanbul"},
            "events": events, "counts": {}}


def _chart(*, timed=True):
    pts = [{"name": n, "sign": "Aries", "sector": {"placidus": 1, "whole_sign": 1},
            "classifications": None}
           for n in ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
                     "Uranus", "Neptune", "Pluto")]
    ch = {"confidence": "exact" if timed else "unknown", "points": pts,
          "relations": [], "sector_rulers": {"placidus": {}, "whole_sign": {}}}
    if timed:
        ch["axes"] = {"ascendant": {"sign": "Leo"}, "mc": {"sign": "Taurus"}}
    return ch


class FakeRetriever:
    def __init__(self, hits):
        self._hits = hits           # list[(record, similarity)]

    def query(self, text, k):
        return self._hits[:k]


# ===========================================================================
# §6.1 — every match domain in {predictive, timing}
# ===========================================================================
def test_inv1_gate_a_domain():
    corpus = [_aspect_rec("nat", "Mars", "Venus", "square", domain="natal"),
              _aspect_rec("pred", "Mars", "Venus", "square", domain="predictive")]
    res = ground_forecast(_forecast([_event()]), _chart(), corpus)
    ids = [m["principle_id"] for m in res.forecast["events"][0]["matched_principles"]]
    assert ids == ["pred"], ids           # the natal-domain record is Gate-A dropped


# ===========================================================================
# §6.2 — structural matches share the DIRECTED (transiting, natal, type) key
# ===========================================================================
def test_inv2_no_cross_pair_leakage():
    corpus = [_aspect_rec("mv", "Mars", "Venus", "square"),
              _aspect_rec("vm", "Venus", "Mars", "square"),   # reversed direction
              _aspect_rec("sm", "Sun", "Moon", "square"),     # different pair
              _aspect_rec("vm-trine", "Venus", "Mars", "trine")]  # same pair, wrong type
    res = ground_forecast(_forecast([_event(transiting="Venus", natal="Mars",
                                            aspect="square")]), _chart(), corpus)
    ids = sorted(m["principle_id"] for m in res.forecast["events"][0]["matched_principles"])
    assert ids == ["vm"], ids             # only tr Venus -> natal Mars; not mv/sm/trine


def test_inv2_direction_not_reversed():
    # F6: "tr Sun □ natal Saturn" must not pull "tr Saturn □ natal Sun", and vice versa.
    corpus = [_aspect_rec("sun-sq-saturn", "Sun", "Saturn", "square"),
              _aspect_rec("saturn-sq-sun", "Saturn", "Sun", "square")]
    fc = _forecast([_event(transiting="Sun", natal="Saturn", aspect="square", eid="a"),
                    _event(transiting="Saturn", natal="Sun", aspect="square", eid="b")])
    res = ground_forecast(fc, _chart(), corpus)
    got = {e["event_id"]: [m["principle_id"] for m in e["matched_principles"]]
           for e in res.forecast["events"]}
    assert got == {"a": ["sun-sq-saturn"], "b": ["saturn-sq-sun"]}, got


def test_inv2_same_body_return():
    # A return (source == target) still keys cleanly under the directed tuple.
    corpus = [_aspect_rec("sat-return", "Saturn", "Saturn", "conjunction")]
    res = ground_forecast(_forecast([_event(transiting="Saturn", natal="Saturn",
                                            aspect="conjunction")]), _chart(), corpus)
    assert [m["principle_id"] for m in res.forecast["events"][0]["matched_principles"]]         == ["sat-return"]


# ===========================================================================
# Tradition gate — predictive is modern-only (CAL D3; F9)
# ===========================================================================
def test_tradition_structural_modern_only():
    corpus = [_aspect_rec("mod", "Mars", "Venus", "square"),
              _aspect_rec("trad", "Mars", "Venus", "square", tradition="traditional"),
              _aspect_rec("none", "Mars", "Venus", "square", tradition=None)]
    res = ground_forecast(_forecast([_event()]), _chart(), corpus)
    m = res.forecast["events"][0]["matched_principles"]
    assert [x["principle_id"] for x in m] == ["mod"], m
    assert all(x["tradition"] == "modern" for x in m)
    assert "trad" not in build_indices(corpus).corpus_ids


def test_tradition_embedding_modern_only():
    trad = _general_rec("trad-gen")
    trad["tradition"] = "traditional"
    mod = _general_rec("mod-gen")
    res = ground_forecast(_forecast([_event()]), _chart(), [trad, mod],
                          retriever=FakeRetriever([(trad, 0.9), (mod, 0.8)]))
    m = res.forecast["events"][0]["matched_principles"]
    assert [x["principle_id"] for x in m] == ["mod-gen"], m
    assert any(d.gate == "TRADITION" and d.principle_id == "trad-gen" for d in res.drops)


# ===========================================================================
# §6.3 — transiting/natal roles byte-identical before and after
# ===========================================================================
def test_inv3_roles_preserved():
    fc = _forecast([_event(transiting="Saturn", natal="Sun", aspect="opposition")])
    corpus = [_aspect_rec("ss", "Saturn", "Sun", "opposition")]
    before = copy.deepcopy(fc["events"][0]["bodies"])
    res = ground_forecast(fc, _chart(), corpus)
    assert res.forecast["events"][0]["bodies"] == before
    assert res.forecast["events"][0]["bodies"]["transiting"] == "Saturn"


# ===========================================================================
# §6.4 — general/unclassified never structural; only embedding ≥ floor
# ===========================================================================
def test_inv4_general_never_structural():
    corpus = [_general_rec("gen")]
    # no structural candidate exists for this pair -> zero structural
    res = ground_forecast(_forecast([_event()]), _chart(), corpus)
    assert res.forecast["events"][0]["matched_principles"] == []

    # with a retriever, the general record may enter, but only as embedding.
    res2 = ground_forecast(_forecast([_event()]), _chart(), corpus,
                           retriever=FakeRetriever([(corpus[0], 0.5)]))
    m = res2.forecast["events"][0]["matched_principles"]
    assert len(m) == 1 and m[0]["source_stage"] == "embedding" and m[0]["similarity"] == 0.5


def test_inv4_embedding_floor_enforced():
    corpus = [_general_rec("gen")]
    res = ground_forecast(_forecast([_event()]), _chart(), corpus,
                          retriever=FakeRetriever([(corpus[0], 0.20)]), sim_floor=0.35)
    assert res.forecast["events"][0]["matched_principles"] == []   # below floor -> dropped


# ===========================================================================
# §6.6 — Gate C reuse: unsatisfiable requirement on a timeless natal drops
# ===========================================================================
def test_inv6_gate_c_birth_time():
    corpus = [_aspect_rec("needs_time", "Mars", "Venus", "square",
                          requires=[{"kind": "birth_time"}])]
    res = ground_forecast(_forecast([_event()]), _chart(timed=False), corpus)
    assert res.forecast["events"][0]["matched_principles"] == []
    assert any(d.gate == "C" for d in res.drops)


# ===========================================================================
# §6.7 — zero-match report is explicit and correct
# ===========================================================================
def test_inv7_zero_match_report():
    corpus = [_aspect_rec("mv", "Mars", "Venus", "square")]
    fc = _forecast([_event(eid="hit"),
                    _event(transiting="Jupiter", natal="Pluto", aspect="trine", eid="miss")])
    res = ground_forecast(fc, _chart(), corpus)
    rep = res.report()
    empties = [e["event_id"] for e in res.forecast["events"] if not e["matched_principles"]]
    assert rep["events_with_zero_matches"] == empties == ["miss"]
    assert rep["events_with_matches"] == 1


# ===========================================================================
# §6.8 — cap N respected; structural ranked ahead of embedding
# ===========================================================================
def test_inv8_cap_and_ranking():
    corpus = [_aspect_rec("mv", "Mars", "Venus", "square"),
              _general_rec("emb1"), _general_rec("emb2")]
    res = ground_forecast(_forecast([_event()]), _chart(), corpus, cap=2,
                          retriever=FakeRetriever([(corpus[1], 0.9), (corpus[2], 0.8)]))
    m = res.forecast["events"][0]["matched_principles"]
    assert len(m) == 2
    assert m[0]["source_stage"] == "structural" and m[0]["principle_id"] == "mv"
    assert m[1]["source_stage"] == "embedding"      # structural ranked ahead


# ===========================================================================
# §6.9 — determinism
# ===========================================================================
def _hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def test_inv9_determinism():
    corpus = [_aspect_rec("mv", "Mars", "Venus", "square"),
              _aspect_rec("vm", "Venus", "Mars", "square")]
    fc = _forecast([_event(), _event(transiting="Sun", natal="Moon", aspect="trine")])
    a = ground_forecast(fc, _chart(), corpus)
    b = ground_forecast(fc, _chart(), corpus)
    assert _hash(a.forecast) == _hash(b.forecast)


# ===========================================================================
# §6.5 + factor-type discipline — against the REAL merged corpus (if present)
# ===========================================================================
def test_inv5_real_corpus_ids_and_factor_types():
    if not os.path.exists(_CORPUS):
        print("  (skip: merged corpus not found)")
        return
    corpus = json.load(open(_CORPUS, encoding="utf-8"))
    records = corpus if isinstance(corpus, list) else next(
        v for v in corpus.values() if isinstance(v, list))
    by_id = {r.get("principle_id"): r for r in records}
    pred_ids = {r["principle_id"] for r in records if r.get("domain") in PREDICTIVE_DOMAINS}

    fc = _forecast([
        _event(transiting="Mars", natal="Sun", aspect="conjunction"),
        _event(transiting="Jupiter", natal="Venus", aspect="trine"),
        _event(family="ingress_house", transiting="Moon", natal=None, aspect=None, house=1),
    ])
    res = ground_forecast(fc, _chart(), records)
    seen = 0
    for ev in res.forecast["events"]:
        for m in ev["matched_principles"]:
            seen += 1
            assert m["principle_id"] in pred_ids                 # §6.5 exists in slice
            if m["source_stage"] == "structural":
                ft = (by_id[m["principle_id"]].get("about") or {}).get("factor_type")
                assert ft not in ("general", "unclassified", None), (m["principle_id"], ft)
    assert seen > 0, "expected some real-corpus matches"


def test_real_corpus_direction_and_tradition():
    # F6/F9 against the real merged corpus: every structural aspect match is the event's
    # own direction, and nothing traditional comes through.
    if not os.path.exists(_CORPUS):
        print("  (skip: merged corpus not found)")
        return
    corpus = json.load(open(_CORPUS, encoding="utf-8"))
    records = corpus if isinstance(corpus, list) else next(
        v for v in corpus.values() if isinstance(v, list))
    by_id = {r.get("principle_id"): r for r in records}
    idx = build_indices(records)
    assert all(by_id[pid].get("tradition") == "modern" for pid in idx.corpus_ids)

    # the Sun/Saturn square has both directions in the corpus (a reverse twin)
    assert ("Sun", "Saturn", "square") in idx.aspect
    assert ("Saturn", "Sun", "square") in idx.aspect
    fc = _forecast([_event(transiting="Sun", natal="Saturn", aspect="square", eid="a"),
                    _event(transiting="Saturn", natal="Sun", aspect="square", eid="b")])
    res = ground_forecast(fc, _chart(), records)
    for ev in res.forecast["events"]:
        tr, na = ev["bodies"]["transiting"], ev["bodies"]["natal"]
        assert ev["matched_principles"], ev["event_id"]
        for m in ev["matched_principles"]:
            a = by_id[m["principle_id"]]["about"]["aspect"]
            assert (a["source"], a["target"]) == (tr, na), (ev["event_id"], m["principle_id"])


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"OK   {fn.__name__}")
            passed += 1
        except AssertionError as exc:
            print(f"FAIL {fn.__name__}: {exc}")
    print(f"\n{passed}/{len(fns)} passed")
    raise SystemExit(0 if passed == len(fns) else 1)
