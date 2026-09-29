#!/usr/bin/env python3
"""build_gazetteer.py — one-off builder for gazetteer.json v2 (ACG change order v3 §2,
replaces spec 02 §6).

Built from **GeoNames** (CC BY 4.0) with no geocoder calls. Selection:

  * ``cities15000`` with population ≥ 300,000 (feature code PPLX — a *section* of a
    populated place, e.g. a city district — is excluded; it duplicates its city)
  * every national capital (GeoNames feature code PPLC)
  * all 81 Turkish province centres (the PPLA/PPLC of each province; plate codes
    from the v1 table below, e.g. Kocaeli → İzmit, Sakarya → Adapazarı)
  * Turkish district centres (PPLA2) with population ≥ 100,000
  * the v1 diaspora / aspiration list (matched to the GeoNames feature)

Every v1 id (``tr-35``, ``de-munich``) and every v1 name / name_tr / alias string is
kept as an alias, so v1 lookups still resolve. ``admin1_id`` links to the Natural
Earth admin-1 region (``regions.json``) by point-in-polygon — run
``build_geo_index.py`` first.

    python Astrocartography/build_geo_index.py
    python Astrocartography/build_gazetteer.py            # rebuild (deterministic)
    python Astrocartography/build_gazetteer.py --check    # validate the committed file
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import unicodedata
import zipfile
from collections import Counter, defaultdict

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import build_geo_index as bgi  # noqa: E402

OUT = os.path.join(_HERE, "gazetteer.json")
LOG = os.path.join(_HERE, "build_gazetteer.log")
SCHEMA_VERSION = "acg-gazetteer-2"
POP_MIN = 300_000
TR_DISTRICT_POP_MIN = 100_000
DIASPORA_MATCH_KM = 30.0
ATTRIBUTION = ("GeoNames (CC BY 4.0), https://www.geonames.org/ — city names, coordinates, "
               "population and Turkish names. Admin-1 links: Natural Earth (public domain).")
SOURCE = ("GeoNames cities15000 + alternateNamesV2 (tr) + countryInfo; admin1_id by "
          "point-in-polygon on Natural Earth 1:10m admin-1 (regions.json)")

# plate code, province (name_tr), centre city when it differs from the province name
TR_PROVINCES: list[tuple[int, str, str | None]] = [
    (1, "Adana", None), (2, "Adıyaman", None), (3, "Afyonkarahisar", None),
    (4, "Ağrı", None), (5, "Amasya", None), (6, "Ankara", None), (7, "Antalya", None),
    (8, "Artvin", None), (9, "Aydın", None), (10, "Balıkesir", None),
    (11, "Bilecik", None), (12, "Bingöl", None), (13, "Bitlis", None), (14, "Bolu", None),
    (15, "Burdur", None), (16, "Bursa", None), (17, "Çanakkale", None),
    (18, "Çankırı", None), (19, "Çorum", None), (20, "Denizli", None),
    (21, "Diyarbakır", None), (22, "Edirne", None), (23, "Elazığ", None),
    (24, "Erzincan", None), (25, "Erzurum", None), (26, "Eskişehir", None),
    (27, "Gaziantep", None), (28, "Giresun", None), (29, "Gümüşhane", None),
    (30, "Hakkâri", None), (31, "Hatay", "Antakya"), (32, "Isparta", None),
    (33, "Mersin", None), (34, "İstanbul", None), (35, "İzmir", None), (36, "Kars", None),
    (37, "Kastamonu", None), (38, "Kayseri", None), (39, "Kırklareli", None),
    (40, "Kırşehir", None), (41, "Kocaeli", "İzmit"), (42, "Konya", None),
    (43, "Kütahya", None), (44, "Malatya", None), (45, "Manisa", None),
    (46, "Kahramanmaraş", None), (47, "Mardin", None), (48, "Muğla", None),
    (49, "Muş", None), (50, "Nevşehir", None), (51, "Niğde", None), (52, "Ordu", None),
    (53, "Rize", None), (54, "Sakarya", "Adapazarı"), (55, "Samsun", None),
    (56, "Siirt", None), (57, "Sinop", None), (58, "Sivas", None),
    (59, "Tekirdağ", None), (60, "Tokat", None), (61, "Trabzon", None),
    (62, "Tunceli", None), (63, "Şanlıurfa", None), (64, "Uşak", None), (65, "Van", None),
    (66, "Yozgat", None), (67, "Zonguldak", None), (68, "Aksaray", None),
    (69, "Bayburt", None), (70, "Karaman", None), (71, "Kırıkkale", None),
    (72, "Batman", None), (73, "Şırnak", None), (74, "Bartın", None),
    (75, "Ardahan", None), (76, "Iğdır", None), (77, "Yalova", None),
    (78, "Karabük", None), (79, "Kilis", None), (80, "Osmaniye", None), (81, "Düzce", None),
]
# v1 id, name (EN), name_tr (v1 Turkish exonym), country_code, v1 aliases, v1 lat, lon
# (v1 coordinates only guide the match to the GeoNames feature)
DIASPORA: list[tuple[str, str, str, str, list[str], float, float]] = [
    ("de-berlin", "Berlin", "Berlin", "DE", [], 52.5174, 13.3951),
    ("de-hamburg", "Hamburg", "Hamburg", "DE", [], 53.5502, 10.0013),
    ("de-munich", "Munich", "Münih", "DE", ["München"], 48.1371, 11.5754),
    ("de-frankfurt", "Frankfurt", "Frankfurt", "DE", ["Frankfurt am Main"], 50.1106, 8.6821),
    ("de-cologne", "Cologne", "Köln", "DE", ["Koeln"], 50.9384, 6.96),
    ("de-dusseldorf", "Düsseldorf", "Düsseldorf", "DE", [], 51.2254, 6.7763),
    ("de-stuttgart", "Stuttgart", "Stuttgart", "DE", [], 48.7784, 9.18),
    ("at-vienna", "Vienna", "Viyana", "AT", ["Wien"], 48.2084, 16.3725),
    ("ch-zurich", "Zurich", "Zürih", "CH", ["Zürich"], 47.3744, 8.541),
    ("nl-amsterdam", "Amsterdam", "Amsterdam", "NL", [], 52.3731, 4.8925),
    ("nl-rotterdam", "Rotterdam", "Rotterdam", "NL", [], 51.9244, 4.4778),
    ("be-brussels", "Brussels", "Brüksel", "BE", ["Bruxelles", "Brussel"], 50.8467, 4.3525),
    ("fr-paris", "Paris", "Paris", "FR", [], 48.8589, 2.32),
    ("fr-lyon", "Lyon", "Lyon", "FR", [], 45.7578, 4.832),
    ("gb-london", "London", "Londra", "GB", [], 51.5074, -0.1278),
    ("se-stockholm", "Stockholm", "Stokholm", "SE", [], 59.3251, 18.0711),
    ("dk-copenhagen", "Copenhagen", "Kopenhag", "DK", ["København"], 55.6867, 12.5701),
    ("no-oslo", "Oslo", "Oslo", "NO", [], 59.9133, 10.739),
    ("es-madrid", "Madrid", "Madrid", "ES", [], 40.4168, -3.7035),
    ("es-barcelona", "Barcelona", "Barselona", "ES", [], 41.3826, 2.1771),
    ("pt-lisbon", "Lisbon", "Lizbon", "PT", ["Lisboa"], 38.7078, -9.1366),
    ("it-rome", "Rome", "Roma", "IT", [], 41.8933, 12.4829),
    ("it-milan", "Milan", "Milano", "IT", [], 45.4642, 9.1896),
    ("gr-athens", "Athens", "Atina", "GR", ["Athina"], 37.9756, 23.7348),
    ("bg-sofia", "Sofia", "Sofya", "BG", [], 42.6977, 23.3217),
    ("cy-nicosia", "Nicosia", "Lefkoşa", "CY", [], 35.1747, 33.3639),
    ("az-baku", "Baku", "Bakü", "AZ", [], 40.3756, 49.8328),
    ("ge-tbilisi", "Tbilisi", "Tiflis", "GE", [], 41.6935, 44.8014),
    ("ru-moscow", "Moscow", "Moskova", "RU", ["Moskva"], 55.7505, 37.6175),
    ("ae-dubai", "Dubai", "Dubai", "AE", [], 25.2647, 55.2924),
    ("qa-doha", "Doha", "Doha", "QA", [], 25.2856, 51.5264),
    ("sa-riyadh", "Riyadh", "Riyad", "SA", [], 24.6389, 46.716),
    ("us-new-york", "New York", "New York", "US", ["NYC"], 40.7127, -74.006),
    ("us-chicago", "Chicago", "Şikago", "US", [], 41.8756, -87.6244),
    ("us-miami", "Miami", "Miami", "US", [], 25.7742, -80.1936),
    ("us-los-angeles", "Los Angeles", "Los Angeles", "US", ["LA"], 34.0537, -118.2428),
    ("us-san-francisco", "San Francisco", "San Francisco", "US", [], 37.7879, -122.4075),
    ("ca-toronto", "Toronto", "Toronto", "CA", [], 43.6535, -79.3839),
    ("ca-montreal", "Montreal", "Montreal", "CA", ["Montréal"], 45.5032, -73.5698),
    ("jp-tokyo", "Tokyo", "Tokyo", "JP", [], 35.6769, 139.7639),
    ("sg-singapore", "Singapore", "Singapur", "SG", [], 1.2899, 103.8519),
    ("au-sydney", "Sydney", "Sidney", "AU", [], -33.8698, 151.2083),
    ("au-melbourne", "Melbourne", "Melbourne", "AU", [], -37.8142, 144.9632),
]
TR_BBOX = (35.5, 42.5, 25.5, 45.0)   # lat_min, lat_max, lon_min, lon_max


def ascii_name(s: str) -> str:
    s = s.replace("İ", "I").replace("ı", "i")
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def fold(text: str) -> str:
    """Same key as acg_locate._fold (case/diacritics-insensitive, İ/ı -> i)."""
    t = (text or "").replace("İ", "i").replace("ı", "i")
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(t.casefold().replace("-", " ").split())


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(min(1.0, math.sqrt(a)))


def read_cities15000() -> list[dict]:
    zf = zipfile.ZipFile(bgi.ensure("cities15000.zip"))
    out = []
    for line in zf.read("cities15000.txt").decode("utf-8").splitlines():
        f = line.split("\t")
        out.append({"gid": int(f[0]), "name": f[1], "asciiname": f[2],
                    "lat": float(f[4]), "lon": float(f[5]), "fcode": f[7], "cc": f[8],
                    "admin1": f[10], "pop": int(f[14] or 0)})
    out.sort(key=lambda r: r["gid"])
    return out


def select(rows: list[dict], log: list[str]) -> tuple[dict[int, dict], dict[int, dict]]:
    """-> ({gid: row}, {gid: {"v1": [(id, name, name_tr, aliases)], "force_tr": str}})."""
    chosen: dict[int, dict] = {}
    extra: dict[int, dict] = defaultdict(lambda: {"v1": [], "force_tr": None})
    why = Counter()
    for r in rows:
        if r["pop"] >= POP_MIN and r["fcode"] != "PPLX":
            chosen[r["gid"]] = r
            why["pop>=300k"] += 1
    n_pplx = sum(1 for r in rows if r["pop"] >= POP_MIN and r["fcode"] == "PPLX")
    for r in rows:
        if r["fcode"] == "PPLC":
            if r["gid"] not in chosen:
                why["capital (added)"] += 1
            chosen[r["gid"]] = r
    # 81 province centres
    tr_seats = [r for r in rows if r["cc"] == "TR" and r["fcode"] in ("PPLA", "PPLC")]
    by_fold = defaultdict(list)
    for r in tr_seats:
        by_fold[fold(r["name"])].append(r)
    for plate, prov, centre in TR_PROVINCES:
        centre_tr = centre or prov
        hits = by_fold.get(fold(centre_tr), [])
        if len(hits) != 1:
            raise SystemExit(f"province {plate:02d} {prov}: {len(hits)} GeoNames seats "
                             f"named {centre_tr!r}")
        r = hits[0]
        if not (TR_BBOX[0] <= r["lat"] <= TR_BBOX[1] and TR_BBOX[2] <= r["lon"] <= TR_BBOX[3]):
            raise SystemExit(f"{prov}: GeoNames seat outside Turkey")
        if r["gid"] not in chosen:
            why["TR province centre (added)"] += 1
        chosen[r["gid"]] = r
        v1_aliases = sorted({centre, ascii_name(centre)}) if centre else []
        extra[r["gid"]]["v1"].append((f"tr-{plate:02d}", ascii_name(prov), prov, v1_aliases))
        extra[r["gid"]]["force_tr"] = centre_tr
    for r in rows:
        if r["cc"] == "TR" and r["fcode"] == "PPLA2" and r["pop"] >= TR_DISTRICT_POP_MIN:
            if r["gid"] not in chosen:
                why["TR district centre ≥100k (added)"] += 1
            chosen[r["gid"]] = r
    # v1 diaspora list: nearest same-country feature within 30 km, largest population
    for cid, name, name_tr, cc, aliases, lat, lon in DIASPORA:
        cands = [(r, haversine_km(lat, lon, r["lat"], r["lon"])) for r in rows
                 if r["cc"] == cc and r["fcode"] != "PPLX"]
        cands = [(r, d) for r, d in cands if d <= DIASPORA_MATCH_KM]
        if not cands:
            raise SystemExit(f"diaspora {cid}: no GeoNames city within {DIASPORA_MATCH_KM} km")
        r = max(cands, key=lambda rd: (rd[0]["pop"], -rd[1], -rd[0]["gid"]))[0]
        if r["gid"] not in chosen:
            why["v1 diaspora (added)"] += 1
        chosen[r["gid"]] = r
        v1_aliases = sorted(set(aliases) | ({ascii_name(name)} - {name}))
        extra[r["gid"]]["v1"].append((cid, name, name_tr, v1_aliases))
        if extra[r["gid"]]["force_tr"] is None:      # the hand-curated v1 exonym
            extra[r["gid"]]["force_tr"] = name_tr
    log.append(f"selected {len(chosen)} cities: " +
               ", ".join(f"{k} {v}" for k, v in why.items()) +
               f"; PPLX sections ≥300k excluded: {n_pplx}")
    return chosen, extra


def build() -> tuple[dict, list[str]]:
    log: list[str] = ["# build_gazetteer.log (ACG change order v3 §2)", ""]
    rows = read_cities15000()
    chosen, extra = select(rows, log)
    tr_names = bgi.tr_alternate_names()

    # admin-1 polygons, restricted to the regions kept in regions.json
    with open(os.path.join(_HERE, "regions.json"), encoding="utf-8") as fh:
        regions = {r["admin1_id"]: r for r in json.load(fh)}
    with open(os.path.join(_HERE, "countries.json"), encoding="utf-8") as fh:
        countries = {c["iso_a2"]: c for c in json.load(fh)}
    by_iso: dict[str, tuple[list, list]] = defaultdict(lambda: ([], []))
    all_geoms, all_ids = [], []
    for attrs, geom in sorted(bgi.read_shp(bgi.ADMIN1), key=lambda f: f[0]["adm1_code"]):
        rid = attrs["adm1_code"]
        if rid in regions:
            by_iso[regions[rid]["iso_a2"]][0].append(geom)
            by_iso[regions[rid]["iso_a2"]][1].append(rid)
            all_geoms.append(geom)
            all_ids.append(rid)
    gids = sorted(chosen)
    # admin-1 by point-in-polygon among the regions of the city's own (GeoNames)
    # country, nearest ≤ 25 km if just outside; a country code Natural Earth does
    # not carry (e.g. BQ) searches every region. This keeps a city on a POV border
    # (Nicosia) or in an enclave (Vatican City) with its own country's region.
    groups: dict[str, list[int]] = defaultdict(list)
    for g in gids:
        cc = chosen[g]["cc"]
        groups[cc if cc in countries else ""].append(g)
    adm_of: dict[int, str] = {}
    how_count = Counter()
    for cc in sorted(groups):
        members = groups[cc]
        geoms, ids = by_iso[cc] if cc else (all_geoms, all_ids)
        lat = np.array([chosen[g]["lat"] for g in members])
        lon = np.array([chosen[g]["lon"] for g in members])
        adm, how = bgi.assign(lon, lat, geoms, ids)
        for g, a, h in zip(members, adm, how):
            adm_of[g] = a
            how_count[int(h)] += 1
    log.append(f"admin1_id (within the city's country): by polygon {how_count[0]}, nearest ≤"
               f"{bgi.NEAREST_MAX_DEG}° {how_count[1]}, none within own country {how_count[2]}")
    no_adm = [g for g in gids if not adm_of[g]]
    if no_adm:          # own country has no region here (POV border): any region
        adm, _ = bgi.assign(np.array([chosen[g]["lon"] for g in no_adm]),
                            np.array([chosen[g]["lat"] for g in no_adm]),
                            all_geoms, all_ids)
        for g, a in zip(no_adm, adm):
            adm_of[g] = a
            log.append(f"  admin1_id outside own country: gn-{g} {chosen[g]['name']} "
                       f"({chosen[g]['cc']}) -> {a or 'null'} "
                       f"({regions[a]['iso_a2'] if a else '-'})")

    cities = []
    tr_cov: dict[str, Counter] = defaultdict(Counter)
    v1_diff = []
    for g in gids:
        r = chosen[g]
        ex = extra.get(g, {"v1": [], "force_tr": None})
        if ex["force_tr"]:
            name_tr, src = ex["force_tr"], "forced"
        elif g in tr_names:
            name_tr, src = tr_names[g], "tr"
        else:
            name_tr, src = r["name"], "fallback"
        tr_cov[r["cc"]][src] += 1
        alias = set()
        for vid, vname, vtr, valiases in ex["v1"]:
            alias.update([vid, vname, vtr, *valiases])
            if not vid.startswith("tr-") and g in tr_names and tr_names[g] != vtr:
                v1_diff.append(f"{vid}: kept v1 name_tr {vtr!r}; GeoNames tr "
                               f"{tr_names[g]!r} (alias)")
        if r["asciiname"]:
            alias.add(r["asciiname"])
        if src == "forced" and g in tr_names:
            alias.add(tr_names[g])
        alias -= {r["name"], name_tr, ""}
        cities.append({
            "id": f"gn-{g}", "name": r["name"], "name_tr": name_tr,
            "aliases": sorted(alias, key=lambda s: (fold(s), s)),
            "country_code": r["cc"], "admin1_code": r["admin1"],
            "admin1_id": adm_of[g] or None,
            "lat": round(r["lat"], 4), "lon": round(r["lon"], 4), "population": r["pop"],
        })
    cities.sort(key=lambda c: c["id"])

    # ---- log: TR coverage per country --------------------------------------------
    tot = Counter()
    for c in tr_cov.values():
        tot.update(c)
    n = sum(tot.values())
    log.append(f"name_tr: GeoNames tr {tot['tr']}, forced (81 province centres + v1 diaspora "
               f"exonyms) {tot['forced']}, "
               f"fallback to name {tot['fallback']} — coverage "
               f"{100.0 * (tot['tr'] + tot['forced']) / n:.1f}% of {n}")
    log.append("")
    log.append("## Turkish-name coverage per country (tr+forced / cities)")
    for cc in sorted(tr_cov):
        c = tr_cov[cc]
        k = sum(c.values())
        log.append(f"{cc}: {c['tr'] + c['forced']}/{k}")
    if v1_diff:
        log.append("")
        log.append("## v1 diaspora: name_tr kept from the hand-curated v1 exonym where GeoNames differs")
        log.extend(v1_diff)

    # ---- log: country coverage ---------------------------------------------------
    per_country = Counter()
    for c in cities:
        reg = regions.get(c["admin1_id"] or "")
        cc = c["country_code"] if c["country_code"] in countries else (
            reg["iso_a2"] if reg else c["country_code"])
        per_country[cc] += 1
    log.append("")
    log.append("## Country coverage (Natural Earth admin-0, TUR POV; city country = GeoNames "
               "country_code when countries.json has it, else its admin-1 region's country "
               "— same rule as acg_geodata.country_of_city)")
    missing = sorted(set(countries) - set(per_country))
    log.append(f"countries with ≥1 city: {len(set(countries) & set(per_country))} of "
               f"{len(countries)}; without: {len(missing)}")
    for cc in missing:
        log.append(f"no city ≥ threshold: {cc} {countries[cc]['name']}")
    outside = sorted(set(per_country) - set(countries))
    if outside:
        log.append("city countries not in countries.json: " +
                   ", ".join(f"{cc} ({per_country[cc]})" for cc in outside))
    data = {"schema_version": SCHEMA_VERSION, "source": SOURCE, "attribution": ATTRIBUTION,
            "cities": cities}
    return data, log


def check(data: dict) -> list[str]:
    errs = []
    cities = data["cities"]
    ids = [c["id"] for c in cities]
    if len(set(ids)) != len(ids):
        errs.append("duplicate ids")
    if len(cities) < 1200:
        errs.append(f"only {len(cities)} cities (< 1,200)")
    aliases = {a for c in cities for a in c["aliases"]}
    miss = [f"tr-{i:02d}" for i in range(1, 82) if f"tr-{i:02d}" not in aliases]
    if miss:
        errs.append(f"province ids missing as aliases: {miss}")
    for c in cities:
        if not c.get("name_tr"):
            errs.append(f"{c['id']}: empty name_tr")
        if not (-90 <= c["lat"] <= 90 and -180 <= c["lon"] <= 180):
            errs.append(f"{c['id']}: bad coordinates")
    return errs


def dumps(data: dict) -> str:
    """One city per line: small, diff-friendly, deterministic."""
    head = {k: v for k, v in data.items() if k != "cities"}
    lines = ["{"]
    for k, v in head.items():
        lines.append(f" {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)},")
    lines.append(' "cities": [')
    body = [" " + json.dumps(c, ensure_ascii=False, separators=(",", ":"))
            for c in data["cities"]]
    lines.append(",\n".join(body))
    lines.append(" ]")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Build gazetteer.json v2 (ACG 07 §2).")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        with open(OUT, encoding="utf-8") as fh:
            data = json.load(fh)
    else:
        data, log = build()
        with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(dumps(data))
        with open(LOG, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(log) + "\n")
    errs = check(data)
    print(f"{len(data['cities'])} cities; " + ("OK" if not errs else "; ".join(errs)))
    if errs:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
