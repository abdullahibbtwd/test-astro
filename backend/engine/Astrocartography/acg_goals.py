#!/usr/bin/env python3
"""acg_goals.py — ACG spec 08: deterministic goal scoring (no LLM).

    load_affinity()                     -> the committed affinity table (08 §2)
    distance_weight(d)                  -> w(d) (08 §3)
    band_of(P, N)                       -> band key (08 §4)
    line_distances(acg, lats, lons)     -> (n_points × 40) perpendicular distances, km
    score_point(acg, lat, lon, aff)     -> {goal: {S, P, N, band, contributions, contributors}}
    goal_scan(acg, aff, gazetteer, grid)-> arrays for goal_scan.npz (08 §6)
    aggregate(...)                      -> country / region aggregate (08 §5)
    heat_geojson(scan, goal)            -> goal_heat_<goal>.geojson (08 §6)

The city path (``score_point``) and the vectorised scan use the SAME distance kernel
(``line_distances``), so a city's score is identical on both paths (08 §7 S6). The
kernel reproduces ``acg_geo.meridian_distance`` / ``polyline_distance`` exactly for
every line within the 1,000 km orb: closed form for MC/IC, and for ASC/DSC the
clamped point-to-arc minimum over the segments within ±15° of latitude.
"""

from __future__ import annotations

import io
import json
import math
import os
import sys
from functools import lru_cache
from typing import Iterable, Optional

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from acg_constants import (  # noqa: E402
    AGG_COUNTRY_FRAC, AGG_COUNTRY_MIN, AGG_REGION_FRAC, AGG_REGION_MIN, ANGLES,
    BAND_MIXED_MIN, BAND_MIXED_RATIO, BAND_NO_EMPHASIS_PN, BAND_STRONG, BAND_SUPPORTIVE,
    BANDS, BODY_ORDER, CONTRIBUTOR_MIN, EARTH_RADIUS_KM, GOAL_ORDER, MAX_ORB_KM,
    PARAN_ORB_DEG, PARANS_PER_PLACE, READ_IN_V1, SEGMENT_LAT_WINDOW_DEG, W_PARAN,
)

AFFINITY_PATH = os.path.join(_ROOT, "principles_grounding", "acg_goal_affinity.json")
SCAN_SCHEMA_VERSION = "acg-goalscan-1"

# The 40 read lines, in a fixed order: body order (Sun..Pluto) × (MC, IC, ASC, DSC).
READ_BODIES: tuple[str, ...] = tuple(b for b in BODY_ORDER if READ_IN_V1[b])
LINE_KEYS: tuple[tuple[str, str], ...] = tuple((b, a) for b in READ_BODIES for a in ANGLES)


# ---------------------------------------------------------------------------
# Affinity table
# ---------------------------------------------------------------------------

def affinity_sha256(path: str = AFFINITY_PATH) -> Optional[str]:
    import hashlib
    if not os.path.exists(path):
        return None
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


@lru_cache(maxsize=4)
def _load_affinity_cached(path: str, mtime: float) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_affinity(path: str = AFFINITY_PATH) -> dict:
    return _load_affinity_cached(path, os.path.getmtime(path))


def affinity_matrix(aff: dict) -> np.ndarray:
    """(40 lines × 11 goals) matrix of A in LINE_KEYS × GOAL_ORDER order (0 if absent)."""
    m = np.zeros((len(LINE_KEYS), len(GOAL_ORDER)), dtype=np.float64)
    cells = aff.get("cells", {})
    for i, (b, a) in enumerate(LINE_KEYS):
        cell = cells.get(f"{b}|{a}") or {}
        for j, g in enumerate(GOAL_ORDER):
            m[i, j] = float((cell.get(g) or {}).get("A", 0.0))
    return m


def cell_contributors(aff: dict, body: str, angle: str, goal: str) -> list[str]:
    return list(((aff.get("cells", {}).get(f"{body}|{angle}") or {}).get(goal) or {})
                .get("contributors", []))


