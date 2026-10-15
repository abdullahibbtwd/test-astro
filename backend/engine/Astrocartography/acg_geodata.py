#!/usr/bin/env python3
"""acg_geodata.py — loaders for the committed ACG geography index (change order v3 §2–§3).

    load_countries()      -> list of {iso_a2, iso_a3, name, name_tr, bbox}
    load_regions()        -> list of {admin1_id, iso_a2, name, name_tr, bbox}
    load_grid()           -> {"lat", "lon", "iso_a2", "admin1_id"} numpy arrays
    load_cities()         -> gazetteer cities (gazetteer.json v2)
    country_of_city(city) -> the countries.json entry for a gazetteer city, or None
    cities_in(iso_a2=None, admin1_id=None) -> gazetteer cities inside a country / region

Built by build_geo_index.py and build_gazetteer.py. Read-only; no network. Loaders are
cached (functools.lru_cache): treat the returned objects as immutable.
"""

from __future__ import annotations

import functools
import json
import os
from typing import Optional

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
COUNTRIES_PATH = os.path.join(_HERE, "countries.json")
REGIONS_PATH = os.path.join(_HERE, "regions.json")
GRID_PATH = os.path.join(_HERE, "geo_grid.npz")
GAZETTEER_PATH = os.path.join(_HERE, "gazetteer.json")


def _read_json(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@functools.lru_cache(maxsize=None)
def load_countries() -> list[dict]:
    return _read_json(COUNTRIES_PATH)


@functools.lru_cache(maxsize=None)
def load_regions() -> list[dict]:
    return _read_json(REGIONS_PATH)


@functools.lru_cache(maxsize=None)
def load_grid() -> dict[str, np.ndarray]:
    """Land sample points (0.5° grid + representative points of small countries and
    of regions the grid misses). Arrays are read-only."""
    with np.load(GRID_PATH, allow_pickle=False) as z:
        out = {k: z[k] for k in ("lat", "lon", "iso_a2", "admin1_id")}
    for a in out.values():
        a.flags.writeable = False
    return out


@functools.lru_cache(maxsize=None)
def load_cities() -> list[dict]:
    data = _read_json(GAZETTEER_PATH)
    return data["cities"] if isinstance(data, dict) else data


@functools.lru_cache(maxsize=None)
def _country_index() -> dict[str, dict]:
    return {c["iso_a2"]: c for c in load_countries()}


@functools.lru_cache(maxsize=None)
def _region_index() -> dict[str, dict]:
    return {r["admin1_id"]: r for r in load_regions()}


def country(iso_a2: str) -> Optional[dict]:
    return _country_index().get((iso_a2 or "").upper())


def region(admin1_id: str) -> Optional[dict]:
    return _region_index().get(admin1_id or "")


def country_of_city(city: dict) -> Optional[dict]:
    """The GeoNames ``country_code`` when countries.json carries it; otherwise the
    country of the city's Natural Earth admin-1 region (e.g. a code Natural Earth
    folds into another country). None if neither resolves."""
    hit = country(city.get("country_code") or "")
    if hit is not None:
        return hit
    reg = region(city.get("admin1_id") or "")
    return country(reg["iso_a2"]) if reg else None


@functools.lru_cache(maxsize=None)
def _cities_by(iso_a2: Optional[str], admin1_id: Optional[str]) -> tuple:
    out = []
    for c in load_cities():
        if admin1_id is not None and c.get("admin1_id") != admin1_id:
            continue
        if iso_a2 is not None:
            co = country_of_city(c)
            if co is None or co["iso_a2"] != iso_a2:
                continue
        out.append(c)
    return tuple(out)


def cities_in(iso_a2: Optional[str] = None, admin1_id: Optional[str] = None) -> list[dict]:
    """Gazetteer cities in a country and/or an admin-1 region (sorted by id). With
    no argument, every city."""
    return list(_cities_by(iso_a2.upper() if iso_a2 else None, admin1_id or None))
