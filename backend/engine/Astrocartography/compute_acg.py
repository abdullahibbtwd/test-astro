#!/usr/bin/env python3
"""compute_acg.py — ACG spec 01: angular lines of every body at the birth instant.

Deterministic. No LLM, no network. Given the natal ``chart.json`` (L1), compute for
each body the four in-mundo lines — MC (upper culmination), IC (lower culmination),
ASC (rising) and DSC (setting) — as geographic polylines, and emit:

    acg.json      canonical, unsplit vertices (validated against acg_schema.json)
    acg.geojson   FeatureCollection for the map UI, split at the antimeridian

Method (index D1/D2): each body's true apparent RA/declination (equator of date)
from Swiss Ephemeris with L1's own flags (Moshier + speed; see exploration report
C1) plus FLG_EQUATORIAL, against Greenwich apparent sidereal time; geometric
horizon (altitude 0, no refraction, geocentric). Hour angle H = GAST + λ − RA:

    MC   H = 0      λ = n180(ra − gast)
    IC   H = 180    λ = n180(ra − gast + 180)
    ASC  H = −H0    λ = n180(ra − H0 − gast)      H0 = acos(−tan φ · tan δ)
    DSC  H = +H0    λ = n180(ra + H0 − gast)

ASC/DSC exist only for |φ| ≤ 90 − |δ|; the exact limit points are always inserted so
the curves close onto the MC line (at −sign(δ)·φ_lim) and the IC line (at +sign(δ)·φ_lim).

The birth instant is L1's: ``jd_ut = compute_chart.julian_day_ut(meta.utc)`` — the
same function on the same UTC timestamp, so it is bit-identical (report C2).
Non-exact birth times produce an absence contract (index D5).

    python Astrocartography/compute_acg.py --chart path/to/chart.json --out-dir DIR
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, os.path.join(_ROOT, "d_layer")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import swisseph as swe  # type: ignore[import-not-found]  # noqa: E402

from acg_constants import (  # noqa: E402
    ACG_EXTRA_FLAG, BODIES, FLAG_NAMES, LAT_MAX, LAT_MIN, LAT_STEP,
    LINE_UNCERTAINTY_DEG_PER_MIN, METHOD, NODE_OUT_OF_SCOPE, SCHEMA_VERSION,
)
from acg_geo import n180, split_antimeridian  # noqa: E402

SCHEMA_PATH = os.path.join(_HERE, "acg_schema.json")


def _l1():
    """L1's time/ephemeris knobs, imported lazily (compute_chart pulls timezonefinder)."""
    import compute_chart  # noqa: WPS433
    return compute_chart


def latitudes() -> list[float]:
    n = int(round((LAT_MAX - LAT_MIN) / LAT_STEP))
    return [LAT_MIN + i * LAT_STEP for i in range(n + 1)]


# ---------------------------------------------------------------------------
# Line construction
# ---------------------------------------------------------------------------

def _meridian(lon: float) -> list[list[float]]:
    return [[lon, lat] for lat in latitudes()]


H0_MAX_STEP = 0.5   # deg of hour angle between consecutive ASC/DSC vertices


def _densify(samples: list[tuple[float, float]], tan_d: float) -> list[tuple[float, float]]:
    """Near the circumpolar joins H₀ (and so the line's longitude) changes very fast
    with latitude: 0.25° latitude steps leave straight segments up to several degrees
    off the true curve. Where consecutive samples differ by more than H0_MAX_STEP in
    hour angle, insert vertices stepped evenly in H₀, placed exactly on the curve via
    the inverse φ = atan(−cos H₀ / tan δ). Latitude order is preserved (φ is monotone
    in H₀ for a fixed δ). Existing samples are kept unchanged."""
    if abs(tan_d) < 1e-12 or len(samples) < 2:
        return samples
    out = [samples[0]]
    for (lat1, h1), (lat2, h2) in zip(samples, samples[1:]):
        gap = abs(h2 - h1)
        if gap > H0_MAX_STEP:
            k = int(math.ceil(gap / H0_MAX_STEP))
            for i in range(1, k):
                h = h1 + (h2 - h1) * i / k
                lat = math.degrees(math.atan(-math.cos(math.radians(h)) / tan_d))
                if lat1 < lat < lat2:
                    out.append((lat, h))
        out.append((lat2, h2))
    return out


def _horizon_lines(ra: float, dec: float, gast: float) -> tuple[dict, dict, float]:
    """ASC and DSC vertex lists (ascending latitude) + the circumpolar limit."""
    if abs(dec) < 1e-9:
        phi_lim = 90.0
    else:
        phi_lim = 90.0 - abs(dec)
    sgn = 1.0 if dec > 0 else (-1.0 if dec < 0 else 0.0)
    tan_d = math.tan(math.radians(dec))

    samples: list[tuple[float, float]] = []            # (lat, H0)
    for lat in latitudes():
        if abs(lat) >= phi_lim:                         # limit points added exactly below
            continue
        x = -math.tan(math.radians(lat)) * tan_d
        samples.append((lat, math.degrees(math.acos(max(-1.0, min(1.0, x))))))

    mc_join: Optional[float] = None
    ic_join: Optional[float] = None
    if sgn != 0.0:
        mc_at, ic_at = -sgn * phi_lim, sgn * phi_lim
        if LAT_MIN <= mc_at <= LAT_MAX:
            samples.append((mc_at, 0.0))               # tan φ tan δ = −1 → H0 = 0
            mc_join = mc_at
        if LAT_MIN <= ic_at <= LAT_MAX:
            samples.append((ic_at, 180.0))             # tan φ tan δ = +1 → H0 = 180
            ic_join = ic_at
    samples.sort(key=lambda s: s[0])
    samples = _densify(samples, tan_d)

    asc = [[n180(ra - h0 - gast), lat] for lat, h0 in samples]
    dsc = [[n180(ra + h0 - gast), lat] for lat, h0 in samples]
    joins = {"MC_at_lat": mc_join, "IC_at_lat": ic_join}
    return ({"vertices": asc, "joins": dict(joins)},
            {"vertices": dsc, "joins": dict(joins)}, phi_lim)


