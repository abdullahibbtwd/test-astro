"""CAL_05 §5 acceptance tests (O1-O4) for run_calendar.py. They use an offline
geocoder and --dry-run (zero model calls). O5 is the existing suites plus
Forecast_compute/test_forecast.py::test_window_tz_current_location.

Run: python -m pytest Calendar/test_run_calendar.py -q
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import run_calendar as RC  # noqa: E402

GEO = {"sofia": {"latitude": 42.6977, "longitude": 23.3219},
       "istanbul": {"latitude": 41.0082, "longitude": 28.9784}}
BIRTH = {"year": 1979, "month": 3, "day": 30, "hour": 6, "minute": 30, "location": "Sofia",
         "time_precision": "exact"}


def geocoder(q: str) -> dict:
    return GEO[q.lower()]


def _run(cur: str) -> dict:
    return RC.run_calendar(BIRTH, current_location=cur, mode="all", start=date(2026, 9, 28),
                           dry_run=True, geocoder=geocoder)


def _load(res: dict, name: str):
    return json.load(open(os.path.join(res["run_dir"], res["manifest"]["outputs"][name]), encoding="utf-8"))


@pytest.fixture(scope="module")
def runs():
    return {"sofia": _run("Sofia"), "istanbul": _run("Istanbul"), "sofia2": _run("Sofia")}


def test_o1_all_mode_two_locations(runs):
    s, i = runs["sofia"], runs["istanbul"]
    assert s["manifest"]["status"] == i["manifest"]["status"] == "ok"
    assert s["manifest"]["params"]["tz"] == "Europe/Sofia" and i["manifest"]["params"]["tz"] == "Europe/Istanbul"
    es, ei = _load(s, "personal_events.json"), _load(i, "personal_events.json")
    utc_s = {e["id"]: (e.get("start_utc") or e.get("t_utc")) for e in es["events"]}
    utc_i = {e["id"]: (e.get("start_utc") or e.get("t_utc")) for e in ei["events"]}
    tr = [k for k in utc_s if k.startswith("tr:")]
    assert tr and all(utc_s[k] == utc_i[k] for k in tr)                    # UTC data identical
    # local dates differ where expected: same UTC instants, and an instant late in the UTC
    # evening (Istanbul is ahead of Sofia in winter) lands on the next day in Istanbul only
    def pairs(doc):
        out = {e["t_utc"]: e["local_date"] for e in doc["events"] if "t_utc" in e}
        for e in doc["events"]:
            out.update(zip(e.get("exacts_utc", []), e.get("exacts_local", [])))
        out.update({c["id"]: c["local_date"] for c in doc["collective_refs"] if "local_date" in c})
        return out
    ls, li = pairs(es), pairs(ei)
    assert set(ls) == set(li)
    diff = [t for t in ls if ls[t] != li[t]]
    assert diff, "expected at least one event whose local date differs"
    for t in diff:
        assert (date.fromisoformat(li[t]) - date.fromisoformat(ls[t])).days == 1
    for name in ("best_days.json", "notifications.json", "day_scores.json", "periods.json",
                 "texts_tr.json", "texts_en.json", "run_manifest.json"):
        assert name in s["manifest"]["outputs"]
    assert any(k.startswith("calendar_") for k in s["manifest"]["outputs"])
    assert diff is not None


def test_o2_second_run_hits_cache(runs):
    st = {x["stage"]: x["status"] for x in runs["sofia2"]["manifest"]["stages"]}
    for k in ("1 collective", "3 events", "4 scores", "5 best_days"):
        assert st[k] == "cache_hit", (k, st)
    assert st["6 notifications"] == "ok"          # derived from cached inputs, no recompute cost


def test_o3_dry_run_zero_calls(runs):
    p = _load(runs["sofia"], "prompts.json")
    assert p["model_calls"] == 0 and p["prompts"] and p["units"]
    assert "texts" not in runs["sofia"]["manifest"]                     # no generator was built


def test_o4_views_reference_known_ids(runs):
    res = runs["sofia"]
    ev = _load(res, "personal_events.json")
    known = {e["id"] for e in ev["events"]} | {c["id"] for c in ev["collective_refs"]}
    per = {p["id"] for p in _load(res, "periods.json")["periods"]}
    for name in res["manifest"]["outputs"]:
        if not (name.startswith("calendar_") and name.endswith(".json")):
            continue
        v = _load(res, name)
        for d in v["days"]:
            for e in d["events"]:
                assert e["id"] in known, e
            for p in d["active_periods"]:
                assert p["id"] in per
        for key in ("lunations", "eclipses", "retrograde_periods", "major_transits"):
            assert set(v[key]) <= known, key
        assert set(v["periods"]) <= per
