#!/usr/bin/env python3
"""
solar_return.py — Solar Return moment finder + chart (via L1 ``compute_chart``).

Moment
------
Given a natal Sun longitude and a calendar year, find the UTC datetime(s) when
the transiting Sun returns to that longitude.

Chart
-----
``compute_solar_return_chart`` builds the return chart at that moment for a
chosen location by calling L1 ``compute_chart(..., utc_override=moment)`` —
same shape as a natal chart (points, houses, aspects, angles). No chart logic
is duplicated here.

Ephemeris path is identical to L1: ``swe.calc_ut(jd, swe.SUN, EPHE_FLAG)`` with
``EPHE_FLAG = FLG_MOSEPH | FLG_SPEED`` via ``compute_chart``.

Edge cases (moment)
-------------------
* All math is in UTC — timezone / DST belong to natal-Sun derivation (L1), not
  to the return search.
* Southern hemisphere and polar latitudes do not affect geocentric Sun
  longitude; the moment finder never reads latitude.
* Leap years: the search window covers a full calendar year plus a 2-day margin.
* Natal Sun near 0° Aries: residuals use a signed±180° difference so the 0/360
  wrap does not invent or miss a root.
* Rare double-return (Sun near ~0° Capricorn / New Year): a leap-year calendar
  year can contain two tropical-year crossings of the same longitude. Both are
  found; ``find_solar_return_utc`` returns the earlier. Spurious half-year
  "roots" at Sun–natal opposition (signed180 discontinuity) are rejected.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import swisseph as swe  # type: ignore[import-not-found]

from chart_types import Chart
from compute_chart import BirthData, EPHE_FLAG, _norm360, compute_chart, julian_day_ut

# Daily Sun motion is ~1°. A true zero-crossing over a 1-day step moves f by
# ~1°; the signed180 wrap at ±180° jumps by ~360°. Reject the wrap.
_MAX_STEP_DELTA_DEG = 90.0
_GRID_STEP_DAYS = 1.0
_YEAR_MARGIN_DAYS = 2.0
_BISECT_ITERS = 60
# ~0.001 day ≈ 1.4 minutes; final polish uses speed-based Newton-ish refine.
_BISECT_TOL_DAYS = 1e-8


def _signed180(deg: float) -> float:
    return (deg + 180.0) % 360.0 - 180.0


def _sun_longitude(jd_ut: float) -> float:
    """Tropical geocentric Sun longitude — same call shape as compute_chart."""
    xx, _ = swe.calc_ut(jd_ut, swe.SUN, EPHE_FLAG)
    return _norm360(xx[0])


def _sun_lon_speed(jd_ut: float) -> tuple[float, float]:
    xx, _ = swe.calc_ut(jd_ut, swe.SUN, EPHE_FLAG)
    return _norm360(xx[0]), xx[3]


def _jd_to_utc(jd_ut: float) -> datetime:
    y, mo, d, h = swe.revjul(jd_ut, swe.GREG_CAL)
    return datetime(int(y), int(mo), int(d), tzinfo=timezone.utc) + timedelta(hours=h)


def _residual(jd_ut: float, natal_sun_longitude: float) -> float:
    return _signed180(_sun_longitude(jd_ut) - _norm360(natal_sun_longitude))


def _bisect_root(natal_sun_longitude: float, jd0: float, jd1: float,
                 f0: float) -> float:
    for _ in range(_BISECT_ITERS):
        if jd1 - jd0 <= _BISECT_TOL_DAYS:
            break
        mid = 0.5 * (jd0 + jd1)
        fm = _residual(mid, natal_sun_longitude)
        if fm == 0.0:
            return mid
        if (f0 < 0.0) != (fm < 0.0):
            jd1 = mid
        else:
            jd0, f0 = mid, fm
    return 0.5 * (jd0 + jd1)


def _refine_with_speed(natal_sun_longitude: float, jd: float) -> float:
    """One or two Newton steps using solar speed (deg/day) for sub-second lock."""
    for _ in range(3):
        lon, speed = _sun_lon_speed(jd)
        if speed == 0.0:
            break
        err = _signed180(lon - _norm360(natal_sun_longitude))
        jd -= err / speed
    return jd


def find_solar_return_jds(natal_sun_longitude: float, year: int) -> list[float]:
    """
    Julian Day (UT) of every true solar return whose UTC calendar year is ``year``.

    Normally one instant. Rarely two when the tropical-year spacing places both
    a early-January and a late-December crossing inside the same leap year for
    longitudes near the New Year Sun (~0° Capricorn cusp).
    """
    if not isinstance(year, int):
        raise TypeError("year must be an int")
    if year < 1 or year > 9999:
        raise ValueError(f"year out of range: {year}")
    target = _norm360(float(natal_sun_longitude))

    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    jd_lo = julian_day_ut(start) - _YEAR_MARGIN_DAYS
    jd_hi = julian_day_ut(end) + _YEAR_MARGIN_DAYS

    roots: list[float] = []
    jd = jd_lo
    f_prev = _residual(jd, target)
    while jd < jd_hi:
        jd_next = min(jd + _GRID_STEP_DAYS, jd_hi)
        f_next = _residual(jd_next, target)
        # Sign change with a small step → true crossing (not ±180 wrap).
        if f_prev == 0.0:
            root = jd
        elif (f_prev < 0.0) != (f_next < 0.0) and abs(f_next - f_prev) < _MAX_STEP_DELTA_DEG:
            root = _bisect_root(target, jd, jd_next, f_prev)
            root = _refine_with_speed(target, root)
        else:
            root = None
        if root is not None:
            utc = _jd_to_utc(root)
            if utc.year == year:
                # Dedup near-identical hits from margin / grid edges.
                if not roots or abs(root - roots[-1]) > 1e-4:
                    roots.append(root)
        jd, f_prev = jd_next, f_next
    return roots


def find_solar_return_utc(natal_sun_longitude: float, year: int) -> datetime:
    """
    UTC datetime of the solar return for ``year``.

    Parameters
    ----------
    natal_sun_longitude:
        Tropical geocentric natal Sun longitude in degrees [0, 360).
    year:
        Gregorian calendar year of the return (UTC year of the instant).

    Returns
    -------
    datetime
        Timezone-aware UTC instant. If two returns fall in ``year`` (rare New
        Year / Capricorn-cusp double-return), the earlier instant is returned.
    """
    roots = find_solar_return_jds(natal_sun_longitude, year)
    if not roots:
        raise ValueError(
            f"no solar return found for longitude={natal_sun_longitude!r} year={year}"
        )
    return _jd_to_utc(roots[0])


def sun_longitude_at(utc: datetime) -> float:
    """Transiting Sun longitude at an aware UTC datetime (test / verify helper)."""
    if utc.tzinfo is None:
        raise ValueError("utc must be timezone-aware")
    return _sun_longitude(julian_day_ut(utc.astimezone(timezone.utc)))


def compute_solar_return_chart(
    moment_utc: datetime,
    latitude: float,
    longitude: float,
) -> Chart:
    """
    Build a Solar Return chart at ``moment_utc`` for ``(latitude, longitude)``.

    Reuses L1 ``compute_chart`` with ``utc_override`` (same path ACG relocation
    uses). The returned dict has the natal chart shape: ``points``, ``sectors``,
    ``axes``, ``relations``, etc. Planet longitudes are fixed by the moment;
    houses and angles depend on the return location.

    Parameters
    ----------
    moment_utc:
        Timezone-aware UTC instant from ``find_solar_return_utc``.
    latitude, longitude:
        Return location in degrees (east/north positive).

    Raises
    ------
    ValueError
        If ``moment_utc`` is naive (no tzinfo), or latitude/longitude are
        outside the valid geographic range.
    """
    if moment_utc.tzinfo is None:
        raise ValueError("moment_utc must be timezone-aware")
    if not (-90.0 <= latitude <= 90.0):
        raise ValueError(f"latitude out of range: {latitude}")
    if not (-180.0 <= longitude <= 180.0):
        raise ValueError(f"longitude out of range: {longitude}")

    instant = moment_utc.astimezone(timezone.utc)
    # BirthData calendar fields are placeholders when utc_override is set;
    # the instant is taken entirely from utc_override (sub-minute precision).
    bd = BirthData(
        year=instant.year,
        month=instant.month,
        day=instant.day,
        hour=instant.hour,
        minute=instant.minute,
        latitude=latitude,
        longitude=longitude,
        time_precision="exact",
    )
    return compute_chart(bd, utc_override=instant)
