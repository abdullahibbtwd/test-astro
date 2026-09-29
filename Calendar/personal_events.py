"""personal_events.py - per-user calendar events (CAL_01 §3).

Rolling 12 months from ``from_local`` (default: today in the user's current tz).
Houses are natal Placidus (CAL_00 D7). The current location only sets the tz (D1).

Outputs ``personal_events.json`` (schema ``cal-events-1``):
  * transit episodes (T in Sun..Pluto, no Moon) to the 10 planets + ASC + MC
  * lunations / eclipses in the chart (natal house + hits)
  * stations on natal points
  * ``collective_refs``: the non-Moon collective events in the horizon, referenced
    by id with their local dates (not copied)
"""

from __future__ import annotations

import calendar
import hashlib
import json
import os
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import cal_astro as A
import cal_constants as K
import collective_events as C

POINT_KEYS = K.NATAL_PLANETS + K.NATAL_ANGLES


# --- natal ------------------------------------------------------------------------------
def natal_points(natal: dict) -> dict[str, float]:
    """{point_key: longitude}. Angles only when a birth time supports them."""
    pts = {p["name"].lower(): float(p["longitude"]) for p in natal["points"]
           if p["name"].lower() in K.NATAL_PLANETS}
    if natal.get("axes") and natal.get("confidence") != "unknown":
        pts["asc"] = float(natal["axes"]["ascendant"]["longitude"])
        pts["mc"] = float(natal["axes"]["mc"]["longitude"])
    return pts


def placidus_cusps(natal: dict) -> Optional[list[float]]:
    if natal.get("confidence") == "unknown":
        return None
    return (natal.get("sectors") or {}).get("placidus_cusps")


