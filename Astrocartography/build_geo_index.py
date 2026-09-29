#!/usr/bin/env python3
"""build_geo_index.py — one-off builder for the ACG country / region / grid index
(ACG change order v3 §3; consumed by ACG_08 §5–§6).

Inputs (open data, downloaded once into ``.cache/geodata/``, never committed):
  * Natural Earth 1:10m admin-0, **Turkey point-of-view** variant
    (``ne_10m_admin_0_countries_tur``; Natural Earth publishes POV variants only
    at 1:10m — there is no 1:50m TUR POV file)
  * Natural Earth 1:50m admin-0 default (compared against the POV file in the log)
  * Natural Earth 1:10m admin-1 states/provinces
  * Natural Earth 1:50m land (grid land mask)
  * GeoNames ``countryInfo.txt`` + ``alternateNamesV2`` (Turkish names, fallback)

Outputs (committed, in ``Astrocartography/``):
  countries.json, countries.geojson, regions.json, regions.geojson,
  geo_grid.npz, build_geo_index.log

All outputs are deterministic (byte-identical re-runs).

    python Astrocartography/build_geo_index.py
"""

from __future__ import annotations

import io
import json
import math
import os
import sys
import urllib.request
import zipfile
from collections import Counter, defaultdict
from typing import Iterable, Optional

import numpy as np
import shapefile  # pyshp
import shapely
from shapely.geometry import MultiPolygon, Polygon, mapping, shape

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
CACHE_DIR = os.path.join(_ROOT, ".cache", "geodata")

URLS = {
    "cities15000.zip": "https://download.geonames.org/export/dump/cities15000.zip",
    "alternateNamesV2.zip": "https://download.geonames.org/export/dump/alternateNamesV2.zip",
    "admin1CodesASCII.txt": "https://download.geonames.org/export/dump/admin1CodesASCII.txt",
    "countryInfo.txt": "https://download.geonames.org/export/dump/countryInfo.txt",
    "ne_10m_admin_0_countries_tur.zip":
        "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries_tur.zip",
    "ne_50m_admin_0_countries.zip":
        "https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip",
    "ne_10m_admin_1_states_provinces.zip":
        "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_1_states_provinces.zip",
    "ne_50m_land.zip": "https://naciscdn.org/naturalearth/50m/physical/ne_50m_land.zip",
}

ADMIN0_POV = "ne_10m_admin_0_countries_tur.zip"
ADMIN0_DEFAULT = "ne_50m_admin_0_countries.zip"
ADMIN1 = "ne_10m_admin_1_states_provinces.zip"
LAND = "ne_50m_land.zip"

# Natural Earth admin-0 features that have no ISO 3166 code at all (ISO_A2 and
# ISO_A2_EH both "-99") but are countries in the Turkey point of view. They get a
# user-assigned code (ISO 3166 reserves X* for user assignment; cf. Kosovo "XK").
# PROVISIONAL — Radul makes the final call on this (change order v3 §3).
NON_ISO_CODES = {"CYN": ("XN", "XNC")}          # Northern Cyprus (KKTC)

GRID_STEP = 0.5
GRID_LAT_MIN, GRID_LAT_MAX = -60.0, 75.0
NEAREST_MAX_DEG = 0.25        # ≈ 25 km: coastline-simplification slack
COUNTRY_SIMPLIFY_DEG = 0.02
REGION_SIMPLIFY_DEG = 0.02
ROUND_DP = 3


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def ensure(name: str) -> str:
    """Path of a cached source file; downloads it once if missing."""
    path = os.path.join(CACHE_DIR, name)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        os.makedirs(CACHE_DIR, exist_ok=True)
        print(f"downloading {URLS[name]}", file=sys.stderr)
        tmp = path + ".part"
        with urllib.request.urlopen(URLS[name], timeout=600) as r, open(tmp, "wb") as fh:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                fh.write(chunk)
        os.replace(tmp, path)
    return path


