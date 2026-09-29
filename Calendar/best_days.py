"""best_days.py - electional scoring for 10 activities over 90 days (CAL_04).

Deterministic. A day is a local day in the user's current tz. The active window is
08:00-22:00 local, and the Moon is taken at local 12:00. Houses are natal Placidus. DSC and
IC (ASC/MC + 180) are key points here only.

Grounding gate (CAL_04 §3.3): a factor contributes only if it is ``enabled`` in the
catalogue (``principles_grounding/best_days_factors.json``), and it can only be enabled
with >= 1 modern record. Per decision Q4 every collective C-factor ships disabled in v1:
their values are still computed and shown, with contribution 0. Because every hard gate
depends on a C-factor, no gate fires in v1.

    python Calendar/best_days.py --write-catalogue     # (re)build the factor catalogue
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, timedelta
from typing import Optional

import cal_astro as A
import cal_constants as K
import cal_corpus
import collective_events as C
import personal_events as P

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CATALOGUE = os.path.join(ROOT, "principles_grounding", "best_days_factors.json")
SCHEMA = "cal-best-days-1"

ACTIVITIES = {
    #  key            (TR, EN, key points, houses)
    "love":          ("Aşk", "Love", ["venus", "moon", "dsc"], [5, 7]),
    "meetings":      ("Görüşmeler ve Randevular", "Meetings & Appointments", ["mercury", "sun", "asc"], [3, 7, 11]),
    "business":      ("İş", "Business", ["jupiter", "sun", "mercury", "mc"], [2, 7, 10]),
    "contract":      ("Sözleşme İmzalama", "Signing a Contract", ["mercury", "jupiter", "saturn"], [3, 7]),
    "conversation":  ("Önemli Konuşma", "Important Conversation", ["mercury", "moon"], [3, 7]),
    "travel":        ("Seyahat", "Travel", ["jupiter", "mercury"], [3, 9]),
    "shopping":      ("Alışveriş", "Shopping", ["venus", "jupiter"], [2]),
    "project_start": ("Proje Başlatma", "Starting a Project", ["sun", "mars", "jupiter", "mc"], [1, 5, 10]),
    "interview":     ("İş Görüşmesi", "Job Interview", ["sun", "mercury", "jupiter", "mc"], [6, 10]),
    "moving":        ("Taşınma", "Moving House", ["moon", "venus", "ic"], [4]),
}
ACTIVITY_ORDER = list(ACTIVITIES)

ALL = {a: 1.0 for a in ACTIVITY_ORDER}
FACTOR_SPECS = {
    "C1": ("voc_fraction", "collective", {"contract": -2, "project_start": -2, "business": -2, "interview": -2,
                                         "shopping": -2, "moving": -2, "meetings": -1, "conversation": -1,
                                         "travel": -1, "love": -0.5}, None),
    "C2": ("mercury_rx", "collective", {"contract": -1.5, "conversation": -1, "interview": -1, "shopping": -1,
                                       "travel": -1, "meetings": -1, "business": -1, "project_start": -0.5,
                                       "moving": -0.5}, None),
    "C3": ("venus_rx", "collective", {"love": -1.5, "shopping": -1, "business": -0.5}, None),
    "C4": ("mars_rx", "collective", {"project_start": -1, "moving": -1, "business": -0.5}, None),
    "C5": ("eclipse_window", "collective", {"project_start": -1.5, "contract": -1.5, "moving": -1.5,
                                           "business": -1, "interview": -1, "love": -0.5}, None),
    "C6": ("waxing_moon", "collective", {"project_start": 0.5, "business": 0.5, "contract": 0.5,
                                        "moving": 0.5, "interview": 0.5}, None),
    "C7": ("moon_benefic_aspects", "collective", {a: 0.5 for a in ACTIVITY_ORDER}, 2),
    "C8": ("moon_malefic_aspects", "collective", {a: -0.5 for a in ACTIVITY_ORDER}, 2),
    "P1": ("benefic_transits", "personal", {a: 1.0 for a in ACTIVITY_ORDER}, 2.0),
    "P2": ("hard_transits", "personal", {a: -1.0 for a in ACTIVITY_ORDER}, 2.0),
    "P3": ("moon_in_house", "personal", {a: 0.75 for a in ACTIVITY_ORDER}, None),
    "P4": ("moon_to_key_points", "personal", {a: 1.0 for a in ACTIVITY_ORDER}, 1.0),
}
BENEFIC_T, BENEFIC_A = ["sun", "venus", "jupiter"], ["conjunction", "sextile", "trine"]
HARD_T, HARD_A = ["mars", "saturn", "uranus", "neptune", "pluto"], ["conjunction", "square", "opposition"]
MOON_ASPECT_VALUE = {"sextile": 0.5, "trine": 0.5, "square": -0.5, "opposition": -0.5}

GRADE_TH_SPEC = {"excellent": 2.0, "good": 1.0, "avoid": -1.5}   # CAL_04 §4
# Calibrated at CAL_04 §6 (thresholds only; Calendar/CAL_BEST_DAYS_CALIBRATION.md). With the
# C-factors disabled (Q4) the spec thresholds leave ~90% of days neutral.
GRADE_TH = {"excellent": 1.25, "good": 0.55, "avoid": -0.8}
CALIBRATION_VERSION = "bd-1.1"


# --- DSC / IC grounding equivalence ---------------------------------------------------------
_OPP_ASPECT = {"conjunction": "opposition", "opposition": "conjunction", "sextile": "trine",
               "trine": "sextile", "square": "square"}


def grounding_cell(t: str, a: str, n: str) -> tuple[str, str, str]:
    """A transit to DSC / IC is geometrically the opposite aspect to ASC / MC (same instant)."""
    if n == "dsc":
        return t, _OPP_ASPECT[a], "asc"
    if n == "ic":
        return t, _OPP_ASPECT[a], "mc"
    return t, a, n


# --- catalogue ------------------------------------------------------------------------------
def build_catalogue(index: dict) -> dict:
    tr = index["transits"]
    pts = K.NATAL_PLANETS + ["asc", "mc"]

    def cells(ts, asps):
        return sorted({i for t in ts for a in asps for n in pts for i in tr.get((t, a, n), [])})

    grounding = {
        "P1": cells(BENEFIC_T, BENEFIC_A),
        "P2": cells(HARD_T, HARD_A),
        "P3": sorted({i for v in index["moon_in_house"].values() for i in v}
                     | set(index["generic"]["moon_house_general"])),
        "P4": sorted(set(cells(["moon"], list(MOON_ASPECT_VALUE))) | set(index["generic"]["electional_moon"])),
    }
    factors = []
    for fid, (name, kind, weights, cap) in FACTOR_SPECS.items():
        g = grounding.get(fid, [])
        # Q4 (Calendar/CAL_EXPLORATION_REPORT.md): C-factors disabled in v1, even C7/C8.
        enabled = bool(g) and kind == "personal"
        factors.append({"id": fid, "name": name, "kind": kind, "weights": weights, "cap": cap,
                        "grounding": g, "enabled": enabled,
                        "note": ("no modern grounding (Phase 0 audit); enable via CAL_06 corpus delta"
                                 if kind == "collective" else "grounded in Hand transit records")})
    return {"version": CALIBRATION_VERSION, "approved": True,
            "approval_note": "Factor grounding lists reviewed under Radul's delegation (2026-09-29).",
            "factors": factors}


def load_catalogue(path: str = CATALOGUE) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# --- helpers --------------------------------------------------------------------------------
def key_points(natal: dict) -> dict[str, float]:
    pts = P.natal_points(natal)
    if "asc" in pts:
        pts["dsc"] = A.norm360(pts["asc"] + 180)
        pts["ic"] = A.norm360(pts["mc"] + 180)
    return pts


def _moon_aspect_times(jd0: float, jd1: float, target_lon: Optional[float], body: Optional[str],
                       aspects: dict[str, float]) -> list[tuple[float, str]]:
    """Exact Moon aspects in [jd0, jd1] to a fixed longitude or a moving body.
    The Moon moves ~8° in 14 h, so each aspect angle is crossed at most once."""
    out = []
    for asp in aspects:
        for e in ([0.0] if asp == "conjunction" else [180.0] if asp == "opposition"
                  else [float(K.ASPECTS[asp]), 360.0 - K.ASPECTS[asp]]):
            def f(j: float, e: float = e) -> float:
                other = target_lon if body is None else A.lon(j, body)
                return A.signed180(A.lon(j, "moon") - other - e)
            f0, f1 = f(jd0), f(jd1)
            if (f0 < 0) != (f1 < 0) and abs(f0) + abs(f1) < 180:
                out.append((A.bisect(f, jd0, jd1, f0), asp))
    return out


def _intensity(t: str, lon_t: float, n_lon: float, asp: str) -> float:
    sep = abs(A.signed180(lon_t - n_lon))
    return max(0.0, 1.0 - abs(sep - K.ASPECTS[asp]) / K.TRANSIT_ORB[t])


# --- one day -----------------------------------------------------------------------------------
def day_factors(d: date, tz: str, pts: dict, cusps: Optional[list], coll: list[dict]) -> dict:
    """Per-day raw factor data shared by all activities."""
    jd_noon = A.local_time_jd(d, 12, 0, tz)
    w0, w1 = A.local_time_jd(d, 8, 0, tz), A.local_time_jd(d, 22, 0, tz)
    lons = {b: A.lon_speed(jd_noon, b) for b in K.TRANSIT_BODIES}
    moon = A.lon(jd_noon, "moon")
    # C1 VOC fraction of the active window
    voc = 0.0
    for ev in coll:
        if ev["kind"] == "voc_moon":
            s, e = A.jd_of(A.parse_iso_utc(ev["start_utc"])), A.jd_of(A.parse_iso_utc(ev["end_utc"]))
            voc += max(0.0, min(e, w1) - max(s, w0))
    ecl_days = [A.local_date_of_iso(ev["t_utc"], tz) for ev in coll if ev["kind"].endswith("_eclipse")]
    ecl_dist = min((abs((date.fromisoformat(x) - d).days) for x in ecl_days), default=99)
    elong = A.elongation(jd_noon)
    c7 = sum(1 for b in ("venus", "jupiter")
             for _ in _moon_aspect_times(w0, w1, None, b, {"conjunction": 0, "sextile": 0, "trine": 0}))
    c8 = sum(1 for b in ("mars", "saturn")
             for _ in _moon_aspect_times(w0, w1, None, b, {"conjunction": 0, "square": 0, "opposition": 0}))
    moon_hits = {n: _moon_aspect_times(w0, w1, lng, None, MOON_ASPECT_VALUE) for n, lng in pts.items()}
    return {"collective": {"C1": round(voc / (w1 - w0), 4), "C2": int(lons["mercury"][1] < 0),
                           "C3": int(lons["venus"][1] < 0), "C4": int(lons["mars"][1] < 0),
                           "C5": int(ecl_dist <= 3), "C6": int(12.0 <= elong <= 168.0),
                           "C7": min(c7, 2), "C8": min(c8, 2)},
            "ecl_dist": ecl_dist, "lons": lons, "moon": moon,
            "moon_house": A.house_of(moon, cusps) if cusps else None, "moon_hits": moon_hits}


def _instances(act: str, df: dict, pts: dict) -> dict[str, list[dict]]:
    """Personal factor instances (each with a raw value and the cell used for grounding/labels)."""
    kp = [n for n in ACTIVITIES[act][2] if n in pts]
    inst: dict[str, list[dict]] = {"P1": [], "P2": [], "P3": [], "P4": []}
    for fid, ts, asps in (("P1", BENEFIC_T, BENEFIC_A), ("P2", HARD_T, HARD_A)):
        for t in ts:
            for n in kp:
                for a in asps:
                    it = _intensity(t, df["lons"][t][0], pts[n], a)
                    if it > 0:
                        inst[fid].append({"kind": "transit", "t": t, "a": a, "n": n, "value": round(it, 4)})
    h = df["moon_house"]
    if h and h in ACTIVITIES[act][3]:
        inst["P3"].append({"kind": "moon_house", "house": h, "value": 1.0})
    for n in kp:
        for _, a in df["moon_hits"].get(n, []):
            inst["P4"].append({"kind": "moon_aspect", "t": "moon", "a": a, "n": n,
                               "value": MOON_ASPECT_VALUE[a]})
    return inst


def score_day(act: str, df: dict, pts: dict, cat: dict) -> dict:
    fac = {f["id"]: f for f in cat["factors"]}
    inst = _instances(act, df, pts)
    rows, parts = [], []
    for fid, f in fac.items():
        w = f["weights"].get(act, 0.0)
        if f["kind"] == "collective":
            value = df["collective"][fid]
            contrib = w * value if f["enabled"] else 0.0
            rows.append({"id": fid, "value": value, "contribution": round(contrib, 4)})
            if contrib:
                parts.append({"factor": fid, "contribution": contrib})
            continue
        items = inst[fid]
        raw = sum(i["value"] for i in items)
        total = w * raw
        if f["cap"] is not None:
            total = max(-f["cap"], min(f["cap"], total))
        if not f["enabled"]:
            total = 0.0
        rows.append({"id": fid, "value": round(raw, 4), "contribution": round(total, 4)})
        scale = (total / (w * raw)) if (w * raw) else 0.0
        for i in items:
            c = w * i["value"] * scale
            if c:
                parts.append({"factor": fid, "contribution": c, **{k: v for k, v in i.items() if k != "value"}})
    R = round(sum(r["contribution"] for r in rows), 4)
    gates = hard_gates(act, df, fac)
    return {"R": R, "factors": rows, "parts": parts, "gates": gates, "grade": grade(R, gates)}


def hard_gates(act: str, df: dict, fac: dict) -> list[str]:
    """CAL_04 §4 hard gates (only for enabled factors)."""
    g = []
    if fac["C1"]["enabled"] and act in ("contract", "project_start", "business", "interview") \
            and df["collective"]["C1"] >= 0.6:
        g.append("voc_fraction>=0.6")
    if fac["C5"]["enabled"] and act in ("contract", "project_start", "moving") and df["ecl_dist"] <= 1:
        g.append("eclipse±1d")
    if fac["C2"]["enabled"] and act == "contract" and df.get("mercury_station_dist", 99) <= 1:
        g.append("mercury_station±1d")
    return g


def grade(R: float, gates: list[str], th: dict = GRADE_TH) -> str:
    if gates or R <= th["avoid"]:
        return "avoid"
    if R >= th["excellent"]:
        return "excellent"
    if R >= th["good"]:
        return "good"
    return "neutral"


# --- reasons (deterministic labels) ------------------------------------------------------------
def _label(part: dict) -> tuple[str, str]:
    import sys
    sys.path.insert(0, os.path.join(ROOT, "calendar_reading"))
    import cr_sections as CS  # lazy: reading package only needed for labels
    if part.get("kind") in ("transit", "moon_aspect"):
        return CS.transit_label(part["t"], part["a"], part["n"])
    if part.get("kind") == "moon_house":
        h = part["house"]
        with open(os.path.join(ROOT, "calendar_reading", "notification_templates.json"), encoding="utf-8") as fh:
            area = json.load(fh)["slot_forms"]["area"]
        return f"Ay {h}. evinizde ({area['tr'][str(h)]})", f"Moon in your {area['en'][str(h)]} area"
    names = {"C1": ("Boşlukta Ay", "Void-of-course Moon"), "C2": ("Merkür retrosu", "Mercury retrograde"),
             "C3": ("Venüs retrosu", "Venus retrograde"), "C4": ("Mars retrosu", "Mars retrograde"),
             "C5": ("Tutulma dönemi", "Eclipse window"), "C6": ("Büyüyen Ay", "Waxing Moon"),
             "C7": ("Ay'ın uyumlu açıları", "Moon's harmonious aspects"),
             "C8": ("Ay'ın gergin açıları", "Moon's tense aspects")}
    return names[part["factor"]]


def reasons(parts: list[dict]) -> dict:
    pos = sorted((p for p in parts if p["contribution"] > 0), key=lambda p: -p["contribution"])[:3]
    neg = sorted((p for p in parts if p["contribution"] < 0), key=lambda p: p["contribution"])[:2]

    def fmt(p):
        tr, en = _label(p)
        return {"factor": p["factor"], "label_tr": tr, "label_en": en, "contribution": round(p["contribution"], 4)}
    return {"positive": [fmt(p) for p in pos], "negative": [fmt(p) for p in neg]}


def part_records(p: dict, index: dict) -> list[str]:
    if p.get("kind") == "transit":
        return index["transits"].get(grounding_cell(p["t"], p["a"], p["n"]), [])
    if p.get("kind") == "moon_aspect":
        return index["transits"].get(grounding_cell("moon", p["a"], p["n"]), [])
    if p.get("kind") == "moon_house":
        return index["moon_in_house"].get(p["house"], [])
    return []


# --- windows / top days ---------------------------------------------------------------------------
GOOD = ("good", "excellent")


def windows(days: list[dict]) -> list[dict]:
    out, run = [], []
    for d in days + [{"grade": None, "local_date": None}]:
        if d["grade"] in GOOD:
            run.append(d["local_date"])
        else:
            if len(run) >= 2:
                out.append({"start": run[0], "end": run[-1], "n": len(run)})
            run = []
    return out


def top_days(days: list[dict], k: int = 5) -> list[str]:
    good = [d for d in days if d["grade"] in GOOD]
    best = sorted(good, key=lambda d: (-d["R"], d["local_date"]))[:k]
    return sorted(d["local_date"] for d in best)


# --- document -----------------------------------------------------------------------------------
def build_best_days(natal: dict, tz: str, from_local: date, n_days: int = K.BEST_DAYS_DAYS,
                    activities: Optional[list[str]] = None, cat: Optional[dict] = None,
                    collective_dir: str = C.COLLECTIVE_DIR, th: dict = GRADE_TH) -> dict:
    cat = cat or load_catalogue()
    acts = activities or ACTIVITY_ORDER
    pts = key_points(natal)
    cusps = P.placidus_cusps(natal)
    jd0 = A.local_midnight_jd(from_local, tz)
    jd1 = A.local_midnight_jd(from_local + timedelta(days=n_days), tz)
    coll = [e for e in C.load_range(jd0 - 5, jd1 + 5, collective_dir)
            if e["kind"] in ("voc_moon", "solar_eclipse", "lunar_eclipse", "station_retrograde", "station_direct")]
    stations = [A.local_date_of_iso(e["t_utc"], tz) for e in coll
                if e["kind"].startswith("station_") and e["body"] == "mercury"]
    out = {a: {"days": [], "top_days": [], "windows": [], "avoid_days": [], "reasons": {}} for a in acts}
    for i in range(n_days):
        d = from_local + timedelta(days=i)
        df = day_factors(d, tz, pts, cusps, coll)
        df["mercury_station_dist"] = min((abs((date.fromisoformat(x) - d).days) for x in stations), default=99)
        for a in acts:
            s = score_day(a, df, pts, cat)
            s["grade"] = grade(s["R"], s["gates"], th)
            day = {"local_date": d.isoformat(), "R": s["R"], "grade": s["grade"], "factors": s["factors"],
                   "_parts": s["parts"]}
            out[a]["days"].append(day)
            if s["grade"] == "avoid":
                trig = s["gates"] or [min(s["parts"], key=lambda p: p["contribution"])["factor"]] if s["parts"] else s["gates"]
                out[a]["avoid_days"].append({"local_date": d.isoformat(), "R": s["R"], "trigger": trig})
    for a in acts:
        days = out[a]["days"]
        out[a]["top_days"] = top_days(days)
        out[a]["windows"] = windows(days)
        for d in days:
            if d["local_date"] in out[a]["top_days"]:
                out[a]["reasons"][d["local_date"]] = reasons(d["_parts"])
    return {"schema_version": SCHEMA, "chart_key": P.chart_key(natal), "tz": tz,
            "horizon": {"from_local": from_local.isoformat(),
                        "to_local": (from_local + timedelta(days=n_days - 1)).isoformat()},
            "calibration_version": cat["version"], "grade_thresholds": th,
            "factors_disabled": sorted(f["id"] for f in cat["factors"] if not f["enabled"]),
            "activities": out}


def public(doc: dict) -> dict:
    """best_days.json as written (internal instance parts dropped)."""
    out = json.loads(json.dumps(doc))
    for a in out["activities"].values():
        for d in a["days"]:
            d.pop("_parts", None)
    return out


def all_windows(doc: dict) -> list[dict]:
    """Windows of every activity, in the shape cal_scoring.notifications() takes."""
    return [{"activity": a, **w} for a, v in doc["activities"].items() for w in v["windows"]]


def dumps(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write-catalogue", action="store_true")
    args = ap.parse_args()
    if args.write_catalogue:
        idx, _ = cal_corpus.load()
        cat = build_catalogue(idx)
        with open(CATALOGUE, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(cat, ensure_ascii=False, indent=1) + "\n")
        for f in cat["factors"]:
            print(f"{f['id']} {f['name']:22} enabled={f['enabled']!s:5} grounding={len(f['grounding'])}")


if __name__ == "__main__":
    main()