def body_lines(ra: float, dec: float, gast: float) -> dict:
    mc_lon = n180(ra - gast)
    asc, dsc, phi_lim = _horizon_lines(ra, dec, gast)
    return {
        "circumpolar_lat_limit": phi_lim,
        "lines": {
            "MC": {"vertices": _meridian(mc_lon)},
            "IC": {"vertices": _meridian(n180(mc_lon + 180.0))},
            "ASC": asc,
            "DSC": dsc,
        },
    }


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def _meta(chart_meta: dict, jd_ut: Optional[float], gast: Optional[float]) -> dict:
    return {
        "jd_ut": jd_ut,
        "gast_deg": gast,
        "flags": list(FLAG_NAMES),
        "ephemeris": chart_meta.get("ephemeris", "moshier"),
        "node_type": chart_meta.get("node_type", "mean"),
        "method": METHOD,
        "sampling": {"lat_min": LAT_MIN, "lat_max": LAT_MAX, "lat_step": LAT_STEP},
        "time_precision": chart_meta.get("time_precision"),
        "line_uncertainty_deg_per_min": LINE_UNCERTAINTY_DEG_PER_MIN,
    }


def _absent(chart_meta: dict, reason: str, detail: Optional[str] = None,
            jd_ut: Optional[float] = None) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "meta": _meta(chart_meta, jd_ut, None),
        "status": "absent",
        "absence": {"reason": reason, "detail": detail},
        "bodies": [],
    }


def jd_ut_of(chart: dict) -> Optional[float]:
    utc = (chart.get("meta") or {}).get("utc")
    if not utc:
        return None
    return _l1().julian_day_ut(datetime.fromisoformat(utc))


def compute_acg(chart: dict) -> dict:
    """Natal chart (L1 dict) -> acg.json dict. Never raises for data problems:
    they become ``status: absent`` with a closed-enum reason (spec 01 §8)."""
    meta = chart.get("meta") or {}
    precision = meta.get("time_precision")
    if precision != "exact":
        return _absent(meta, "birth_time_not_exact", str(precision))
    jd_ut = jd_ut_of(chart)
    if jd_ut is None:
        return _absent(meta, "missing_utc_instant")

    flags = _l1().EPHE_FLAG | ACG_EXTRA_FLAG
    try:
        gast = swe.sidtime(jd_ut) * 15.0             # apparent sidereal time, degrees
        bodies = []
        for body, swe_id, _display, read in BODIES:
            xx, _ = swe.calc_ut(jd_ut, swe_id, flags)
            ra, dec = xx[0], xx[1]
            entry = {
                "body": body,
                "read_in_v1": read,
                "out_of_scope": None if read else NODE_OUT_OF_SCOPE,
                "equatorial": {"ra": ra, "dec": dec, "dist": xx[2]},
            }
            entry.update(body_lines(ra, dec, gast))
            bodies.append(entry)
    except swe.Error as err:
        return _absent(meta, "ephemeris_error", str(err), jd_ut)

    return {
        "schema_version": SCHEMA_VERSION,
        "meta": _meta(meta, jd_ut, gast),
        "status": "ok",
        "absence": None,
        "bodies": bodies,
    }


def to_geojson(acg: dict) -> dict:
    """acg.json -> GeoJSON FeatureCollection: one Feature per (body, angle),
    MultiLineString split at the antimeridian, coordinates rounded to 4 dp."""
    features = []
    for b in acg.get("bodies", []):
        for angle, line in b["lines"].items():
            parts = split_antimeridian(line["vertices"])
            if not parts:
                continue
            coords = [[[round(lon, 4), round(lat, 4)] for lon, lat in part] for part in parts]
            features.append({
                "type": "Feature",
                "properties": {"body": b["body"], "angle": angle,
                               "read_in_v1": b["read_in_v1"]},
                "geometry": {"type": "MultiLineString", "coordinates": coords},
            })
    return {"type": "FeatureCollection", "features": features}


def validate_acg(acg: dict) -> None:
    """Raise jsonschema.ValidationError if ``acg`` breaks acg_schema.json."""
    import jsonschema
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        schema = json.load(fh)
    jsonschema.validate(acg, schema)


def dumps(obj) -> str:
    """The one serialisation used for every ACG artifact (determinism, spec 01 C8)."""
    return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"


def write_acg(acg: dict, acg_path: str, geojson_path: str) -> None:
    """Validate on write (spec 01 §7.3), then write both artifacts."""
    validate_acg(acg)
    with open(acg_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(dumps(acg))
    with open(geojson_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(to_geojson(acg), ensure_ascii=False, separators=(",", ":")) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="Compute astrocartography lines (ACG spec 01).")
    ap.add_argument("--chart", required=True, help="natal chart.json from compute_chart")
    ap.add_argument("--out-dir", default=".")
    args = ap.parse_args()
    with open(args.chart, encoding="utf-8") as fh:
        chart = json.load(fh)
    acg = compute_acg(chart)
    write_acg(acg, os.path.join(args.out_dir, "acg.json"),
              os.path.join(args.out_dir, "acg.geojson"))
    print(f"status={acg['status']} bodies={len(acg['bodies'])} -> {args.out_dir}")


if __name__ == "__main__":
    main()