# ---------------------------------------------------------------------------
# Distance weight and bands
# ---------------------------------------------------------------------------

def distance_weight(d: float) -> float:
    """w(d): 1 to 150 km, linear to 0.5 at 400 km, linear to 0 at 1,000 km; excluded beyond."""
    if d <= 150.0:
        return 1.0
    if d <= 400.0:
        return 1.0 - 0.5 * (d - 150.0) / 250.0
    if d <= 1000.0:
        return 0.5 - 0.5 * (d - 400.0) / 600.0
    return 0.0


def distance_weight_np(d: np.ndarray) -> np.ndarray:
    w = np.where(d <= 150.0, 1.0,
                 np.where(d <= 400.0, 1.0 - 0.5 * (d - 150.0) / 250.0,
                          np.where(d <= 1000.0, 0.5 - 0.5 * (d - 400.0) / 600.0, 0.0)))
    return np.where(np.isfinite(d), w, 0.0)


def band_of(P: float, N: float) -> str:
    """08 §4, evaluated in order."""
    S = P - N
    if P + N < BAND_NO_EMPHASIS_PN:
        return "no_emphasis"
    hi, lo = max(P, N), min(P, N)
    if hi >= BAND_MIXED_MIN and lo >= BAND_MIXED_RATIO * hi:
        return "mixed"
    if S >= BAND_STRONG:
        return "strongly_supportive"
    if S >= BAND_SUPPORTIVE:
        return "supportive"
    if S <= -BAND_SUPPORTIVE:
        return "challenging"
    return "no_emphasis"


_BAND_CODES = ("no_emphasis", "mixed", "strongly_supportive", "supportive", "challenging")


def band_codes_np(P: np.ndarray, N: np.ndarray) -> np.ndarray:
    """Vectorised band_of -> int8 index into _BAND_CODES."""
    S = P - N
    hi, lo = np.maximum(P, N), np.minimum(P, N)
    out = np.zeros(P.shape, dtype=np.int8)                       # default no_emphasis
    out = np.where(S <= -BAND_SUPPORTIVE, 4, out)
    out = np.where(S >= BAND_SUPPORTIVE, 3, out)
    out = np.where(S >= BAND_STRONG, 2, out)
    out = np.where((hi >= BAND_MIXED_MIN) & (lo >= BAND_MIXED_RATIO * hi), 1, out)
    out = np.where(P + N < BAND_NO_EMPHASIS_PN, 0, out)
    return out.astype(np.int8)


def band_label(band: str, lang: str = "tr") -> str:
    return BANDS[band][0 if lang == "tr" else 1]


# ---------------------------------------------------------------------------
# Distance kernel (shared by the city path and the scan)
# ---------------------------------------------------------------------------

def _unit(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    lo, la = np.radians(lon), np.radians(lat)
    return np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], axis=-1)


def _haversine_np(lon1, lat1, lon2, lat2) -> np.ndarray:
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(lon2 - lon1)
    h = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return EARTH_RADIUS_KM * 2.0 * np.arcsin(np.minimum(1.0, np.sqrt(h)))


def _meridian_np(lats: np.ndarray, lons: np.ndarray, line_lon: float) -> np.ndarray:
    dl = ((lons - line_lon + 180.0) % 360.0) - 180.0
    s = np.cos(np.radians(lats)) * np.abs(np.sin(np.radians(dl)))
    d = EARTH_RADIUS_KM * np.arcsin(np.minimum(1.0, s))
    return np.where(np.abs(dl) > 90.0, np.inf, d)


