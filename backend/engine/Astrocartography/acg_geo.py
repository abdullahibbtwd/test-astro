#!/usr/bin/env python3
"""acg_geo.py — spherical geometry for the ACG layer (spec 01 §6, spec 02 §3).

Pure functions on a spherical Earth (R = 6371.0 km). Longitudes are degrees east,
latitudes degrees north. No astrology here.
"""

from __future__ import annotations

import math
from typing import Optional

from acg_constants import EARTH_RADIUS_KM, SEGMENT_LAT_WINDOW_DEG


def n180(x: float) -> float:
    """Normalise a longitude with ((x + 180) % 360) - 180 (spec 01 §3)."""
    return ((x + 180.0) % 360.0) - 180.0


# ---------------------------------------------------------------------------
# Antimeridian split (GeoJSON only; acg.json keeps the unsplit vertex list)
# ---------------------------------------------------------------------------

def split_antimeridian(vertices: list[list[float]]) -> list[list[list[float]]]:
    """Split a [lon, lat] polyline wherever two consecutive vertices differ by more
    than 180° of longitude. An interpolated vertex at ±180 is inserted on both
    sides of every split. Returns the parts (a MultiLineString's coordinates)."""
    if not vertices:
        return []
    parts: list[list[list[float]]] = [[list(vertices[0])]]
    for (lon1, lat1), (lon2, lat2) in zip(vertices, vertices[1:]):
        d = lon2 - lon1
        if abs(d) > 180.0:
            # unwrap lon2 next to lon1, find where the unwrapped segment hits ±180
            edge = 180.0 if d < 0 else -180.0          # side of lon1
            lon2u = lon2 + (360.0 if d < 0 else -360.0)
            span = lon2u - lon1
            t = (edge - lon1) / span if span else 0.0
            lat_x = lat1 + t * (lat2 - lat1)
            parts[-1].append([edge, lat_x])
            parts.append([[-edge, lat_x]])
        parts[-1].append([lon2, lat2])
    return [p for p in parts if len(p) >= 2]


# ---------------------------------------------------------------------------
# Distances (spec 02 §3)
# ---------------------------------------------------------------------------

def _xyz(lon: float, lat: float) -> tuple[float, float, float]:
    lo, la = math.radians(lon), math.radians(lat)
    return (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))


def _lonlat(v: tuple[float, float, float]) -> tuple[float, float]:
    x, y, z = v
    return (math.degrees(math.atan2(y, x)),
            math.degrees(math.atan2(z, math.hypot(x, y))))


def _dot(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    n = math.sqrt(_dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n) if n else a


def central_angle(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle angle (radians) between two points (haversine; stable when small)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2.0 * math.asin(min(1.0, math.sqrt(h)))


def gc_distance_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    return EARTH_RADIUS_KM * central_angle(lon1, lat1, lon2, lat2)


def _side(place_lon: float, point_lon: float) -> str:
    return "east" if n180(place_lon - point_lon) >= 0 else "west"


def meridian_distance(place_lon: float, place_lat: float,
                      line_lon: float) -> Optional[dict]:
    """Perpendicular distance from a place to a meridian line (MC/IC). Closed form:
    d = R·asin(cos φ·|sin Δλ|) for |Δλ| ≤ 90°; beyond that the meridian is on the far
    side of the globe and nothing is returned (spec 02 §3)."""
    dl = n180(place_lon - line_lon)
    if abs(dl) > 90.0:
        return None
    s = math.cos(math.radians(place_lat)) * abs(math.sin(math.radians(dl)))
    d = EARTH_RADIUS_KM * math.asin(min(1.0, s))
    # foot of the perpendicular on the meridian: the latitude where the great circle
    # through the place meets the meridian at right angles.
    foot_lat = math.degrees(math.atan2(math.tan(math.radians(place_lat)),
                                       math.cos(math.radians(dl))))
    return {"distance_km": d, "nearest_point": [line_lon, foot_lat],
            "side": _side(place_lon, line_lon)}


def point_to_arc(place: tuple[float, float], a: tuple[float, float],
                 b: tuple[float, float]) -> tuple[float, tuple[float, float]]:
    """Distance (km) from ``place`` to the minor great-circle arc a→b, clamped to the
    arc's endpoints (cross-track when the foot lies on the arc, else the nearer
    endpoint). Returns (distance_km, nearest [lon, lat])."""
    P, A, B = _xyz(*place), _xyz(*a), _xyz(*b)
    n = _cross(A, B)
    nn = math.sqrt(_dot(n, n))
    if nn < 1e-15:                                    # degenerate arc (a == b)
        return gc_distance_km(*place, *a), a
    n = (n[0] / nn, n[1] / nn, n[2] / nn)
    # foot of the perpendicular on the great circle through A, B
    pn = _dot(P, n)
    F = _norm((P[0] - pn * n[0], P[1] - pn * n[1], P[2] - pn * n[2]))
    # along-track check: F is on the minor arc iff it is "between" A and B
    if _dot(_cross(A, F), n) >= 0 and _dot(_cross(F, B), n) >= 0:
        d = EARTH_RADIUS_KM * math.asin(min(1.0, abs(pn)))
        return d, _lonlat(F)
    da, db = gc_distance_km(*place, *a), gc_distance_km(*place, *b)
    return (da, a) if da <= db else (db, b)


def polyline_distance(place_lon: float, place_lat: float,
                      vertices: list[list[float]]) -> Optional[dict]:
    """Minimum perpendicular distance from a place to an ASC/DSC polyline. Only the
    segments with a vertex within ±SEGMENT_LAT_WINDOW_DEG of the place's latitude
    are searched. Segments that jump the antimeridian are handled by the arc
    geometry itself (3-D vectors), so no unwrap is needed."""
    best: Optional[tuple[float, tuple[float, float]]] = None
    lo, hi = place_lat - SEGMENT_LAT_WINDOW_DEG, place_lat + SEGMENT_LAT_WINDOW_DEG
    for (lon1, lat1), (lon2, lat2) in zip(vertices, vertices[1:]):
        if not (lo <= lat1 <= hi or lo <= lat2 <= hi):
            continue
        d, pt = point_to_arc((place_lon, place_lat), (lon1, lat1), (lon2, lat2))
        if best is None or d < best[0]:
            best = (d, pt)
    if best is None:
        return None
    d, (plon, plat) = best
    return {"distance_km": d, "nearest_point": [plon, plat], "side": _side(place_lon, plon)}
