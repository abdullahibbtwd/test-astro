#!/usr/bin/env python3
"""
compute_forecast.py  —  PREDICTIVE LAYER: deterministic event engine

This module is the analogue of ``compute_chart.py``, one level up in the
pipeline. Where ``compute_chart`` answers "what is the chart" at a single
instant, this answers "what happens across a window, and when". It is a PURE
FUNCTION:

    natal chart object + target date + horizon  ->  dated event list (forecast)

Same inputs -> byte-identical output. No randomness, no network, no model calls
(the only non-deterministic fields — ``meta.generated_at`` / ``meta.run_id`` —
are injectable for reproducible tests; see ``compute_forecast(now=, run_id=)``).

It performs ZERO interpretation. Every event is a table lookup or an ephemeris
crossing. Phase, cycle-stage, horizon filtering and day boundaries — everything
the corpus cannot supply — are enforced HERE, deterministically. Downstream,
forecast-grounding matches these events to predictive principles (via the §9
``grounding`` signature) and the reading layer renders them per profile. Neither
of those is in this module.

Astronomy is REUSED from ``compute_chart.py`` (Swiss Ephemeris access, dignity
logic, both house systems, sect, day/hour ruler, timezone resolution). New code
here is only the time-windowed event detection. See FORECAST_COMPUTE_SPEC.md.

Dependencies: pyswisseph, timezonefinder  (and stdlib zoneinfo, Python >=3.9)
"""

from __future__ import annotations

import calendar
import hashlib
import json
import os
import random
import string
import sys
from dataclasses import dataclass
from datetime import date as _date
from datetime import datetime, timedelta, timezone
from typing import Optional, cast
from zoneinfo import ZoneInfo

# --- reuse the LAYER-1 engine, do not fork (SPEC §2) -----------------------
# compute_chart.py lives in ../d_layer and imports its sibling chart_types by
# bare name, so we add that directory to sys.path and import it as a module.
_D_LAYER = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "..", "d_layer"))
if _D_LAYER not in sys.path:
    sys.path.insert(0, _D_LAYER)

import swisseph as swe  # type: ignore[import-not-found]  # noqa: E402

import compute_chart as cc  # noqa: E402
from compute_chart import (  # noqa: E402
    EPHE_FLAG,
    ELEMENTS,
    SIGNS,
    _angular_sep,  # noqa: F401  (kept for parity / future use)
    _deg_in_sign,
    _house_of,
    _norm360,
    _sign_index,
    compute_planetary_day_hour,
    dignities_for,
    julian_day_ut,
)
from forecast_types import Forecast  # noqa: E402

# ---------------------------------------------------------------------------
# BODIES
# ---------------------------------------------------------------------------
# The ten transiting bodies (SPEC §4a): seven classical + three modern. The
# lunar nodes are NOT transiting bodies here, and are not natal targets either.
TRANSITING = [
    ("Sun", swe.SUN), ("Moon", swe.MOON), ("Mercury", swe.MERCURY),
    ("Venus", swe.VENUS), ("Mars", swe.MARS), ("Jupiter", swe.JUPITER),
    ("Saturn", swe.SATURN), ("Uranus", swe.URANUS), ("Neptune", swe.NEPTUNE),
    ("Pluto", swe.PLUTO),
]
SWE_ID = dict(TRANSITING)
# Natal aspect targets: the same ten bodies (angles are added separately).
NATAL_BODIES = [name for name, _ in TRANSITING]

# Speed classes (SPEC §6 rows). The Moon groups with the fast bodies for the
# speed_class label; the horizon filter treats "Moon" as its own row.
FAST = {"Sun", "Moon", "Mercury", "Venus", "Mars"}
SLOW = {"Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"}
LUMINARIES = {"Sun", "Moon"}


def _speed_class(name: str) -> Optional[str]:
    if name in FAST:
        return "fast"
    if name in SLOW:
        return "slow"
    return None


# ---------------------------------------------------------------------------
# ASPECTS & THE 8-STAGE SYNODIC CYCLE
# ---------------------------------------------------------------------------
# Ptolemaic aspects only (SPEC §4a). Full names, matching chart_schema.json's
# AspectType (the §11 override mandates reusing chart names over inventing
# parallel abbreviations, so we use "square" not "sq", "opposition" not "opp").
ASPECTS = [
    ("conjunction", 0), ("sextile", 60), ("square", 90),
    ("trine", 120), ("opposition", 180),
]


def _aspect_elongations(angle: int) -> list[float]:
    """The elongation value(s) d = (T - natal) mod 360 at which this aspect is
    exact. Conjunction and opposition are single-valued; the others perfect on
    both the waxing (applying-side) and waning (approaching-side) arcs."""
    if angle in (0, 180):
        return [float(angle)]
    return [float(angle), float(360 - angle)]


# Elongation -> synodic cycle-stage (SPEC §5). The eight canonical elongations
# and the stage each one snaps to.
_STAGE_BY_ELONG = {0: 1, 60: 2, 90: 3, 120: 4, 180: 5, 240: 6, 270: 7, 300: 8}
_STAGE_ELONGS = sorted(_STAGE_BY_ELONG)  # [0,60,90,120,180,240,270,300]
STAGE_NAME = {
    1: "conjunction", 2: "separating sextile", 3: "separating square",
    4: "separating trine", 5: "opposition", 6: "approaching trine",
    7: "approaching square", 8: "approaching sextile",
}


