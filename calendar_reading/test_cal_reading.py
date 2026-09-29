"""CAL_03 §6 acceptance tests (T1-T5) with a fake generator (no model calls).
Run: python -m pytest calendar_reading/test_cal_reading.py -q"""

from __future__ import annotations

import os
import sys
from datetime import date

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (HERE, os.path.join(ROOT, "Calendar"), os.path.join(ROOT, "d_layer")):
    sys.path.insert(0, p)

import build_transit_affinity as BA  # noqa: E402
import cal_corpus  # noqa: E402
import cal_scoring as S  # noqa: E402
import collective_events as C  # noqa: E402
import cr_generate as G  # noqa: E402
import cr_sections as CS  # noqa: E402
import personal_events as P  # noqa: E402
from compute_chart import BirthData, compute_chart  # noqa: E402
from cr_validate import validate_unit  # noqa: E402

FILLER = ["bu", "dönem", "içinde", "duyguların", "daha", "görünür", "hale", "geliyor", "ve",
          "sakin", "bir", "farkındalık", "sana", "eşlik", "ediyor"]


def _sentence(n: int, ids: list[str]) -> dict:
    words = [FILLER[i % len(FILLER)] for i in range(n)]
    return {"text": " ".join(words).capitalize() + ".", "ids": ids}


