"""CAL_02 §8 acceptance tests (S1-S6).  Run: python -m pytest Calendar/test_cal_scoring.py -q"""

from __future__ import annotations

import os
import re
import sys
from datetime import date

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "d_layer"))

import build_transit_affinity as BA  # noqa: E402
import cal_constants as K  # noqa: E402
import cal_scoring as S  # noqa: E402
import collective_events as C  # noqa: E402
import personal_events as P  # noqa: E402
from compute_chart import BirthData, compute_chart  # noqa: E402

TH = {"quiet": 0.15, "mixed_min": 0.30, "mixed_ratio": 0.5, "strong": 0.80, "normal": 0.30}


# S1 --------------------------------------------------------------------------------------
def test_s1_affinity_formula():
    assert BA.cell_value(5, 0, 0)["A"] == pytest.approx(0.714, abs=5e-4)
    assert BA.cell_value(0, 5, 0)["A"] == pytest.approx(-0.714, abs=5e-4)
    assert BA.cell_value(0, 0, 4)["A"] == 0.0
    assert BA.cell_value(1, 0, 0)["A"] == pytest.approx((1 / 3) * (1 / 5), abs=1e-6)


# S2 --------------------------------------------------------------------------------------
def test_s2_intensity_linear():
    assert S.intensity(90.0, 90, 2.0) == 1.0
    assert S.intensity(92.0, 90, 2.0) == 0.0
    assert S.intensity(88.0, 90, 2.0) == 0.0
    assert S.intensity(91.0, 90, 2.0) == pytest.approx(0.5)
    assert S.intensity(95.0, 90, 2.0) == 0.0


# S3 --------------------------------------------------------------------------------------
def test_s3_band_precedence():
    assert S.band(0.05, 0.05, TH) == "quiet"
    assert S.band(1.0, 0.6, TH) == "mixed"              # mixed wins over strongly_supportive? S=0.4 anyway
    assert S.band(1.6, 0.8, TH) == "mixed"              # S = 0.8 would be strong; mixed first
    assert S.band(0.9, 0.05, TH) == "strongly_supportive"
    assert S.band(0.4, 0.05, TH) == "supportive"
    assert S.band(0.05, 0.9, TH) == "strongly_challenging"
    assert S.band(0.05, 0.4, TH) == "challenging"
    assert S.band(0.2, 0.05, TH) == "quiet"             # S below normal


# S4 --------------------------------------------------------------------------------------
def _fake(bands: list[str], major_exact_on: str | None = None):
    days = []
    for i, b in enumerate(bands):
        d = date(2026, 10, 1 + i).isoformat()
        sgn = 1 if "supportive" in b else -1 if "challenging" in b else 0
        days.append({"local_date": d, "goals": {g: {"S": 0.5 * sgn, "P": 0, "N": 0, "band": b if g == "career" else "quiet"}
                                                for g in S.GOAL_ORDER},
                     "_contrib": {g: ({"tr:x": 0.5 * sgn} if g == "career" and sgn else {}) for g in S.GOAL_ORDER}})
    ev = {"events": [{"id": "tr:x", "importance": "major" if major_exact_on else "minor",
                      "exacts_local": [major_exact_on] if major_exact_on else []}]}
    return {"days": days, "chart_key": "k", "tz": "UTC", "horizon": {}}, ev


def test_s4_periods_merge_and_drop():
    sc, ev = _fake(["supportive", "supportive", "quiet", "supportive", "quiet", "quiet",
                    "supportive", "quiet", "quiet"])
    per = [p for p in S.periods(sc, ev)["periods"] if p["goal"] == "career"]
    assert [(p["start_local"], p["end_local"]) for p in per] == [("2026-10-01", "2026-10-04")]
    sc, ev = _fake(["quiet", "supportive", "quiet", "quiet"], major_exact_on="2026-10-02")
    per = [p for p in S.periods(sc, ev)["periods"] if p["goal"] == "career"]
    assert len(per) == 1 and per[0]["start_local"] == per[0]["end_local"] == "2026-10-02"
    assert per[0]["importance"] == "major"


