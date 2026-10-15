#!/usr/bin/env python3
"""acg_recommend.py — deterministic area views and ranking (ACG 07 §6.3, 08 §5, 09 §3).

No LLM. Everything here is a pure function of the chart's goal scan, the affinity
table and the committed geography files.

    area_view(kind, code, acg, scan, aff)       -> country / region data block (07 §6.3)
    rank(goal, scope, acg, scan, aff)           -> the "Where Should I Go?" ranking (09 §3)
    item_honesty(acg, lat, lon, aff, goal)      -> band, S/P/N, dominant/supporting/challenging
                                                   lines and contributor ids for one point
"""

from __future__ import annotations

import math
import os
import sys
from collections import Counter, defaultdict
from functools import lru_cache
from typing import Optional

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import acg_geodata as geo  # noqa: E402
import acg_goals as ag  # noqa: E402
from acg_constants import BAND_RANK, CONTRIBUTOR_MIN, GOAL_ORDER  # noqa: E402
from acg_geo import gc_distance_km  # noqa: E402

ELIGIBLE = ("strongly_supportive", "supportive")
CARD_GOALS = ("travel", "relocation", "career", "business", "love", "family")
COVER_KM = 400.0          # a line "covers" a point within this distance (07 §6.3)
CROSS_KM = 40.0           # a line "crosses" an area if it passes within ~half a grid cell
MAX_CITIES, MAX_REGIONS, MAX_COUNTRIES = 10, 5, 5
TR_CITIES, TR_REGIONS = 5, 3
CITY_MIN_SEP_KM = 150.0
TRADEOFF_N = 0.25


def _gi(goal: str) -> int:
    return list(GOAL_ORDER).index(goal)


# ---------------------------------------------------------------------------
# per-point honesty fields (09 §3.5)
# ---------------------------------------------------------------------------

# The chart's parans.json (spec 10). Set once per run by the caller (run_acg /
# acg_views) so every score here matches the goal scan, which includes parans.
PARANS: Optional[dict] = None


def set_parans(parans: Optional[dict]) -> None:
    global PARANS
    PARANS = parans


def item_honesty(acg: dict, lat: float, lon: float, aff: dict, goal: str) -> dict:
    sc = ag.score_point(acg, lat, lon, aff, PARANS)[goal]
    return _honesty_from(sc)


def line_key_of(item_line: Optional[dict]) -> str:
    """Diversity key: 'body|ANGLE' for a line, 'paran:<a>-<b>' for a paran (spec 10 §6)."""
    if not item_line:
        return "none"
    if item_line.get("kind") == "paran":
        return f"paran:{item_line['pair']}"
    return f"{item_line['body']}|{item_line['angle']}"


def _honesty_from(sc: dict) -> dict:
    pos = [c for c in sc["contributions"] if c["contribution"] > CONTRIBUTOR_MIN]
    neg = [c for c in sc["contributions"] if c["contribution"] < -CONTRIBUTOR_MIN]
    ppos = [c for c in sc.get("paran_contributions", []) if c["contribution"] > CONTRIBUTOR_MIN]
    pneg = [c for c in sc.get("paran_contributions", []) if c["contribution"] < -CONTRIBUTOR_MIN]
    line = lambda c: {"kind": "line", "body": c["body"], "angle": c["angle"],  # noqa: E731
                      "distance_km": round(c["distance_km"], 1),
                      "contribution": round(c["contribution"], 4)}
    par = lambda c: {"kind": "paran", "id": c["id"], "pair": c["pair"],  # noqa: E731
                     "bodies": [c["a"]["body"], c["b"]["body"]],
                     "angles": [c["a"]["angle"], c["b"]["angle"]],
                     "dlat_km": c["dlat_km"], "contribution": round(c["contribution"], 4)}
    dom_line = max(pos, key=lambda c: (c["contribution"], -c["distance_km"]), default=None)
    dom_par = max(ppos, key=lambda c: (c["contribution"], -c["dlat_km"]), default=None)
    # a paran is dominant only if no real line contributes more (spec 10 §6)
    if dom_par is not None and (dom_line is None or dom_par["contribution"] > dom_line["contribution"]):
        dom = par(dom_par)
    else:
        dom = line(dom_line) if dom_line else None
    supporting = ([line(c) for c in sorted(pos, key=lambda c: -c["contribution"])]
                  + [par(c) for c in sorted(ppos, key=lambda c: -c["contribution"])])
    challenging = ([line(c) for c in sorted(neg, key=lambda c: c["contribution"])]
                   + [par(c) for c in sorted(pneg, key=lambda c: c["contribution"])])
    return {"band": sc["band"], "S": round(sc["S"], 6), "P": round(sc["P"], 6),
            "N": round(sc["N"], 6), "dominant_line": dom,
            "supporting_lines": supporting, "challenging_lines": challenging,
            "contributors": sc["contributors"], "has_tradeoff": sc["N"] >= TRADEOFF_N}