def _polyline_np(lats: np.ndarray, lons: np.ndarray, verts: list) -> np.ndarray:
    """Min clamped point-to-arc distance, searching per point only the segments with a
    vertex within ±SEGMENT_LAT_WINDOW_DEG of its latitude (as acg_geo does)."""
    out = np.full(lats.shape, np.inf)
    if len(verts) < 2 or lats.size == 0:
        return out
    V = np.asarray(verts, dtype=np.float64)
    a_lon, a_lat, b_lon, b_lat = V[:-1, 0], V[:-1, 1], V[1:, 0], V[1:, 1]
    A, B = _unit(a_lon, a_lat), _unit(b_lon, b_lat)
    n = np.cross(A, B)
    nn = np.linalg.norm(n, axis=1)
    degenerate = nn < 1e-15
    n = n / np.where(degenerate, 1.0, nn)[:, None]
    P_all = _unit(lons, lats)

    # Bounding cone per segment: every point of the minor arc AB lies within
    # half = angle(A, B)/2 of the normalised midpoint M, so angle(P, M) − half is a
    # lower bound on the distance. Pairs whose bound exceeds the orb cannot score and
    # skip the exact arithmetic; the exact result is kept for every pair within orb.
    M = A + B
    M /= np.linalg.norm(M, axis=1).clip(min=1e-300)[:, None]
    half = 0.5 * np.arccos(np.clip(np.einsum("sk,sk->s", A, B), -1.0, 1.0))
    reach = MAX_ORB_KM / EARTH_RADIUS_KM + 1e-9
    # angle(P, M) <= reach + half  <=>  P·M >= cos(reach + half)
    cos_thr = np.cos(np.minimum(reach + half, np.pi))
    W = SEGMENT_LAT_WINDOW_DEG
    chunk = 4096
    for s0 in range(0, lats.size, chunk):
        P = P_all[s0:s0 + chunk]
        plat, plon = lats[s0:s0 + chunk], lons[s0:s0 + chunk]
        pi, si = np.nonzero((P @ M.T) >= cos_thr[None, :])             # m × s -> pairs
        # per-point window: at least one segment vertex within ±W of the point
        keep = ((np.abs(a_lat[si] - plat[pi]) <= W) | (np.abs(b_lat[si] - plat[pi]) <= W))
        pi, si = pi[keep], si[keep]
        if pi.size == 0:
            continue
        Pp, ns = P[pi], n[si]
        pn = np.einsum("ik,ik->i", Pp, ns)
        F = Pp - pn[:, None] * ns
        F /= np.linalg.norm(F, axis=1).clip(min=1e-300)[:, None]
        c1 = np.einsum("ik,ik->i", ns, np.cross(A[si], F))
        c2 = np.einsum("ik,ik->i", ns, np.cross(F, B[si]))
        on_arc = (c1 >= 0) & (c2 >= 0) & ~degenerate[si]
        d_perp = EARTH_RADIUS_KM * np.arcsin(np.minimum(1.0, np.abs(pn)))
        da = _haversine_np(plon[pi], plat[pi], a_lon[si], a_lat[si])
        db = _haversine_np(plon[pi], plat[pi], b_lon[si], b_lat[si])
        d = np.where(on_arc, d_perp, np.minimum(da, db))
        best = np.full(P.shape[0], np.inf)
        np.minimum.at(best, pi, d)
        out[s0:s0 + chunk] = best
    return out


def line_distances(acg: dict, lats: Iterable[float], lons: Iterable[float]) -> np.ndarray:
    """(n_points × 40) perpendicular distances (km; inf when not measurable) to the
    40 read lines in LINE_KEYS order."""
    lats = np.asarray(list(lats) if not isinstance(lats, np.ndarray) else lats, dtype=np.float64)
    lons = np.asarray(list(lons) if not isinstance(lons, np.ndarray) else lons, dtype=np.float64)
    bodies = {b["body"]: b for b in acg.get("bodies", [])}
    D = np.full((lats.size, len(LINE_KEYS)), np.inf)
    for j, (body, angle) in enumerate(LINE_KEYS):
        line = bodies[body]["lines"][angle]
        if not line["vertices"]:
            continue
        if angle in ("MC", "IC"):
            D[:, j] = _meridian_np(lats, lons, line["vertices"][0][0])
        else:
            D[:, j] = _polyline_np(lats, lons, line["vertices"])
    return D


