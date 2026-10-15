#!/usr/bin/env python3
"""acg_destinations.py — viable destinations, viability policy and user filters (ACG spec 11
§2–§4). The recommender (spec 11 §5–§8) calls this API. Read-only, no network; loaders are
cached (functools.lru_cache): treat the returned objects as immutable.

    load_destinations() -> list[dict]            destinations.json rows (sorted by id)
    load_policy() -> dict                        viability_policy.json
    load_regions_map() -> dict                   regions_map.json (ISO-2 -> region keys)
    policy_verdict(dest) -> (allowed, rule)      P1–P7, first matching rule decides
    DEFAULT_PURPOSE                              goal -> default purpose list (§4)
    resolve_filters(goal, *, regions, city_size, max_distance_km, home_latlon, climate,
                    purpose) -> Filters          resolved filters_applied (§7) + home_latlon
    filters_applied(filters) -> dict             the JSON echo (drops home_latlon)
    passes_filters(dest, filters, *, ignore_size=False) -> bool
    candidates(filters, *, include_unreviewed=False, ignore_size=False, country=None)
        -> list[dict]                            reviewed & !exclude & policy-allowed & filters

Built by build_destinations.py.
"""

from __future__ import annotations

import functools
import json
import math
import os
from typing import Iterable, Optional, Sequence

_HERE = os.path.dirname(os.path.abspath(__file__))
DESTINATIONS_PATH = os.path.join(_HERE, "destinations.json")
POLICY_PATH = os.path.join(_HERE, "viability_policy.json")
REGIONS_MAP_PATH = os.path.join(_HERE, "regions_map.json")

POLICY_ID = "viable_world_v1"
REGION_KEYS = ("europe", "turkey", "mediterranean", "middle_east_gulf", "caucasus", "americas",
               "east_asia", "south_southeast_asia", "oceania", "central_asia")
SIZES = ("big", "mid", "small")
CLIMATES = ("warm", "mild", "cold")
PURPOSES = ("living", "travel")
# Default changed to big only (Radul, 2026-09-28: "more known places"). Spec 11 §4 had
# big + mid; users can still pass city_size to widen it.
DEFAULT_CITY_SIZE = ("big",)
EARTH_RADIUS_KM = 6371.0

# Goal -> default purpose (spec 11 §4)
DEFAULT_PURPOSE: dict[str, list[str]] = {
    "relocation": ["living"], "career": ["living"], "business": ["living"],
    "money": ["living"], "education": ["living"], "family": ["living"],
    "travel": ["travel"], "rest": ["travel"],
    "love": ["living", "travel"], "creativity": ["living", "travel"],
    "spirituality": ["living", "travel"],
}