def _signed180(x: float) -> float:
    """Map an angle difference into (-180, 180]."""
    return ((x + 180.0) % 360.0) - 180.0


def _cycle_stage_from_elongation(d: float) -> int:
    """Snap an elongation d in [0,360) to the nearest of the eight synodic
    stations and return its 1..8 stage index (SPEC §5)."""
    best_e, best_gap = 0, 999.0
    for e in _STAGE_ELONGS:
        gap = abs(_signed180(d - e))
        if gap < best_gap:
            best_gap, best_e = gap, e
    return _STAGE_BY_ELONG[best_e]


# ---------------------------------------------------------------------------
# ORB TABLE (SPEC §7) — used only for standing (in-orb-at-window-start) aspects.
# Perfection events need no orb. Orbs are NOT widened by horizon.
# ---------------------------------------------------------------------------
def _orb_allow(transiting: str) -> float:
    return 1.5 if transiting in LUMINARIES else 1.0


# ---------------------------------------------------------------------------
# GROUNDING VOCABULARY (SPEC §9) — the allowed grounding.kind set is exactly the
# corpus `requires.kind` vocabulary the forecast-grounding step matches against.
# NOTE: the corpus has NO "midheaven" kind; MC/IC/DSC angle contacts therefore
# ground as "other" with rich topic_tags (only the Ascendant gets "ascendant").
# ---------------------------------------------------------------------------
GROUNDING_KINDS = {
    "point_aspects", "point_house", "point_sign", "point_dignity",
    "sign_element", "ascendant", "house_ruler", "birth_time",
    "native_gender", "other",
}


# ---------------------------------------------------------------------------
# INPUT
# ---------------------------------------------------------------------------
@dataclass
class ForecastConfig:
    """Optional-module switches. Both ship OFF (SPEC §4d, §4a)."""
    enable_profections: bool = False        # SPEC §4d — stubbed, not wired
    enable_lots_targets: bool = False        # SPEC §4a — Fortune/Spirit targets


# ---------------------------------------------------------------------------
# TIME / GRID HELPERS
# ---------------------------------------------------------------------------
_GRID_STEP = {
    "day": timedelta(minutes=10),
    "month": timedelta(minutes=60),
    "year": timedelta(hours=6),
}


def _add_horizon(dt: datetime, horizon: str) -> datetime:
    """One local calendar day / month / year after ``dt`` (SPEC §3), clamping
    the day-of-month on month/year rollover (e.g. Jan-31 +1mo -> Feb-28)."""
    if horizon == "day":
        return dt + timedelta(days=1)
    if horizon == "month":
        y, m = dt.year, dt.month + 1
        if m > 12:
            y, m = y + 1, 1
        d = min(dt.day, calendar.monthrange(y, m)[1])
        return dt.replace(year=y, month=m, day=d)
    if horizon == "year":
        y = dt.year + 1
        d = min(dt.day, calendar.monthrange(y, dt.month)[1])
        return dt.replace(year=y, day=d)
    raise ValueError(f"bad horizon: {horizon!r}")


def _jd_to_utc(jd: float) -> datetime:
    y, mo, d, h = swe.revjul(jd, swe.GREG_CAL)
    return datetime(int(y), int(mo), int(d), tzinfo=timezone.utc) + timedelta(hours=h)


def _iso_local(jd: float, tz: ZoneInfo) -> str:
    # Round to the nearest second (not truncate): the JD->civil reconstruction
    # carries sub-millisecond float noise, and truncating a boundary instant like
    # 22:00:00.0 -> 21:59:59.9995 would display it one second before the window
    # start even though it is genuinely in-window.
    dt = _jd_to_utc(jd) + timedelta(milliseconds=500)
    return dt.astimezone(tz).replace(microsecond=0).isoformat()


def _grid(start_utc: datetime, end_utc: datetime, step: timedelta) -> list[float]:
    """Julian-day samples across [start, end], inclusive of the end edge so a
    crossing in the final partial step is still bracketed."""
    out, t = [], start_utc
    while t < end_utc:
        out.append(julian_day_ut(t))
        t += step
    out.append(julian_day_ut(end_utc))
    return out


# ---------------------------------------------------------------------------
# EPHEMERIS SAMPLING (memoized per body per run)
# ---------------------------------------------------------------------------
def _lon_at(jd: float, swe_id: int) -> float:
    return _norm360(swe.calc_ut(jd, swe_id, EPHE_FLAG)[0][0])


def _lon_speed_at(jd: float, swe_id: int) -> tuple[float, float]:
    xx, _ = swe.calc_ut(jd, swe_id, EPHE_FLAG)
    return _norm360(xx[0]), xx[3]


# ---------------------------------------------------------------------------
# ROOT-FINDING (bisection) for exact perfection / ingress datetimes
# ---------------------------------------------------------------------------
def _bisect_elongation(swe_id: int, nat_lon: float, e: float,
                       jd0: float, f0: float, jd1: float, f1: float,
                       iters: int = 60) -> float:
    """Refine the exact JD where elongation (T - natal) == e, given a sign change
    of f = signed180(elongation - e) between jd0 and jd1."""
    for _ in range(iters):
        jm = 0.5 * (jd0 + jd1)
        fm = _signed180(_norm360(_lon_at(jm, swe_id) - nat_lon) - e)
        if fm == 0.0:
            return jm
        if (f0 < 0) != (fm < 0):
            jd1, f1 = jm, fm
        else:
            jd0, f0 = jm, fm
    return 0.5 * (jd0 + jd1)


