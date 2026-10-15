"""collective_events.py - global sky events per calendar year (CAL_01 §2).

The same for every user; cached as ``cal_run/_collective/<year>.json``. A year
covers UTC [Y-01-01, Y+1-01-01). Events are keyed by instant (or start) in that
range; a retrograde period belongs to the year its station R falls in.

    python Calendar/collective_events.py --years 2026 2027     # build/refresh
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Optional

import cal_astro as A
import cal_constants as K

ENGINE_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
REPO_ROOT = os.path.normpath(os.path.join(ENGINE_ROOT, "..", ".."))  # astrology-app root
COLLECTIVE_DIR = os.path.join(REPO_ROOT, "cal_run", "_collective")

_MOON_STEP = 0.25                  # Moon is monotonic; 6 h < 30° / max relative speed
_ASPECT_ELONGS = [(0, "conjunction"), (60, "sextile"), (90, "square"), (120, "trine"),
                  (180, "opposition"), (240, "trine"), (270, "square"), (300, "sextile")]
_MARGIN = 40.0                     # days of look-around for periods / VOC across year edges


def _year_bounds(year: int) -> tuple[float, float]:
    return (A.jd_of(datetime(year, 1, 1, tzinfo=timezone.utc)),
            A.jd_of(datetime(year + 1, 1, 1, tzinfo=timezone.utc)))


def _date_utc(jd: float) -> str:
    return A.iso_utc(jd)[:10]


# --- lunations -------------------------------------------------------------------
def lunations(jd0: float, jd1: float) -> list[tuple[float, str]]:
    """[(jd, 'new'|'full')] exact Sun-Moon conjunctions / oppositions in [jd0, jd1)."""
    out = []
    for e, kind in ((0.0, "new"), (180.0, "full")):
        def f(j: float, e: float = e) -> float:
            return A.signed180(A.elongation(j) - e)
        jd, fv = jd0, f(jd0)
        while jd < jd1:
            nj = jd + _MOON_STEP
            nf = f(nj)
            if (fv < 0) != (nf < 0) and abs(fv) + abs(nf) < 180.0:
                root = A.bisect(f, jd, nj, fv, tol_days=1e-9)
                if jd0 <= root < jd1:
                    out.append((root, kind))
            jd, fv = nj, nf
    return sorted(out)


# --- sign ingresses ----------------------------------------------------------------
def ingresses(body: str, jd0: float, jd1: float, step: float) -> list[tuple[float, int, bool]]:
    """[(jd, sign_index_entered, retro)] sign-boundary crossings in [jd0, jd1)."""
    grid = A.sample_grid(body, jd0, jd1, step) if body not in ("sun", "moon") else \
        [jd0 + i * step for i in range(int((jd1 - jd0) / step) + 1)] + [jd1]
    out = []
    prev_j, prev_l = grid[0], A.lon(grid[0], body)
    for j in grid[1:]:
        l = A.lon(j, body)
        si0, si1 = int(prev_l // 30), int(l // 30)
        if si0 != si1:
            # the boundary crossed: forward -> start of si1; backward -> start of si0
            fwd = (si1 - si0) % 12 == 1
            boundary = (si1 * 30.0) if fwd else (si0 * 30.0)

            def g(x: float, b: float = boundary) -> float:
                return A.signed180(A.lon(x, body) - b)
            root = A.bisect(g, prev_j, j, g(prev_j), tol_days=1e-9)
            if jd0 <= root < jd1:
                entered = si1 if fwd else (si0 - 1) % 12
                out.append((root, entered % 12, not fwd))
        prev_j, prev_l = j, l
    return out


# --- VOC ----------------------------------------------------------------------------
def moon_aspects(jd0: float, jd1: float) -> list[tuple[float, str, str]]:
    """[(jd, body, aspect)] exact Moon major aspects to Sun..Pluto in [jd0, jd1)."""
    out = []
    n = int((jd1 - jd0) / _MOON_STEP) + 1
    grid = [jd0 + i * _MOON_STEP for i in range(n + 1)]
    moon = [A.lon(j, "moon") for j in grid]
    for body in K.VOC_BODIES:
        bl = [A.lon(j, body) for j in grid]
        for e, asp in _ASPECT_ELONGS:
            def f(x: float, e: float = e, body: str = body) -> float:
                return A.signed180(A.lon(x, "moon") - A.lon(x, body) - e)
            prev = A.signed180(moon[0] - bl[0] - e)
            for i in range(1, len(grid)):
                cur = A.signed180(moon[i] - bl[i] - e)
                if (prev < 0) != (cur < 0) and abs(prev) + abs(cur) < 180.0:
                    root = A.bisect(f, grid[i - 1], grid[i], prev, tol_days=1e-9)
                    if jd0 <= root < jd1:
                        out.append((root, body, asp))
                prev = cur
    return sorted(out)


def voc_periods(jd0: float, jd1: float) -> list[dict]:
    """VOC (modern): from the Moon's last exact major aspect before each sign
    ingress, until that ingress. Returned for ingresses in [jd0, jd1)."""
    ing = ingresses("moon", jd0 - 3, jd1, _MOON_STEP)
    asp = moon_aspects(jd0 - 5, jd1)
    out = []
    k = 0
    for ij, _si, _r in ing:
        if ij < jd0:
            continue
        while k + 1 < len(asp) and asp[k + 1][0] < ij:
            k += 1
        if not asp or asp[k][0] >= ij:
            continue
        sj, body, a = asp[k]
        out.append({"id": f"voc:{A.iso_utc(ij)}", "kind": "voc_moon",
                    "start_utc": A.iso_utc(sj), "end_utc": A.iso_utc(ij),
                    "last_aspect": {"body": body, "aspect": a}})
    return out


# --- year build -----------------------------------------------------------------------
def build_year(year: int) -> dict:
    jd0, jd1 = _year_bounds(year)
    events: list[dict] = []

    # eclipses first, so lunations can link to them
    ecl = []
    for t, kind in A.solar_eclipses(jd0, jd1):
        ecl.append((t, "solar", kind))
    for t, kind in A.lunar_eclipses(jd0, jd1):
        ecl.append((t, "lunar", kind))
    lun = lunations(jd0, jd1)

    def link(t: float, want: str) -> Optional[tuple[float, str]]:
        for lt, lk in lun:
            if lk == want and abs(lt - t) <= K.ECLIPSE_LUNATION_LINK_DAYS:
                return lt, lk
        return None

    ecl_by_lun: dict[str, str] = {}
    for t, sl, kind in sorted(ecl):
        lum = "sun" if sl == "solar" else "moon"
        lng = A.lon(t, lum)
        eid = f"ecl:{_date_utc(t)}:{sl}"
        l = link(t, "new" if sl == "solar" else "full")
        lid = f"lun:{_date_utc(l[0])}:{l[1]}" if l else None
        if lid:
            ecl_by_lun[lid] = eid
        events.append({"id": eid, "kind": f"{sl}_eclipse", "t_utc": A.iso_utc(t),
                       "eclipse_kind": kind, "sign": A.sign_key(lng),
                       "degree": A.deg_in_sign(lng), "lunation_id": lid})

    for t, kind in lun:
        lng = A.lon(t, "sun" if kind == "new" else "moon")   # full moon: the Moon's degree
        lid = f"lun:{_date_utc(t)}:{kind}"
        events.append({"id": lid, "kind": f"{kind}_moon", "t_utc": A.iso_utc(t),
                       "sign": A.sign_key(lng), "degree": A.deg_in_sign(lng),
                       "eclipse_id": ecl_by_lun.get(lid)})

    # stations + retrograde periods
    for body in K.STATION_BODIES:
        st = A.stations(body, jd0 - 400, jd1 + 400)
        for t, d in st:
            if jd0 <= t < jd1:
                lng = A.lon(t, body)
                events.append({"id": f"stn:{body}:{d}:{_date_utc(t)}",
                               "kind": "station_retrograde" if d == "R" else "station_direct",
                               "t_utc": A.iso_utc(t), "body": body,
                               "sign": A.sign_key(lng), "degree": A.deg_in_sign(lng)})
        for i, (t, d) in enumerate(st):
            if d == "R" and jd0 <= t < jd1 and i + 1 < len(st) and st[i + 1][1] == "D":
                te = st[i + 1][0]
                events.append({"id": f"rx:{body}:{_date_utc(t)}", "kind": "retrograde_period",
                               "body": body, "start_utc": A.iso_utc(t), "end_utc": A.iso_utc(te),
                               "sign_start": A.sign_key(A.lon(t, body)),
                               "sign_end": A.sign_key(A.lon(te, body))})

    # planet sign ingresses
    for body in K.INGRESS_BODIES:
        for t, si, retro in ingresses(body, jd0, jd1, 0.5):
            events.append({"id": f"ing:{body}:{A.SIGN_KEYS[si]}:{A.iso_utc(t)}",
                           "kind": "ingress", "t_utc": A.iso_utc(t), "body": body,
                           "sign": A.SIGN_KEYS[si], "retro": retro})

    # Moon ingresses + VOC
    for t, si, _ in ingresses("moon", jd0, jd1, _MOON_STEP):
        events.append({"id": f"min:{A.iso_utc(t)}", "kind": "moon_ingress",
                       "t_utc": A.iso_utc(t), "sign": A.SIGN_KEYS[si]})
    events.extend(voc_periods(jd0, jd1))

    events.sort(key=lambda e: (e.get("t_utc") or e["start_utc"], e["id"]))
    return {"schema_version": K.SCHEMA_COLLECTIVE, "year": year,
            "ephemeris": A.EPHEMERIS_NAME, "events": events}


def dumps(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def path_for(year: int, base: str = COLLECTIVE_DIR) -> str:
    return os.path.join(base, f"{year}.json")


def ensure_year(year: int, base: str = COLLECTIVE_DIR, rebuild: bool = False) -> dict:
    """Load the cached year, building it on first use (global cache, CAL_05 stage 1)."""
    p = path_for(year, base)
    if os.path.exists(p) and not rebuild:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("schema_version") == K.SCHEMA_COLLECTIVE and data.get("ephemeris") == A.EPHEMERIS_NAME:
            return data
    data = build_year(year)
    os.makedirs(base, exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(dumps(data))
    os.replace(tmp, p)
    return data


def load_range(jd0: float, jd1: float, base: str = COLLECTIVE_DIR) -> list[dict]:
    """All collective events of every year touching [jd0, jd1) (not filtered)."""
    y0 = A.jd_to_utc(jd0).year
    y1 = A.jd_to_utc(jd1).year
    out: list[dict] = []
    for y in range(y0, y1 + 1):
        out.extend(ensure_year(y, base)["events"])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--years", type=int, nargs="*", default=list(K.COLLECTIVE_BUILD_YEARS))
    ap.add_argument("--rebuild", action="store_true")
    args = ap.parse_args()
    for y in args.years:
        d = ensure_year(y, rebuild=args.rebuild)
        print(f"{y}: {len(d['events'])} events -> {path_for(y)}")


if __name__ == "__main__":
    main()