# real-chart fixtures ---------------------------------------------------------------------
@pytest.fixture(scope="module")
def world(tmp_path_factory):
    cdir = str(tmp_path_factory.mktemp("coll"))
    natal = compute_chart(BirthData(year=1979, month=3, day=30, hour=6, minute=30,
                                    latitude=42.6977, longitude=23.3219))
    table = BA.load()
    out = {}
    for tz in ("Europe/Sofia", "Asia/Tokyo"):
        ev = P.build_personal_events(natal, tz, date(2026, 9, 28), collective_dir=cdir)
        sc = S.day_scores(ev, natal, table)
        per = S.periods(sc, ev)
        coll = C.load_range(2461300, 2461700, cdir)
        notif = S.notifications(per, ev, coll, S.load_templates(),
                                windows=[{"activity": "contract", "start": "2026-10-20", "end": "2026-10-22", "n": 3}])
        out[tz] = {"events": ev, "scores": sc, "periods": per, "notif": notif}
    return out


# S5 --------------------------------------------------------------------------------------
def test_s5_notifications(world):
    tpl = S.load_templates()
    w = world["Europe/Sofia"]
    cands = w["notif"]["candidates"]
    assert cands
    keys = [(c["type"], c["id"]) for c in cands]
    assert len(keys) == len(set(keys))
    types = {c["type"] for c in cands}
    assert {"period_start", "favorable_window", "retrograde_start"} <= types
    for c in cands:
        tr, en = S.render(tpl, c["template_id"], c["slots"])
        assert (c["text_tr"], c["text_en"]) == (tr, en)
        assert "{" not in tr and "{" not in en
    per = {p["id"]: p for p in w["periods"]["periods"]}
    for c in cands:
        if c["type"] == "period_start":
            p = per[c["deep_link"]["ref"]]
            assert c["trigger_local_date"] == S._minus(p["start_local"], 1)
            assert c["priority"] == (1 if p["importance"] == "major" and p["strength"] == "strong" else 2)
        if c["type"] == "favorable_window":
            assert c["trigger_local_date"] == "2026-10-19" and c["priority"] == 2
        if c["type"] == "eclipse_hit":
            ev = next(e for e in w["events"]["events"] if e["id"] == c["deep_link"]["ref"])
            assert c["trigger_local_date"] == S._minus(ev["local_date"], 2) and c["priority"] == 1


def test_s5_every_template_renders_every_slot():
    tpl = S.load_templates()
    forms = tpl["slot_forms"]
    slot_of = {t: set(re.findall(r"\{(\w+?)_(?:tr|en)\w*\}", v["tr"] + v["en"])) | ({"n"} if "{n}" in v["tr"] else set())
               for t, v in tpl["templates"].items()}
    for t, slots in slot_of.items():
        named = [s for s in slots if s != "n"]
        if not named:
            S.render(tpl, t, {"n": 2} if "n" in slots else {})
            continue
        (name,) = named
        values = next(iter(forms[name].values())).keys()
        for v in values:
            tr, en = S.render(tpl, t, {name: v, **({"n": 3} if "n" in slots else {})})
            assert "{" not in tr + en and tr and en


# S6 --------------------------------------------------------------------------------------
def test_s6_determinism_and_tz(world, tmp_path):
    natal = compute_chart(BirthData(year=1979, month=3, day=30, hour=6, minute=30,
                                    latitude=42.6977, longitude=23.3219))
    w = world["Europe/Sofia"]
    again = S.day_scores(w["events"], natal, BA.load())
    assert S.dumps(S.public_scores(again)) == S.dumps(S.public_scores(w["scores"]))
    assert S.dumps(S.periods(again, w["events"])) == S.dumps(w["periods"])
    # tz change: UTC-based event data identical, local dates may shift
    a = {e["id"]: e["exacts_utc"] for e in w["events"]["events"] if e["kind"] == "transit"}
    b = {e["id"]: e["exacts_utc"] for e in world["Asia/Tokyo"]["events"]["events"] if e["kind"] == "transit"}
    common = set(a) & set(b)
    assert common and all(a[k] == b[k] for k in common)
    assert world["Asia/Tokyo"]["scores"]["tz"] == "Asia/Tokyo"
