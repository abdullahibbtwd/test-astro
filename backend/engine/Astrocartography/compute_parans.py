#!/usr/bin/env python3
"""compute_parans.py — ACG spec 10: parans (latitude crossings) at the birth moment.

A paran is a latitude φ at which planet A is on angle α while planet B is on angle β.
Line A-α sits at longitude λ = RA_A + h_α(φ, δ_A) − GAST (spec 01 §4), so the two
lines cross where

    f(φ) = n180( h_α(φ, δ_A) − h_β(φ, δ_B) − (RA_B − RA_A) ) = 0

    h_MC = 0,  h_IC = 180,  h_ASC = −H₀,  h_DSC = +H₀,  H₀ = acos(−tan φ · tan δ)

which does not depend on GAST: the crossing is a property of the whole latitude.

Scope (spec 10 §2): the 10 planets; every angle combination per unordered pair except
meridian × meridian (12 per pair × 45 pairs); latitudes −80…+80 inside each horizon
body's circumpolar limit. Roots: sample every 0.05°, take sign changes of f that are
not wrap jumps (|Δf| > 90), refine by bisection to 1e-9°.

Deterministic. No LLM, no network. Reads the equatorial data already in acg.json.
"""

from __future__ import annotations

import json
import math
import os
import sys
from itertools import combinations
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from acg_constants import (  # noqa: E402
    ANGLES, BODY_DISPLAY, BODY_ORDER, LAT_MAX, LAT_MIN, PARAN_BISECT_TOL, PARAN_SAMPLE_STEP,
    PARAN_WRAP_JUMP, PARANS_SCHEMA_VERSION, PLANET_TR, READ_IN_V1,
)
from acg_geo import n180  # noqa: E402

MERIDIAN = ("MC", "IC")
READ_BODIES = tuple(b for b in BODY_ORDER if READ_IN_V1[b])


def hour_angle(angle: str, lat: float, dec: float) -> Optional[float]:
    """h_angle(φ, δ) in degrees, or None where the body never reaches the horizon."""
    if angle == "MC":
        return 0.0
    if angle == "IC":
        return 180.0
    x = -math.tan(math.radians(lat)) * math.tan(math.radians(dec))
    if abs(x) > 1.0 + 1e-12:
        return None
    h0 = math.degrees(math.acos(max(-1.0, min(1.0, x))))
    return -h0 if angle == "ASC" else h0


def _lat_range(angle_a: str, dec_a: float, angle_b: str, dec_b: float) -> tuple[float, float]:
    lo, hi = LAT_MIN, LAT_MAX
    for angle, dec in ((angle_a, dec_a), (angle_b, dec_b)):
        if angle in MERIDIAN:
            continue
        lim = 90.0 - abs(dec) if abs(dec) >= 1e-9 else 90.0
        lo, hi = max(lo, -lim), min(hi, lim)
    return lo, hi


def _roots(f, lo: float, hi: float) -> list[float]:
    if hi <= lo:
        return []
    n = int(math.floor((hi - lo) / PARAN_SAMPLE_STEP))
    xs = [lo + i * PARAN_SAMPLE_STEP for i in range(n + 1)]
    if xs[-1] < hi:
        xs.append(hi)
    vals = [f(x) for x in xs]
    roots = []
    for (x0, f0), (x1, f1) in zip(zip(xs, vals), zip(xs[1:], vals[1:])):
        if f0 is None or f1 is None:
            continue
        if f0 == 0.0:
            roots.append(x0)
            continue
        if (f0 < 0) == (f1 < 0) or abs(f1 - f0) > PARAN_WRAP_JUMP:
            continue
        a, b, fa = x0, x1, f0
        while b - a > PARAN_BISECT_TOL:
            m = 0.5 * (a + b)
            fm = f(m)
            if fm is None:
                break
            if (fm < 0) == (fa < 0):
                a, fa = m, fm
            else:
                b = m
        roots.append(0.5 * (a + b))
    if vals and vals[-1] == 0.0:
        roots.append(xs[-1])
    return roots


