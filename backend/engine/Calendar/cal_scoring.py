"""cal_scoring.py - daily goal scores, supportive/challenging periods, notification
candidates (CAL_02 §4-6). Deterministic; no model calls.

Inputs: ``personal_events.json`` (CAL_01) + the transit affinity table (CAL_02 §3)
+ the natal chart (for longitudes). Lunations, eclipses and stations do not score in
v1 (CAL_02 §4); the Phase 0 audit found no goal-taggable modern lunation-in-house records.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta
from typing import Iterable, Optional

import cal_astro as A
import cal_constants as K
import personal_events as P

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if os.path.join(ROOT, "Astrocartography") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "Astrocartography"))
from acg_constants import GOAL_ORDER  # noqa: E402

TEMPLATES_PATH = os.path.join(ROOT, "calendar_reading", "notification_templates.json")

SCHEMA_SCORES = "cal-scores-1"
SCHEMA_PERIODS = "cal-periods-1"
SCHEMA_NOTIF = "cal-notifications-1"

FAVORABLE = ("supportive", "strongly_supportive")
CHALLENGING = ("challenging", "strongly_challenging")


# --- §4 daily score ---------------------------------------------------------------------
def intensity(sep: float, aspect_angle: float, orb: float) -> float:
    """1 at exact, 0 at the orb edge, linear between (S2)."""
    return max(0.0, 1.0 - abs(sep - aspect_angle) / orb)


def band(P_: float, N_: float, th: dict = K.BAND) -> str:
    """Band precedence of CAL_02 §4: quiet, mixed, then strong before normal (S3)."""
    S = P_ - N_
    if P_ + N_ < th["quiet"]:
        return "quiet"
    hi, lo = max(P_, N_), min(P_, N_)
    if hi >= th["mixed_min"] and lo >= th["mixed_ratio"] * hi:
        return "mixed"
    if S >= th["strong"]:
        return "strongly_supportive"
    if S >= th["normal"]:
        return "supportive"
    if S <= -th["strong"]:
        return "strongly_challenging"
    if S <= -th["normal"]:
        return "challenging"
    return "quiet"


def day_tone(bands: dict) -> str:
    sup = sum(1 for b in bands.values() if b in FAVORABLE)
    cha = sum(1 for b in bands.values() if b in CHALLENGING)
    if sup >= 2 and cha == 0:
        return "favorable"
    if cha >= 2 and sup == 0:
        return "challenging"
    if sup >= 1 and cha >= 1:
        return "mixed"
    return "quiet"


def _affinity(table: dict, t: str, a: str, n: str) -> dict:
    cell = table["cells"].get(f"{t}|{a}|{n}")
    return {g: v["A"] for g, v in cell["goals"].items()} if cell else {}


def local_days(first: date, last: date) -> list[date]:
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def day_scores(events_doc: dict, natal: dict, table: dict,
               th: Optional[dict] = None) -> dict:
    th = th or K.BAND
    tz = events_doc["tz"]
    points = P.natal_points(natal)
    first = date.fromisoformat(events_doc["horizon"]["from_local"])
    last = date.fromisoformat(events_doc["horizon"]["to_local"])
    transits = [e for e in events_doc["events"] if e["kind"] == "transit"]
    spans = [(A.jd_of(A.parse_iso_utc(e["start_utc"])), A.jd_of(A.parse_iso_utc(e["end_utc"])), e)
             for e in transits]
    aff = {e["id"]: _affinity(table, e["t_body"], e["aspect"], e["n_point"]) for e in transits}
    days = []
    for d in local_days(first, last):
        jd = A.local_time_jd(d, 12, 0, tz)
        P_ = {g: 0.0 for g in GOAL_ORDER}
        N_ = {g: 0.0 for g in GOAL_ORDER}
        contribs: dict = {g: [] for g in GOAL_ORDER}
        for s, t, e in spans:
            if not (s <= jd <= t):
                continue
            sep = abs(A.signed180(A.lon(jd, e["t_body"]) - points[e["n_point"]]))
            it = intensity(sep, K.ASPECTS[e["aspect"]], K.TRANSIT_ORB[e["t_body"]])
            if it <= 0:
                continue
            m = min(1.0, e["I"] / 6.0)
            for g, a in aff[e["id"]].items():
                c = it * m * a
                if c > 0:
                    P_[g] += c
                elif c < 0:
                    N_[g] -= c
                if c != 0:
                    contribs[g].append((abs(c), e["id"], c))
        goals, drivers = {}, {}
        for g in GOAL_ORDER:
            p, n = round(P_[g], 6), round(N_[g], 6)
            goals[g] = {"S": round(p - n, 6), "P": p, "N": n, "band": band(p, n, th)}
            drivers[g] = [i for _, i, _ in sorted(contribs[g], key=lambda x: (-x[0], x[1]))[:3]]
        days.append({"local_date": d.isoformat(),
                     "tone": day_tone({g: v["band"] for g, v in goals.items()}),
                     "goals": goals, "drivers": drivers,
                     "_contrib": {g: {i: round(c, 6) for _, i, c in contribs[g]} for g in GOAL_ORDER}})
    return {"schema_version": SCHEMA_SCORES, "chart_key": events_doc["chart_key"], "tz": tz,
            "horizon": events_doc["horizon"], "bands": th, "days": days}


def public_scores(doc: dict) -> dict:
    """day_scores.json as written (drops the internal per-event contributions)."""
    out = dict(doc)
    out["days"] = [{k: v for k, v in d.items() if k != "_contrib"} for d in doc["days"]]
    return out


# --- §5 periods ----------------------------------------------------------------------------
def _runs(flags: list[bool]) -> list[tuple[int, int]]:
    runs, i = [], 0
    while i < len(flags):
        if flags[i]:
            j = i
            while j + 1 < len(flags) and flags[j + 1]:
                j += 1
            runs.append((i, j))
            i = j + 1
        else:
            i += 1
    return runs


def merge_runs(runs: list[tuple[int, int]], max_gap: int = 1) -> list[tuple[int, int]]:
    """Merge runs separated by <= max_gap unmarked days (S4)."""
    out: list[list[int]] = []
    for a, b in runs:
        if out and a - out[-1][1] - 1 <= max_gap:
            out[-1][1] = b
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def periods(scores: dict, events_doc: dict) -> dict:
    days = scores["days"]
    ev = {e["id"]: e for e in events_doc["events"]}
    out = []
    for g in GOAL_ORDER:
        for kind, marks in (("favorable", FAVORABLE), ("challenging", CHALLENGING)):
            flags = [d["goals"][g]["band"] in marks for d in days]
            for a, b in merge_runs(_runs(flags)):
                span = days[a:b + 1]
                sign = 1 if kind == "favorable" else -1
                summed: dict = {}
                for d in span:
                    for i, c in d["_contrib"][g].items():
                        if c * sign > 0:
                            summed[i] = summed.get(i, 0.0) + abs(c)
                drivers = [i for i, _ in sorted(summed.items(), key=lambda x: (-x[1], x[0]))]
                if a == b:
                    dd = span[0]["local_date"]
                    if not any(ev[i]["importance"] == "major" and dd in ev[i].get("exacts_local", [])
                               for i in drivers):
                        continue
                peak = max(span, key=lambda d: (sign * d["goals"][g]["S"], d["local_date"]))
                strong = any(d["goals"][g]["band"].startswith("strongly_") for d in span)
                start = span[0]["local_date"]
                out.append({"id": f"per:{g}:{kind}:{start}", "goal": g, "kind": kind,
                            "start_local": start, "end_local": span[-1]["local_date"],
                            "peak_local": peak["local_date"], "peak_S": peak["goals"][g]["S"],
                            "strength": "strong" if strong else "normal", "drivers": drivers,
                            "importance": "major" if any(ev[i]["importance"] == "major" for i in drivers)
                            else "moderate"})
    out.sort(key=lambda p: (p["start_local"], p["goal"], p["kind"]))
    return {"schema_version": SCHEMA_PERIODS, "chart_key": scores["chart_key"], "tz": scores["tz"],
            "horizon": scores["horizon"], "periods": out}


# --- §6 notification candidates --------------------------------------------------------
def load_templates(path: str = TEMPLATES_PATH) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def render(templates: dict, template_id: str, slots: dict) -> tuple[str, str]:
    """Fill a template: slot values are keys into the catalogue's word-form tables."""
    t = templates["templates"][template_id]
    forms = templates["slot_forms"]
    fill = {}
    for name, value in slots.items():
        if name == "n":
            fill["n"] = str(value)
            continue
        for suffix, table in forms[name].items():
            fill[f"{name}_{suffix}"] = table[str(value)]
    return t["tr"].format(**fill), t["en"].format(**fill)


