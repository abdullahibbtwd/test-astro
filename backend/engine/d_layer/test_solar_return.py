#!/usr/bin/env python3
"""Solar Return moment-finder tests (instant only; no chart build).

Run: python -m pytest backend/engine/d_layer/test_solar_return.py -q
  or: python backend/engine/d_layer/test_solar_return.py
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from compute_chart import BirthData, compute_chart
from solar_return import (
    find_solar_return_jds,
    find_solar_return_utc,
    sun_longitude_at,
)

_HERE = os.path.dirname(os.path.abspath(__file__))
_FIXTURES = os.path.join(_HERE, "fixtures", "solar_return_refs.json")

_MINUTE = 60.0
_ARCMINUTE = 1.0 / 60.0  # degrees


def _load_refs() -> list[dict]:
    with open(_FIXTURES, encoding="utf-8") as fh:
        return json.load(fh)


def _parse_utc(iso_z: str) -> datetime:
    return datetime.strptime(iso_z, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _signed180(deg: float) -> float:
    return (deg + 180.0) % 360.0 - 180.0


def _natal_sun_longitude(birth: dict) -> float:
    chart = compute_chart(BirthData(
        year=birth["year"], month=birth["month"], day=birth["day"],
        hour=birth["hour"], minute=birth["minute"],
        latitude=birth["latitude"], longitude=birth["longitude"],
        time_precision="exact",
    ))
    return next(p["longitude"] for p in chart["points"] if p["name"] == "Sun")


def test_reference_returns_within_one_minute() -> None:
    for ref in _load_refs():
        lon = _natal_sun_longitude(ref["birth"])
        # Fixture longitude must match the L1 natal Sun (within a few arcsec).
        assert abs(_signed180(lon - ref["natal_sun"]["longitude"])) < 0.01, ref["id"]
        got = find_solar_return_utc(lon, ref["return_year"])
        expected = _parse_utc(ref["expected_utc"])
        delta_s = abs((got - expected).total_seconds())
        assert delta_s < _MINUTE, (
            f"{ref['id']}: |Δ|={delta_s:.2f}s got={got.isoformat()} "
            f"expected={expected.isoformat()}"
        )
        sun = sun_longitude_at(got)
        err_deg = abs(_signed180(sun - lon))
        assert err_deg < _ARCMINUTE, (
            f"{ref['id']}: Sun mismatch {err_deg * 60:.4f}' at {got.isoformat()}"
        )


def test_deterministic_same_input_twice() -> None:
    lon = 276.6057
    a = find_solar_return_utc(lon, 2024)
    b = find_solar_return_utc(lon, 2024)
    assert a == b
    assert a.tzinfo is not None
    assert a.utcoffset() == timezone.utc.utcoffset(None)


def test_polar_latitude_does_not_crash() -> None:
    chart = compute_chart(BirthData(
        year=2000, month=6, day=21, hour=12, minute=0,
        latitude=89.0, longitude=0.0, time_precision="exact",
    ))
    lon = next(p["longitude"] for p in chart["points"] if p["name"] == "Sun")
    got = find_solar_return_utc(lon, 2024)
    assert got.year == 2024
    assert abs(_signed180(sun_longitude_at(got) - lon)) < _ARCMINUTE


def test_zero_aries_and_southern_hemisphere() -> None:
    # 0° Aries wrap
    got = find_solar_return_utc(0.0, 2024)
    assert got.year == 2024
    assert abs(_signed180(sun_longitude_at(got) - 0.0)) < _ARCMINUTE

    # Southern hemisphere natal place still yields a clean return from its Sun lon.
    chart = compute_chart(BirthData(
        year=2000, month=6, day=21, hour=12, minute=0,
        latitude=-45.0, longitude=170.0, time_precision="exact",
    ))
    lon = next(p["longitude"] for p in chart["points"] if p["name"] == "Sun")
    got = find_solar_return_utc(lon, 2024)
    assert got.year == 2024
    assert abs(_signed180(sun_longitude_at(got) - lon)) < _ARCMINUTE


def test_rare_double_return_near_new_year_cusp() -> None:
    # Longitude of the Sun at 2024-01-01 00:00 UTC sits on the Capricorn /
    # calendar-year cusp: two tropical crossings fall inside leap year 2024.
    cusp = sun_longitude_at(datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc))
    roots = find_solar_return_jds(cusp, 2024)
    assert len(roots) == 2
    primary = find_solar_return_utc(cusp, 2024)
    assert primary == datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)


if __name__ == "__main__":
    test_reference_returns_within_one_minute()
    test_deterministic_same_input_twice()
    test_polar_latitude_does_not_crash()
    test_zero_aries_and_southern_hemisphere()
    test_rare_double_return_near_new_year_cusp()
    print("all solar_return tests passed")