# ---------------------------------------------------------------------------
# Scores
# ---------------------------------------------------------------------------

def _pns(Wt: np.ndarray, Am: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Wt: n × 40 distance weights, Am: 40 × 11 affinity -> (P, N) each n × 11."""
    P = np.zeros((Wt.shape[0], Am.shape[1]))
    N = np.zeros_like(P)
    for g in range(Am.shape[1]):
        c = Wt * Am[:, g][None, :]
        P[:, g] = np.clip(c, 0, None).sum(axis=1)
        N[:, g] = np.clip(-c, 0, None).sum(axis=1)
    return P, N


def paran_affinity(aff: dict, pair: str) -> np.ndarray:
    """Apar(A,B,g) for the 11 goals (spec 10 §6), 0 where the table has no entry."""
    blk = (aff.get("parans") or {}).get(pair) or {}
    return np.array([float((blk.get(g) or {}).get("A", 0.0)) for g in GOAL_ORDER])


def paran_contributors(aff: dict, pair: str, goal: str) -> list[str]:
    return list((((aff.get("parans") or {}).get(pair) or {}).get(goal) or {})
                .get("contributors", []))


def _paran_terms(parans: Optional[dict], lat: float, aff: dict) -> list[dict]:
    """The near parans of one latitude with weight and Apar (spec 10 §4, §6)."""
    if not parans:
        return []
    from compute_parans import parans_near  # noqa: WPS433
    rows = parans_near(parans, lat)
    for r in rows:
        r["weight"] = W_PARAN * (1.0 - r["dlat_deg"] / PARAN_ORB_DEG)   # current constant
        r["Apar"] = paran_affinity(aff, r["pair"])
    return rows


def score_point(acg: dict, lat: float, lon: float, aff: dict,
                parans: Optional[dict] = None) -> dict:
    """The city path (08 §3 + spec 10 §6): full per-goal result for one place.
    ``parans`` (parans.json) adds the near parans' contributions; None = lines only."""
    D = line_distances(acg, [lat], [lon])[0]
    Am = affinity_matrix(aff)
    Wt = distance_weight_np(D)
    P, N = _pns(Wt[None, :], Am)
    pterms = _paran_terms(parans, lat, aff)
    for r in pterms:
        c = r["weight"] * r["Apar"]
        P[0] += np.clip(c, 0, None)
        N[0] += np.clip(-c, 0, None)
    out: dict = {}
    for gi, goal in enumerate(GOAL_ORDER):
        paran_contribs = []
        for r in pterms:
            c = float(r["weight"] * r["Apar"][gi])
            paran_contribs.append({"kind": "paran", "id": r["id"], "pair": r["pair"],
                                   "a": r["a"], "b": r["b"], "dlat_deg": r["dlat_deg"],
                                   "dlat_km": r["dlat_km"], "w": r["weight"],
                                   "A": float(r["Apar"][gi]), "contribution": c})
        contributions = []
        contributors: list[str] = []
        for j, (body, angle) in enumerate(LINE_KEYS):
            if not (D[j] <= MAX_ORB_KM):
                continue
            c = float(Wt[j] * Am[j, gi])
            contributions.append({"body": body, "angle": angle,
                                  "distance_km": float(D[j]), "w": float(Wt[j]),
                                  "A": float(Am[j, gi]), "contribution": c})
            if abs(c) >= CONTRIBUTOR_MIN:
                for rid in cell_contributors(aff, body, angle, goal):
                    if rid not in contributors:
                        contributors.append(rid)
        contributions.sort(key=lambda r: (-abs(r["contribution"]), r["distance_km"]))
        for pc in paran_contribs:
            if abs(pc["contribution"]) >= CONTRIBUTOR_MIN:
                for rid in paran_contributors(aff, pc["pair"], goal):
                    if rid not in contributors:
                        contributors.append(rid)
        p, n = float(P[0, gi]), float(N[0, gi])
        out[goal] = {"S": p - n, "P": p, "N": n, "band": band_of(p, n),
                     "contributions": contributions, "paran_contributions": paran_contribs,
                     "contributors": sorted(contributors)}
    return out


def goal_scores_summary(scores: dict) -> dict:
    """The compact per-goal block attached to readings (bands + numbers, no text)."""
    return {g: {"band": s["band"], "band_label_tr": band_label(s["band"], "tr"),
                "band_label_en": band_label(s["band"], "en"),
                "S": round(s["S"], 4), "P": round(s["P"], 4), "N": round(s["N"], 4)}
            for g, s in scores.items()}


def _paran_pn(lats: np.ndarray, parans: Optional[dict], aff: dict
              ) -> tuple[np.ndarray, np.ndarray]:
    """Vectorised paran P/N (n × 11): per point the ≤ 2 closest parans within ±1°,
    ties broken by id — the same selection as compute_parans.parans_near."""
    n = lats.size
    P = np.zeros((n, len(GOAL_ORDER)))
    N = np.zeros_like(P)
    rows = (parans or {}).get("parans") or []
    if not rows or n == 0:
        return P, N
    from compute_parans import pair_key  # noqa: WPS433
    order = sorted(range(len(rows)), key=lambda i: rows[i]["id"])      # id tie-break
    plat = np.array([rows[i]["lat"] for i in order])
    Apar = np.stack([paran_affinity(aff, pair_key(rows[i])) for i in order])   # m × 11
    for s0 in range(0, n, 8192):
        lat = lats[s0:s0 + 8192]
        d = np.abs(lat[:, None] - plat[None, :])                                  # k × m
        # stable argsort on distance keeps the id order for exact ties
        idx = np.argsort(d, axis=1, kind="stable")[:, :PARANS_PER_PLACE]
        dsel = np.take_along_axis(d, idx, axis=1)
        w = np.where(dsel <= PARAN_ORB_DEG, W_PARAN * (1.0 - dsel / PARAN_ORB_DEG), 0.0)
        c = w[:, :, None] * Apar[idx]                                             # k × 2 × 11
        P[s0:s0 + 8192] = np.clip(c, 0, None).sum(axis=1)
        N[s0:s0 + 8192] = np.clip(-c, 0, None).sum(axis=1)
    return P, N


def score_arrays(acg: dict, lats: np.ndarray, lons: np.ndarray, Am: np.ndarray,
                 parans: Optional[dict] = None, aff: Optional[dict] = None
                 ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    D = line_distances(acg, lats, lons)
    P, N = _pns(distance_weight_np(D), Am)
    if parans and aff is not None:
        pp, pn = _paran_pn(np.asarray(lats, dtype=np.float64), parans, aff)
        P, N = P + pp, N + pn
    return D, P, N


# ---------------------------------------------------------------------------
# Goal scan (08 §6)
# ---------------------------------------------------------------------------

def goal_scan(acg: dict, aff: dict, gazetteer: list[dict], grid: Optional[dict],
              parans: Optional[dict] = None) -> dict:
    """-> dict of numpy arrays for goal_scan.npz. Cities are in gazetteer order
    sorted by id; grid points in the grid's own order. ``parans`` adds the paran
    contributions (spec 10 §6); None = lines only."""
    Am = affinity_matrix(aff)
    cities = sorted(gazetteer, key=lambda c: c["id"])
    c_lat = np.array([c["lat"] for c in cities], dtype=np.float64)
    c_lon = np.array([c["lon"] for c in cities], dtype=np.float64)
    c_D, c_P, c_N = score_arrays(acg, c_lat, c_lon, Am, parans, aff)
    out = {
        "goals": np.array(GOAL_ORDER),
        "lines": np.array([f"{b}|{a}" for b, a in LINE_KEYS]),
        "city_ids": np.array([c["id"] for c in cities]),
        "city_S": (c_P - c_N).astype(np.float32),
        "city_P": c_P.astype(np.float32),
        "city_N": c_N.astype(np.float32),
        "city_dist": np.where(np.isfinite(c_D), c_D, -1.0).astype(np.float32),
    }
    if grid is not None and len(grid.get("lat", [])):
        g_lat = np.asarray(grid["lat"], dtype=np.float64)
        g_lon = np.asarray(grid["lon"], dtype=np.float64)
        _, g_P, g_N = score_arrays(acg, g_lat, g_lon, Am, parans, aff)
        out.update({
            "grid_lat": g_lat.astype(np.float32), "grid_lon": g_lon.astype(np.float32),
            "grid_S": (g_P - g_N).astype(np.float32),
            "grid_P": g_P.astype(np.float32), "grid_N": g_N.astype(np.float32),
        })
    return out


def save_scan(scan: dict, path: str) -> None:
    """np.savez_compressed writes fixed zip timestamps -> byte-identical re-runs."""
    buf = io.BytesIO()
    np.savez_compressed(buf, **scan)
    with open(path, "wb") as fh:
        fh.write(buf.getvalue())


def load_scan(path: str) -> dict:
    with np.load(path, allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def heat_geojson(scan: dict, goal: str) -> dict:
    """Grid points whose band != no_emphasis, with {band, S}; coords at 2 dp."""
    gi = list(GOAL_ORDER).index(goal)
    if "grid_P" not in scan:
        return {"type": "FeatureCollection", "features": []}
    P = scan["grid_P"][:, gi].astype(np.float64)
    N = scan["grid_N"][:, gi].astype(np.float64)
    codes = band_codes_np(P, N)
    feats = []
    for i in np.nonzero(codes != 0)[0]:
        feats.append({"type": "Feature",
                      "properties": {"band": _BAND_CODES[codes[i]], "S": round(float(P[i] - N[i]), 3)},
                      "geometry": {"type": "Point",
                                   "coordinates": [round(float(scan["grid_lon"][i]), 2),
                                                   round(float(scan["grid_lat"][i]), 2)]}})
    return {"type": "FeatureCollection", "features": feats}


# ---------------------------------------------------------------------------
# Aggregates (08 §5)
# ---------------------------------------------------------------------------

def aggregate(S: np.ndarray, P: np.ndarray, N: np.ndarray, *, kind: str) -> dict:
    """S, P, N: (n_points × 11) for the points inside one country/region.
    -> {goal: {S_agg, P_agg, N_agg, band, k, n_points, top_idx}}."""
    n = S.shape[0]
    if kind == "country":
        k = max(AGG_COUNTRY_MIN, math.ceil(AGG_COUNTRY_FRAC * n))
    else:
        k = max(AGG_REGION_MIN, math.ceil(AGG_REGION_FRAC * n))
    k = min(k, n)
    out = {}
    for gi, goal in enumerate(GOAL_ORDER):
        if n == 0:
            out[goal] = {"S_agg": 0.0, "P_agg": 0.0, "N_agg": 0.0, "band": "no_emphasis",
                         "k": 0, "n_points": 0, "top_idx": []}
            continue
        # top-k by S; stable tie-break by index
        top = np.lexsort((np.arange(n), -S[:, gi].astype(np.float64)))[:k]
        p, nn = float(P[top, gi].mean()), float(N[top, gi].mean())
        out[goal] = {"S_agg": float(S[top, gi].mean()), "P_agg": p, "N_agg": nn,
                     "band": band_of(p, nn), "k": int(k), "n_points": int(n),
                     "top_idx": [int(i) for i in top]}
    return out