def _bisect_predicate(swe_id: int, pred, jd0: float, jd1: float,
                      iters: int = 50) -> float:
    """Refine the JD at which a boolean predicate pred(lon) flips from False (at
    jd0) to True (at jd1). Used for sign / house boundary crossings."""
    for _ in range(iters):
        jm = 0.5 * (jd0 + jd1)
        if pred(_lon_at(jm, swe_id)):
            jd1 = jm
        else:
            jd0 = jm
    return jd1


# ---------------------------------------------------------------------------
# SEGMENTATION (SPEC §10)
# ---------------------------------------------------------------------------
def _segment(jd: float, start_jd: float, end_jd: float, horizon: str) -> Optional[str]:
    if horizon == "day":
        return None
    frac = (jd - start_jd) / (end_jd - start_jd) if end_jd > start_jd else 0.0
    frac = min(max(frac, 0.0), 0.999999)
    if horizon == "month":
        return ("early", "mid", "late")[int(frac * 3)]
    return ("q1", "q2", "q3", "q4")[int(frac * 4)]  # year


# ---------------------------------------------------------------------------
# EVENT ID (deterministic)
# ---------------------------------------------------------------------------
def _event_id(family: str, transiting: Optional[str], natal: Optional[str],
              aspect: Optional[str], extra: str, jd: float) -> str:
    slug = f"{family}|{transiting or ''}|{natal or ''}|{aspect or ''}|{extra}|{jd:.6f}"
    return f"{family}-" + hashlib.md5(slug.encode("utf-8")).hexdigest()[:10]


# ---------------------------------------------------------------------------
# DIGNITY (compact, for dignity-modulation of aspect valence — SPEC §9)
# ---------------------------------------------------------------------------
def _compact_dignity(planet: str, lon: float, is_diurnal: Optional[bool]) -> Optional[dict]:
    dg = dignities_for(planet, lon, is_diurnal)
    if dg is None:
        return None
    return {
        "sign": SIGNS[_sign_index(lon)],
        "sign_ruler": dg["sign_ruler"],
        "in_domicile": dg["in_domicile"],
        "in_detriment": dg["in_detriment"],
        "in_exaltation": dg["in_exaltation"],
        "in_fall": dg["in_fall"],
    }


