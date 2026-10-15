"""cal_astro.py - ephemeris primitives for the calendar (CAL_01).

Reuses L1 (d_layer/compute_chart.py) for the ephemeris flag, house lookup and
timezone resolution, and the forecast engine for eclipse typing. It does not fork them.
Everything here works on Julian Day UT floats. Local dates are derived only at
output time (CAL_01 §4).

Search strategy: a body's longitude is monotonic between its stations. So a
grid of daily samples with the station instants inserted brackets every crossing
of a fixed longitude (exact aspect, orb edge, sign boundary) in exactly one step.
Bisection then refines it. That makes the search exhaustive regardless of step size.
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Iterable, Optional
from zoneinfo import ZoneInfo

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
for _p in (os.path.join(_ROOT, "d_layer"), os.path.join(_ROOT, "Forecast_compute")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import swisseph as swe  # type: ignore[import-not-found]  # noqa: E402

from compute_chart import (  # noqa: E402
    EPHE_FLAG,
    EPHEMERIS_NAME,
    SIGNS,
    _house_of,
    _norm360,
    julian_day_ut,
    resolve_timezone,
)
from compute_forecast import _lunar_ecl_type, _signed180, _solar_ecl_type  # noqa: E402

__all__ = [
    "EPHE_FLAG", "EPHEMERIS_NAME", "SWE", "SIGN_KEYS", "house_of", "norm360",
    "signed180", "resolve_timezone", "lon", "lon_speed", "elongation",
    "sign_key", "deg_in_sign", "jd_of", "jd_to_utc", "iso_utc", "local_date",
    "local_midnight_jd", "bisect", "stations", "sample_grid", "moon_phase",
    "solar_eclipses", "lunar_eclipses",
]

SWE = {"sun": swe.SUN, "moon": swe.MOON, "mercury": swe.MERCURY,
       "venus": swe.VENUS, "mars": swe.MARS, "jupiter": swe.JUPITER,
       "saturn": swe.SATURN, "uranus": swe.URANUS, "neptune": swe.NEPTUNE,
       "pluto": swe.PLUTO}
SIGN_KEYS = [s.lower() for s in SIGNS]

norm360 = _norm360
signed180 = _signed180
house_of = _house_of


# --- ephemeris ---------------------------------------------------------------
def lon(jd: float, body: str) -> float:
    return _norm360(swe.calc_ut(jd, SWE[body], EPHE_FLAG)[0][0])


def lon_speed(jd: float, body: str) -> tuple[float, float]:
    xx, _ = swe.calc_ut(jd, SWE[body], EPHE_FLAG)
    return _norm360(xx[0]), xx[3]


def elongation(jd: float) -> float:
    """Sun-Moon elongation (Moon - Sun) mod 360. Waxing when < 180 (CAL_01 §2 moon_phase_daily)."""
    return _norm360(lon(jd, "moon") - lon(jd, "sun"))


moon_phase = elongation


def sign_key(longitude: float) -> str:
    return SIGN_KEYS[int(_norm360(longitude) // 30) % 12]


def deg_in_sign(longitude: float) -> float:
    return round(_norm360(longitude) % 30.0, 4)


# --- time ---------------------------------------------------------------------
def jd_of(dt: datetime) -> float:
    return julian_day_ut(dt.astimezone(timezone.utc))


def jd_to_utc(jd: float) -> datetime:
    y, mo, d, h = swe.revjul(jd, swe.GREG_CAL)
    return datetime(int(y), int(mo), int(d), tzinfo=timezone.utc) + timedelta(hours=h)


def _round_second(jd: float) -> datetime:
    return (jd_to_utc(jd) + timedelta(milliseconds=500)).replace(microsecond=0)


def iso_utc(jd: float) -> str:
    """ISO-8601 UTC, rounded to the second, 'Z' suffix (byte-stable)."""
    return _round_second(jd).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso_utc(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def local_date(jd: float, tz: str) -> str:
    """The instant's date in the user's tz (DST-aware), rounded to the second first."""
    return _round_second(jd).astimezone(ZoneInfo(tz)).date().isoformat()


def local_date_of_iso(t_utc: str, tz: str) -> str:
    return parse_iso_utc(t_utc).astimezone(ZoneInfo(tz)).date().isoformat()


def local_midnight_jd(d: date, tz: str) -> float:
    return jd_of(datetime(d.year, d.month, d.day, tzinfo=ZoneInfo(tz)))


def local_time_jd(d: date, hour: int, minute: int, tz: str) -> float:
    return jd_of(datetime(d.year, d.month, d.day, hour, minute, tzinfo=ZoneInfo(tz)))


# --- root finding -----------------------------------------------------------------
def bisect(f: Callable[[float], float], jd0: float, jd1: float,
           f0: Optional[float] = None, tol_days: float = 1e-8, max_iter: int = 80) -> float:
    """Root of f on [jd0, jd1], given a sign change of f across the bracket."""
    if f0 is None:
        f0 = f(jd0)
    for _ in range(max_iter):
        if jd1 - jd0 <= tol_days:
            break
        jm = 0.5 * (jd0 + jd1)
        fm = f(jm)
        if fm == 0.0:
            return jm
        if (f0 < 0) != (fm < 0):
            jd1 = jm
        else:
            jd0, f0 = jm, fm
    return 0.5 * (jd0 + jd1)


# --- stations ---------------------------------------------------------------------
def stations(body: str, jd0: float, jd1: float, step: float = 1.0) -> list[tuple[float, str]]:
    """Stations (speed = 0) in [jd0, jd1): [(jd, 'R'|'D')]. The Sun and Moon never station."""
    if body in ("sun", "moon"):
        return []
    out: list[tuple[float, str]] = []

    def spd(j: float) -> float:
        return lon_speed(j, body)[1]

    jd, s = jd0, spd(jd0)
    while jd < jd1:
        nj = min(jd + step, jd1)
        ns = spd(nj)
        if (s < 0) != (ns < 0):
            root = bisect(spd, jd, nj, s, tol_days=1e-9)
            if jd0 <= root < jd1:
                out.append((root, "R" if ns < 0 else "D"))
        jd, s = nj, ns
    return out


def sample_grid(body: str, jd0: float, jd1: float, step: float = 1.0,
                extra: Iterable[float] = ()) -> list[float]:
    """Uniform grid over [jd0, jd1] plus the body's station instants (see module doc)."""
    pts = set()
    n = int((jd1 - jd0) / step)
    for i in range(n + 1):
        pts.add(jd0 + i * step)
    pts.add(jd1)
    for j, _ in stations(body, jd0, jd1):
        pts.add(j)
    pts.update(x for x in extra if jd0 <= x <= jd1)
    return sorted(pts)


# --- eclipses -----------------------------------------------------------------------
def solar_eclipses(jd0: float, jd1: float) -> list[tuple[float, str]]:
    """[(jd_max, kind)] for global solar eclipses with maximum in [jd0, jd1)."""
    out, jd = [], jd0
    while True:
        flag, tret = swe.sol_eclipse_when_glob(jd, EPHE_FLAG, 0, False)
        t = tret[0]
        if t >= jd1:
            return out
        if t >= jd0:
            out.append((t, _solar_ecl_type(flag)))
        jd = t + 2.0


def lunar_eclipses(jd0: float, jd1: float) -> list[tuple[float, str]]:
    out, jd = [], jd0
    while True:
        flag, tret = swe.lun_eclipse_when(jd, EPHE_FLAG, 0, False)
        t = tret[0]
        if t >= jd1:
            return out
        if t >= jd0:
            out.append((t, _lunar_ecl_type(flag)))
        jd = t + 2.0