# ---------------------------------------------------------------------------
# scan access
# ---------------------------------------------------------------------------

@lru_cache(maxsize=2)
def _city_table() -> tuple[list[dict], dict[str, int]]:
    cities = sorted(geo.load_cities(), key=lambda c: c["id"])
    return cities, {c["id"]: i for i, c in enumerate(cities)}


def _city_rows(scan: dict) -> list[dict]:
    """Gazetteer cities aligned with the scan's city arrays."""
    cities, idx = _city_table()
    if list(scan["city_ids"]) != [c["id"] for c in cities]:
        raise ValueError("goal_scan.npz was built against a different gazetteer")
    return cities


def _grid_mask(iso: Optional[str] = None, admin1: Optional[str] = None) -> np.ndarray:
    grid = geo.load_grid()
    m = np.ones(grid["lat"].shape, dtype=bool)
    if iso:
        m &= grid["iso_a2"] == iso
    if admin1:
        m &= grid["admin1_id"] == admin1
    return m


def _area_arrays(scan: dict, iso: Optional[str], admin1: Optional[str]):
    """S, P, N (n × 11) and lat/lon of the grid points + gazetteer cities in an area."""
    cities = _city_rows(scan)
    cmask = np.array([(iso is None or c["country_code"] == iso) and
                      (admin1 is None or c.get("admin1_id") == admin1) for c in cities])
    gmask = _grid_mask(iso, admin1) if "grid_S" in scan else np.zeros(0, dtype=bool)
    parts_S = [scan["city_S"][cmask]]
    parts_P = [scan["city_P"][cmask]]
    parts_N = [scan["city_N"][cmask]]
    lat = [np.array([c["lat"] for c, m in zip(cities, cmask) if m])]
    lon = [np.array([c["lon"] for c, m in zip(cities, cmask) if m])]
    if gmask.size:
        parts_S.append(scan["grid_S"][gmask])
        parts_P.append(scan["grid_P"][gmask])
        parts_N.append(scan["grid_N"][gmask])
        lat.append(scan["grid_lat"][gmask].astype(np.float64))
        lon.append(scan["grid_lon"][gmask].astype(np.float64))
    return (np.concatenate(parts_S).astype(np.float64), np.concatenate(parts_P).astype(np.float64),
            np.concatenate(parts_N).astype(np.float64), np.concatenate(lat), np.concatenate(lon),
            int(gmask.sum()) if gmask.size else 0)


def best_cities(scan: dict, goal: str, iso: Optional[str] = None,
                admin1: Optional[str] = None, n: int = 3) -> list[dict]:
    cities = _city_rows(scan)
    gi = _gi(goal)
    rows = []
    for i, c in enumerate(cities):
        if iso and c["country_code"] != iso:
            continue
        if admin1 and c.get("admin1_id") != admin1:
            continue
        P, N = float(scan["city_P"][i, gi]), float(scan["city_N"][i, gi])
        rows.append((float(scan["city_S"][i, gi]), c.get("population") or 0, c, P, N))
    rows.sort(key=lambda r: (-r[0], -r[1], r[2]["id"]))
    return [{"id": c["id"], "name": c["name"], "name_tr": c["name_tr"], "S": round(S, 6),
             "band": ag.band_of(P, N)} for S, _, c, P, N in rows[:n]]


# ---------------------------------------------------------------------------
# area view (07 §6.3, 08 §5)
# ---------------------------------------------------------------------------

def area_aggregate(scan: dict, kind: str, iso: Optional[str], admin1: Optional[str]) -> dict:
    S, P, N, lat, lon, n_grid = _area_arrays(scan, iso, admin1)
    agg = ag.aggregate(S, P, N, kind=kind)
    for g in agg.values():
        g["top_points"] = [[float(lat[i]), float(lon[i])] for i in g.pop("top_idx")]
    return {"aggregate": agg, "lat": lat, "lon": lon, "n_grid": n_grid}


