#!/usr/bin/env python3
"""
compute_chart.py  —  LAYER 1: deterministic chart computation

This module is a PURE FUNCTION:

    birth data + reading date  ->  fully-specified chart object (dict / JSON)

It performs ZERO interpretation. It only computes astronomical positions and
applies fixed lookup tables / formulas. The interpretation layer (the LLM)
consumes the output of this module and is the ONLY place where meaning is
assigned. This separation is the mechanism that prevents hallucinated chart
data: the model cannot invent an Ascendant, a sect, or a dignity because all
of those are computed here and handed to it as hard data.

Hard contract guaranteed by this module
----------------------------------------
1. A field is present in the output ONLY if it is real for the given birth
   precision. Fields that cannot be supported (e.g. Ascendant for an unknown
   birth time) are OMITTED, not faked. Absence means "cannot speak to this".
2. Every time-dependent field carries a confidence marker, and — for
   approximate births — an `unstable` flag when the value flips across the
   plausible time window.
3. Nothing here is interpreted. Sect, dignities, lots, aspects are all table
   lookups or formulas.

Astrology decisions are LOCKED in this file (see CHART_DECISIONS.md for the
rationale). Another engineer should not need to make astrology calls to
iterate on this code — only validate the tables and extend functionality.

Dependencies: pyswisseph, timezonefinder  (and stdlib zoneinfo, Python >=3.9)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional, cast
from zoneinfo import ZoneInfo

import swisseph as swe  # type: ignore[import-not-found]
from timezonefinder import TimezoneFinder

from chart_types import Chart

# ---------------------------------------------------------------------------
# REPRODUCIBILITY KNOBS
# ---------------------------------------------------------------------------
# Moshier is self-contained (no external .se1 files) and fully deterministic;
# arcsecond-level accuracy for the modern era is plenty for astrology. Switch
# to FLG_SWIEPH + set_ephe_path(<dir of .se1 files>) for max precision, but
# then you MUST ship and version-pin those files. Pin pyswisseph in your
# lockfile so identical birth data always yields a byte-identical chart.
EPHE_FLAG = swe.FLG_MOSEPH | swe.FLG_SPEED
EPHEMERIS_NAME = "moshier"

_tf = TimezoneFinder()

# ---------------------------------------------------------------------------
# CONSTANTS — zodiac, bodies
# ---------------------------------------------------------------------------
SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
ELEMENTS = ["fire", "earth", "air", "water"] * 3  # index by sign -> element

# (display name, swe id, traditional?)  — order is the canonical body order.
# Note: the lunar nodes ARE traditional (Ra's/Dhanab, Head/Tail of the Dragon)
# and are heavily used in the Arabic material, so they are flagged traditional.
# We use the MEAN node (the traditional choice). Outer planets are modern.
BODIES = [
    ("Sun", swe.SUN, True),
    ("Moon", swe.MOON, True),
    ("Mercury", swe.MERCURY, True),
    ("Venus", swe.VENUS, True),
    ("Mars", swe.MARS, True),
    ("Jupiter", swe.JUPITER, True),
    ("Saturn", swe.SATURN, True),
    ("Uranus", swe.URANUS, False),
    ("Neptune", swe.NEPTUNE, False),
    ("Pluto", swe.PLUTO, False),
    ("North Node", swe.MEAN_NODE, True),  # South Node is derived (+180)
]
CLASSICAL_SEVEN = {"Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"}

# ---------------------------------------------------------------------------
# DIGNITY TABLES  (sign index 0..11)
# These are static, well-established tables. They encode no judgment, only the
# traditional scheme. >>> VALIDATE against a printed reference before launch:
# transcription typos in the bounds table are the most likely error here. <<<
# ---------------------------------------------------------------------------

# Domicile (rulership) — traditional 7-planet scheme, no outer-planet rulers.
DOMICILE = [
    "Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
    "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter",
]
# Detriment = ruler of the opposite sign (derived below).

# Exaltation: sign index -> (planet, exact degree).  Fall = opposite sign.
EXALTATION = {
    0: ("Sun", 19), 1: ("Moon", 3), 5: ("Mercury", 15), 11: ("Venus", 27),
    9: ("Mars", 28), 3: ("Jupiter", 15), 6: ("Saturn", 21),
}

# Triplicity (Dorothean) by element: (day ruler, night ruler, participating).
TRIPLICITY = {
    "fire":  ("Sun", "Jupiter", "Saturn"),
    "earth": ("Venus", "Moon", "Mars"),
    "air":   ("Saturn", "Mercury", "Jupiter"),
    "water": ("Venus", "Mars", "Moon"),
}

# Egyptian bounds/terms: per sign, list of (ruler, upper_bound_degree).
# Each sign's entries are cumulative and end at 30.
BOUNDS = {
    0:  [("Jupiter", 6), ("Venus", 12), ("Mercury", 20), ("Mars", 25), ("Saturn", 30)],
    1:  [("Venus", 8), ("Mercury", 14), ("Jupiter", 22), ("Saturn", 27), ("Mars", 30)],
    2:  [("Mercury", 6), ("Jupiter", 12), ("Venus", 17), ("Mars", 24), ("Saturn", 30)],
    3:  [("Mars", 7), ("Venus", 13), ("Mercury", 19), ("Jupiter", 26), ("Saturn", 30)],
    4:  [("Jupiter", 6), ("Venus", 11), ("Saturn", 18), ("Mercury", 24), ("Mars", 30)],
    5:  [("Mercury", 7), ("Venus", 17), ("Jupiter", 21), ("Mars", 28), ("Saturn", 30)],
    6:  [("Saturn", 6), ("Mercury", 14), ("Jupiter", 21), ("Venus", 28), ("Mars", 30)],
    7:  [("Mars", 7), ("Venus", 11), ("Mercury", 19), ("Jupiter", 24), ("Saturn", 30)],
    8:  [("Jupiter", 12), ("Venus", 17), ("Mercury", 21), ("Saturn", 26), ("Mars", 30)],
    9:  [("Mercury", 7), ("Jupiter", 14), ("Venus", 22), ("Saturn", 26), ("Mars", 30)],
    10: [("Mercury", 7), ("Venus", 13), ("Jupiter", 20), ("Mars", 25), ("Saturn", 30)],
    11: [("Venus", 12), ("Jupiter", 16), ("Mercury", 19), ("Mars", 28), ("Saturn", 30)],
}

# Faces / decans (Chaldean order). Repeating 7-cycle starting Aries 1st decan.
_FACE_CYCLE = ["Mars", "Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter"]

# Modern aspects: name -> (exact angle, orb in degrees).
MODERN_ASPECTS = {
    "conjunction": (0, 8),
    "sextile": (60, 6),
    "square": (90, 8),
    "trine": (120, 8),
    "opposition": (180, 8),
}
# Whole-sign (traditional) aspect by sign-distance (0..6). 1 and 5 are aversions.
SIGN_DISTANCE_ASPECT = {0: "conjunction", 2: "sextile", 3: "square",
                        4: "trine", 6: "opposition"}

# Planetary day ruler by Python weekday() (Mon=0 .. Sun=6).
WEEKDAY_RULER = {0: "Moon", 1: "Mars", 2: "Mercury", 3: "Jupiter",
                 4: "Venus", 5: "Saturn", 6: "Sun"}
# Chaldean order, used for planetary hours.
CHALDEAN = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]


# ---------------------------------------------------------------------------
# INPUT
# ---------------------------------------------------------------------------
@dataclass
class BirthData:
    """All user-supplied inputs. `time_precision` drives the whole contract."""
    year: int
    month: int
    day: int
    latitude: float
    longitude: float
    # time_precision in {"exact", "approximate", "unknown"}
    time_precision: str = "exact"
    # for "exact": hour/minute are the clock time
    hour: int = 12
    minute: int = 0
    # for "approximate": a bucket key from APPROX_BUCKETS (hour/minute ignored)
    approx_bucket: Optional[str] = None
    # reading date for transits (defaults to "now" UTC if None)
    reading_date_utc: Optional[datetime] = None


# Approximate buckets: name -> (midpoint_hour, window_start_hour, window_end_hour)
# Windows that cross midnight are handled (end < start). Tune freely.
APPROX_BUCKETS = {
    "early_morning":   (6, 4, 8),
    "morning":         (9, 6, 12),
    "midday":          (12, 11, 13),
    "afternoon":       (15, 12, 17),
    "evening":         (19, 17, 21),
    "night":           (23, 21, 1),
    "late_night":      (3, 1, 5),
}


# ---------------------------------------------------------------------------
# SMALL HELPERS
# ---------------------------------------------------------------------------
def _norm360(x: float) -> float:
    return x % 360.0


def _sign_index(lon: float) -> int:
    return int(_norm360(lon) // 30)


def _deg_in_sign(lon: float) -> float:
    return _norm360(lon) % 30.0


def _angular_sep(a: float, b: float) -> float:
    """Smallest angular separation 0..180."""
    d = abs(_norm360(a) - _norm360(b)) % 360.0
    return d if d <= 180 else 360 - d


# ---------------------------------------------------------------------------
# TIME -> UTC -> JULIAN DAY
# ---------------------------------------------------------------------------
def resolve_timezone(lat: float, lon: float) -> str:
    """IANA zone name for coordinates. Raises if not found (e.g. open ocean)."""
    tzname = _tf.timezone_at(lat=lat, lng=lon)
    if tzname is None:
        # fall back to the nearest zone; surface to caller via meta
        tzname = _tf.closest_timezone_at(lat=lat, lng=lon)  # type: ignore[attr-defined]
    if tzname is None:
        raise ValueError(f"Could not resolve timezone for lat={lat}, lon={lon}")
    return tzname


def local_to_utc(year, month, day, hour, minute, tzname):
    """
    Convert local civil time to UTC using the zone's rules AT THAT DATE.
    NOTE on edge cases (documented, not silently swallowed):
      * Ambiguous local times (DST fall-back) resolve to fold=0 (first
        occurrence). zoneinfo handles this.
      * Nonexistent local times (spring-forward gap) are shifted forward by
        the gap. This is a known, accepted approximation.
      * Pre-1970 zone data is historically unreliable in tzdata. For Turkey
        specifically (many DST changes; permanent UTC+3 since 2016) you MUST
        validate with the test suite of known charts.
    """
    dt_local = datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(tzname))
    dt_utc = dt_local.astimezone(timezone.utc)
    return dt_utc


def julian_day_ut(dt_utc: datetime) -> float:
    hour = dt_utc.hour + dt_utc.minute / 60 + dt_utc.second / 3600
    return swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, hour, swe.GREG_CAL)


# ---------------------------------------------------------------------------
# DIGNITY LOOKUPS
# ---------------------------------------------------------------------------
def _detriment_planet(sign_idx: int) -> str:
    return DOMICILE[(sign_idx + 6) % 12]


def _bound_ruler(sign_idx: int, deg: float) -> str:
    for ruler, upper in BOUNDS[sign_idx]:
        if deg < upper:
            return ruler
    return BOUNDS[sign_idx][-1][0]  # safety: 30.0 exactly


def _face_ruler(lon: float) -> str:
    decan_index = int(_norm360(lon) // 10)  # 0..35
    return _FACE_CYCLE[decan_index % 7]


def dignities_for(planet: str, lon: float,
                  is_diurnal: Optional[bool]) -> Optional[dict]:
    """
    Essential dignities for one body. Returns None for bodies that have no
    traditional dignity scheme (outer planets, nodes). `is_diurnal` selects the
    triplicity ruler (True -> day ruler, False -> night ruler); if it is None
    (sect unknown, i.e. no birth time) we report both day/night rulers and leave
    the chosen triplicity ruler null.
    """
    if planet not in CLASSICAL_SEVEN:
        return None

    s = _sign_index(lon)
    d = _deg_in_sign(lon)
    element = ELEMENTS[s]

    trip_day, trip_night, trip_part = TRIPLICITY[element]
    if is_diurnal is True:
        triplicity_ruler = trip_day
    elif is_diurnal is False:
        triplicity_ruler = trip_night
    else:
        triplicity_ruler = None  # cannot pick without sect

    exalt_planet = EXALTATION.get(s, (None, None))[0]
    fall_planet = EXALTATION.get((s + 6) % 12, (None, None))[0]

    return {
        "sign_ruler": DOMICILE[s],
        "in_domicile": DOMICILE[s] == planet,
        "in_detriment": _detriment_planet(s) == planet,
        "in_exaltation": exalt_planet == planet,
        "in_fall": fall_planet == planet,
        "triplicity_ruler": triplicity_ruler,
        "triplicity_rulers_all": {"day": trip_day, "night": trip_night,
                                  "participating": trip_part},
        "in_triplicity": (triplicity_ruler == planet) if triplicity_ruler else None,
        "bound_ruler": _bound_ruler(s, d),
        "in_own_bound": _bound_ruler(s, d) == planet,
        "face_ruler": _face_ruler(lon),
        "in_own_face": _face_ruler(lon) == planet,
    }


# ---------------------------------------------------------------------------
# SECT
# ---------------------------------------------------------------------------
def compute_sect(sun_lon: float, asc_lon: float, mc_lon: float) -> bool:
    """
    Returns True for a diurnal (day) chart, False for nocturnal (night).
    Day chart if the Sun is above the horizon, else night.
    Geometric method independent of house system: the horizon great circle
    crosses the ecliptic at Asc and Desc (=Asc+180), splitting it into two
    180-degree arcs. The 'above' arc is the one containing the MC. The Sun is
    above the horizon iff it lies on the same arc as the MC.
    """
    desc = _norm360(asc_lon + 180)
    # arc from desc -> asc going in increasing longitude; does it contain MC?
    span = _norm360(asc_lon - desc)          # == 180
    mc_offset = _norm360(mc_lon - desc)
    mc_in_desc_to_asc = mc_offset <= span
    sun_offset = _norm360(sun_lon - desc)
    sun_in_desc_to_asc = sun_offset <= span
    # Sun above horizon iff it shares the MC's arc.
    above = (sun_in_desc_to_asc == mc_in_desc_to_asc)
    return above  # True = diurnal/day, False = nocturnal/night


# ---------------------------------------------------------------------------
# LOTS
# ---------------------------------------------------------------------------
def compute_lots(asc, sun, moon, is_diurnal: bool) -> dict:
    """Part of Fortune & Spirit. Sect-sensitive (formulas swap day/night)."""
    if is_diurnal:
        fortune = _norm360(asc + moon - sun)
        spirit = _norm360(asc + sun - moon)
    else:  # night
        fortune = _norm360(asc + sun - moon)
        spirit = _norm360(asc + moon - sun)
    return {
        "fortune": _point(fortune),
        "spirit": _point(spirit),
    }


# ---------------------------------------------------------------------------
# HOUSES
# ---------------------------------------------------------------------------
def _house_of(lon: float, cusps: list) -> int:
    """House number 1..12 for a longitude given 12 cusp longitudes."""
    lon = _norm360(lon)
    for i in range(12):
        start = _norm360(cusps[i])
        end = _norm360(cusps[(i + 1) % 12])
        span = _norm360(end - start)
        if _norm360(lon - start) < span:
            return i + 1
    return 12  # safety


def compute_sector_rulers(cusps_by_system: dict, bodies: list) -> dict:
    """
    Precompute the rulership of each sector (house) for every house system.

    For each house 1..12 this resolves the sign on the cusp, that sign's
    domicile ruler, and where the ruling planet sits (its sign and its house
    IN THE SAME house system). This is pure restructuring of facts already
    computed: longitude->sign and sign->ruler are the same steps the engine
    runs for every point, applied here to cusps. NO new ruler map is introduced
    — `DOMICILE` is exactly the table that populates `classifications.sign_ruler`,
    so a house ruler can never disagree with a point's `sign_ruler` (CHART_SECTOR
    _RULERS_SPEC.md §3).

    `cusps_by_system` maps system name ("placidus"/"whole_sign") to its 12 cusp
    longitudes. `ruler_sector` is reported in the block's own system, keeping each
    block internally consistent in a single house system (§4 self-containment).
    """
    by_name = {b["name"]: b for b in bodies}
    out: dict = {}
    for system, cusps in cusps_by_system.items():
        # EXTENSION POINT: when time_precision != "exact" and cusps are unavailable,
        # omit sector_rulers entirely (structural omission, not null). Not implemented:
        # current scope is exact-time charts only. (Also guards Placidus above the
        # polar circle, where cusps is None and no ruler_sector exists.)
        if cusps is None:
            continue
        block: dict = {}
        for i in range(12):
            sign_idx = _sign_index(cusps[i])
            ruler = DOMICILE[sign_idx]               # canonical map — do NOT redefine
            ruler_body = by_name[ruler]
            block[str(i + 1)] = {
                "sign_on_cusp": SIGNS[sign_idx],
                "ruler": ruler,
                "ruler_sign": ruler_body["sign"],
                "ruler_sector": ruler_body["sector"][system],
            }
        out[system] = block
    return out


def compute_houses(jd, lat, lon):
    """
    Returns dict with placidus + whole_sign cusp lists, plus asc/mc.

    Whole Sign is computed first because it (and the Ascendant/MC) is defined at
    every latitude. Placidus is undefined above the polar circle (~66.5 deg);
    if swe.houses raises there, placidus_cusps is set to None rather than
    crashing. This never triggers for Turkey (36-42 deg N) but guards against
    users born at extreme latitudes.
    """
    ws_cusps, ws_ascmc = swe.houses(jd, lat, lon, b"W")
    asc = ws_ascmc[0]
    mc = ws_ascmc[1]
    try:
        plac_cusps, _ = swe.houses(jd, lat, lon, b"P")
        plac_cusps = list(plac_cusps)
    except swe.Error:
        plac_cusps = None  # Placidus undefined at this latitude
    return {
        "ascendant": asc,
        "mc": mc,
        "placidus_cusps": plac_cusps,
        "whole_sign_cusps": list(ws_cusps),
    }


# ---------------------------------------------------------------------------
# ASPECTS
# ---------------------------------------------------------------------------
def _orb_now_and_later(lon_a, spd_a, lon_b, spd_b, exact_angle, dt=1e-3):
    """Orb from exact aspect now and a tiny step later -> applying if closing."""
    def orb(la, lb):
        sep = _angular_sep(la, lb)
        return abs(sep - exact_angle)
    now = orb(lon_a, lon_b)
    later = orb(lon_a + spd_a * dt, lon_b + spd_b * dt)
    return now, (later < now)


def compute_modern_aspects(bodies: list) -> list:
    """Degree-orb aspects among non-node bodies, with applying/separating."""
    out = []
    pts = [b for b in bodies if "Node" not in b["name"]]
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            a, b = pts[i], pts[j]
            sep = _angular_sep(a["longitude"], b["longitude"])
            for name, (angle, orb_allow) in MODERN_ASPECTS.items():
                if abs(sep - angle) <= orb_allow:
                    orb_val, applying = _orb_now_and_later(
                        a["longitude"], a["speed"], b["longitude"], b["speed"], angle)
                    out.append({
                        "source": a["name"], "target": b["name"], "type": name,
                        "scheme": "modern",
                        "orb": round(orb_val, 3),
                        "applying": applying,
                    })
                    break  # one aspect per pair
    return out


def compute_traditional_aspects(bodies: list) -> list:
    """Whole-sign aspects among the classical seven. No orb; by sign distance."""
    out = []
    pts = [b for b in bodies if b["name"] in CLASSICAL_SEVEN]
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            a, b = pts[i], pts[j]
            dist = abs(a["sign_index"] - b["sign_index"])
            dist = min(dist, 12 - dist)
            asp = SIGN_DISTANCE_ASPECT.get(dist)
            if asp:
                out.append({
                    "source": a["name"], "target": b["name"], "type": asp,
                    "scheme": "whole_sign",
                })
            # dist 1 and 5 -> aversion (intentionally emitted as nothing)
    return out


# ---------------------------------------------------------------------------
# PLANETARY DAY & HOUR  (needs sunrise/sunset; only meaningful with a time)
# ---------------------------------------------------------------------------
def _rise_set(jd, lat, lon, body, rsmi):
    """
    Wrapper around swe.rise_trans; returns JD of the next event at/after `jd`,
    or None. Signature (pyswisseph 2.10.x):
        rise_trans(tjdut, body, rsmi, geopos, atpress, attemp, flags)
    geopos = (longitude_east, latitude_north, altitude_m).
    res == -2 means circumpolar (no rise/set) at high latitudes.
    """
    try:
        res, tret = swe.rise_trans(jd, body, rsmi, (lon, lat, 0.0),
                                   0.0, 0.0, EPHE_FLAG)
        if res != 0:
            return None
        return tret[0]
    except Exception:
        return None


def compute_planetary_day_hour(jd, lat, lon):
    """
    Returns (day_ruler, hour_ruler) or (None, None) if uncomputable
    (e.g. circumpolar latitudes where the Sun doesn't rise/set).

    The astrological day begins at sunrise. Daytime (sunrise->sunset) is split
    into 12 unequal hours, nighttime (sunset->next sunrise) into 12 more. Hours
    are assigned in Chaldean order starting from the day ruler at sunrise.

    >>> Validate against a reference (e.g. an established planetary-hours
        calculator) before relying on it; the weekday is taken from the
        sunrise date in UT, a minor approximation at the day boundary. <<<
    """
    # sunrise beginning the astrological day that contains `jd`
    r = _rise_set(jd - 1.0, lat, lon, swe.SUN, swe.CALC_RISE)
    if r is None:
        return None, None
    day_start = r if r <= jd else _rise_set(jd - 2.0, lat, lon, swe.SUN, swe.CALC_RISE)
    if day_start is None:
        return None, None

    sunset = _rise_set(day_start, lat, lon, swe.SUN, swe.CALC_SET)
    next_sunrise = _rise_set(day_start + 0.4, lat, lon, swe.SUN, swe.CALC_RISE)
    if sunset is None or next_sunrise is None:
        return None, None

    # weekday of the astrological day, from the sunrise date (UT approximation)
    import datetime as _dt
    y, m, d, _h = swe.revjul(day_start, swe.GREG_CAL)
    day_ruler = WEEKDAY_RULER[_dt.date(int(y), int(m), int(d)).weekday()]

    if day_start <= jd < sunset:
        hour_len = (sunset - day_start) / 12.0
        idx = min(int((jd - day_start) / hour_len), 11)
    else:
        hour_len = (next_sunrise - sunset) / 12.0
        idx = 12 + min(int((jd - sunset) / hour_len), 11)

    chal_start = CHALDEAN.index(day_ruler)
    hour_ruler = CHALDEAN[(chal_start + idx) % 7]
    return day_ruler, hour_ruler


# ---------------------------------------------------------------------------
# CORE: compute one chart at a single, fully-specified UTC instant
# ---------------------------------------------------------------------------
def _point(lon: float) -> dict:
    s = _sign_index(lon)
    return {
        "longitude": round(_norm360(lon), 4),
        "sign": SIGNS[s],
        "sign_index": s,
        "degree_in_sign": round(_deg_in_sign(lon), 4),
    }


def _compute_at(dt_utc, lat, lon, has_time: bool):
    """
    Compute the raw chart at one instant. `has_time` is False for 'unknown'
    precision: in that case we omit Asc/houses/sect/lots entirely.
    Returns a dict of the volatile + stable pieces.
    """
    jd = julian_day_ut(dt_utc)

    # planets
    bodies = []
    body_lon = {}
    for name, swe_id, traditional in BODIES:
        xx, _ = swe.calc_ut(jd, swe_id, EPHE_FLAG)
        lon_, _lat, _dist, spd, *_ = xx
        body_lon[name] = lon_
        bodies.append({
            "name": name,
            "traditional": traditional,
            "longitude": round(_norm360(lon_), 4),
            "sign": SIGNS[_sign_index(lon_)],
            "sign_index": _sign_index(lon_),
            "degree_in_sign": round(_deg_in_sign(lon_), 4),
            "speed": spd,
            "retrograde": spd < 0,
        })
    # derived South Node
    nn = next(b for b in bodies if b["name"] == "North Node")
    sn_lon = _norm360(nn["longitude"] + 180)
    bodies.append({
        "name": "South Node", "traditional": True,
        "longitude": round(sn_lon, 4), "sign": SIGNS[_sign_index(sn_lon)],
        "sign_index": _sign_index(sn_lon),
        "degree_in_sign": round(_deg_in_sign(sn_lon), 4),
        "speed": nn["speed"], "retrograde": nn["retrograde"],
    })
    body_lon["South Node"] = sn_lon

    result = {"jd": jd, "bodies": bodies}

    if has_time:
        h = compute_houses(jd, lat, lon)
        asc, mc = h["ascendant"], h["mc"]
        is_diurnal = compute_sect(body_lon["Sun"], asc, mc)
        result.update({
            "ascendant": _point(asc),
            "mc": _point(mc),
            "placidus_cusps": h["placidus_cusps"],
            "whole_sign_cusps": h["whole_sign_cusps"],
            "is_diurnal": is_diurnal,
            "lots": compute_lots(asc, body_lon["Sun"], body_lon["Moon"],
                                 is_diurnal),
        })
        # sector (house) placement per body in both systems
        for b in bodies:
            b["sector"] = {
                "placidus": (_house_of(b["longitude"], h["placidus_cusps"])
                             if h["placidus_cusps"] else None),
                "whole_sign": _house_of(b["longitude"], h["whole_sign_cusps"]),
            }
    else:
        is_diurnal = None

    # classifications (sect-aware; if no sect, triplicity ruler left None)
    for b in bodies:
        b["classifications"] = dignities_for(b["name"], b["longitude"],
                                             is_diurnal)

    return result


# ---------------------------------------------------------------------------
# STABILITY CHECK for 'approximate' births
# ---------------------------------------------------------------------------
def _volatile_signature(chart_pieces, has_time):
    """Snapshot of fields that can flip across the time window."""
    sig = {}
    if has_time:
        sig["asc_sign"] = chart_pieces["ascendant"]["sign"]
        sig["mc_sign"] = chart_pieces["mc"]["sign"]
        sig["is_diurnal"] = chart_pieces["is_diurnal"]
        sig["sectors"] = {b["name"]: (b["sector"]["placidus"],
                                      b["sector"]["whole_sign"])
                          for b in chart_pieces["bodies"]}
    sig["moon_sign"] = next(b["sign"] for b in chart_pieces["bodies"]
                            if b["name"] == "Moon")
    return sig


def _bucket_datetimes(bd: BirthData, tzname):
    """Midpoint + window-edge local datetimes for an approximate bucket."""
    assert bd.approx_bucket is not None  # validated by caller
    mid_h, start_h, end_h = APPROX_BUCKETS[bd.approx_bucket]

    def at(hour):
        # windows can cross midnight (end < start): roll the date for the
        # end edge into the next day.
        day = bd.day
        if hour < start_h and start_h > end_h:
            # this is the post-midnight edge of a wrap-around window
            return (bd.year, bd.month, day, hour, 0, True)
        return (bd.year, bd.month, day, hour, 0, False)

    edges = []
    for hour in (mid_h, start_h, end_h):
        y, mo, d, hh, mm, rolled = at(hour)
        dt_local = datetime(y, mo, d, hh, mm, tzinfo=ZoneInfo(tzname))
        if rolled:
            dt_local += timedelta(days=1)
        edges.append(dt_local.astimezone(timezone.utc))
    return edges  # [midpoint, start, end]


# ---------------------------------------------------------------------------
# PUBLIC ENTRY POINT
# ---------------------------------------------------------------------------
def compute_chart(bd: BirthData) -> Chart:
    """
    Build the full chart object for one birth. This is the only function the
    rest of the pipeline should call. Output is JSON-serializable.
    """
    if bd.time_precision not in ("exact", "approximate", "unknown"):
        raise ValueError(f"bad time_precision: {bd.time_precision}")

    tzname = resolve_timezone(bd.latitude, bd.longitude)
    has_time = bd.time_precision != "unknown"

    meta = {
        "time_precision": bd.time_precision,
        "zodiac": "tropical",
        "ephemeris": EPHEMERIS_NAME,
        "pyswisseph_version": getattr(swe, "__version__", "unknown"),
        "house_systems": ["placidus", "whole_sign"],
        "node_type": "mean",
        "timezone": tzname,
    }

    # ---- determine the instant(s) to compute ----
    if bd.time_precision == "exact":
        dt_utc = local_to_utc(bd.year, bd.month, bd.day, bd.hour, bd.minute, tzname)
        meta["utc"] = dt_utc.isoformat()
        pieces = _compute_at(dt_utc, bd.latitude, bd.longitude, has_time=True)
        confidence = "exact"
        unstable = {}

    elif bd.time_precision == "approximate":
        if bd.approx_bucket not in APPROX_BUCKETS:
            raise ValueError(f"unknown approx_bucket: {bd.approx_bucket}")
        mid_utc, start_utc, end_utc = _bucket_datetimes(bd, tzname)
        meta["utc"] = mid_utc.isoformat()
        meta["approx_bucket"] = bd.approx_bucket
        pieces = _compute_at(mid_utc, bd.latitude, bd.longitude, has_time=True)
        # recompute at edges and diff the volatile signature
        p_start = _compute_at(start_utc, bd.latitude, bd.longitude, has_time=True)
        p_end = _compute_at(end_utc, bd.latitude, bd.longitude, has_time=True)
        sig_mid = _volatile_signature(pieces, True)
        sig_a = _volatile_signature(p_start, True)
        sig_b = _volatile_signature(p_end, True)
        unstable = _diff_signatures(sig_mid, sig_a, sig_b)
        confidence = "approximate"

    else:  # unknown
        # noon UTC is used only to get planet positions (Asc/houses omitted)
        dt_utc = datetime(bd.year, bd.month, bd.day, 12, 0, tzinfo=timezone.utc)
        meta["utc"] = dt_utc.isoformat()
        meta["note"] = ("No birth time: Ascendant, houses, sect, lots, and "
                        "planetary hour omitted. Moon position is a daily range.")
        pieces = _compute_at(dt_utc, bd.latitude, bd.longitude, has_time=False)
        confidence = "unknown"
        unstable = {}
        # Moon as a range across the day
        moon = next(b for b in pieces["bodies"] if b["name"] == "Moon")
        m0, _ = swe.calc_ut(julian_day_ut(
            datetime(bd.year, bd.month, bd.day, 0, 0, tzinfo=timezone.utc)),
            swe.MOON, EPHE_FLAG)
        m1, _ = swe.calc_ut(julian_day_ut(
            datetime(bd.year, bd.month, bd.day, 23, 59, tzinfo=timezone.utc)),
            swe.MOON, EPHE_FLAG)
        moon["range"] = {
            "start": _point(m0[0]),
            "end": _point(m1[0]),
            "note": "Moon moves up to ~15 deg/day; exact position needs a time.",
        }

    # ---- assemble output ----
    chart: dict = {
        "meta": meta,
        "confidence": confidence,
        "points": pieces["bodies"],
    }
    if has_time:
        chart["axes"] = {"ascendant": pieces["ascendant"], "mc": pieces["mc"]}
        chart["sectors"] = {
            "placidus_cusps": ([round(c, 4) for c in pieces["placidus_cusps"]]
                               if pieces["placidus_cusps"] else None),
            "whole_sign_cusps": [round(c, 4) for c in pieces["whole_sign_cusps"]],
        }
        chart["is_diurnal"] = pieces["is_diurnal"]
        chart["derived_points"] = pieces["lots"]
        # Precomputed sector rulership, both systems, in each block's own house
        # system. Reads only facts already on points[] (sign + sector); adds no
        # astronomy. See CHART_SECTOR_RULERS_SPEC.md.
        chart["sector_rulers"] = compute_sector_rulers(
            {"placidus": pieces["placidus_cusps"],
             "whole_sign": pieces["whole_sign_cusps"]},
            pieces["bodies"])
        # planetary day/hour (skip for approximate hour if unstable? keep, flag)
        jd = pieces["jd"]
        day_ruler, hour_ruler = compute_planetary_day_hour(
            jd, bd.latitude, bd.longitude)
        chart["planetary_day"] = day_ruler
        chart["planetary_hour"] = hour_ruler
        if confidence == "approximate":
            chart["unstable_fields"] = unstable

    # relations (aspect edge list over points)
    chart["relations"] = (compute_modern_aspects(pieces["bodies"])
                          + compute_traditional_aspects(pieces["bodies"]))

    return cast(Chart, chart)


def _diff_signatures(mid, a, b) -> dict:
    """
    Compare midpoint signature against both window edges. A field is unstable
    if it differs at either edge. House instability is reported per body.
    """
    unstable: dict = {}
    for key in ("asc_sign", "mc_sign", "is_diurnal", "moon_sign"):
        if key in mid and (mid[key] != a.get(key) or mid[key] != b.get(key)):
            unstable[key] = True
    if "sectors" in mid:
        bad = []
        for body, val in mid["sectors"].items():
            if val != a["sectors"].get(body) or val != b["sectors"].get(body):
                bad.append(body)
        if bad:
            unstable["house_placements"] = bad
    return unstable


# ---------------------------------------------------------------------------
# DEMO
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json

    # Istanbul, an exact-time birth
    demo = BirthData(
        year=1988, month=12, day=28, hour=13, minute=30,
        latitude=42.14856797650102,  longitude=24.690919461501238, time_precision="exact",
    )
    chart = compute_chart(demo)
    with open("chart.json", "w", encoding="utf-8") as f:
        json.dump(chart, f, ensure_ascii=False, indent=2)
    print("Wrote chart.json")
