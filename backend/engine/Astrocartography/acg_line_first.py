#!/usr/bin/env python3
"""acg_line_first.py — ACG spec 11 §5: line-first recommendations over viable destinations.

Astrology ranks; viability decides eligibility. The candidate set comes from
``acg_destinations.candidates`` (reviewed, not excluded, allowed by the viability
policy and the user's filters). The ranking recommends the user's strongest lines for
the goal and the viable places along each one. Filters never change any score (DV8).

No LLM. Uses the same scoring kernel as the goal scan (lines + parans), so every S
here equals the scan's value for the same point.
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from typing import Optional

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import acg_goals as ag  # noqa: E402
import acg_recommend as rec  # noqa: E402
from acg_constants import GOAL_ORDER  # noqa: E402
from acg_geo import gc_distance_km  # noqa: E402

A_MIN = 0.30                  # a line / paran is "strong" for a goal at A >= this
GROUP_LINES = 4               # line groups shown
MIN_REAL_LINES = 3            # of which at least this many real lines, when available
PER_LINE = 5                  # destinations per group
PER_COUNTRY_PER_LINE = 2
LINE_RADIUS_KM = 400.0        # a destination is "along" a line within this distance
PARAN_RADIUS_DEG = 1.0        # ... or within ±1° of a paran's latitude
MIN_SEP_KM = 150.0
FLAT_MAX, FLAT_PER_COUNTRY = 10, 3
TR_CITIES, TR_REGIONS = 5, 3


def _gi(goal: str) -> int:
    return list(GOAL_ORDER).index(goal)


def _line_ref(line: dict) -> dict:
    if line["kind"] == "paran":
        return {"kind": "paran", "id": line["id"], "pair": line["pair"],
                "bodies": line["bodies"], "angles": line["angles"]}
    return {"kind": "line", "body": line["body"], "angle": line["angle"]}


def strong_lines(aff: dict, goal: str, parans: Optional[dict]) -> list[dict]:
    """Every line with A(p,a,g) >= A_MIN and every paran with Apar >= A_MIN, strongest first."""
    from compute_parans import pair_key  # noqa: WPS433
    gi = _gi(goal)
    Am = ag.affinity_matrix(aff)
    out = []
    for j, (body, angle) in enumerate(ag.LINE_KEYS):
        if Am[j, gi] >= A_MIN:
            out.append({"kind": "line", "body": body, "angle": angle, "j": j,
                        "affinity": float(Am[j, gi])})
    for p in (parans or {}).get("parans", []):
        pk = pair_key(p)
        a = float(ag.paran_affinity(aff, pk)[gi])
        if a >= A_MIN:
            out.append({"kind": "paran", "id": p["id"], "pair": pk,
                        "bodies": [p["a"]["body"], p["b"]["body"]],
                        "angles": [p["a"]["angle"], p["b"]["angle"]], "lat": p["lat"],
                        "affinity": a})
    out.sort(key=lambda x: (-x["affinity"], x["kind"] != "line",
                            x.get("id") or f"{x['body']}|{x['angle']}"))
    return out


def _pick(members: list[int], dests: list[dict]) -> list[int]:
    chosen: list[int] = []
    per_c: Counter = Counter()
    for i in members:
        d = dests[i]
        if per_c[d["country"]] >= PER_COUNTRY_PER_LINE:
            continue
        if any(gc_distance_km(d["lon"], d["lat"], dests[k]["lon"], dests[k]["lat"]) < MIN_SEP_KM
               for k in chosen):
            continue
        chosen.append(i)
        per_c[d["country"]] += 1
        if len(chosen) >= PER_LINE:
            break
    return chosen


def _dest_item(acg, aff, goal, d: dict, line: dict, dist_km: float) -> dict:
    h = rec.item_honesty(acg, d["lat"], d["lon"], aff, goal)
    return {"kind": "destination", "id": d["id"], "name": d["name"], "name_tr": d["name_tr"],
            "country": d["country"], "admin1_id": d.get("admin1_id"), "size": d.get("size"),
            "dest_kind": d.get("kind"), "purposes": d.get("purposes", []),
            "appeal": d.get("appeal"), "lat": d["lat"], "lon": d["lon"],
            "population": d.get("population"), "reviewed": d.get("reviewed"),
            "group_line": _line_ref(line), "group_distance_km": round(dist_km, 1), **h}


def line_groups(goal: str, acg: dict, aff: dict, dests: list[dict]
                ) -> tuple[list[dict], list[dict]]:
    """-> (groups, lines_without_destinations) for one candidate set (spec 11 §5.2–5.5)."""
    lines = strong_lines(aff, goal, rec.PARANS)
    if not dests:
        return [], [{"line": _line_ref(ln), "affinity": round(ln["affinity"], 4)}
                    for ln in lines if ln["kind"] == "line"]
    gi = _gi(goal)
    lats = np.array([d["lat"] for d in dests], dtype=np.float64)
    lons = np.array([d["lon"] for d in dests], dtype=np.float64)
    D, P, N = ag.score_arrays(acg, lats, lons, ag.affinity_matrix(aff), rec.PARANS, aff)
    S = P[:, gi] - N[:, gi]
    eligible = [ag.band_of(float(P[i, gi]), float(N[i, gi])) in rec.ELIGIBLE
                for i in range(len(dests))]
    found: list[tuple[dict, list[int], np.ndarray]] = []
    without = []
    for ln in lines:
        if ln["kind"] == "line":
            dist = D[:, ln["j"]]
            near = dist <= LINE_RADIUS_KM
        else:
            dist = np.abs(lats - ln["lat"]) * 111.2
            near = np.abs(lats - ln["lat"]) <= PARAN_RADIUS_DEG
        members = [int(i) for i in np.nonzero(near)[0] if eligible[i]]
        members.sort(key=lambda i: (-S[i], dests[i].get("appeal") or 3, float(N[i, gi]),
                                    dests[i]["id"]))
        picked = _pick(members, dests)
        if picked:
            found.append((ln, picked, dist))
        elif ln["kind"] == "line":
            without.append({"line": _line_ref(ln), "affinity": round(ln["affinity"], 4)})
    # up to 4 groups: the strongest real lines first (at least 3 when available), then
    # the best remaining line or paran fills the rest (spec 11 §5.4)
    real = [f for f in found if f[0]["kind"] == "line"]
    chosen = real[:MIN_REAL_LINES]
    rest = [f for f in found if all(f is not c for c in chosen)]
    chosen += rest[:max(0, GROUP_LINES - len(chosen))]
    chosen.sort(key=lambda f: (-f[0]["affinity"], f[0]["kind"] != "line"))
    groups = [{"line": _line_ref(ln), "kind": ln["kind"], "affinity": round(ln["affinity"], 4),
               "destinations": [_dest_item(acg, aff, goal, dests[i], ln, float(dist[i]))
                                for i in picked]}
              for ln, picked, dist in chosen]
    return groups, without


def flat_list(groups: list[dict]) -> list[dict]:
    seen, rows = set(), []
    for g in groups:
        for d in g["destinations"]:
            if d["id"] not in seen:
                seen.add(d["id"])
                rows.append(d)
    rows.sort(key=lambda d: (-d["S"], d.get("appeal") or 3, d["id"]))
    out, per_c = [], Counter()
    for d in rows:
        if per_c[d["country"]] >= FLAT_PER_COUNTRY:
            continue
        per_c[d["country"]] += 1
        out.append(d)
        if len(out) >= FLAT_MAX:
            break
    return out


def rank_line_first(goal: str, scope: str, acg: dict, scan: dict, aff: dict,
                    filters: dict, *, include_unreviewed: bool = False) -> dict:
    """The v4 "Where Should I Go?" ranking (spec 11 §5). No LLM."""
    import acg_destinations as dst  # noqa: WPS433
    scope = scope if scope == "world" else scope.upper()
    country = None if scope == "world" else scope
    cands = dst.candidates(filters, include_unreviewed=include_unreviewed, country=country)
    groups, without = line_groups(goal, acg, aff, cands)
    flat = flat_list(groups)
    in_groups = [d for g in groups for d in g["destinations"]]
    active = set(filters.get("purpose") or [])
    by_purpose = {p: sorted({d["id"] for d in in_groups if p in (d.get("purposes") or [])})
                  for p in ("living", "travel") if p in active}
    admin1s = {d.get("admin1_id") for d in in_groups if d.get("admin1_id")}
    isos = {d["country"] for d in in_groups}
    regions = ([r for r in rec.rank_regions(acg, scan, aff, goal, scope, limit=10_000)
                if r["id"] in admin1s][:rec.MAX_REGIONS] if admin1s else [])
    countries = ([c for c in rec.rank_countries(acg, scan, aff, goal, limit=10_000)
                  if c["id"] in isos][:rec.MAX_COUNTRIES] if scope == "world" and isos else [])
    out = {"goal": goal, "scope": scope,
           "filters_applied": {k: v for k, v in filters.items() if k != "home_latlon"},
           "include_unreviewed": include_unreviewed,
           "by_line": groups, "lines_without_destinations": without,
           "by_purpose": by_purpose, "cities": flat, "regions": regions,
           "countries": countries, "thin_result": len(flat) < 3}
    regs = filters.get("regions") or ["all"]
    if scope == "world" and ("all" in regs or "turkey" in regs):
        tr_c = dst.candidates(filters, include_unreviewed=include_unreviewed,
                              ignore_size=True, country="TR")
        tg, tw = line_groups(goal, acg, aff, tr_c)
        tflat = flat_list(tg)[:TR_CITIES]
        t_admin = {d.get("admin1_id") for g in tg for d in g["destinations"]}
        tr = {"by_line": tg, "lines_without_destinations": tw, "cities": tflat,
              "regions": [r for r in rec.rank_regions(acg, scan, aff, goal, "TR", limit=81)
                          if r["id"] in t_admin][:TR_REGIONS],
              "none_eligible": not tflat}
        if not tflat:
            tr["best_available"] = rec.best_city_any(acg, scan, aff, goal, "TR")
        out["turkey"] = tr
    return out