def area_view(kind: str, code: str, acg: dict, scan: dict, aff: dict) -> dict:
    if kind == "country":
        meta = geo.country(code)
        iso, admin1 = code, None
    else:
        meta = geo.region(code)
        iso, admin1 = (meta or {}).get("iso_a2"), code
    if meta is None:
        return {"status": "absent", "absence": {"reason": f"unknown_{kind}", "detail": code}}
    ar = area_aggregate(scan, kind, iso, admin1)
    agg, lat, lon = ar["aggregate"], ar["lat"], ar["lon"]
    if lat.size == 0:
        return {"status": "absent", "absence": {"reason": "no_points_in_area", "detail": code}}

    # lines crossing / covering the area
    D = ag.line_distances(acg, lat, lon)
    crossing, cover = [], []
    for j, (body, angle) in enumerate(ag.LINE_KEYS):
        dmin = float(np.min(D[:, j]))
        if dmin <= CROSS_KM:
            crossing.append({"body": body, "angle": angle, "crosses": True})
        share = float(np.mean(D[:, j] <= COVER_KM))
        if share > 0:
            cover.append({"body": body, "angle": angle, "share": round(share, 4)})
    cover.sort(key=lambda c: (-c["share"], ag.LINE_KEYS.index((c["body"], c["angle"]))))

    bands = {g: {"band": a["band"], "S_agg": round(a["S_agg"], 6), "P_agg": round(a["P_agg"], 6),
                 "N_agg": round(a["N_agg"], 6), "k": a["k"], "n_points": a["n_points"]}
             for g, a in agg.items()}
    view = {"status": "ok", "absence": None, "kind": kind, "code": code,
            "name": meta.get("name"), "name_tr": meta.get("name_tr") or meta.get("name"),
            "iso_a2": iso, "bands": bands, "lines_crossing": crossing,
            "top_cover_lines": cover[:3],
            "best_cities": {g: best_cities(scan, g, iso, admin1) for g in GOAL_ORDER},
            "varies_by_region": False, "region_spread": {}}

    if kind == "country":
        regions = [r for r in geo.load_regions() if r["iso_a2"] == iso]
        per = []
        for r in regions:
            ra = area_aggregate(scan, "region", iso, r["admin1_id"])
            if ra["lat"].size == 0:
                continue
            per.append((r, ra["aggregate"]))
        spread = {}
        for g in CARD_GOALS:
            if len(per) < 2:
                break
            ranks = [(BAND_RANK[a[g]["band"]], a[g]["S_agg"], r) for r, a in per]
            best = max(ranks, key=lambda t: (t[0], t[1], t[2]["admin1_id"]))
            worst = min(ranks, key=lambda t: (t[0], t[1], t[2]["admin1_id"]))
            spread[g] = {"diff": best[0] - worst[0],
                         "best_region": {"admin1_id": best[2]["admin1_id"],
                                         "name": best[2]["name"],
                                         "name_tr": best[2].get("name_tr") or best[2]["name"],
                                         "band": per[[p[0] for p in per].index(best[2])][1][g]["band"]}}
        view["region_spread"] = spread
        view["varies_by_region"] = any(v["diff"] >= 2 for v in spread.values())
        # highlight the goals that really vary, preferring ones whose best region is
        # actually supportive (naming a "no emphasis" region as "best" says nothing)
        top2 = sorted(((g, v) for g, v in spread.items() if v["diff"] >= 2),
                      key=lambda kv: (kv[1]["best_region"]["band"] not in ELIGIBLE,
                                      -kv[1]["diff"], CARD_GOALS.index(kv[0])))[:2]
        view["varies_highlight"] = [{"goal": g, **v["best_region"]} for g, v in top2] \
            if view["varies_by_region"] else []
    return view


# ---------------------------------------------------------------------------
# ranking (09 §3)
# ---------------------------------------------------------------------------

def _city_candidates(scan: dict, goal: str, scope: str) -> list[dict]:
    cities = _city_rows(scan)
    gi = _gi(goal)
    out = []
    for i, c in enumerate(cities):
        if scope != "world" and c["country_code"] != scope:
            continue
        P, N = float(scan["city_P"][i, gi]), float(scan["city_N"][i, gi])
        band = ag.band_of(P, N)
        out.append({"city": c, "S": P - N, "P": P, "N": N, "band": band})
    out.sort(key=lambda r: (-r["S"], r["N"], -(r["city"].get("population") or 0),
                            r["city"]["id"]))
    return out


def rank_cities(acg: dict, scan: dict, aff: dict, goal: str, scope: str,
                limit: int = MAX_CITIES) -> tuple[list[dict], bool]:
    chosen: list[dict] = []
    per_line: Counter = Counter()
    per_country: Counter = Counter()
    for row in _city_candidates(scan, goal, scope):
        if row["band"] not in ELIGIBLE:
            continue
        c = row["city"]
        h = item_honesty(acg, c["lat"], c["lon"], aff, goal)
        dom = h["dominant_line"]
        dkey = line_key_of(dom)
        if per_line[dkey] >= 2:
            continue
        if scope == "world" and per_country[c["country_code"]] >= 3:
            continue
        if any(gc_distance_km(c["lon"], c["lat"], x["lon"], x["lat"]) < CITY_MIN_SEP_KM
               for x in chosen):
            continue
        per_line[dkey] += 1
        per_country[c["country_code"]] += 1
        chosen.append({"kind": "city", "id": c["id"], "name": c["name"], "name_tr": c["name_tr"],
                       "country": c["country_code"], "lat": c["lat"], "lon": c["lon"],
                       "population": c.get("population"), **h})
        if len(chosen) >= limit:
            break
    return chosen, len(chosen) < 3


