#!/usr/bin/env python3
"""acg_locate.py — ACG spec 02: locate, relocate, city scan.

Deterministic. No LLM. The only network access is the existing (cached) L1
geocoder, used for a place that is not in the committed gazetteer.

    resolve_place(city=..., lat=..., lon=...)   -> (place, absence)
    lines_near(acg, lat, lon)                   -> lines within 1,000 km, nearest first
    relocate(natal_chart, place)                -> (chart_relocated | None, relocation block)
    house_diff(natal_chart, relocated_chart)    -> planets whose Placidus house changed
    build_locate(acg, natal_chart, place, ...)  -> (locate.json dict, chart_relocated | None)
    city_scan(acg, gazetteer)                   -> city_scan.json dict

Distances are perpendicular great-circle distances on a spherical Earth (acg_geo).
Relocation keeps the natal UTC instant (index D7) via compute_chart's
``utc_override``; it is unavailable above |lat| 66° (index D8).
"""

from __future__ import annotations

import json
import os
import sys
import unicodedata
from datetime import datetime
from typing import Callable, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, os.path.join(_ROOT, "d_layer")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from acg_constants import (  # noqa: E402
    BODY_DISPLAY, BODY_ORDER, LOCATE_SCHEMA_VERSION, MAX_ORB_KM, ORB_TIERS_KM,
    READ_IN_V1, RELOCATION_MAX_ABS_LAT,
)
from acg_geo import meridian_distance, polyline_distance  # noqa: E402

GAZETTEER_PATH = os.path.join(_HERE, "gazetteer.json")
SCAN_SCHEMA_VERSION = "acg-scan-1"
SCAN_TIERS = ("tight", "strong")
SCAN_BY_LINE_MAX = 5
ANGULAR_HOUSES = (1, 4, 7, 10)
READ_BODIES = tuple(b for b in BODY_ORDER if READ_IN_V1[b])


# ---------------------------------------------------------------------------
# Tiers
# ---------------------------------------------------------------------------

def tier_for(distance_km: float) -> Optional[str]:
    """tight ≤ 150 < strong ≤ 400 < wide ≤ 1000 < not reported (index D6)."""
    for tier, limit in ORB_TIERS_KM:
        if distance_km <= limit:
            return tier
    return None


# ---------------------------------------------------------------------------
# Place resolution (spec 02 §2)
# ---------------------------------------------------------------------------

def _fold(text: str) -> str:
    """Case- and diacritic-insensitive key; Turkish dotted/dotless i both -> i."""
    t = (text or "").replace("İ", "i").replace("ı", "i")
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(t.casefold().replace("-", " ").split())


def load_gazetteer(path: str = GAZETTEER_PATH) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return data["cities"] if isinstance(data, dict) else data


def gazetteer_lookup(query: str, gazetteer: list[dict]) -> Optional[dict]:
    """Resolve a query against the gazetteer: an exact id ("gn-311046") first, then
    name / name_tr, then aliases (which carry the v1 ids such as "tr-35" and the v1
    names such as "münih"). Several matches of the same kind -> the most populous
    (ties by id), so the result does not depend on the list order."""
    raw = (query or "").strip()
    q = _fold(query)
    # "Izmir, Turkey" -> also try the part before the first comma
    candidates = [q] + ([_fold(query.split(",")[0])] if "," in query else [])
    for city in gazetteer:
        if city["id"] == raw:
            return city
    for c in candidates:
        best = None
        for city in gazetteer:
            if c in (_fold(city["name"]), _fold(city["name_tr"])):
                rank = 0
            elif c in {_fold(k) for k in city.get("aliases", [])}:
                rank = 1
            else:
                continue
            key = (rank, -(city.get("population") or 0), city["id"])
            if best is None or key < best[0]:
                best = (key, city)
        if best is not None:
            return best[1]
    return None


def _default_geocoder(query: str) -> dict:
    """The existing non-interactive, cached L1 geocoder (exploration report §4)."""
    import run_predictive  # noqa: WPS433 — lazy: pulls the orchestrator's sys.path setup
    return run_predictive.geocode(query)


def resolve_place(city: Optional[str] = None, lat: Optional[float] = None,
                  lon: Optional[float] = None, *, gazetteer: Optional[list[dict]] = None,
                  geocoder: Optional[Callable[[str], dict]] = None
                  ) -> tuple[Optional[dict], Optional[dict]]:
    """-> (place, absence). Exactly one of ``city`` or (``lat``, ``lon``)."""
    if city is None and lat is not None and lon is not None:
        name = f"{lat:.4f}, {lon:.4f}"
        return ({"query": None, "name": name, "name_tr": name, "lat": float(lat),
                 "lon": float(lon), "country_code": None, "source": "manual"}, None)
    if not city or not city.strip():
        return None, {"reason": "place_not_found", "detail": "empty place query"}
    gaz = load_gazetteer() if gazetteer is None else gazetteer
    hit = gazetteer_lookup(city, gaz)
    if hit is not None:
        return ({"query": city, "name": hit["name"], "name_tr": hit["name_tr"],
                 "lat": hit["lat"], "lon": hit["lon"],
                 "country_code": hit.get("country_code"), "source": "gazetteer"}, None)
    try:
        geo = (geocoder or _default_geocoder)(city)
    except Exception as err:  # noqa: BLE001 — StageError / network error -> absence
        return None, {"reason": "place_not_found", "detail": str(err)}
    name = (geo.get("display_name") or city).split(",")[0].strip() or city
    return ({"query": city, "name": name, "name_tr": name,
             "lat": float(geo["latitude"]), "lon": float(geo["longitude"]),
             "country_code": None, "source": "geocoder"}, None)