def read_shp(name: str) -> list[tuple[dict, object]]:
    """[(attributes, shapely geometry)] for a zipped Natural Earth shapefile."""
    zf = zipfile.ZipFile(ensure(name))
    base = name[:-4]
    r = shapefile.Reader(shp=io.BytesIO(zf.read(base + ".shp")),
                         shx=io.BytesIO(zf.read(base + ".shx")),
                         dbf=io.BytesIO(zf.read(base + ".dbf")), encoding="utf-8")
    out = []
    for sr in r.iterShapeRecords():
        geom = shape(sr.shape.__geo_interface__)
        if not geom.is_valid:
            polys = polygons(shapely.make_valid(geom))
            geom = polys[0] if len(polys) == 1 else MultiPolygon(polys)
        out.append((sr.record.as_dict(), geom))
    return out


def tr_alternate_names() -> dict[int, str]:
    """geonameid -> Turkish name (isPreferredName first, else the first ``tr``
    row in file order). Historic and colloquial names are skipped. The ``tr``
    rows are filtered from the 785 MB alternateNamesV2 stream once and cached."""
    cached = os.path.join(CACHE_DIR, "alternateNames_tr.tsv")
    if not os.path.exists(cached):
        zf = zipfile.ZipFile(ensure("alternateNamesV2.zip"))
        with zf.open("alternateNamesV2.txt") as fh, \
                open(cached + ".part", "w", encoding="utf-8", newline="\n") as out:
            for raw in fh:
                p = raw.split(b"\t", 3)
                if len(p) > 3 and p[2] == b"tr":
                    out.write(raw.decode("utf-8").rstrip("\r\n") + "\n")
        os.replace(cached + ".part", cached)
    first: dict[int, str] = {}
    preferred: dict[int, str] = {}
    with open(cached, encoding="utf-8") as fh:
        for line in fh:
            f = line.rstrip("\n").split("\t")
            f += [""] * (10 - len(f))
            gid, name = int(f[1]), f[3].strip()
            if not name or f[6] == "1" or f[7] == "1":      # colloquial / historic
                continue
            first.setdefault(gid, name)
            if f[4] == "1":
                preferred.setdefault(gid, name)
    return {**first, **preferred}


