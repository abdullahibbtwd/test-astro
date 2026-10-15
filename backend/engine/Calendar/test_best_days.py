"""CAL_04 §7 acceptance tests (B1-B6).  Run: python -m pytest Calendar/test_best_days.py -q"""

from __future__ import annotations

import copy
import os
import sys
from datetime import date

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "d_layer"))

import best_days as B  # noqa: E402
import cal_scoring as S  # noqa: E402
from compute_chart import BirthData, compute_chart  # noqa: E402


@pytest.fixture(scope="module")
def natal():
    return compute_chart(BirthData(year=1979, month=3, day=30, hour=6, minute=30,
                                   latitude=42.6977, longitude=23.3219))


@pytest.fixture(scope="module")
def doc(natal):
    return B.build_best_days(natal, "Europe/Sofia", date(2026, 9, 28), n_days=30)


# B1 ------------------------------------------------------------------------------------------
def test_b1_voc_fraction_two_timezones():
    coll = [{"kind": "voc_moon", "start_utc": "2026-10-05T10:00:00Z", "end_utc": "2026-10-05T13:30:00Z"}]
    d = date(2026, 10, 5)
    lon = B.day_factors(d, "Europe/London", {}, None, coll)["collective"]["C1"]
    tok = B.day_factors(d, "Asia/Tokyo", {}, None, coll)["collective"]["C1"]
    assert lon == pytest.approx(3.5 / 14, abs=1e-3)       # 08-22 BST = 07-21Z: fully inside
    assert tok == pytest.approx(3.0 / 14, abs=1e-3)       # 08-22 JST = 23Z(-1)-13Z: 10-13Z


# B2 ------------------------------------------------------------------------------------------
def test_b2_disabled_factor_zero(natal, doc):
    assert set(doc["factors_disabled"]) == {f"C{i}" for i in range(1, 9)}
    for a in doc["activities"].values():
        for d in a["days"]:
            for f in d["factors"]:
                if f["id"] in doc["factors_disabled"]:
                    assert f["contribution"] == 0
    cat = copy.deepcopy(B.load_catalogue())
    for f in cat["factors"]:
        if f["id"] == "C6":
            f["enabled"], f["grounding"] = True, ["fixture"]
    on = B.build_best_days(natal, "Europe/Sofia", date(2026, 9, 28), n_days=20, activities=["contract"], cat=cat)
    assert "C6" not in on["factors_disabled"]
    c6 = [f for d in on["activities"]["contract"]["days"] for f in d["factors"] if f["id"] == "C6"]
    assert any(f["contribution"] == 0.5 * f["value"] and f["value"] for f in c6)


# B3 ------------------------------------------------------------------------------------------
def test_b3_hard_gate_overrides():
    cat = copy.deepcopy(B.load_catalogue())
    fac = {f["id"]: f for f in cat["factors"]}
    fac["C1"]["enabled"] = True
    df = {"collective": {"C1": 0.7}, "ecl_dist": 99}
    gates = B.hard_gates("contract", df, fac)
    assert gates == ["voc_fraction>=0.6"]
    assert B.grade(2.5, gates) == "avoid"
    fac["C1"]["enabled"] = False
    assert B.hard_gates("contract", df, fac) == [] and B.grade(2.5, []) == "excellent"


# B4 ------------------------------------------------------------------------------------------
def test_b4_windows_and_notifications(doc):
    days = [{"local_date": f"2026-10-0{i}", "grade": g}
            for i, g in enumerate(["good", "neutral", "good", "excellent", "good", "avoid", "good"], 1)]
    assert B.windows(days) == [{"start": "2026-10-03", "end": "2026-10-05", "n": 3}]
    wins = B.all_windows(doc)
    ev = {"tz": "Europe/Sofia", "chart_key": "k", "horizon": {"from_local": "2026-09-28", "to_local": "2027-09-27"},
          "events": []}
    notif = S.notifications({"periods": []}, ev, [], S.load_templates(), windows=wins)
    got = {c["id"] for c in notif["candidates"] if c["type"] == "favorable_window"}
    assert got == {f"n:favorable_window:win:{w['activity']}:{w['start']}" for w in wins}
    assert all(w["n"] >= 2 for w in wins)


# B5 ------------------------------------------------------------------------------------------
def test_b5_reasons_are_top_contributions(doc):
    n = 0
    for act, a in doc["activities"].items():
        for d in a["days"]:
            if d["local_date"] not in a["top_days"]:
                continue
            r = a["reasons"][d["local_date"]]
            pos = sorted((p["contribution"] for p in d["_parts"] if p["contribution"] > 0), reverse=True)[:3]
            neg = sorted(p["contribution"] for p in d["_parts"] if p["contribution"] < 0)[:2]
            assert [x["contribution"] for x in r["positive"]] == [round(x, 4) for x in pos]
            assert [x["contribution"] for x in r["negative"]] == [round(x, 4) for x in neg]
            assert all(x["label_tr"] and x["label_en"] for x in r["positive"] + r["negative"])
            n += 1
    assert n > 0


# B6 ------------------------------------------------------------------------------------------
def test_b6_determinism_and_tz(natal, doc):
    again = B.build_best_days(natal, "Europe/Sofia", date(2026, 9, 28), n_days=30)
    assert B.dumps(B.public(again)) == B.dumps(B.public(doc))
    tokyo = B.build_best_days(natal, "Asia/Tokyo", date(2026, 9, 28), n_days=30)
    assert tokyo["factors_disabled"] == doc["factors_disabled"]
    assert tokyo["tz"] == "Asia/Tokyo" and tokyo["horizon"] == doc["horizon"]
    assert [f["id"] for f in tokyo["activities"]["love"]["days"][0]["factors"]] == \
           [f["id"] for f in doc["activities"]["love"]["days"][0]["factors"]]