# ===========================================================================
# THE ENGINE
# ===========================================================================
class _Forecaster:
    """Holds per-run state so the detectors can share the grid, natal facts and
    the memoized ephemeris samples. One instance == one forecast."""

    def __init__(self, natal: dict, horizon: str, tz: ZoneInfo,
                 start_jd: float, end_jd: float,
                 latitude: Optional[float], longitude: Optional[float],
                 config: ForecastConfig):
        self.natal = natal
        self.horizon = horizon
        self.tz = tz
        self.start_jd = start_jd
        self.end_jd = end_jd
        self.lat = latitude
        self.lon = longitude
        self.config = config

        self.is_diurnal: Optional[bool] = natal.get("is_diurnal")
        # --- natal targets ---------------------------------------------------
        pts = {p["name"]: p for p in natal["points"]}
        self.natal_lon = {nm: pts[nm]["longitude"] for nm in NATAL_BODIES}
        self.natal_dignity = {nm: pts[nm].get("classifications") for nm in NATAL_BODIES}

        self.has_axes = "axes" in natal
        self.angles: dict[str, float] = {}
        if self.has_axes:
            asc = natal["axes"]["ascendant"]["longitude"]
            mc = natal["axes"]["mc"]["longitude"]
            self.angles = {
                "Ascendant": asc, "Descendant": _norm360(asc + 180),
                "MC": mc, "IC": _norm360(mc + 180),
            }
        self.plac_cusps = (natal.get("sectors") or {}).get("placidus_cusps")
        self.ws_cusps = (natal.get("sectors") or {}).get("whole_sign_cusps")

        # --- precision fallback (SPEC §8) -----------------------------------
        self.tier = natal["confidence"]
        self.degraded = self.tier == "unknown"
        # Without a birth time there are no houses or angles at all, so those
        # families cannot be computed. Record which we are suppressing.
        self.suppressed: list[str] = []
        if self.degraded:
            self.suppressed = ["ingress_house", "angle_aspect", "lunation_in_house"]

        self._sample_cache: dict[int, list[tuple[float, float, float]]] = {}
        self._grid_jds: list[float] = _grid(
            _jd_to_utc(start_jd), _jd_to_utc(end_jd), _GRID_STEP[horizon])

    # -- ephemeris samples for one body across the grid (memoized) -----------
    def _samples(self, name: str) -> list[tuple[float, float, float]]:
        sid = SWE_ID[name]
        cached = self._sample_cache.get(sid)
        if cached is None:
            cached = [(jd, *_lon_speed_at(jd, sid)) for jd in self._grid_jds]
            self._sample_cache[sid] = cached
        return cached

    def _in_window(self, jd: float) -> bool:
        return self.start_jd <= jd < self.end_jd

    # -- natal targets active for this horizon/precision ---------------------
    def _targets(self) -> list[tuple[str, float, bool]]:
        """(name, longitude, is_angle). Angles only when a birth time supports
        them (SPEC §8). Lots-as-targets are gated OFF (SPEC §4a)."""
        out = [(nm, self.natal_lon[nm], False) for nm in NATAL_BODIES]
        if self.has_axes and not self.degraded:
            for nm in ("Ascendant", "MC", "Descendant", "IC"):
                out.append((nm, self.angles[nm], True))
        return out

    # -- which transiting bodies form aspects at this horizon (SPEC §6) ------
    def _aspect_bodies(self) -> list[str]:
        if self.horizon == "year":
            return [n for n in NATAL_BODIES if n in SLOW]   # slow spine only
        return list(NATAL_BODIES)                            # day & month: all

    # =====================================================================
    # 4a. TRANSIT-TO-NATAL ASPECTS
    # =====================================================================
    def transit_aspects(self) -> list[dict]:
        events: list[dict] = []
        perfected: set[tuple] = set()   # (body,target,aspect,e) that perfect in-window

        for body in self._aspect_bodies():
            sid = SWE_ID[body]
            samples = self._samples(body)
            for tname, nat_lon, is_angle in self._targets():
                for asp, angle in ASPECTS:
                    for e in _aspect_elongations(angle):
                        prev_f: Optional[float] = None
                        prev_jd = 0.0
                        for jd, lon, _spd in samples:
                            f = _signed180(_norm360(lon - nat_lon) - e)
                            if prev_f is not None:
                                crossed = (f == 0.0) or (
                                    (prev_f < 0) != (f < 0)
                                    and abs(prev_f) + abs(f) < 180.0)
                                if crossed:
                                    jd_x = (jd if f == 0.0 else
                                            _bisect_elongation(sid, nat_lon, e,
                                                               prev_jd, prev_f, jd, f))
                                    if self._in_window(jd_x):
                                        ev = self._make_aspect_event(
                                            body, tname, nat_lon, is_angle, asp,
                                            e, jd_x, standing=False)
                                        if ev is not None:
                                            events.append(ev)
                                            perfected.add((body, tname, asp, e))
                            prev_f, prev_jd = f, jd

        # standing background aspects (in orb at window start, perfecting OUTSIDE
        # the window). NOT emitted on the DAY horizon (invariant 3).
        if self.horizon != "day":
            events.extend(self._standing_aspects(perfected))
        return events

    def _standing_aspects(self, perfected: set) -> list[dict]:
        events: list[dict] = []
        for body in self._aspect_bodies():
            lon0, spd0 = _lon_speed_at(self.start_jd, SWE_ID[body])
            allow = _orb_allow(body)
            for tname, nat_lon, is_angle in self._targets():
                d0 = _norm360(lon0 - nat_lon)
                for asp, angle in ASPECTS:
                    for e in _aspect_elongations(angle):
                        if (body, tname, asp, e) in perfected:
                            continue            # perfection already covers it
                        if abs(_signed180(d0 - e)) <= allow:
                            ev = self._make_aspect_event(
                                body, tname, nat_lon, is_angle, asp, e,
                                self.start_jd, standing=True, spd_hint=spd0)
                            if ev is not None:
                                events.append(ev)
        return events

    def _make_aspect_event(self, body: str, tname: str, nat_lon: float,
                           is_angle: bool, asp: str, e: float, jd: float,
                           standing: bool, spd_hint: Optional[float] = None
                           ) -> Optional[dict]:
        # precision fallback: drop angle contacts when degraded (SPEC §8)
        if is_angle and self.degraded:
            return None

        lon, spd = _lon_speed_at(jd, SWE_ID[body])
        if spd_hint is not None:
            spd = spd_hint
        d = _norm360(lon - nat_lon)

        if standing:
            # applying if the body is moving toward exact, else separating
            d_next = _norm360((lon + spd * 1e-3) - nat_lon)
            approaching = abs(_signed180(d_next - e)) < abs(_signed180(d - e))
            phase = "applying" if approaching else "separating"
            stage = _cycle_stage_from_elongation(d)
        else:
            phase = "perfecting"
            stage = _STAGE_BY_ELONG[int(round(e))]

        sign = SIGNS[_sign_index(lon)]
        dignity = {
            "transiting": _compact_dignity(body, lon, self.is_diurnal),
            "natal": _dignity_summary(self.natal_dignity.get(tname)) if not is_angle else None,
        }
        tags = ["transit", "transit to natal", asp, phase, body,
                f"transiting {body}", STAGE_NAME[stage], _speed_class(body) or "",
                f"{asp} to natal {tname}"]
        if _lon_speed_at(jd, SWE_ID[body])[1] < 0:
            tags.append("retrograde")

        grounding = self._aspect_grounding(body, tname, is_angle, asp, phase, stage, tags)
        return _event(
            family="transit_aspect",
            event_id=_event_id("transit_aspect", body, tname, asp, f"{e:.0f}", jd),
            datetime=_iso_local(jd, self.tz), standing=standing,
            transiting=body, natal=tname, aspect=asp, phase=phase,
            cycle_stage=stage, speed_class=_speed_class(body),
            house_placidus=None, house_wholesign=None, sign=sign,
            dignity=dignity,
            segment=_segment(jd, self.start_jd, self.end_jd, self.horizon),
            grounding=grounding)

    def _aspect_grounding(self, body, tname, is_angle, asp, phase, stage, tags) -> dict:
        if not is_angle:
            return {"kind": "point_aspects", "transiting_point": body,
                    "natal_point": tname, "point": tname, "aspect": asp,
                    "phase": phase, "cycle_stage": stage, "topic_tags": tags}
        if tname == "Ascendant":
            return {"kind": "ascendant", "transiting_point": body, "aspect": asp,
                    "phase": phase, "cycle_stage": stage, "angle": tname,
                    "topic_tags": tags + ["Ascendant", "rising", "angle"]}
        # MC / IC / Descendant have no corpus kind -> "other" + rich tags
        return {"kind": "other", "transiting_point": body, "aspect": asp,
                "phase": phase, "cycle_stage": stage, "angle": tname,
                "topic_tags": tags + [tname, "angle", "midheaven"
                                      if tname == "MC" else tname.lower()]}

    # =====================================================================
    # 4b. INGRESSES
    # =====================================================================
    def _sign_ingress_bodies(self) -> list[str]:
        if self.horizon == "month":
            return ["Sun", "Mercury", "Venus", "Mars"]          # fast + Sun
        if self.horizon == "year":
            return ["Sun", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
        return []                                               # day: none (§6)

    def _house_ingress_bodies(self) -> list[str]:
        if self.degraded:
            return []                                           # no houses (§8)
        if self.horizon == "day":
            return ["Moon", "Sun", "Mercury", "Venus", "Mars"]  # Moon + fast
        if self.horizon == "month":
            return ["Sun", "Mercury", "Venus", "Mars"]          # fast + Sun
        return ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]  # year: slow

    def sign_ingresses(self) -> list[dict]:
        events = []
        for body in self._sign_ingress_bodies():
            sid = SWE_ID[body]
            prev = None
            for jd, lon, _spd in self._samples(body):
                s = _sign_index(lon)
                if prev is not None and s != prev[0]:
                    s1 = s
                    jd_x = _bisect_predicate(
                        sid, lambda L, s1=s1: _sign_index(L) == s1, prev[1], jd)
                    if self._in_window(jd_x):
                        events.append(self._make_sign_ingress(body, jd_x))
                prev = (s, jd)
        return events

    def _make_sign_ingress(self, body: str, jd: float) -> dict:
        lon = _lon_at(jd, SWE_ID[body])
        s = _sign_index(lon)
        sign, element = SIGNS[s], ELEMENTS[s]
        tags = ["ingress", "sign ingress", body, sign, element,
                f"{body} enters {sign}", _speed_class(body) or ""]
        return _event(
            family="ingress_sign",
            event_id=_event_id("ingress_sign", body, None, None, sign, jd),
            datetime=_iso_local(jd, self.tz), standing=False,
            transiting=body, natal=None, aspect=None, phase=None,
            cycle_stage=None, speed_class=_speed_class(body),
            house_placidus=None, house_wholesign=None, sign=sign, dignity=None,
            segment=_segment(jd, self.start_jd, self.end_jd, self.horizon),
            grounding={"kind": "sign_element", "point": body, "sign": sign,
                       "element": element, "topic_tags": tags})

    def house_ingresses(self) -> list[dict]:
        """Ingress into a natal house. Detection runs on the Placidus cusps (they
        drive domain routing); the whole-sign house at the same instant is
        recorded as classical texture (SPEC §4b). If Placidus is undefined
        (circumpolar natal) we detect on whole-sign and leave placidus null."""
        events = []
        detect_cusps = self.plac_cusps if self.plac_cusps else self.ws_cusps
        on_placidus = self.plac_cusps is not None
        if not detect_cusps:
            return events
        for body in self._house_ingress_bodies():
            sid = SWE_ID[body]
            prev = None
            for jd, lon, _spd in self._samples(body):
                h = _house_of(lon, detect_cusps)
                if prev is not None and h != prev[0]:
                    h1 = h
                    jd_x = _bisect_predicate(
                        sid, lambda L, h1=h1: _house_of(L, detect_cusps) == h1,
                        prev[1], jd)
                    if self._in_window(jd_x):
                        events.append(self._make_house_ingress(body, jd_x, on_placidus))
                prev = (h, jd)
        return events

    def _make_house_ingress(self, body: str, jd: float, on_placidus: bool) -> dict:
        lon = _lon_at(jd, SWE_ID[body])
        hp = _house_of(lon, self.plac_cusps) if self.plac_cusps else None
        hw = _house_of(lon, self.ws_cusps) if self.ws_cusps else None
        driver = hp if on_placidus else hw
        sign = SIGNS[_sign_index(lon)]
        tags = ["ingress", "house ingress", body, f"house {driver}",
                f"{body} enters house {driver}", _speed_class(body) or ""]
        return _event(
            family="ingress_house",
            event_id=_event_id("ingress_house", body, None, None, str(driver), jd),
            datetime=_iso_local(jd, self.tz), standing=False,
            transiting=body, natal=None, aspect=None, phase=None,
            cycle_stage=None, speed_class=_speed_class(body),
            house_placidus=hp, house_wholesign=hw, sign=sign, dignity=None,
            segment=_segment(jd, self.start_jd, self.end_jd, self.horizon),
            grounding={"kind": "point_house", "point": body,
                       "house_placidus": hp, "house_wholesign": hw,
                       "topic_tags": tags})

    # =====================================================================
    # 4c. LUNATIONS & ECLIPSES
    # =====================================================================
    def lunations(self) -> list[dict]:
        """New/Full Moons in window. On YEAR, ordinary lunations are demoted and
        only eclipses survive (SPEC §6). Each lunation that coincides with an
        ephemeris eclipse is re-tagged family='eclipse'."""
        eclipses = self._eclipse_instants()   # [(jd, 'solar'|'lunar', type_str)]
        events: list[dict] = []

        year = self.horizon == "year"
        if not year:
            for jd, kind in self._syzygies():   # kind: 'new'|'full'
                ecl = self._match_eclipse(jd, kind, eclipses)
                events.append(self._make_lunation(jd, kind, ecl))
        else:
            # YEAR: eclipses only, located directly from the ephemeris.
            for jd, sl, etype in eclipses:
                kind = "new" if sl == "solar" else "full"
                events.append(self._make_lunation(jd, kind, (sl, etype)))
        return events

    def _syzygies(self) -> list[tuple[float, str]]:
        """New (Sun-Moon elongation crosses 0) and Full (crosses 180) instants in
        window, via crossings of E = (Moon - Sun) mod 360."""
        sun = self._samples("Sun")
        moon = self._samples("Moon")
        out: list[tuple[float, str]] = []
        for e, kind in ((0.0, "new"), (180.0, "full")):
            prev = None
            for (jd, slon, _s), (_jd2, mlon, _m) in zip(sun, moon):
                f = _signed180(_norm360(mlon - slon) - e)
                if prev is not None:
                    pf, pjd = prev
                    if (pf < 0) != (f < 0) and abs(pf) + abs(f) < 180.0:
                        jd_x = self._bisect_syzygy(e, pjd, pf, jd, f)
                        if self._in_window(jd_x):
                            out.append((jd_x, kind))
                prev = (f, jd)
        return out

    def _bisect_syzygy(self, e, jd0, f0, jd1, f1, iters=60) -> float:
        for _ in range(iters):
            jm = 0.5 * (jd0 + jd1)
            fm = _signed180(_norm360(_lon_at(jm, swe.MOON) - _lon_at(jm, swe.SUN)) - e)
            if fm == 0.0:
                return jm
            if (f0 < 0) != (fm < 0):
                jd1, f1 = jm, fm
            else:
                jd0, f0 = jm, fm
        return 0.5 * (jd0 + jd1)

    def _eclipse_instants(self) -> list[tuple[float, str, str]]:
        out: list[tuple[float, str, str]] = []
        # solar (global search)
        jd = self.start_jd
        for _ in range(40):
            try:
                retflag, tret = swe.sol_eclipse_when_glob(jd, EPHE_FLAG, 0, False)
            except Exception:
                break
            tmax = tret[0]
            if tmax >= self.end_jd:
                break
            if tmax >= self.start_jd:
                out.append((tmax, "solar", _solar_ecl_type(retflag)))
            jd = tmax + 2.0
        # lunar
        jd = self.start_jd
        for _ in range(40):
            try:
                retflag, tret = swe.lun_eclipse_when(jd, EPHE_FLAG, 0, False)
            except Exception:
                break
            tmax = tret[0]
            if tmax >= self.end_jd:
                break
            if tmax >= self.start_jd:
                out.append((tmax, "lunar", _lunar_ecl_type(retflag)))
            jd = tmax + 2.0
        return out

    @staticmethod
    def _match_eclipse(jd, kind, eclipses, tol=0.12):
        want = "solar" if kind == "new" else "lunar"
        for ejd, sl, etype in eclipses:
            if sl == want and abs(ejd - jd) <= tol:
                return (sl, etype)
        return None

    def _make_lunation(self, jd: float, kind: str, ecl) -> dict:
        moon_lon = _lon_at(jd, swe.MOON)
        sign = SIGNS[_sign_index(moon_lon)]
        is_eclipse = ecl is not None
        family = "eclipse" if is_eclipse else "lunation"
        phase_word = "new moon" if kind == "new" else "full moon"

        # house of the lunation (both systems) when a birth time supports it
        hp = hw = None
        if not self.degraded:
            hp = _house_of(moon_lon, self.plac_cusps) if self.plac_cusps else None
            hw = _house_of(moon_lon, self.ws_cusps) if self.ws_cusps else None

        # aspects the lunation makes to natal points -> topic tags (SPEC §4c)
        natal_tags = self._lunation_natal_aspects(moon_lon)

        tags = ["lunation", phase_word, sign, "Moon", "Sun"]
        if is_eclipse:
            sl, etype = ecl
            tags += ["eclipse", f"{sl} eclipse", f"{etype} eclipse"]
        tags += natal_tags

        # grounding: point_house when a house is known, else "other" (SPEC §9)
        if hp is not None or hw is not None:
            grounding = {"kind": "point_house", "point": "Moon",
                         "house_placidus": hp, "house_wholesign": hw,
                         "topic_tags": tags}
        else:
            grounding = {"kind": "other", "topic_tags": tags}

        # A lunation/eclipse is a pure sky event (a Sun-Moon syzygy), not a body
        # transiting TO a natal point, so bodies.transiting is null. This is also
        # what keeps invariant 2 literally true on the YEAR horizon: the Moon
        # never occupies the transiting slot; eclipses survive as sky events and
        # the luminary is carried in grounding.point / topic_tags instead.
        return _event(
            family=family,
            event_id=_event_id(family, "Moon", None, None, phase_word, jd),
            datetime=_iso_local(jd, self.tz), standing=False,
            transiting=None, natal=None, aspect=None, phase=None,
            cycle_stage=None, speed_class=None,
            house_placidus=hp, house_wholesign=hw, sign=sign, dignity=None,
            segment=_segment(jd, self.start_jd, self.end_jd, self.horizon),
            grounding=grounding)

    def _lunation_natal_aspects(self, moon_lon: float, orb: float = 3.0) -> list[str]:
        tags = []
        for nm in NATAL_BODIES:
            sep = _angular_sep(moon_lon, self.natal_lon[nm])
            for asp, angle in ASPECTS:
                if abs(sep - angle) <= orb:
                    tags.append(f"{asp} natal {nm}")
                    break
        return tags

    # =====================================================================
    # 4d. PROFECTIONS — OPTIONAL, OFF BY DEFAULT (SPEC §4d)
    # =====================================================================
    def profections(self) -> list[dict]:
        if not self.config.enable_profections:
            return []
        # Extension point only: annual/monthly/daily whole-sign profection,
        # emitting the activated house + its lord as a focus event. Deliberately
        # unimplemented pending the corpus-coverage decision (SPEC §4d).
        raise NotImplementedError("profections module is stubbed off (SPEC §4d)")