def _minus(d: str, n: int) -> str:
    return (date.fromisoformat(d) - timedelta(days=n)).isoformat()


def notifications(periods_doc: dict, events_doc: dict, collective: Iterable[dict],
                  templates: dict, windows: Iterable[dict] = ()) -> dict:
    tz = events_doc["tz"]
    first, last = events_doc["horizon"]["from_local"], events_doc["horizon"]["to_local"]
    cands: dict = {}

    def add(ntype: str, ref: str, trigger: str, priority: int, template_id: str,
            slots: dict, link: dict) -> None:
        key = f"n:{ntype}:{ref}"
        if key in cands or trigger < first:      # a trigger before the horizon is already past
            return
        tr, en = render(templates, template_id, slots)
        cands[key] = {"id": key, "type": ntype, "trigger_local_date": trigger,
                      "suggested_local_time": templates.get("suggested_local_time", "09:00"),
                      "priority": priority, "template_id": template_id, "slots": slots,
                      "text_tr": tr, "text_en": en, "deep_link": link}

    for p in periods_doc["periods"]:
        if p["importance"] == "major" or p["strength"] == "strong":
            both = p["importance"] == "major" and p["strength"] == "strong"
            add("period_start", p["id"], _minus(p["start_local"], 1), 1 if both else 2,
                f"period_start_{p['kind']}", {"goal": p["goal"]}, {"view": "period", "ref": p["id"]})
    for w in windows:
        if w["n"] >= 2:
            ref = f"win:{w['activity']}:{w['start']}"
            add("favorable_window", ref, _minus(w["start"], 1), 2, "favorable_window",
                {"n": w["n"], "activity": w["activity"]}, {"view": "best_days", "ref": ref})
    for e in events_doc["events"]:
        if e["kind"] in ("new_moon", "full_moon") and e["importance"] in ("major", "moderate") \
                and e.get("natal_house"):
            add("lunation_in_house", e["id"], e["local_date"], 2 if e["importance"] == "major" else 3,
                f"lunation_in_house_{e['kind'].split('_')[0]}", {"area": e["natal_house"]},
                {"view": "event", "ref": e["id"]})
        elif e["kind"] in ("solar_eclipse", "lunar_eclipse") and e["hits"]:
            add("eclipse_hit", e["id"], _minus(e["local_date"], 2), 1, "eclipse_hit", {"n": 2},
                {"view": "event", "ref": e["id"]})
        elif e["kind"] == "station_on_point" and e["importance"] == "major":
            add("station_on_point", e["ref"], _minus(e["local_date"], 1), 1, "station_on_point",
                {"planet": e["body"]}, {"view": "event", "ref": e["id"]})
    for c in collective:
        if c["kind"] == "station_retrograde" and c["body"] == "mercury":
            ld = A.local_date_of_iso(c["t_utc"], tz)
            trig = _minus(ld, 1)
            if first <= ld <= last:
                add("retrograde_start", c["id"], trig, 3, "retrograde_start", {},
                    {"view": "event", "ref": c["id"]})
    out = sorted(cands.values(), key=lambda n: (n["trigger_local_date"], n["priority"], n["id"]))
    return {"schema_version": SCHEMA_NOTIF, "chart_key": events_doc["chart_key"], "tz": tz,
            "catalogue_version": templates.get("version"), "candidates": out}


def dumps(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