def country_info() -> dict[str, dict]:
    """GeoNames countryInfo.txt: ISO-2 -> {name, capital, geonameid}."""
    out = {}
    with open(ensure("countryInfo.txt"), encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            f = line.rstrip("\n").split("\t")
            out[f[0]] = {"name": f[4], "capital": f[5].strip(),
                         "geonameid": int(f[16]) if len(f) > 16 and f[16] else None}
    return out


# ---------------------------------------------------------------------------
# Country codes (Natural Earth quirks)
# ---------------------------------------------------------------------------

def _iso(v: str, n: int) -> Optional[str]:
    v = (v or "").strip()
    return v if len(v) == n and v.isascii() and v.isalpha() and v.isupper() else None


def country_codes(attrs: dict) -> tuple[Optional[str], Optional[str]]:
    """(iso_a2, iso_a3) for a Natural Earth admin-0 feature. ``ISO_A2`` is "-99"
    for e.g. France and Norway, so fall back to ``ISO_A2_EH``; then the explicit
    ``NON_ISO_CODES`` table; else (None, None) = skipped and logged."""
    a3 = attrs.get("ADM0_A3")
    if a3 in NON_ISO_CODES:
        return NON_ISO_CODES[a3]
    a2 = _iso(attrs.get("ISO_A2"), 2) or _iso(attrs.get("ISO_A2_EH"), 2)
    if a2 is None:
        return None, None
    iso3 = _iso(attrs.get("ISO_A3"), 3) or _iso(attrs.get("ISO_A3_EH"), 3) or a3
    return a2, iso3


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def polygons(geom) -> list[Polygon]:
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    out = []
    for g in getattr(geom, "geoms", []):
        out.extend(polygons(g))
    return out


def bbox(geoms: Iterable) -> list[float]:
    b = shapely.total_bounds(list(geoms))
    return [round(float(b[0]), 4), round(float(b[1]), 4),
            round(float(b[2]), 4), round(float(b[3]), 4)]


def _ring(coords, dp: int) -> Optional[list]:
    out: list[list[float]] = []
    for x, y in coords:
        p = [round(float(x), dp), round(float(y), dp)]
        if not out or out[-1] != p:
            out.append(p)
    if len(out) < 4 or out[0] != out[-1]:
        return None
    return out


def simplified_multipolygon(polys: list[Polygon], tol: float, dp: int = ROUND_DP) -> list:
    """GeoJSON MultiPolygon coordinates: each polygon simplified (topology
    preserving) and rounded; degenerate rings dropped. Never returns empty for a
    non-empty input (falls back to the largest polygon at 5 dp, unsimplified)."""
    out = []
    for p in polys:
        s = p.simplify(tol, preserve_topology=True)
        for sp in polygons(s):
            ext = _ring(sp.exterior.coords, dp)
            if ext is None:
                continue
            holes = [h for h in (_ring(i.coords, dp) for i in sp.interiors) if h]
            out.append([ext] + holes)
    if not out and polys:
        big = max(polys, key=lambda g: g.area)
        ext = _ring(big.exterior.coords, 5)
        if ext:
            out.append([ext])
    return out


def _dump_json(obj, path: str, *, indent: Optional[int] = None) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        if indent is None:
            json.dump(obj, fh, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(obj, fh, ensure_ascii=False, indent=indent)
        fh.write("\n")


def save_npz_deterministic(path: str, **arrays: np.ndarray) -> None:
    """np.savez_compressed, but with fixed zip timestamps so re-runs are
    byte-identical. Readable with np.load."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for key in sorted(arrays):
            buf = io.BytesIO()
            np.lib.format.write_array(buf, np.asanyarray(arrays[key]), allow_pickle=False)
            info = zipfile.ZipInfo(key + ".npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, buf.getvalue(), compresslevel=9)


# ---------------------------------------------------------------------------
# Point assignment (vectorised)
# ---------------------------------------------------------------------------

def assign(lon: np.ndarray, lat: np.ndarray, geoms: list, labels: list[str],
           max_deg: float = NEAREST_MAX_DEG) -> tuple[np.ndarray, np.ndarray]:
    """Label of the polygon containing each point; if none, the nearest polygon
    within ``max_deg`` (planar degrees). Ties (shared borders) go to the lowest
    polygon index, so the result is deterministic. Returns (labels, how) with
    how = 0 inside, 1 nearest, 2 unresolved."""
    pts = shapely.points(lon, lat)
    tree = shapely.STRtree(geoms)
    n = len(pts)
    best = np.full(n, -1, dtype=np.int64)
    pi, gi = tree.query(pts, predicate="intersects")
    if len(pi):
        order = np.lexsort((gi, pi))
        pi, gi = pi[order], gi[order]
        first = np.r_[True, pi[1:] != pi[:-1]]
        best[pi[first]] = gi[first]
    how = np.where(best >= 0, 0, 2).astype(np.int8)
    miss = np.nonzero(best < 0)[0]
    if len(miss) and max_deg > 0:
        mi, mg = tree.query_nearest(pts[miss], max_distance=max_deg, all_matches=True)
        if len(mi):
            order = np.lexsort((mg, mi))
            mi, mg = mi[order], mg[order]
            first = np.r_[True, mi[1:] != mi[:-1]]
            best[miss[mi[first]]] = mg[first]
            how[miss[mi[first]]] = 1
    lab = np.array([""] + list(labels), dtype=object)[best + 1]
    return lab, how


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def load_admin0(log: list[str]) -> tuple[dict[str, dict], list[tuple[dict, object]]]:
    """-> ({iso_a2: {attrs of primary feature, iso_a3, polys, features}}, raw features)."""
    feats = read_shp(ADMIN0_POV)
    groups: dict[str, dict] = {}
    skipped = []
    for attrs, geom in feats:
        a2, a3 = country_codes(attrs)
        if a2 is None:
            skipped.append(attrs)
            continue
        g = groups.setdefault(a2, {"iso_a3": a3, "features": [], "polys": []})
        g["features"].append((attrs, geom))
        g["polys"].extend(polygons(geom))
    for a2, g in groups.items():
        # primary feature: the one whose own ISO_A2 is this code, else the largest
        strict = [f for f in g["features"] if _iso(f[0].get("ISO_A2"), 2) == a2
                  or f[0].get("ADM0_A3") in NON_ISO_CODES]
        pool = strict or g["features"]
        g["attrs"] = max(pool, key=lambda f: (f[1].area, f[0].get("ADM0_A3", "")))[0]
        if _iso(g["attrs"].get("ISO_A3"), 3):
            g["iso_a3"] = g["attrs"]["ISO_A3"]
    log.append(f"admin-0 features in POV file: {len(feats)}; countries (unique iso_a2): "
               f"{len(groups)}; skipped (no usable code): {len(skipped)}")
    for a in sorted(skipped, key=lambda a: a.get("ADM0_A3", "")):
        log.append(f"  skipped admin-0 {a.get('ADM0_A3')} {a.get('ADMIN')!r} "
                   f"(ISO_A2={a.get('ISO_A2')}, ISO_A2_EH={a.get('ISO_A2_EH')}, "
                   f"TYPE={a.get('TYPE')})")
    merged = sorted((a2, [f[0].get("ADM0_A3") for f in g["features"]])
                    for a2, g in groups.items() if len(g["features"]) > 1)
    for a2, a3s in merged:
        log.append(f"  merged into {a2}: {', '.join(sorted(a3s))}")
    for a3, (a2, _) in sorted(NON_ISO_CODES.items()):
        log.append(f"  non-ISO code assigned: {a3} -> {a2} (provisional; POV decision)")
    return groups, feats


def build() -> None:
    log: list[str] = ["# build_geo_index.log (ACG change order v3 §3)", ""]
    log.append("## Point of view")
    log.append("Admin-0 borders: Natural Earth 1:10m **Turkey point-of-view** "
               "(ne_10m_admin_0_countries_tur). Natural Earth publishes POV variants only at "
               "1:10m; there is no 1:50m TUR POV file, so the 1:10m POV file is used (the spec "
               "asked for 1:50m admin-0) and simplified for the UI.")
    log.append("Cyprus: the TUR POV file has 'Cyprus' (CY, the south) and 'Northern Cyprus' "
               "(ADM0_A3 CYN, no ISO code; FCLASS_TR = Admin-0 country) as separate countries. "
               "Northern Cyprus is kept as its own country with the provisional user-assigned "
               "code XN / XNC. The UK Sovereign Base Areas (Akrotiri, Dhekelia) have no ISO "
               "code and are skipped. Radul makes the final call.")
    tr_names = tr_alternate_names()
    cinfo = country_info()

    # ---- default POV comparison --------------------------------------------------
    default = read_shp(ADMIN0_DEFAULT)
    d_codes = {country_codes(a)[0] for a, _ in default} - {None}
    log.append("")
    log.append("## Countries")
    groups, _ = load_admin0(log)
    log.append(f"  1:50m default admin-0: {len(default)} features, {len(d_codes)} codes; "
               f"codes only in POV: {sorted(set(groups) - d_codes)}; "
               f"codes only in default: {sorted(d_codes - set(groups))}")
    d_names = {a.get("ADM0_A3"): a.get("ADMIN") for a, _ in default}
    p_a3 = {f[0].get("ADM0_A3") for g in groups.values() for f in g["features"]}
    only_default = sorted(set(d_names) - p_a3 - set(NON_ISO_CODES))
    if only_default:
        log.append("  admin-0 units only in the default file (absorbed in the TUR POV): " +
                   ", ".join(f"{a} {d_names[a]!r}" for a in only_default))

    countries = []
    features = []
    src_count = Counter()
    for a2 in sorted(groups):
        g = groups[a2]
        at = g["attrs"]
        name = (at.get("NAME_EN") or at.get("ADMIN") or at.get("NAME") or a2).strip()
        gid = (cinfo.get(a2) or {}).get("geonameid")
        if (at.get("NAME_TR") or "").strip():
            name_tr, src = at["NAME_TR"].strip(), "ne"
        elif gid and gid in tr_names:
            name_tr, src = tr_names[gid], "geonames"
        else:
            name_tr, src = name, "english"
        src_count[src] += 1
        bb = bbox(g["polys"])
        countries.append({"iso_a2": a2, "iso_a3": g["iso_a3"], "name": name,
                          "name_tr": name_tr, "bbox": bb})
        features.append({"type": "Feature",
                         "properties": {"iso_a2": a2, "iso_a3": g["iso_a3"], "name": name,
                                        "name_tr": name_tr},
                         "geometry": {"type": "MultiPolygon",
                                      "coordinates": simplified_multipolygon(
                                          g["polys"], COUNTRY_SIMPLIFY_DEG)}})
    log.append(f"countries.json: {len(countries)}; name_tr source: "
               f"NE NAME_TR {src_count['ne']}, GeoNames tr {src_count['geonames']}, "
               f"English {src_count['english']}")
    codes = set(groups)

    # ---- regions -----------------------------------------------------------------
    log.append("")
    log.append("## Regions (Natural Earth 1:10m admin-1, default POV)")
    a3_to_a2 = {f[0].get("ADM0_A3"): a2 for a2, g in groups.items() for f in g["features"]}
    # admin-1 is default POV: a unit whose adm0_a3 is absorbed in the TUR POV
    # (Somaliland, Western Sahara, Kashmir, Baikonur) takes the POV country that
    # contains its representative point.
    pov_geoms, pov_labels = [], []
    for a2, g in sorted(groups.items()):
        for _, geom in g["features"]:
            pov_geoms.append(geom)
            pov_labels.append(a2)
    for attrs, geom in read_shp(ADMIN0_POV):
        if country_codes(attrs)[0] is None:
            pov_geoms.append(geom)
            pov_labels.append("")
    regions = []
    rfeatures = []
    rgeoms: list = []
    rids: list[str] = []
    rsrc = Counter()
    rskipped = []
    remapped = Counter()
    pov_moves: list[str] = []
    a1 = sorted(read_shp(ADMIN1), key=lambda f: f[0]["adm1_code"])
    a1_polys = [polygons(g) for _, g in a1]
    rp = [max(ps, key=lambda p: p.area).representative_point() if ps else None
          for ps in a1_polys]
    pov_lab, pov_how = assign(np.array([p.x if p else 0.0 for p in rp]),
                              np.array([p.y if p else 0.0 for p in rp]),
                              pov_geoms, pov_labels, max_deg=0.0)
    for k, (attrs, geom) in enumerate(a1):
        rid = attrs["adm1_code"]
        ne_a2 = _iso(attrs.get("iso_a2"), 2)
        polys = a1_polys[k]
        mapped = a3_to_a2.get(attrs.get("adm0_a3"))
        pov = pov_lab[k] if (polys and pov_how[k] == 0) else None
        # the POV admin-0 polygon containing the region wins (e.g. Crimea is
        # Ukraine in the TUR POV but RUS-* in the default-POV admin-1 file)
        a2 = pov or mapped
        if pov and mapped and pov != mapped:
            pov_moves.append(f"  admin-1 {rid} {attrs.get('name')!r}: adm0_a3 "
                             f"{attrs.get('adm0_a3')} -> {pov} by the POV border")
        if a2 is None:
            rskipped.append(attrs)
            continue
        if ne_a2 != a2:
            remapped[(attrs.get("adm0_a3"), attrs.get("iso_a2"), a2)] += 1
        if not polys:
            rskipped.append(attrs)
            continue
        name = (attrs.get("name") or attrs.get("name_en") or attrs.get("gn_name")
                or rid).strip()
        gid = attrs.get("gn_id") or 0
        if (attrs.get("name_tr") or "").strip():
            name_tr, src = attrs["name_tr"].strip(), "ne"
        elif gid > 0 and gid in tr_names:
            name_tr, src = tr_names[gid], "geonames"
        else:
            name_tr, src = name, "english"
        rsrc[src] += 1
        regions.append({"admin1_id": rid, "iso_a2": a2, "name": name, "name_tr": name_tr,
                        "bbox": bbox(polys)})
        rfeatures.append({"type": "Feature",
                          "properties": {"admin1_id": rid, "iso_a2": a2, "name": name,
                                         "name_tr": name_tr},
                          "geometry": {"type": "MultiPolygon",
                                       "coordinates": simplified_multipolygon(
                                           polys, REGION_SIMPLIFY_DEG)}})
        rgeoms.append(MultiPolygon(polys) if len(polys) > 1 else polys[0])
        rids.append(rid)
    log.append(f"regions.json: {len(regions)}; skipped (no country in the POV index): "
               f"{len(rskipped)}; name_tr source: NE name_tr {rsrc['ne']}, "
               f"GeoNames tr {rsrc['geonames']}, English {rsrc['english']}")
    for a in rskipped:
        log.append(f"  skipped admin-1 {a['adm1_code']} {a.get('name')!r} "
                   f"(adm0_a3={a.get('adm0_a3')}, iso_a2={a.get('iso_a2')})")
    log.extend(pov_moves)
    for (a3, ne_a2, a2), n in sorted(remapped.items()):
        log.append(f"  admin-1 iso_a2 remapped via adm0_a3 {a3}: NE {ne_a2!r} -> {a2} "
                   f"({n} regions)")
    reg_iso = {r["admin1_id"]: r["iso_a2"] for r in regions}

    # ---- grid ---------------------------------------------------------------------
    log.append("")
    log.append("## Grid")
    lats = np.round(np.arange(GRID_LAT_MIN, GRID_LAT_MAX + 1e-9, GRID_STEP), 4)
    lons = np.round(np.arange(-180.0, 180.0, GRID_STEP), 4)
    glat, glon = np.meshgrid(lats, lons, indexing="ij")
    glat, glon = glat.ravel(), glon.ravel()
    land = [g for _, g in read_shp(LAND)]
    land_tree = shapely.STRtree(land)
    pi, _ = land_tree.query(shapely.points(glon, glat), predicate="intersects")
    mask = np.zeros(len(glat), dtype=bool)
    mask[pi] = True
    glat, glon = glat[mask], glon[mask]
    log.append(f"0.5° nodes lat {GRID_LAT_MIN}..{GRID_LAT_MAX}, lon -180..179.5: "
               f"{mask.size}; on land (ne_50m_land): {int(mask.sum())}")

    # country polygons: every POV feature (uncoded ones label "" so a point inside
    # e.g. Dhekelia is not pushed into a neighbour)
    cgeoms, clabels = [], []
    for attrs, geom in read_shp(ADMIN0_POV):
        a2, _ = country_codes(attrs)
        cgeoms.append(geom)
        clabels.append(a2 or "")
    ciso, chow = assign(glon, glat, cgeoms, clabels)
    radm, rhow = assign(glon, glat, rgeoms, rids)

    # small countries with no grid point: representative point of the largest polygon
    have = set(ciso.tolist())
    extra = []
    for a2 in sorted(codes - have):
        big = max(groups[a2]["polys"], key=lambda p: p.area)
        rp = big.representative_point()
        extra.append((a2, round(rp.y, 4), round(rp.x, 4)))
    if extra:
        elat = np.array([e[1] for e in extra])
        elon = np.array([e[2] for e in extra])
        eadm, _ = assign(elon, elat, rgeoms, rids)
        glat = np.concatenate([glat, elat])
        glon = np.concatenate([glon, elon])
        ciso = np.concatenate([ciso, np.array([e[0] for e in extra], dtype=object)])
        radm = np.concatenate([radm, eadm])
        chow = np.concatenate([chow, np.zeros(len(extra), dtype=np.int8)])
        rhow = np.concatenate([rhow, np.zeros(len(extra), dtype=np.int8)])
    log.append(f"small countries given a representative point ({len(extra)}): " +
               ", ".join(e[0] for e in extra))

    # regions with no grid point get one too (spec addition: ACG_08 §5 needs ≥ 1
    # point per region; a 0.5° grid misses ~1/3 of the admin-1 units)
    have_r = set(radm.tolist())
    rextra = []
    for rid, geom in zip(rids, rgeoms):
        if rid in have_r:
            continue
        big = max(polygons(geom), key=lambda p: p.area)
        rp = big.representative_point()
        rextra.append((rid, round(rp.y, 4), round(rp.x, 4)))
    if rextra:
        elat = np.array([e[1] for e in rextra])
        elon = np.array([e[2] for e in rextra])
        eiso, ehow = assign(elon, elat, cgeoms, clabels)
        for i, e in enumerate(rextra):            # off the admin-0 coastline: the
            if not eiso[i]:                       # region's own country
                eiso[i], ehow[i] = reg_iso[e[0]], 1
        glat = np.concatenate([glat, elat])
        glon = np.concatenate([glon, elon])
        ciso = np.concatenate([ciso, eiso])
        radm = np.concatenate([radm, np.array([e[0] for e in rextra], dtype=object)])
        chow = np.concatenate([chow, ehow])
        rhow = np.concatenate([rhow, np.zeros(len(rextra), dtype=np.int8)])
    log.append(f"regions given a representative point (no 0.5° node inside): {len(rextra)}")
    log.append(f"grid points: {len(glat)}; country by polygon {int((chow == 0).sum())}, "
               f"by nearest ≤{NEAREST_MAX_DEG}° {int((chow == 1).sum())}, "
               f"unresolved {int((ciso == '').sum())}")
    log.append(f"admin-1 by polygon {int((rhow == 0).sum())}, nearest ≤{NEAREST_MAX_DEG}° "
               f"{int((rhow == 1).sum())}, unresolved {int((radm == '').sum())}")
    mism = sum(1 for c, r in zip(ciso, radm) if c and r and reg_iso.get(r) != c)
    log.append(f"points whose admin-1 region belongs to a different country than the "
               f"admin-0 polygon (border slivers / POV differences): {mism}")
    unres = [(float(a), float(o)) for a, o, c in zip(glat, glon, ciso) if not c]
    if unres:
        log.append(f"unresolved country points ({len(unres)}), first 40 as (lat, lon): " +
                   ", ".join(f"({a}, {o})" for a, o in unres[:40]))
    per = Counter(c for c in ciso.tolist() if c)
    log.append("points per country (top 15): " +
               ", ".join(f"{k} {v}" for k, v in sorted(per.items(),
                                                        key=lambda kv: (-kv[1], kv[0]))[:15]))
    no_region = sorted({r["admin1_id"] for r in regions} - set(radm.tolist()))
    log.append(f"regions with no grid point after that: {len(no_region)}")

    # ---- write ---------------------------------------------------------------------
    order = np.lexsort((glon, glat))
    admin_w = max(1, max((len(s) for s in radm.tolist()), default=1))
    save_npz_deterministic(
        os.path.join(_HERE, "geo_grid.npz"),
        lat=glat[order].astype(np.float64), lon=glon[order].astype(np.float64),
        iso_a2=ciso[order].astype("U3"), admin1_id=radm[order].astype(f"U{admin_w}"))
    _dump_json(countries, os.path.join(_HERE, "countries.json"), indent=1)
    _dump_json(regions, os.path.join(_HERE, "regions.json"), indent=None)
    _dump_json({"type": "FeatureCollection", "features": features},
               os.path.join(_HERE, "countries.geojson"))
    _dump_json({"type": "FeatureCollection", "features": rfeatures},
               os.path.join(_HERE, "regions.geojson"))
    log.append("")
    log.append("## Files")
    for fn in ("countries.json", "countries.geojson", "regions.json", "regions.geojson",
               "geo_grid.npz"):
        log.append(f"{fn}: {os.path.getsize(os.path.join(_HERE, fn)):,} bytes")
    with open(os.path.join(_HERE, "build_geo_index.log"), "w", encoding="utf-8",
              newline="\n") as fh:
        fh.write("\n".join(log) + "\n")
    print("\n".join(log))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    build()