# ---------------------------------------------------------------------------
# EVENT / DIGNITY CONSTRUCTORS
# ---------------------------------------------------------------------------
def _event(**kw) -> dict:
    """Assemble one Event dict with every §11 key present (null where N/A) and a
    stable key order."""
    return {
        "event_id": kw["event_id"],
        "family": kw["family"],
        "datetime": kw["datetime"],
        "standing": kw["standing"],
        "bodies": {"transiting": kw["transiting"], "natal": kw["natal"]},
        "aspect": kw["aspect"],
        "phase": kw["phase"],
        "cycle_stage": kw["cycle_stage"],
        "speed_class": kw["speed_class"],
        "house_placidus": kw["house_placidus"],
        "house_wholesign": kw["house_wholesign"],
        "sign": kw["sign"],
        "dignity": kw["dignity"],
        "segment": kw["segment"],
        "grounding": kw["grounding"],
    }


def _dignity_summary(classifications: Optional[dict]) -> Optional[dict]:
    """Compact natal dignity from a chart point's classifications block."""
    if not classifications:
        return None
    return {
        "sign": None,  # sign lives on the natal point; tone only needs the flags
        "sign_ruler": classifications["sign_ruler"],
        "in_domicile": classifications["in_domicile"],
        "in_detriment": classifications["in_detriment"],
        "in_exaltation": classifications["in_exaltation"],
        "in_fall": classifications["in_fall"],
    }