# ---------------------------------------------------------------------------
# Lines near a place (spec 02 §3–§4)
# ---------------------------------------------------------------------------

def _line_distance(angle: str, line: dict, lat: float, lon: float) -> Optional[dict]:
    verts = line["vertices"]
    if not verts:
        return None
    if angle in ("MC", "IC"):
        return meridian_distance(lon, lat, verts[0][0])
    return polyline_distance(lon, lat, verts)


def lines_near(acg: dict, lat: float, lon: float, *,
               max_km: float = MAX_ORB_KM) -> list[dict]:
    """Every (body, angle) line within ``max_km``, sorted by distance ascending
    (ties by body order, then angle order)."""
    out = []
    for b in acg.get("bodies", []):
        for angle in ("MC", "IC", "ASC", "DSC"):
            hit = _line_distance(angle, b["lines"][angle], lat, lon)
            if hit is None or hit["distance_km"] > max_km:
                continue
            out.append({
                "body": b["body"],
                "angle": angle,
                "distance_km": round(hit["distance_km"], 1),
                "tier": tier_for(hit["distance_km"]),
                "read_in_v1": b["read_in_v1"],
                "nearest_point": [round(hit["nearest_point"][0], 4),
                                  round(hit["nearest_point"][1], 4)],
                "side": hit["side"],
                "_d": hit["distance_km"],
            })
    order = {b: i for i, b in enumerate(BODY_ORDER)}
    aorder = {"MC": 0, "IC": 1, "ASC": 2, "DSC": 3}
    out.sort(key=lambda r: (r["_d"], order[r["body"]], aorder[r["angle"]]))
    for r in out:
        del r["_d"]
    return out


# ---------------------------------------------------------------------------
# Relocation (spec 02 §5)
# ---------------------------------------------------------------------------

def relocate(natal_chart: dict, place: dict, *,
             natal_latlon: Optional[tuple[float, float]] = None
             ) -> tuple[Optional[dict], dict]:
    """Same UTC instant, new coordinates. Returns (relocated chart | None,
    locate.json ``relocation`` block without chart_path)."""
    block: dict = {"status": "ok", "absence": None, "chart_path": None}
    if natal_latlon is not None:
        block["relocated_from"] = {"natal_lat": natal_latlon[0], "natal_lon": natal_latlon[1]}
    if abs(place["lat"]) > RELOCATION_MAX_ABS_LAT:
        block.update(status="absent", absence={
            "reason": "placidus_undefined_high_latitude",
            "detail": f"|lat| {abs(place['lat']):.2f} > {RELOCATION_MAX_ABS_LAT}"})
        return None, block
    utc = (natal_chart.get("meta") or {}).get("utc")
    if not utc or (natal_chart.get("meta") or {}).get("time_precision") != "exact":
        block.update(status="absent", absence={"reason": "birth_time_not_exact",
                                               "detail": None})
        return None, block

    from compute_chart import BirthData, compute_chart  # noqa: WPS433
    instant = datetime.fromisoformat(utc)
    bd = BirthData(year=instant.year, month=instant.month, day=instant.day,
                   hour=instant.hour, minute=instant.minute,
                   latitude=place["lat"], longitude=place["lon"], time_precision="exact")
    chart = compute_chart(bd, utc_override=instant)
    if not (chart.get("sectors") or {}).get("placidus_cusps"):
        block.update(status="absent", absence={
            "reason": "placidus_undefined_high_latitude", "detail": "no Placidus cusps"})
        return None, block
    return chart, block


def house_diff(natal_chart: dict, relocated_chart: dict) -> list[dict]:
    """The 10 read planets whose Placidus house changed (spec 02 §5.1)."""
    nat = {p["name"]: p for p in natal_chart.get("points", [])}
    rel = {p["name"]: p for p in relocated_chart.get("points", [])}
    out = []
    for body in READ_BODIES:
        name = BODY_DISPLAY[body]
        nh = ((nat.get(name) or {}).get("sector") or {}).get("placidus")
        rh = ((rel.get(name) or {}).get("sector") or {}).get("placidus")
        if nh is None or rh is None or nh == rh:
            continue
        out.append({"body": body, "natal_house": nh, "relocated_house": rh,
                    "angular_after": rh in ANGULAR_HOUSES})
    return out


# ---------------------------------------------------------------------------
# locate.json
# ---------------------------------------------------------------------------

