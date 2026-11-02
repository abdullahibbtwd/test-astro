#!/usr/bin/env python3
"""Solar Return *chart* tests (Phase 2 — compute_chart reuse).

Run: python -m pytest backend/engine/d_layer/test_solar_return_chart.py -q
"""

from __future__ import annotations

import json
import os

from compute_chart import BirthData, compute_chart
from solar_return import (
    compute_solar_return_chart,
    find_solar_return_utc,
)

_HERE = os.path.dirname(os.path.abspath(__file__))
_FIXTURES = os.path.join(_HERE, "fixtures", "solar_return_refs.json")

_PLANETS = (
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
)
_ARCMINUTE = 1.0 / 60.0


def _signed180(deg: float) -> float:
    return (deg + 180.0) % 360.0 - 180.0


def _load_kano() -> dict:
    with open(_FIXTURES, encoding="utf-8") as fh:
        return next(r for r in json.load(fh) if r["id"] == "kano_2024")


def _natal_sun_and_moment(ref: dict):
    birth = ref["birth"]
    natal = compute_chart(BirthData(
        year=birth["year"], month=birth["month"], day=birth["day"],
        hour=birth["hour"], minute=birth["minute"],
        latitude=birth["latitude"], longitude=birth["longitude"],
        time_precision="exact",
    ))
    sun_lon = next(p["longitude"] for p in natal["points"] if p["name"] == "Sun")
    moment = find_solar_return_utc(sun_lon, ref["return_year"])
    return natal, sun_lon, moment


def test_return_chart_houses_planets_and_sun() -> None:
    ref = _load_kano()
    _natal, sun_lon, moment = _natal_sun_and_moment(ref)
    chart = compute_solar_return_chart(
        moment, ref["birth"]["latitude"], ref["birth"]["longitude"],
    )

    cusps = chart["sectors"]["whole_sign_cusps"]
    assert len(cusps) == 12

    names = {p["name"] for p in chart["points"]}
    for planet in _PLANETS:
        assert planet in names, planet

    sun = next(p for p in chart["points"] if p["name"] == "Sun")
    assert abs(_signed180(sun["longitude"] - sun_lon)) < _ARCMINUTE


def test_return_chart_shape_matches_natal_schema_keys() -> None:
    ref = _load_kano()
    natal, sun_lon, moment = _natal_sun_and_moment(ref)
    returned = compute_solar_return_chart(
        moment, ref["birth"]["latitude"], ref["birth"]["longitude"],
    )
    assert set(returned.keys()) == set(natal.keys())
    # Nested contracts the frontend relies on for chart rendering.
    for key in ("meta", "points", "axes", "sectors", "relations"):
        assert key in returned
    assert "ascendant" in returned["axes"] and "mc" in returned["axes"]
    assert "placidus_cusps" in returned["sectors"]
    assert "whole_sign_cusps" in returned["sectors"]
    assert set(returned["meta"].keys()) == set(natal["meta"].keys())
    # Sun still locked to natal longitude via the moment.
    sun = next(p for p in returned["points"] if p["name"] == "Sun")
    assert abs(_signed180(sun["longitude"] - sun_lon)) < _ARCMINUTE


def test_polar_latitude_returns_chart_not_crash() -> None:
    ref = _load_kano()
    _natal, sun_lon, moment = _natal_sun_and_moment(ref)
    chart = compute_solar_return_chart(moment, 89.0, 0.0)
    assert "points" in chart and "sectors" in chart
    # Placidus may be undefined above the polar circle; whole-sign remains.
    assert chart["sectors"]["placidus_cusps"] is None
    assert len(chart["sectors"]["whole_sign_cusps"]) == 12
    sun = next(p for p in chart["points"] if p["name"] == "Sun")
    assert abs(_signed180(sun["longitude"] - sun_lon)) < _ARCMINUTE


def test_relocated_vs_birth_location_houses_differ_sun_same() -> None:
    ref = _load_kano()
    _natal, sun_lon, moment = _natal_sun_and_moment(ref)
    birth = compute_solar_return_chart(
        moment, ref["birth"]["latitude"], ref["birth"]["longitude"],
    )
    # London — far enough west/north that houses/angles must move.
    relocated = compute_solar_return_chart(moment, 51.5074, -0.1278)

    sun_b = next(p for p in birth["points"] if p["name"] == "Sun")
    sun_r = next(p for p in relocated["points"] if p["name"] == "Sun")
    assert abs(_signed180(sun_b["longitude"] - sun_r["longitude"])) < _ARCMINUTE
    assert abs(_signed180(sun_b["longitude"] - sun_lon)) < _ARCMINUTE

    assert birth["axes"]["ascendant"]["longitude"] != relocated["axes"]["ascendant"]["longitude"]
    assert birth["sectors"]["whole_sign_cusps"] != relocated["sectors"]["whole_sign_cusps"]


def test_naive_moment_raises_clear_error() -> None:
    from datetime import datetime
    try:
        compute_solar_return_chart(datetime(2024, 1, 1, 12, 0), 12.0, 8.52)
        raised = False
    except ValueError as err:
        raised = True
        assert "timezone-aware" in str(err)
    assert raised