# Swiss Ephemeris eclipse-type bit flags -> label.
def _solar_ecl_type(flag: int) -> str:
    if flag & swe.ECL_TOTAL:
        return "total"
    if flag & swe.ECL_ANNULAR:
        return "annular"
    if flag & swe.ECL_ANNULAR_TOTAL:
        return "hybrid"
    if flag & swe.ECL_PARTIAL:
        return "partial"
    return "solar"


def _lunar_ecl_type(flag: int) -> str:
    if flag & swe.ECL_TOTAL:
        return "total"
    if flag & swe.ECL_PARTIAL:
        return "partial"
    if flag & swe.ECL_PENUMBRAL:
        return "penumbral"
    return "lunar"


# ---------------------------------------------------------------------------
# RUN ID (SPEC §12; same scheme as natal/synastry runs)
# ---------------------------------------------------------------------------
def mint_run_id(now_utc: datetime) -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=3))
    return now_utc.strftime("%Y%m%d-%H%M%S") + "_" + suffix


def _natal_ref(natal: dict) -> str:
    """Stable short hash identifying the natal chart the forecast was built on."""
    blob = json.dumps(natal, sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


# ===========================================================================
# PUBLIC ENTRY POINT
# ===========================================================================
def compute_forecast(natal: dict, target_date, horizon: str, *,
                     latitude: Optional[float] = None,
                     longitude: Optional[float] = None,
                     config: Optional[ForecastConfig] = None,
                     now: Optional[datetime] = None,
                     run_id: Optional[str] = None,
                     window_tz: Optional[str] = None) -> Forecast:
    """Build the dated forecast object for one natal chart over one horizon.

    natal        : a chart object from compute_chart() (consumed as-is).
    target_date  : date the horizon starts on — a datetime.date, a "YYYY-MM-DD"
                   string, or None for "today" in the BIRTH-location tz (§3).
    horizon      : "day" | "month" | "year"  (week is intentionally absent).
    latitude/longitude : birth coordinates, needed ONLY for the day/hour ruler
                   (DAY horizon). Omit them and the ruler is reported as null.
    now / run_id : injection points for deterministic tests (invariant 7).
    window_tz    : IANA tz that anchors the DAY/MONTH/YEAR window (CAL_00 D1: the
                   user's CURRENT location). Default = the birth-location tz, so
                   behaviour is unchanged when omitted. Houses stay natal.
    """
    if horizon not in ("day", "month", "year"):
        raise ValueError(f"bad horizon: {horizon!r} (day|month|year only)")
    config = config or ForecastConfig()
    now = now or datetime.now(timezone.utc)

    tzname = window_tz or natal["meta"]["timezone"]
    tz = ZoneInfo(tzname)

    # --- target date resolved in the birth-location tz (SPEC §3) ------------
    if target_date is None:
        td = datetime.now(tz).date()
    elif isinstance(target_date, str):
        td = _date.fromisoformat(target_date)
    elif isinstance(target_date, datetime):
        td = target_date.date()
    else:
        td = target_date  # datetime.date

    start_local = datetime(td.year, td.month, td.day, 0, 0, tzinfo=tz)
    end_local = _add_horizon(start_local, horizon)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    start_jd = julian_day_ut(start_utc)
    end_jd = julian_day_ut(end_utc)

    fc = _Forecaster(natal, horizon, tz, start_jd, end_jd, latitude, longitude, config)

    # --- detect every family, then order by datetime ------------------------
    events: list[dict] = []
    events += fc.transit_aspects()
    events += fc.sign_ingresses()
    events += fc.house_ingresses()
    events += fc.lunations()
    events += fc.profections()
    events.sort(key=lambda e: (e["datetime"], e["event_id"]))

    # --- counts (SPEC §11; invariant 9) -------------------------------------
    by_family: dict[str, int] = {}
    by_segment: dict[str, int] = {}
    for e in events:
        by_family[e["family"]] = by_family.get(e["family"], 0) + 1
        seg = e["segment"] if e["segment"] is not None else "none"
        by_segment[seg] = by_segment.get(seg, 0) + 1

    forecast: dict = {
        "meta": {
            "natal_ref": _natal_ref(natal),
            "target_date": td.isoformat(),
            "horizon": horizon,
            "generated_at": now.replace(microsecond=0).astimezone(timezone.utc)
                               .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "run_id": run_id or mint_run_id(now),
            "precision_tier": fc.tier,
            "degraded": fc.degraded,
            "suppressed_families": fc.suppressed,
            "ephemeris": cc.EPHEMERIS_NAME,
            "config": {"enable_profections": config.enable_profections,
                       "enable_lots_targets": config.enable_lots_targets},
        },
        "window": {
            "start": start_local.replace(microsecond=0).isoformat(),
            "end": end_local.replace(microsecond=0).isoformat(),
            "tz": tzname,
        },
        "events": events,
        "counts": {"by_family": by_family, "by_segment": by_segment},
    }

    # DAY horizon carries the target-date planetary day/hour ruler (invariant 5).
    # MONTH/YEAR do not. Needs birth coordinates for the sunrise anchor.
    if horizon == "day":
        day_ruler = hour_ruler = None
        if latitude is not None and longitude is not None:
            noon_local = datetime(td.year, td.month, td.day, 12, 0, tzinfo=tz)
            jd_noon = julian_day_ut(noon_local.astimezone(timezone.utc))
            day_ruler, hour_ruler = compute_planetary_day_hour(
                jd_noon, latitude, longitude)
        forecast["rulers"] = {"planetary_day": day_ruler,
                              "planetary_hour": hour_ruler}

    return cast(Forecast, forecast)


# ---------------------------------------------------------------------------
# PERSISTENCE (SPEC §12)
# ---------------------------------------------------------------------------
# Forecasts are retained as data, one run folder per generation, using the same
# YYYYMMDD-HHMMSS_<3char> scheme as natal/synastry runs. compute_forecast()
# itself stays a pure function (like compute_chart); this helper does the I/O,
# mirroring how run.py owns all writing for LAYER 1.
_ENGINE_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
_REPO_ROOT = os.path.normpath(os.path.join(_ENGINE_ROOT, "..", ".."))


def write_forecast(forecast: dict, runs_dir: Optional[str] = None) -> str:
    """Persist a forecast into runs/<run_id>/, returning the written file path.
    The file name carries the horizon and target date so a forecast pulled out
    of its folder is self-identifying (cf. the birth-date suffix on chart runs)."""
    meta = forecast["meta"]
    runs_dir = runs_dir or os.path.join(_REPO_ROOT, "runs")
    run_dir = os.path.join(runs_dir, meta["run_id"])
    os.makedirs(run_dir, exist_ok=True)
    path = os.path.join(run_dir, f"forecast_{meta['horizon']}_{meta['target_date']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(forecast, f, ensure_ascii=False, indent=2)
    return path


# ---------------------------------------------------------------------------
# DEMO
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from compute_chart import BirthData, compute_chart

    natal = compute_chart(BirthData(
        year=1990, month=6, day=15, hour=14, minute=30,
        latitude=41.0082, longitude=28.9784, time_precision="exact"))
    fcast = compute_forecast(natal, "2026-07-01", "month",
                             latitude=41.0082, longitude=28.9784)
    print(f"events={len(fcast['events'])}  by_family={fcast['counts']['by_family']}")
    out = write_forecast(fcast)
    print(f"Wrote {out}")