def absent_locate(place: Optional[dict], reason: str, detail: Optional[str] = None) -> dict:
    return {
        "schema_version": LOCATE_SCHEMA_VERSION,
        "place": place,
        "status": "absent",
        "absence": {"reason": reason, "detail": detail},
        "lines_near": [],
        "relocation": {"status": "absent", "absence": {"reason": reason, "detail": detail},
                       "chart_path": None},
        "house_diff": [],
    }


def build_locate(acg: dict, natal_chart: dict, place: dict, *,
                 natal_latlon: Optional[tuple[float, float]] = None,
                 chart_filename: str = "chart_relocated.json",
                 parans: Optional[dict] = None
                 ) -> tuple[dict, Optional[dict]]:
    """-> (locate.json dict, relocated chart | None). If the natal acg.json is
    absent, locate is absent with the same reason (spec 02 §4). ``parans``
    (parans.json, spec 10 §4) adds ``parans_near`` / ``parans_display``."""
    if acg.get("status") != "ok":
        ab = acg.get("absence") or {}
        return absent_locate(place, ab.get("reason", "acg_absent"), ab.get("detail")), None
    near = lines_near(acg, place["lat"], place["lon"])
    relocated, reloc = relocate(natal_chart, place, natal_latlon=natal_latlon)
    if relocated is not None:
        reloc["chart_path"] = chart_filename
    diff = house_diff(natal_chart, relocated) if relocated is not None else []
    out = {
        "schema_version": LOCATE_SCHEMA_VERSION,
        "place": place,
        "status": "ok",
        "absence": None,
        "lines_near": near,
        "relocation": reloc,
        "house_diff": diff,
    }
    if parans is not None:
        import compute_parans as cp  # noqa: WPS433
        pn = cp.parans_near(parans, place["lat"])
        out["parans_near"] = [{k: v for k, v in r.items()} for r in pn]
        out["parans_display"] = cp.parans_display(pn)
    return out, relocated


# ---------------------------------------------------------------------------
# City scan (spec 02 §7)
# ---------------------------------------------------------------------------

def city_scan(acg: dict, gazetteer: Optional[list[dict]] = None) -> dict:
    """For every gazetteer city: its tight/strong lines of read bodies, plus the
    inverted ``by_line`` index (up to 5 nearest cities per line). No network."""
    gaz = load_gazetteer() if gazetteer is None else gazetteer
    if acg.get("status") != "ok":
        return {"schema_version": SCAN_SCHEMA_VERSION, "status": "absent",
                "absence": acg.get("absence"), "cities": [], "by_line": {}}
    cities = []
    by_line: dict[str, list[dict]] = {}
    ordered = sorted(gaz, key=lambda c: c["id"])
    # Vectorised prefilter (acg_goals' kernel reproduces acg_geo exactly): only cities
    # with some read line within the strong orb get the full scalar lines_near pass.
    import acg_goals  # noqa: WPS433
    D = acg_goals.line_distances(acg, [c["lat"] for c in ordered],
                                 [c["lon"] for c in ordered])
    bodies = {b["body"]: b for b in acg["bodies"]}
    order_b = {b: i for i, b in enumerate(BODY_ORDER)}
    order_a = {"MC": 0, "IC": 1, "ASC": 2, "DSC": 3}
    limit = ORB_TIERS_KM[1][1]
    for i, city in enumerate(ordered):
        near = []
        for j in (D[i] <= limit + 1.0).nonzero()[0]:
            body, angle = acg_goals.LINE_KEYS[j]
            hit = _line_distance(angle, bodies[body]["lines"][angle], city["lat"], city["lon"])
            if hit is None or hit["distance_km"] > limit:
                continue
            near.append({"body": body, "angle": angle,
                         "distance_km": round(hit["distance_km"], 1),
                         "tier": tier_for(hit["distance_km"]), "read_in_v1": True,
                         "nearest_point": [round(hit["nearest_point"][0], 4),
                                           round(hit["nearest_point"][1], 4)],
                         "side": hit["side"], "_d": hit["distance_km"]})
        near.sort(key=lambda r: (r["_d"], order_b[r["body"]], order_a[r["angle"]]))
        for r in near:
            del r["_d"]
        cities.append({"city_id": city["id"], "name": city["name"],
                       "name_tr": city["name_tr"], "lines_near": near})
        for r in near:
            by_line.setdefault(f"{r['body']}|{r['angle']}", []).append(
                {"city_id": city["id"], "distance_km": r["distance_km"]})
    order = {b: i for i, b in enumerate(BODY_ORDER)}
    aorder = {"MC": 0, "IC": 1, "ASC": 2, "DSC": 3}
    idx = {}
    for key in sorted(by_line, key=lambda k: (order[k.split("|")[0]], aorder[k.split("|")[1]])):
        idx[key] = sorted(by_line[key], key=lambda e: (e["distance_km"], e["city_id"]))[
            :SCAN_BY_LINE_MAX]
    return {"schema_version": SCAN_SCHEMA_VERSION, "status": "ok", "absence": None,
            "cities": cities, "by_line": idx}