class FakeGen:
    def __init__(self):
        self.drafted: list[str] = []

    def draft(self, units, feedback=None):
        out = {}
        for u in units:
            self.drafted.append(u["unit_id"])
            lo, hi = u["words"]
            n = (lo + hi) // 2
            pos = [r["id"] for r in u["pool"] if r.get("polarity") in ("mixed", "supportive")]
            first = pos[:1] or [u["pool"][0]["id"]]
            out[u["unit_id"]] = {"unit_id": u["unit_id"],
                                 "sentences": [_sentence(n // 2, first), _sentence(n - n // 2, [u["pool"][-1]["id"]])]}
        return out

    def reask_length(self, u, current):
        return current

    def translate(self, units):
        return {u["unit_id"]: {"unit_id": u["unit_id"], "sentences": [
            {"text": "This period brings a calm awareness.", "ids": s["ids"]} for s in u["sentences"]]}
            for u in units}

    def detox(self, unit, lang, problems):
        return unit


@pytest.fixture(scope="module")
def corpus():
    return cal_corpus.load()


@pytest.fixture(scope="module")
def chart_units(tmp_path_factory, corpus):
    index, modern = corpus
    cdir = str(tmp_path_factory.mktemp("coll"))
    tags = BA.json.load(open(BA.TAGS, encoding="utf-8"))
    table = BA.load()
    out = []
    for (y, m, d, h, mi) in ((1979, 3, 30, 6, 30), (1990, 7, 13, 14, 0)):
        natal = compute_chart(BirthData(year=y, month=m, day=d, hour=h, minute=mi,
                                        latitude=42.6977, longitude=23.3219))
        ev = P.build_personal_events(natal, "Europe/Sofia", date(2026, 9, 28), collective_dir=cdir)
        sc = S.day_scores(ev, natal, table)
        per = S.periods(sc, ev)
        coll = {c["id"]: c for c in C.load_range(2461300, 2461800, cdir)}
        grounding = {"new_moon": ["lunation-activates-natal-planet"]}      # T1 fixture grounding
        units = CS.plan_units(ev, per, ev["collective_refs"], coll, index, modern, tags,
                              collective_grounding=grounding)
        out.append({"natal": natal, "events": ev, "units": units})
    return out


def _store(tmp_path, name):
    return G.TextStore(str(tmp_path / "collective" / "texts.json"), str(tmp_path / name / "texts.json"))


# T1 -----------------------------------------------------------------------------------------
def test_t1_collective_generated_once(chart_units, tmp_path):
    gen = FakeGen()
    a, b = chart_units
    ca = [u for u in a["units"].values() if u["unit_type"] == "collective_event" and u["text"]][:2]
    cb = [b["units"][u["unit_id"]] for u in ca]
    assert ca and all(u["text"] for u in cb)
    G.ensure_texts(ca, _store(tmp_path, "A"), gen, "sha", a["events"]["chart_key"])
    G.ensure_texts(cb, _store(tmp_path, "B"), gen, "sha", b["events"]["chart_key"])
    assert sorted(gen.drafted) == sorted(u["unit_id"] for u in ca)        # chart B: zero calls


# T2 -----------------------------------------------------------------------------------------
def test_t2_minor_transit_label_only(chart_units, tmp_path):
    units = chart_units[0]["units"]
    minor = [u for u in units.values() if u["unit_type"] == "personal_transit" and u["importance"] == "minor"]
    assert minor and all(not u["text"] and u["label_tr"] and u["label_en"] for u in minor)
    gen = FakeGen()
    G.ensure_texts(minor, _store(tmp_path, "A"), gen, "sha", "k")
    assert gen.drafted == []


# T3 -----------------------------------------------------------------------------------------
def test_t3_no_grounding_label_and_gap(chart_units, tmp_path):
    units = chart_units[0]["units"]
    no = [u for u in units.values() if u["unit_type"] == "collective_event" and not u["pool"]]
    assert no, "retrograde / eclipse / ingress collective units have no modern grounding"
    assert all(not u["text"] and u["gap"] == "no_grounding" for u in no)
    assert {g["unit_id"] for g in G.gaps(units)} >= {u["unit_id"] for u in no}
    gen = FakeGen()
    G.ensure_texts(no, _store(tmp_path, "A"), gen, "sha", "k")
    assert gen.drafted == []


# T4 -----------------------------------------------------------------------------------------
def _plan(unit_type="personal_transit", kind=None, pool=None, words=(30, 50)):
    return {"unit_id": "u1", "unit_type": unit_type, "words": words,
            "pool": pool or [{"id": "a", "text": "x", "polarity": "challenging"},
                             {"id": "b", "text": "y", "polarity": "mixed"}],
            "context": {"kind": kind} if kind else {}}


def _good(ids_first=("a",), ids_second=("b",), n=40):
    tr = {"unit_id": "u1", "sentences": [_sentence(n // 2, list(ids_first)), _sentence(n - n // 2, list(ids_second))]}
    en = {"unit_id": "u1", "sentences": [{"text": "A calm awareness grows.", "ids": list(ids_first)},
                                         {"text": "It stays with you.", "ids": list(ids_second)}]}
    return tr, en


def test_t4_cv1_trace():
    tr, en = _good()
    assert validate_unit(_plan(), tr, en) == []
    tr["sentences"][0]["ids"] = ["zzz"]
    assert any(e.startswith("CV1") for e in validate_unit(_plan(), tr, en))
    tr["sentences"][0]["ids"] = []
    assert any("sentence without ids" in e for e in validate_unit(_plan(), tr, en))


def test_t4_cv2_numbers():
    tr, en = _good()
    assert validate_unit(_plan(), tr, en) == []
    for bad in ("12 Ekim'de başlıyor.", "Ekim ayında başlıyor.", "Yedinci ev vurgulanıyor.", "Kare açısı etkili."):
        t2 = {"unit_id": "u1", "sentences": [dict(tr["sentences"][0]), {"text": tr["sentences"][1]["text"] + " " + bad, "ids": ["b"]}]}
        assert any(e.startswith("CV2") for e in validate_unit(_plan(), t2, en)), bad
    e2 = {"unit_id": "u1", "sentences": [en["sentences"][0], {"text": "It peaks in October.", "ids": ["b"]}]}
    assert any(e.startswith("CV2") for e in validate_unit(_plan(), tr, e2))


def test_t4_cv3_directive_and_event_words():
    tr, en = _good()
    assert validate_unit(_plan(), tr, en) == []
    t2 = {"unit_id": "u1", "sentences": [tr["sentences"][0], {"text": tr["sentences"][1]["text"] + " Kesinlikle kaza geçireceksin.", "ids": ["b"]}]}
    errs = validate_unit(_plan(), t2, en)
    assert any("AV2" in e for e in errs) and any("AV8" in e for e in errs)


def test_t4_cv3_body_words_and_planet_names():
    from cr_validate import text_problems
    assert text_problems("Kalbinin olduğu yönü gözden geçirebilirsin.", "tr") == []
    assert text_problems("Follow where your heart leads.", "en") == []
    assert any("CV3" in p for p in text_problems("Kalp ile dolaşım sistemini yorma.", "tr"))
    assert any("CV3" in p for p in text_problems("Göz çevresinde hassasiyet olabilir.", "tr"))
    assert any("CV3" in p for p in text_problems("Evde sakarlıklar olabilir.", "tr"))
    assert any("CV3" in p for p in text_problems("Watch your circulation and eyes.", "en"))
    assert any("English planet" in p for p in text_problems("Saturn etkisi artıyor.", "tr"))
    assert text_problems("Satürn etkisi yavaşça artıyor.", "tr") == []


def test_t4_cv4_constructive_angle():
    plan = _plan("period", "challenging")
    tr, en = _good(("b",), ("b",))
    assert validate_unit(plan, tr, en) == []
    tr, en = _good(("a",), ("a",))
    assert any(e.startswith("CV4") for e in validate_unit(plan, tr, en))


def test_t4_cv5_length():
    tr, en = _good(n=40)
    assert validate_unit(_plan(), tr, en) == []
    tr, en = _good(n=80)
    assert any(e.startswith("CV5") for e in validate_unit(_plan(), tr, en))


# T5 -----------------------------------------------------------------------------------------
def test_t5_prewarm_next_14_days(chart_units, tmp_path):
    units = chart_units[0]["units"]
    today = date(2026, 10, 1)
    sel = G.prewarm_units(units, today, 14)
    first, last = "2026-10-01", "2026-10-14"
    assert sel
    for u in sel:
        assert u["text"] and u["span"][0] <= last and u["span"][1] >= first
    outside = [u for u in units.values() if u["text"] and (u["span"][0] > last or u["span"][1] < first)]
    assert outside and not set(u["unit_id"] for u in outside) & set(u["unit_id"] for u in sel)
    gen = FakeGen()
    store = _store(tmp_path, "A")
    G.ensure_texts(sel[:3], store, gen, "sha", "k")
    gen2 = FakeGen()
    G.ensure_texts(sel, store, gen2, "sha", "k")
    assert sorted(gen2.drafted) == sorted(u["unit_id"] for u in sel[3:])     # only the uncached