def _read_json(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@functools.lru_cache(maxsize=None)
def load_destinations() -> list[dict]:
    return _read_json(DESTINATIONS_PATH)["destinations"]


@functools.lru_cache(maxsize=None)
def load_policy() -> dict:
    return _read_json(POLICY_PATH)


@functools.lru_cache(maxsize=None)
def load_regions_map() -> dict:
    return _read_json(REGIONS_MAP_PATH)


@functools.lru_cache(maxsize=None)
def _by_id() -> dict[str, dict]:
    return {d["id"]: d for d in load_destinations()}


def destination(dest_id: str) -> Optional[dict]:
    return _by_id().get(dest_id)


# ---------------------------------------------------------------------------
# Policy (§3)
# ---------------------------------------------------------------------------

def _condition_holds(dest: dict, cond: dict, rule: dict) -> bool:
    for key, val in cond.items():
        if key == "countries":
            ok = dest.get("country") in val
        elif key == "federal_district_in":
            district = (rule.get("federal_districts") or {}).get(dest.get("admin1_id") or "")
            ok = district in val
        elif key == "size_in":
            ok = dest.get("size") in val
        elif key == "coast_km_max":
            ok = dest.get("coast_km") is not None and dest["coast_km"] <= val
        elif key == "med_coast_km_max":
            ok = dest.get("med_coast_km") is not None and dest["med_coast_km"] <= val
        elif key == "geonameids":
            ok = dest.get("geonameid") in val
        elif key == "island":
            ok = bool(dest.get("island")) is bool(val)
        elif key == "any_of":
            ok = any(_condition_holds(dest, c, rule) for c in val)
        else:
            raise ValueError(f"policy rule {rule.get('id')}: unknown condition {key!r}")
        if not ok:
            return False
    return True


def _rule_matches(dest: dict, match: dict) -> bool:
    if match.get("any"):
        return True
    return dest.get("country") in (match.get("countries") or ())


def evaluate_policy(dest: dict, policy: dict) -> tuple[bool, str]:
    """(allowed, rule id) under ``policy``; the first rule whose match holds decides."""
    for rule in policy["rules"]:
        if not _rule_matches(dest, rule.get("match") or {}):
            continue
        action = rule["action"]
        if action == "exclude":
            return False, rule["id"]
        if action == "allow":
            return True, rule["id"]
        if action == "allow_if":
            return _condition_holds(dest, rule.get("condition") or {}, rule), rule["id"]
        raise ValueError(f"policy rule {rule['id']}: unknown action {action!r}")
    return True, "none"


def policy_verdict(dest: dict) -> tuple[bool, str]:
    """(allowed, rule) for a destination under viable_world_v1 (P1–P7, first match decides).
    Depends only on the destination's fields, never on its ``exclude`` flag."""
    return evaluate_policy(dest, load_policy())


# ---------------------------------------------------------------------------
# Filters (§4, §7)
# ---------------------------------------------------------------------------

class Filters(dict):
    """The resolved ``filters_applied`` dict (spec 11 §7). ``home_latlon`` is kept as an
    attribute (not a key), so the dict serialises exactly as §7."""
    home_latlon: Optional[tuple[float, float]] = None


def _as_list(v, name: str, allowed: Sequence[str]) -> list[str]:
    if isinstance(v, str):
        v = [p.strip() for p in v.split(",") if p.strip()]
    out = []
    for x in v:
        x = str(x).strip().lower()
        if x not in allowed:
            raise ValueError(f"{name}: unknown value {x!r} (allowed: {', '.join(allowed)})")
        if x not in out:
            out.append(x)
    if not out:
        raise ValueError(f"{name}: empty")
    return [a for a in allowed if a in out]          # canonical order


def resolve_filters(goal: str, *, regions: Optional[Iterable[str] | str] = None,
                    city_size: Optional[Iterable[str] | str] = None,
                    max_distance_km: Optional[float] = None,
                    home_latlon: Optional[tuple[float, float]] = None,
                    climate: Optional[Iterable[str] | str] = None,
                    purpose: Optional[Iterable[str] | str] = None) -> Filters:
    """Resolve user filters to spec 11 §7 ``filters_applied``. Omitted = default:
    regions ["all"], city_size ["big", "mid"], max_distance_km None, climate None (not
    applied), purpose from the goal (DEFAULT_PURPOSE; "both" = ["living", "travel"])."""
    if goal not in DEFAULT_PURPOSE:
        raise ValueError(f"unknown goal {goal!r}")
    if regions is None or regions == "all" or (not isinstance(regions, str)
                                               and list(regions) == ["all"]):
        reg = ["all"]
    else:
        reg = _as_list(regions, "regions", REGION_KEYS)
    size = list(DEFAULT_CITY_SIZE) if city_size is None else _as_list(city_size, "city_size", SIZES)
    clim = None if climate is None else _as_list(climate, "climate", CLIMATES)
    if purpose is None:
        pur = list(DEFAULT_PURPOSE[goal])
    elif isinstance(purpose, str) and purpose.strip().lower() == "both":
        pur = list(PURPOSES)
    else:
        pur = _as_list(purpose, "purpose", PURPOSES)
    if max_distance_km is not None:
        max_distance_km = float(max_distance_km)
        if max_distance_km <= 0:
            raise ValueError("max_distance_km must be > 0")
        if home_latlon is None:
            raise ValueError("max_distance_km needs home_latlon (home city, else birthplace)")
    f = Filters(regions=reg, city_size=size, max_distance_km=max_distance_km, climate=clim,
                purpose=pur, policy=POLICY_ID)
    f.home_latlon = (float(home_latlon[0]), float(home_latlon[1])) if home_latlon else None
    return f


def filters_applied(filters: dict) -> dict:
    """The plain JSON echo of a resolved filter set (spec 11 §7 keys only)."""
    return {k: filters.get(k) for k in ("regions", "city_size", "max_distance_km", "climate",
                                        "purpose", "policy")}


def _home(filters: dict) -> Optional[tuple[float, float]]:
    h = getattr(filters, "home_latlon", None)
    return h if h is not None else filters.get("home_latlon")


def great_circle_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def passes_filters(dest: dict, filters: dict, *, ignore_size: bool = False) -> bool:
    """User filters only (regions, size, distance, climate, purpose); the policy, ``exclude``
    and ``reviewed`` are checked by candidates()."""
    reg = filters.get("regions") or ["all"]
    if "all" not in reg:
        if not set(load_regions_map().get(dest.get("country"), ())) & set(reg):
            return False
    if not ignore_size and dest.get("size") not in (filters.get("city_size") or DEFAULT_CITY_SIZE):
        return False
    mx = filters.get("max_distance_km")
    if mx is not None:
        home = _home(filters)
        if home is None:
            raise ValueError("max_distance_km set without home_latlon")
        if great_circle_km(home[0], home[1], dest["lat"], dest["lon"]) > mx:
            return False
    clim = filters.get("climate")
    if clim is not None and dest.get("climate") not in clim:
        return False
    pur = filters.get("purpose")
    if pur and not set(dest.get("purposes") or ()) & set(pur):
        return False
    return True


def candidates(filters: dict, *, include_unreviewed: bool = False, ignore_size: bool = False,
               country: Optional[str] = None) -> list[dict]:
    """Destinations eligible for recommendation (spec 11 §5 step 1): reviewed (unless
    include_unreviewed), not excluded, allowed by the policy, passing every active filter
    (size skipped with ignore_size, e.g. the Turkey block), optionally one country. Sorted
    by id."""
    cc = country.upper() if country else None
    out = []
    for d in load_destinations():
        if cc is not None and d["country"] != cc:
            continue
        if not (d["reviewed"] or include_unreviewed) or d["exclude"]:
            continue
        if not policy_verdict(d)[0]:
            continue
        if passes_filters(d, filters, ignore_size=ignore_size):
            out.append(d)
    return out
