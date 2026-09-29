#!/usr/bin/env python3
"""acg_overall.py — "overall improvement" recommendations: which places help the most
across ALL 11 goals at once (an extension on top of ACG 08 / 11; deterministic, no LLM).

For every viable destination (acg_destinations.candidates, same policy and filters):

    S_g       the goal score for each of the 11 goals (08 §3 + parans, spec 10 §6)
    overall   O = mean_g S_g                         (equal weights by default)
    breadth   #goals with band supportive / strongly_supportive
    strain    #goals with band challenging

Eligible: O >= OVERALL_MIN and breadth >= BREADTH_MIN. Ranked by O (ties: breadth, then
appeal, then lower mean N). Diversity: <= 3 per country, >= 150 km apart, <= 2 per
dominant line (the line or paran with the largest positive contribution summed over
all goals). A Turkey block runs with the size default ignored, as in spec 11 §5.7.
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

OVERALL_MIN = 0.05            # mean score across the 11 goals must be at least this
BREADTH_MIN = 2               # ... and at least this many goals supported
MAX_PLACES, PER_COUNTRY, PER_LINE, MIN_SEP_KM = 10, 3, 2, 150.0
TR_PLACES = 5
ELIGIBLE = ("strongly_supportive", "supportive")


def _dominant(scores: dict) -> Optional[dict]:
    """The line/paran with the largest positive contribution summed over all goals."""
    tot: dict[str, float] = {}
    ref: dict[str, dict] = {}
    for g, sc in scores.items():
        for c in sc["contributions"]:
            k = f"{c['body']}|{c['angle']}"
            tot[k] = tot.get(k, 0.0) + max(0.0, c["contribution"])
            ref[k] = {"kind": "line", "body": c["body"], "angle": c["angle"],
                      "distance_km": round(c["distance_km"], 1)}
        for c in sc.get("paran_contributions", []):
            k = f"paran:{c['pair']}"
            tot[k] = tot.get(k, 0.0) + max(0.0, c["contribution"])
            ref[k] = {"kind": "paran", "id": c["id"], "pair": c["pair"],
                      "bodies": [c["a"]["body"], c["b"]["body"]], "dlat_km": c["dlat_km"]}
    if not tot or max(tot.values()) <= 0:
        return None
    k = max(sorted(tot), key=lambda x: tot[x])
    return {**ref[k], "total_contribution": round(tot[k], 4)}


def place_profile(acg: dict, aff: dict, d: dict) -> dict:
    """Full per-goal breakdown for one destination (the explanation's facts)."""
    scores = ag.score_point(acg, d["lat"], d["lon"], aff, rec.PARANS)
    goals = {g: {"band": s["band"], "S": round(s["S"], 4), "P": round(s["P"], 4),
                 "N": round(s["N"], 4)} for g, s in scores.items()}
    supported = sorted((g for g in GOAL_ORDER if goals[g]["band"] in ELIGIBLE),
                       key=lambda g: -goals[g]["S"])
    challenged = sorted((g for g in GOAL_ORDER if goals[g]["band"] == "challenging"),
                        key=lambda g: goals[g]["S"])
    mixed = [g for g in GOAL_ORDER if goals[g]["band"] == "mixed"]
    contributors: list[str] = []
    for g in supported[:3] + challenged[:2]:
        for rid in scores[g]["contributors"]:
            if rid not in contributors:
                contributors.append(rid)
    lines = []
    for g in supported[:3] + challenged[:2]:
        h = rec._honesty_from(scores[g])
        for ln in h["supporting_lines"] + h["challenging_lines"]:
            key = rec.line_key_of(ln)
            if key not in [rec.line_key_of(x) for x in lines]:
                lines.append(ln)
    return {"overall": round(float(np.mean([s["S"] for s in scores.values()])), 6),
            "goals": goals, "supported": supported, "challenged": challenged, "mixed": mixed,
            "breadth": len(supported), "strain": len(challenged),
            "dominant_line": _dominant(scores), "lines": lines,
            "contributors": contributors, "has_tradeoff": bool(challenged)}


def rank_overall(acg: dict, aff: dict, dests: list[dict], limit: int = MAX_PLACES) -> list[dict]:
    if not dests:
        return []
    lats = np.array([d["lat"] for d in dests])
    lons = np.array([d["lon"] for d in dests])
    _, P, N = ag.score_arrays(acg, lats, lons, ag.affinity_matrix(aff), rec.PARANS, aff)
    S = P - N
    O = S.mean(axis=1)
    codes = ag.band_codes_np(P, N)                                   # n × 11
    breadth = np.isin(codes, [2, 3]).sum(axis=1)                     # strongly / supportive
    order = sorted(range(len(dests)),
                   key=lambda i: (-O[i], -breadth[i], dests[i].get("appeal") or 3,
                                  float(N[i].mean()), dests[i]["id"]))
    chosen: list[dict] = []
    per_c, per_l = Counter(), Counter()
    for i in order:
        if O[i] < OVERALL_MIN or breadth[i] < BREADTH_MIN:
            continue
        d = dests[i]
        if per_c[d["country"]] >= PER_COUNTRY:
            continue
        if any(gc_distance_km(d["lon"], d["lat"], c["lon"], c["lat"]) < MIN_SEP_KM for c in chosen):
            continue
        prof = place_profile(acg, aff, d)
        lk = rec.line_key_of(prof["dominant_line"])
        if per_l[lk] >= PER_LINE:
            continue
        per_c[d["country"]] += 1
        per_l[lk] += 1
        chosen.append({"id": d["id"], "name": d["name"], "name_tr": d["name_tr"],
                       "country": d["country"], "admin1_id": d.get("admin1_id"),
                       "size": d.get("size"), "dest_kind": d.get("kind"), "lat": d["lat"],
                       "lon": d["lon"], "appeal": d.get("appeal"), **prof})
        if len(chosen) >= limit:
            break
    return chosen


def recommend_overall(acg: dict, aff: dict, filters: dict, scope: str = "world", *,
                      include_unreviewed: bool = False) -> dict:
    import acg_destinations as dst  # noqa: WPS433
    scope = scope if scope == "world" else scope.upper()
    cands = dst.candidates(filters, include_unreviewed=include_unreviewed,
                           country=None if scope == "world" else scope)
    places = rank_overall(acg, aff, cands)
    out = {"goal": "overall", "scope": scope,
           "filters_applied": {k: v for k, v in filters.items() if k != "home_latlon"},
           "include_unreviewed": include_unreviewed, "places": places,
           "thin_result": len(places) < 3,
           "method": {"overall": "mean of the 11 goal scores", "overall_min": OVERALL_MIN,
                      "breadth_min": BREADTH_MIN}}
    regs = filters.get("regions") or ["all"]
    if scope == "world" and ("all" in regs or "turkey" in regs):
        tr = dst.candidates(filters, include_unreviewed=include_unreviewed, ignore_size=True,
                            country="TR")
        out["turkey"] = {"places": rank_overall(acg, aff, tr, limit=TR_PLACES)}
    return out