def chart_key(natal: dict) -> str:
    """Stable per-chart key: birth instant + precision + angles/cusps (location-dependent)."""
    meta = natal.get("meta") or {}
    blob = json.dumps({"utc": meta.get("utc"), "precision": meta.get("time_precision"),
                       "points": {k: round(v, 4) for k, v in natal_points(natal).items()},
                       "cusps": placidus_cusps(natal)}, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


# --- horizon -------------------------------------------------------------------------------
def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    y += d.year
    m += 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def horizon(from_local: date, tz: str, months: int = K.CALENDAR_MONTHS) -> tuple[date, date, float, float]:
    """(first_local_day, last_local_day, jd_start, jd_end): [local 00:00 first, local 00:00 after last)."""
    end_excl = add_months(from_local, months)
    return (from_local, end_excl - timedelta(days=1),
            A.local_midnight_jd(from_local, tz), A.local_midnight_jd(end_excl, tz))


# --- importance ----------------------------------------------------------------------------
def transit_importance(t: str, aspect: str, n: str) -> tuple[str, float]:
    i = round(K.W_T[t] * K.W_N[n] * K.W_A[aspect], 4)
    lvl = "major" if i >= K.IMPORTANCE_MAJOR else "moderate" if i >= K.IMPORTANCE_MODERATE else "minor"
    return lvl, i


def speed_class(body: str) -> str:
    return "slow" if body in K.SLOW_BODIES else "fast"


# --- transit windows ------------------------------------------------------------------------
def _elongs(angle: int) -> list[float]:
    return [float(angle)] if angle in (0, 180) else [float(angle), float(360 - angle)]


def _windows_for(body: str, grid: list[float], lons: list[float], nat: float,
                 e: float, orb: float) -> list[dict]:
    """Orb windows of (body - nat) around elongation e, with exacts, from a
    station-aware grid (monotonic between samples, cal_astro doc)."""
    def f(j: float) -> float:
        return A.signed180(A.lon(j, body) - nat - e)

    def g_edge(level: float):
        return lambda j: f(j) - level

    fs = [A.signed180(l - nat - e) for l in lons]
    wins: list[dict] = []
    cur: Optional[dict] = None
    if abs(fs[0]) <= orb:
        cur = {"start": grid[0], "exacts": [], "open_start": True}
    for i in range(1, len(grid)):
        j0, j1, f0, f1 = grid[i - 1], grid[i], fs[i - 1], fs[i]
        if abs(f0) + abs(f1) >= 180.0:           # wrap at ±180, far from any orb
            continue
        # events inside (j0, j1] in time order: entry, exact, exit
        evs: list[tuple[float, str]] = []
        crosses_zero = (f0 < 0) != (f1 < 0) or f1 == 0.0
        if crosses_zero:
            evs.append((A.bisect(f, j0, j1, f0), "exact"))
        for level in (-orb, orb):
            a0, a1 = f0 - level, f1 - level
            if (a0 < 0) != (a1 < 0):
                evs.append((A.bisect(g_edge(level), j0, j1, a0), "edge"))
        for t, kind in sorted(evs):
            if kind == "exact":
                if cur is None:                   # numerically touching the edge
                    cur = {"start": t, "exacts": [], "open_start": False}
                cur["exacts"].append(t)
            elif cur is None:
                cur = {"start": t, "exacts": [], "open_start": False}
            else:
                cur["end"] = t
                cur["open_end"] = False
                wins.append(cur)
                cur = None
    if cur is not None:
        cur["end"] = grid[-1]
        cur["open_end"] = True
        wins.append(cur)
    return wins


def _closest(body: str, nat: float, e: float, j0: float, j1: float) -> float:
    """Closest approach inside a window without an exact (a station inside orb)."""
    best_j, best = j0, 1e9
    n = max(8, int((j1 - j0) * 4))
    for k in range(n + 1):
        j = j0 + (j1 - j0) * k / n
        v = abs(A.signed180(A.lon(j, body) - nat - e))
        if v < best:
            best_j, best = j, v
    return best_j


def transit_episodes(points: dict[str, float], jd0: float, jd1: float,
                     margin: float = K.SCAN_MARGIN_DAYS) -> list[dict]:
    """Episodes overlapping [jd0, jd1), each merged across retrograde passes (CAL_01 §3.1)."""
    s0, s1 = jd0 - margin, jd1 + margin
    out: list[dict] = []
    for body in K.TRANSIT_BODIES:
        grid = A.sample_grid(body, s0, s1, 1.0)
        lons = [A.lon(j, body) for j in grid]
        orb = K.TRANSIT_ORB[body]
        for n in POINT_KEYS:
            if n not in points:
                continue
            for asp in K.ASPECT_ORDER:
                wins: list[dict] = []
                for e in _elongs(K.ASPECTS[asp]):
                    for w in _windows_for(body, grid, lons, points[n], e, orb):
                        w["e"] = e
                        wins.append(w)
                wins.sort(key=lambda w: w["start"])
                episodes: list[list[dict]] = []
                for w in wins:
                    if episodes and w["start"] - episodes[-1][-1]["end"] < K.EPISODE_MERGE_GAP_DAYS:
                        episodes[-1].append(w)
                    else:
                        episodes.append([w])
                for ep in episodes:
                    start, end = ep[0]["start"], max(w["end"] for w in ep)
                    if end < jd0 or start >= jd1:
                        continue
                    exacts = sorted(x for w in ep for x in w["exacts"])
                    rec = {"t_body": body, "aspect": asp, "n_point": n,
                           "start": start, "end": end, "exacts": exacts,
                           "truncated": bool(ep[0].get("open_start") or ep[-1].get("open_end"))}
                    if not exacts:
                        w = min(ep, key=lambda w: w["start"])
                        rec["closest"] = _closest(body, points[n], w["e"], w["start"], w["end"])
                    out.append(rec)
    return out


def phase_on(event: dict, jd: float) -> str:
    """approaching | exact_window | separating for a transit event at instant jd."""
    pivots = [A.jd_of(A.parse_iso_utc(t)) for t in event["exacts_utc"]] or \
        [A.jd_of(A.parse_iso_utc(event["closest_utc"]))]
    w = K.EXACT_WINDOW_DAYS[speed_class(event["t_body"])]
    if any(abs(jd - p) <= w for p in pivots):
        return "exact_window"
    return "approaching" if jd < pivots[0] else "separating"


# --- lunations / eclipses / stations in the chart ------------------------------------------
def _conj_opp_hits(lng: float, points: dict[str, float], orb: float) -> list[dict]:
    hits = []
    for n in POINT_KEYS:
        if n not in points:
            continue
        sep = abs(A.signed180(lng - points[n]))
        for asp, target in (("conjunction", 0.0), ("opposition", 180.0)):
            o = abs(sep - target)
            if o <= orb:
                hits.append({"point": n, "aspect": asp, "orb": round(o, 2)})
    return hits


def _lng_of(ev: dict) -> float:
    si = A.SIGN_KEYS.index(ev["sign"])
    return si * 30.0 + ev["degree"]


def lunation_events(coll: list[dict], points: dict, cusps: Optional[list[float]],
                    jd0: float, jd1: float, tz: str) -> list[dict]:
    out = []
    eclipses = {e["id"]: e for e in coll if e["kind"] in ("solar_eclipse", "lunar_eclipse")}
    for ev in coll:
        if ev["kind"] not in ("new_moon", "full_moon"):
            continue
        jd = A.jd_of(A.parse_iso_utc(ev["t_utc"]))
        if not (jd0 <= jd < jd1):
            continue
        ecl = eclipses.get(ev.get("eclipse_id") or "")
        src = ecl or ev
        lng = _lng_of(src)
        is_ecl = ecl is not None
        hits = _conj_opp_hits(lng, points, K.ECLIPSE_HIT_ORB if is_ecl else K.LUNATION_HIT_ORB)
        hit_pts = {h["point"] for h in hits}
        if (hit_pts & K.LUMINARIES_ANGLES) or (is_ecl and hits):
            imp = "major"
        elif is_ecl or hits:
            imp = "moderate"
        else:
            imp = "minor"
        t_utc = src["t_utc"]
        ld = A.local_date_of_iso(t_utc, tz)
        rec = {"id": (f"ecl:{ld}:{ecl['kind'].split('_')[0]}" if is_ecl
                      else f"lun:{ld}:{ev['kind'].split('_')[0]}"),
               "kind": ecl["kind"] if is_ecl else ev["kind"],
               "ref": src["id"], "t_utc": t_utc, "local_date": ld,
               "sign": src["sign"],
               "natal_house": A.house_of(lng, cusps) if cusps else None,
               "hits": hits, "importance": imp}
        if is_ecl:
            rec["eclipse_kind"] = ecl["eclipse_kind"]
            rec["lunation_ref"] = ev["id"]
        out.append(rec)
    return out


def station_events(coll: list[dict], points: dict, jd0: float, jd1: float, tz: str) -> list[dict]:
    out = []
    for ev in coll:
        if ev["kind"] not in ("station_retrograde", "station_direct"):
            continue
        jd = A.jd_of(A.parse_iso_utc(ev["t_utc"]))
        if not (jd0 <= jd < jd1):
            continue
        lng = _lng_of(ev)
        body = ev["body"]
        for n in POINT_KEYS:
            if n not in points:
                continue
            sep = abs(A.signed180(lng - points[n]))
            for asp in K.STATION_POINT_ASPECTS:
                o = abs(sep - K.ASPECTS[asp])
                if o > K.STATION_POINT_ORB:
                    continue
                if body in K.FAST_STATION_BODIES:
                    major = n in K.LUMINARIES_ANGLES
                else:
                    major = o <= K.STATION_POINT_MAJOR_ORB_SLOW
                d = "R" if ev["kind"] == "station_retrograde" else "D"
                out.append({"id": f"stp:{body}:{d}:{asp}:{n}:{A.local_date_of_iso(ev['t_utc'], tz)}",
                            "kind": "station_on_point", "ref": ev["id"], "body": body,
                            "direction": d, "aspect": asp, "n_point": n, "orb": round(o, 2),
                            "t_utc": ev["t_utc"], "local_date": A.local_date_of_iso(ev["t_utc"], tz),
                            "importance": "major" if major else "moderate"})
    return out


_REF_KINDS = {"new_moon", "full_moon", "solar_eclipse", "lunar_eclipse",
              "station_retrograde", "station_direct", "retrograde_period", "ingress"}


def collective_refs(coll: list[dict], jd0: float, jd1: float, tz: str) -> list[dict]:
    out = []
    for ev in coll:
        if ev["kind"] not in _REF_KINDS:
            continue
        if "t_utc" in ev:
            jd = A.jd_of(A.parse_iso_utc(ev["t_utc"]))
            if jd0 <= jd < jd1:
                out.append({"id": ev["id"], "kind": ev["kind"],
                            "local_date": A.local_date_of_iso(ev["t_utc"], tz)})
        else:
            s = A.jd_of(A.parse_iso_utc(ev["start_utc"]))
            e = A.jd_of(A.parse_iso_utc(ev["end_utc"]))
            if s < jd1 and e >= jd0:
                out.append({"id": ev["id"], "kind": ev["kind"],
                            "start_local": A.local_date_of_iso(ev["start_utc"], tz),
                            "end_local": A.local_date_of_iso(ev["end_utc"], tz)})
    return out


# --- assembly ----------------------------------------------------------------------------
def _transit_records(eps: list[dict], tz: str) -> list[dict]:
    recs = []
    for ep in eps:
        lvl, i = transit_importance(ep["t_body"], ep["aspect"], ep["n_point"])
        pivot = ep["exacts"][0] if ep["exacts"] else ep["closest"]
        rec = {"kind": "transit", "t_body": ep["t_body"], "aspect": ep["aspect"],
               "n_point": ep["n_point"],
               "start_utc": A.iso_utc(ep["start"]), "end_utc": A.iso_utc(ep["end"]),
               "exacts_utc": [A.iso_utc(x) for x in ep["exacts"]],
               "start_local": A.local_date(ep["start"], tz),
               "end_local": A.local_date(ep["end"], tz),
               "exacts_local": [A.local_date(x, tz) for x in ep["exacts"]],
               "importance": lvl, "I": i, "_pivot": pivot}
        if not ep["exacts"]:
            rec["closest_utc"] = A.iso_utc(ep["closest"])
        if ep["truncated"]:
            rec["truncated"] = True
        recs.append(rec)
    # ids: tr:<T>:<a>:<N>:<year of pivot><a,b,..> (deterministic)
    recs.sort(key=lambda r: (r["t_body"], r["aspect"], r["n_point"], r["_pivot"]))
    seen: dict[str, int] = {}
    for r in recs:
        base = f"tr:{r['t_body']}:{r['aspect']}:{r['n_point']}:{A.jd_to_utc(r['_pivot']).year}"
        k = seen.get(base, 0)
        seen[base] = k + 1
        r["id"] = base + chr(ord("a") + k)
        del r["_pivot"]
    return recs


def build_personal_events(natal: dict, tz: str, from_local: Optional[date] = None,
                          months: int = K.CALENDAR_MONTHS,
                          collective_dir: str = C.COLLECTIVE_DIR) -> dict:
    if from_local is None:
        from_local = datetime.now(ZoneInfo(tz)).date()
    first, last, jd0, jd1 = horizon(from_local, tz, months)
    points = natal_points(natal)
    cusps = placidus_cusps(natal)
    coll = C.load_range(jd0 - 1, jd1 + 1, collective_dir)

    events = _transit_records(transit_episodes(points, jd0, jd1), tz)
    events += lunation_events(coll, points, cusps, jd0, jd1, tz)
    events += station_events(coll, points, jd0, jd1, tz)

    def sort_key(e: dict) -> tuple:
        return (e.get("start_utc") or e["t_utc"], e["id"])
    events.sort(key=sort_key)
    return {"schema_version": K.SCHEMA_EVENTS, "chart_key": chart_key(natal), "tz": tz,
            "horizon": {"from_local": first.isoformat(), "to_local": last.isoformat()},
            "orbs": K.TRANSIT_ORB, "events": events,
            "collective_refs": collective_refs(coll, jd0, jd1, tz)}


def dumps(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def write(obj: dict, path: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(dumps(obj))
    os.replace(tmp, path)
    return path