def best_city_any(acg: dict, scan: dict, aff: dict, goal: str, scope: str) -> Optional[dict]:
    rows = _city_candidates(scan, goal, scope)
    if not rows:
        return None
    c = rows[0]["city"]
    return {"kind": "city", "id": c["id"], "name": c["name"], "name_tr": c["name_tr"],
            "country": c["country_code"], "lat": c["lat"], "lon": c["lon"],
            "population": c.get("population"),
            **item_honesty(acg, c["lat"], c["lon"], aff, goal)}


def _area_item(acg, aff, goal, kind, meta, agg_goal, extra=None) -> dict:
    """Honesty fields of an area: from its best (top-1) point, band/S from the aggregate."""
    lat, lon = agg_goal["top_points"][0]
    h = item_honesty(acg, lat, lon, aff, goal)
    h.update(band=agg_goal["band"], S=round(agg_goal["S_agg"], 6),
             P=round(agg_goal["P_agg"], 6), N=round(agg_goal["N_agg"], 6),
             has_tradeoff=agg_goal["N_agg"] >= TRADEOFF_N)
    item = {"kind": kind, "name": meta.get("name"),
            "name_tr": meta.get("name_tr") or meta.get("name"), **h}
    item.update(extra or {})
    return item


def rank_regions(acg, scan, aff, goal, scope, limit=MAX_REGIONS) -> list[dict]:
    gi_regions = [r for r in geo.load_regions() if scope == "world" or r["iso_a2"] == scope]
    scored = []
    for r in gi_regions:
        ar = area_aggregate(scan, "region", r["iso_a2"], r["admin1_id"])
        if ar["lat"].size == 0:
            continue
        a = ar["aggregate"][goal]
        if a["band"] in ELIGIBLE:
            scored.append((a["S_agg"], r, a))
    scored.sort(key=lambda t: (-t[0], t[1]["admin1_id"]))
    out, per_line, per_country = [], Counter(), Counter()
    for S, r, a in scored:
        item = _area_item(acg, aff, goal, "region", r, a,
                          {"id": r["admin1_id"], "country": r["iso_a2"]})
        dom = item["dominant_line"]
        dkey = line_key_of(dom)
        if per_line[dkey] >= 2 or per_country[r["iso_a2"]] >= 2:
            continue
        per_line[dkey] += 1
        per_country[r["iso_a2"]] += 1
        out.append(item)
        if len(out) >= limit:
            break
    return out


def rank_countries(acg, scan, aff, goal, limit=MAX_COUNTRIES) -> list[dict]:
    scored = []
    for c in geo.load_countries():
        ar = area_aggregate(scan, "country", c["iso_a2"], None)
        if ar["lat"].size == 0:
            continue
        a = ar["aggregate"][goal]
        if a["band"] in ELIGIBLE:
            scored.append((a["S_agg"], c, a))
    scored.sort(key=lambda t: (-t[0], t[1]["iso_a2"]))
    out = []
    for S, c, a in scored[:limit]:
        regions = rank_regions(acg, scan, aff, goal, c["iso_a2"], limit=1)
        out.append(_area_item(acg, aff, goal, "country", c, a, {
            "id": c["iso_a2"], "country": c["iso_a2"],
            "best_cities": best_cities(scan, goal, c["iso_a2"]),
            "best_region": ({"id": regions[0]["id"], "name": regions[0]["name"],
                             "name_tr": regions[0]["name_tr"]} if regions else None)}))
    return out


def rank(goal: str, scope: str, acg: dict, scan: dict, aff: dict) -> dict:
    """The full deterministic ranking (09 §3). No LLM."""
    scope = scope if scope == "world" else scope.upper()
    cities, thin = rank_cities(acg, scan, aff, goal, scope)
    out = {"goal": goal, "scope": scope, "cities": cities,
           "regions": rank_regions(acg, scan, aff, goal, scope),
           "countries": rank_countries(acg, scan, aff, goal) if scope == "world" else [],
           "thin_result": thin}
    if scope == "world":
        tc, _ = rank_cities(acg, scan, aff, goal, "TR", limit=TR_CITIES)
        tr = {"cities": tc, "regions": rank_regions(acg, scan, aff, goal, "TR",
                                                    limit=TR_REGIONS),
              "none_eligible": not tc}
        if not tc:
            best = best_city_any(acg, scan, aff, goal, "TR")
            tr["best_available"] = best
        out["turkey"] = tr
    return out