def compute_parans(acg: dict) -> dict:
    """acg.json dict -> parans.json dict (empty list when acg is absent)."""
    out = {"schema_version": PARANS_SCHEMA_VERSION, "status": acg.get("status", "absent"),
           "parans": []}
    if acg.get("status") != "ok":
        out["absence"] = acg.get("absence")
        return out
    gast = acg["meta"]["gast_deg"]
    eq = {b["body"]: b["equatorial"] for b in acg["bodies"]}
    parans = []
    for A, B in combinations(READ_BODIES, 2):
        ra_a, dec_a = eq[A]["ra"], eq[A]["dec"]
        ra_b, dec_b = eq[B]["ra"], eq[B]["dec"]
        d_ra = ra_b - ra_a
        for alpha in ANGLES:
            for beta in ANGLES:
                if alpha in MERIDIAN and beta in MERIDIAN:
                    continue

                def f(lat, alpha=alpha, beta=beta):
                    ha, hb = hour_angle(alpha, lat, dec_a), hour_angle(beta, lat, dec_b)
                    if ha is None or hb is None:
                        return None
                    return n180(ha - hb - d_ra)

                lo, hi = _lat_range(alpha, dec_a, beta, dec_b)
                for lat in _roots(f, lo, hi):
                    ha = hour_angle(alpha, lat, dec_a)
                    parans.append({
                        "id": f"{A}-{alpha}__{B}-{beta}",
                        "a": {"body": A, "angle": alpha},
                        "b": {"body": B, "angle": beta},
                        "lat": lat,
                        "crossing_lon": n180(ra_a + ha - gast),
                    })
    parans.sort(key=lambda p: (p["lat"], p["id"]))
    # an id can repeat when one combination crosses at two latitudes: suffix by order
    seen: dict[str, int] = {}
    for p in parans:
        seen[p["id"]] = seen.get(p["id"], 0) + 1
        if seen[p["id"]] > 1:
            p["id"] = f"{p['id']}#{seen[p['id']]}"
    out["parans"] = parans
    return out


def pair_key(p: dict) -> str:
    """Alphabetical lowercase pair key, as used by the affinity table's parans block."""
    return "-".join(sorted((p["a"]["body"], p["b"]["body"])))


# ---------------------------------------------------------------------------
# Map layer
# ---------------------------------------------------------------------------

def to_geojson(parans: dict, step_deg: float = 10.0) -> dict:
    """One LineString per paran along its latitude (−180…180, vertices every 10° so
    web-mercator renderers draw it straight), plus a Point at the crossing."""
    feats = []
    n = int(round(360.0 / step_deg))
    for p in parans.get("parans", []):
        lat = round(p["lat"], 4)
        props = {"kind": "paran", "id": p["id"],
                 "planets": [p["a"]["body"], p["b"]["body"]],
                 "angles": [p["a"]["angle"], p["b"]["angle"]]}
        feats.append({"type": "Feature", "properties": props,
                      "geometry": {"type": "LineString",
                                   "coordinates": [[round(-180.0 + i * step_deg, 4), lat]
                                                   for i in range(n + 1)]}})
        feats.append({"type": "Feature", "properties": {**props, "kind": "paran_crossing"},
                      "geometry": {"type": "Point",
                                   "coordinates": [round(p["crossing_lon"], 4), lat]}})
    return {"type": "FeatureCollection", "features": feats}


# ---------------------------------------------------------------------------
# Near a place (spec 10 §4) — shared by locate and scoring
# ---------------------------------------------------------------------------

def parans_near(parans: dict, lat: float) -> list[dict]:
    """The ≤ PARANS_PER_PLACE parans within ±PARAN_ORB_DEG of ``lat``, closest first
    (ties by id). Each row carries |Δφ|, the weight and the display fields."""
    from acg_constants import KM_PER_DEG_LAT, PARAN_ORB_DEG, PARANS_PER_PLACE, W_PARAN
    rows = []
    for p in parans.get("parans", []):
        d = abs(lat - p["lat"])
        if d <= PARAN_ORB_DEG:
            rows.append((d, p["id"], p))
    rows.sort(key=lambda r: (r[0], r[1]))
    out = []
    for d, _, p in rows[:PARANS_PER_PLACE]:
        km = d * KM_PER_DEG_LAT
        out.append({"id": p["id"], "a": p["a"], "b": p["b"], "pair": pair_key(p),
                    "dlat_deg": d, "dlat_km": round(km, 1),
                    "weight": W_PARAN * (1.0 - d / PARAN_ORB_DEG),
                    "north_south": "north" if lat >= p["lat"] else "south"})
    return out


def parans_display(near: list[dict]) -> list[dict]:
    out = []
    for r in near:
        a, b = r["a"]["body"], r["b"]["body"]
        km = r["dlat_km"]
        out.append({"id": r["id"], "planets_en": [BODY_DISPLAY[a], BODY_DISPLAY[b]],
                    "planets_tr": [PLANET_TR[a], PLANET_TR[b]], "north_south": r["north_south"],
                    "distance_km_rounded": "<10" if km < 10 else int(km / 10 + 0.5) * 10,
                    "label_en": "Latitude crossing", "label_tr": "Enlem kesişimi"})
    return out


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"
