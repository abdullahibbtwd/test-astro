#!/usr/bin/env python3
"""build_destinations.py — builds the ACG candidate-destination list (spec 11 §2–§4).

Outputs (committed, in ``Astrocartography/``; deterministic, byte-identical re-runs):

  destinations.json          {"schema_version": "acg-destinations-1", "policy": "viable_world_v1",
                              "attribution", "destinations": [...]} (sorted by id)
  destinations_review.csv    the human review sheet (Radul fills reviewed / exclude / appeal ...)
  regions_map.json           ISO-2 -> region keys (spec 11 §4)
  build_destinations.log     counts by seed source, policy rule, review state, coverage

Inputs: ``viability_policy.json`` (hand-maintained, read here and by acg_destinations.py),
``gazetteer.json`` (81 province centres + v1 diaspora, reviewed in earlier specs),
``regions.json`` / ``countries.json`` (build_geo_index.py), and open data in
``.cache/geodata/`` (never committed): GeoNames cities15000 + allCountries + alternate
names (tr) + countryInfo, Natural Earth 1:10m admin-1 / coastline / marine polygons,
WorldClim 2.1 bio1 (10').

Seeds (spec 11 §2): national capitals (GeoNames PPLC), GeoNames cities >= 200,000 (city
proper; PPLX sections skipped), all 81 Turkish province centres, the curated Turkish
coastal/heritage list (TR_CURATED below), the v1 diaspora list, and an LLM-drafted list of
international travel destinations (``destinations_llm_draft.json``, cached: a re-run makes
no model call). Drafted and curated rows are geocoded by matching GeoNames names (no network
geocoder). Only rows seeded by the province centres or the v1 diaspora list are
``reviewed: true``; every other row waits for Radul's review (no auto-approval).

    python Astrocartography/build_destinations.py                 # rebuild
    python Astrocartography/build_destinations.py --review FILE   # merge a filled review sheet
    python Astrocartography/build_destinations.py --redraft       # re-run the LLM draft (costs)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import sys
import zipfile
from collections import Counter, defaultdict

import numpy as np
import shapely
from shapely.ops import unary_union

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import build_geo_index as bgi  # noqa: E402
import build_gazetteer as bg  # noqa: E402

OUT = os.path.join(_HERE, "destinations.json")
REVIEW_CSV = os.path.join(_HERE, "destinations_review.csv")
REGIONS_MAP = os.path.join(_HERE, "regions_map.json")
POLICY = os.path.join(_HERE, "viability_policy.json")
LLM_DRAFT = os.path.join(_HERE, "destinations_llm_draft.json")
LOG = os.path.join(_HERE, "build_destinations.log")
MATCH_CACHE = os.path.join(bgi.CACHE_DIR, "allCountries_dest_match.json")

SCHEMA_VERSION = "acg-destinations-1"
POLICY_ID = "viable_world_v1"
ATTRIBUTION = ("City and place data © GeoNames (geonames.org), CC BY 4.0. Climate: WorldClim 2.1 "
               "(Fick & Hijmans 2017), CC BY 4.0. Coastlines, marine areas and admin-1 regions: "
               "Natural Earth (public domain).")

bgi.URLS.update({
    "allCountries.zip": "https://download.geonames.org/export/dump/allCountries.zip",
    "ne_10m_coastline.zip":
        "https://naciscdn.org/naturalearth/10m/physical/ne_10m_coastline.zip",
    "ne_10m_geography_marine_polys.zip":
        "https://naciscdn.org/naturalearth/10m/physical/ne_10m_geography_marine_polys.zip",
    "wc2.1_10m_bio.zip":
        "https://geodata.ucdavis.edu/climate/worldclim/2_1/base/wc2.1_10m_bio.zip",
})

POP_MIN = 200_000
SIZE_BIG, SIZE_MID = 1_000_000, 200_000
REGION_DEDUP_KM = 25.0
MED_NULL_KM = 500.0
CLIMATE_SEARCH_KM = 50.0
WARM_C, MILD_C = 18.0, 10.0
MATCH_KM = {"city": 75.0, "resort": 75.0, "region": 400.0}

MED_SEAS = ("Mediterranean Sea", "Alboran Sea", "Strait of Gibraltar", "Balearic Sea",
            "Ligurian Sea", "Tyrrhenian Sea", "Ionian Sea", "Adriatic Sea", "Aegean Sea",
            "Sea of Crete", "Libyan Sea", "Gulf of Sidra", "Gulf of Gabès")

# Precedence when seeds merge (lower wins for name / kind / name_tr).
SEED_ORDER = ("tr_province", "diaspora", "capital", "geonames_200k", "tr_curated", "llm_draft")
REVIEWED_SEEDS = {"tr_province", "diaspora"}
TRAVEL_SEEDS = {"tr_curated", "llm_draft"}

# Main Turkish coastal / heritage destinations (spec 11 §2). slug, name, name_tr, kind,
# approx lat, lon (guides the GeoNames match only), radius_km, appeal, GeoNames names.
TR_CURATED: list[tuple] = [
    ("bodrum", "Bodrum", "Bodrum", "resort", 37.04, 27.43, 0, 1, ["Bodrum"]),
    ("fethiye", "Fethiye", "Fethiye", "resort", 36.65, 29.12, 0, 1, ["Fethiye"]),
    ("kas", "Kaş", "Kaş", "resort", 36.20, 29.64, 0, 2, ["Kaş", "Kas"]),
    ("kalkan", "Kalkan", "Kalkan", "resort", 36.27, 29.41, 0, 2, ["Kalkan"]),
    ("alanya", "Alanya", "Alanya", "resort", 36.54, 32.00, 0, 1, ["Alanya"]),
    ("side", "Side", "Side", "resort", 36.77, 31.39, 0, 2, ["Side", "Selimiye"]),
    ("kemer", "Kemer", "Kemer", "resort", 36.60, 30.56, 0, 2, ["Kemer"]),
    ("belek", "Belek", "Belek", "resort", 36.86, 31.06, 0, 2, ["Belek"]),
    ("olympos", "Olympos", "Olimpos", "resort", 36.42, 30.47, 0, 3,
     ["Çıralı", "Cirali", "Olimpos", "Olympos"]),
    ("marmaris", "Marmaris", "Marmaris", "resort", 36.86, 28.27, 0, 1, ["Marmaris"]),
    ("datca", "Datça", "Datça", "resort", 36.73, 27.69, 0, 2, ["Datça", "Datca"]),
    ("dalyan", "Dalyan", "Dalyan", "resort", 36.83, 28.64, 0, 3, ["Dalyan"]),
    ("akyaka", "Akyaka", "Akyaka", "resort", 37.05, 28.33, 0, 3, ["Akyaka"]),
    ("cesme", "Çeşme", "Çeşme", "resort", 38.32, 26.30, 0, 1, ["Çeşme", "Cesme"]),
    ("alacati", "Alaçatı", "Alaçatı", "resort", 38.28, 26.37, 0, 2, ["Alaçatı", "Alacati"]),
    ("kusadasi", "Kuşadası", "Kuşadası", "resort", 37.86, 27.26, 0, 1,
     ["Kuşadası", "Kusadasi"]),
    ("selcuk", "Selçuk (Ephesus)", "Selçuk (Efes)", "resort", 37.95, 27.37, 0, 2,
     ["Selçuk", "Selcuk"]),
    ("sirince", "Şirince", "Şirince", "resort", 37.94, 27.43, 0, 3, ["Şirince", "Sirince"]),
    ("didim", "Didim", "Didim", "resort", 37.38, 27.27, 0, 2, ["Didim"]),
    ("ayvalik", "Ayvalık", "Ayvalık", "resort", 39.32, 26.69, 0, 2, ["Ayvalık", "Ayvalik"]),
    ("foca", "Foça", "Foça", "resort", 38.67, 26.76, 0, 3, ["Foça", "Foca"]),
    ("assos", "Assos", "Assos", "resort", 39.49, 26.34, 0, 3, ["Behramkale", "Assos"]),
    ("bozcaada", "Bozcaada", "Bozcaada", "resort", 39.83, 26.07, 0, 2, ["Bozcaada"]),
    ("gokceada", "Gökçeada", "Gökçeada", "resort", 40.19, 25.90, 0, 3,
     ["Gökçeada", "Gokceada"]),
    ("pamukkale", "Pamukkale", "Pamukkale", "resort", 37.92, 29.12, 0, 1, ["Pamukkale"]),
    ("cappadocia", "Cappadocia", "Kapadokya", "region", 38.64, 34.83, 40, 1,
     ["Cappadocia", "Kapadokya", "Göreme", "Goreme"]),
    ("safranbolu", "Safranbolu", "Safranbolu", "resort", 41.25, 32.69, 0, 2, ["Safranbolu"]),
    ("amasra", "Amasra", "Amasra", "resort", 41.75, 32.39, 0, 3, ["Amasra"]),
    ("uzungol", "Uzungöl", "Uzungöl", "resort", 40.62, 40.29, 0, 2, ["Uzungöl", "Uzungol"]),
    ("ayder", "Ayder", "Ayder", "resort", 40.95, 41.10, 0, 3, ["Ayder"]),
    ("sapanca", "Sapanca", "Sapanca", "resort", 40.69, 30.27, 0, 3, ["Sapanca"]),
    ("mardin", "Mardin", "Mardin", "city", 37.31, 40.74, 0, 2, ["Mardin"]),
    ("trabzon", "Trabzon", "Trabzon", "city", 41.00, 39.72, 0, 2, ["Trabzon"]),
    ("antalya", "Antalya", "Antalya", "city", 36.90, 30.70, 0, 1, ["Antalya"]),
]

# regions_map.json (spec 11 §4): region key -> members; the rest by GeoNames continent.
REGION_KEYS = ("europe", "turkey", "mediterranean", "middle_east_gulf", "caucasus", "americas",
               "east_asia", "south_southeast_asia", "oceania", "central_asia")
REGION_EXPLICIT = {
    "turkey": "TR",
    "mediterranean": ("ES FR MC IT MT SI HR BA ME AL GR TR CY XN SY LB IL PS EG LY TN DZ MA GI"),
    "middle_east_gulf": "TR AE SA QA BH KW OM IL PS IR IQ SY LB JO YE EG",
    "caucasus": "GE AM AZ",
    "east_asia": "CN HK MO TW JP KR KP MN",
    "south_southeast_asia": ("AF IN PK BD LK NP BT MV MM TH LA KH VN MY SG ID PH BN TL"),
    "central_asia": "KZ UZ KG TJ TM",
}
CONTINENT_REGION = {"EU": "europe", "NA": "americas", "SA": "americas", "OC": "oceania"}
REGION_EXTRA_EUROPE = ("TR", "XN")          # TR is AS in GeoNames; XN like CY (EU)
REGION_NOT_OCEANIA = ("TL",)                # GeoNames puts Timor-Leste in OC


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

fold = bg.fold
haversine_km = bg.haversine_km


def slugify(text: str) -> str:
    s = bg.ascii_name(text).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "x"


def size_of(pop: int) -> str:
    return "big" if pop >= SIZE_BIG else ("mid" if pop >= SIZE_MID else "small")


def _load_json(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _continents() -> dict[str, str]:
    out = {}
    with open(bgi.ensure("countryInfo.txt"), encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            f = line.rstrip("\n").split("\t")
            out[f[0]] = f[8]
    return out


# ---------------------------------------------------------------------------
# regions_map.json
# ---------------------------------------------------------------------------

def build_regions_map(countries: dict[str, dict]) -> dict[str, list[str]]:
    cont = _continents()
    cont["XN"] = "EU"
    members: dict[str, set] = defaultdict(set)
    for cc in countries:
        key = CONTINENT_REGION.get(cont.get(cc, ""))
        if key and not (key == "oceania" and cc in REGION_NOT_OCEANIA):
            members[cc].add(key)
    for cc in REGION_EXTRA_EUROPE:
        members[cc].add("europe")
    for key, ccs in REGION_EXPLICIT.items():
        for cc in ccs.split():
            members[cc].add(key)
    return {cc: [k for k in REGION_KEYS if k in members.get(cc, ())] for cc in sorted(countries)}


# ---------------------------------------------------------------------------
# LLM draft (cached)
# ---------------------------------------------------------------------------

DRAFT_BATCHES = [
    ("west_north_europe", 70, "Western and Northern Europe: the UK, Ireland, the Nordic "
     "countries, Benelux, France, Germany, Switzerland, Austria, Spain and Portugal including "
     "their Atlantic islands (Canary Islands, Madeira, Azores)"),
    ("south_east_europe", 65, "Southern and Eastern Europe: Italy, Malta, Greece and the Greek "
     "islands, Cyprus, Croatia and the Balkans, Central Europe (Czechia, Hungary, Poland...), "
     "Romania, Bulgaria, the Baltics, and the Caucasus (Georgia, Armenia, Azerbaijan)"),
    ("middle_east_africa_ca", 30, "the Middle East and the Gulf (UAE, Qatar, Oman, Saudi "
     "Arabia, Israel, Jordan...), Egypt and North Africa, the best-known sub-Saharan and Indian "
     "Ocean destinations (Zanzibar, Cape Town, Mauritius, Seychelles...), and Central Asia"),
    ("asia", 60, "East Asia, South Asia and Southeast Asia (Japan, South Korea, China, Hong "
     "Kong, Taiwan, Thailand, Vietnam, Indonesia, Malaysia, Singapore, the Philippines, India, "
     "Sri Lanka, the Maldives, Nepal...)"),
    ("americas", 50, "the Americas and the Caribbean (USA, Canada, Mexico, Cuba, the Dominican "
     "Republic, Brazil, Argentina, Chile, Peru, Colombia, Costa Rica...)"),
    ("oceania", 15, "Australia, New Zealand and the Pacific islands"),
]

DRAFT_SYSTEM = (
    "You are a travel-geography expert drafting a candidate list of travel destinations for a "
    "Turkish astrology app. A human editor reviews every row, so be accurate and conservative: "
    "only real, well-known places, with correct countries and approximate coordinates. "
    "Return JSON only, matching the schema.")

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {"destinations": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "name_tr": {"type": "string"},
            "country": {"type": "string"},
            "kind": {"type": "string", "enum": ["city", "resort", "region"]},
            "lat": {"type": "number"},
            "lon": {"type": "number"},
            "radius_km": {"type": "number"},
            "appeal": {"type": "integer"},
            "geonames_names": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["name", "name_tr", "country", "kind", "lat", "lon", "radius_km",
                     "appeal", "geonames_names"],
    }}},
    "required": ["destinations"],
}


def draft_user_prompt(area: str, n: int) -> str:
    return (
        f"List about {n} well-known international travel destinations in {area} that travellers "
        "from Turkey know or aspire to visit: famous cities, beach / island / ski resorts, and "
        "tourist regions. Do not include places in Turkey.\n"
        "For each destination give:\n"
        "- name: the common English name\n"
        "- name_tr: the Turkish name as used in Turkish media (Turkish exonym, e.g. Venice -> "
        "Venedik, Lisbon -> Lizbon); if Turkish uses the same name, repeat it\n"
        "- country: ISO 3166-1 alpha-2 code of the country that administers it today (Canary "
        "Islands -> ES, Madeira -> PT, Bali -> ID, Zanzibar -> TZ)\n"
        "- kind: 'city' (a city people visit or live in), 'resort' (a small town, island or "
        "beach/ski destination) or 'region' (a multi-town area, e.g. Algarve, Tuscany, Amalfi "
        "Coast, Bali, Cappadocia)\n"
        "- lat, lon: approximate centre, 2 decimals\n"
        "- radius_km: 0 for city and resort; for a region, the rough radius of the area (10-300)\n"
        "- appeal: 1 = iconic worldwide, 2 = well known, 3 = niche\n"
        "- geonames_names: 1-3 names under which the GeoNames gazetteer may list the place: the "
        "local-language name first, then the main town (e.g. Amalfi Coast -> ['Costiera "
        "Amalfitana', 'Amalfi']; Algarve -> ['Algarve', 'Faro']; Santorini -> ['Santorini', "
        "'Thira', 'Fira'])\n"
        "Order the list by appeal, then by name.")


def llm_draft(redraft: bool, log: list[str]) -> list[dict]:
    """The drafted rows. Cached in destinations_llm_draft.json (committed); a batch is only
    (re)generated when missing, its prompt changed, or --redraft is given."""
    cache = _load_json(LLM_DRAFT) if os.path.exists(LLM_DRAFT) else {"batches": {}}
    batches = cache.setdefault("batches", {})
    calls = 0
    usage_new = Counter()
    for key, n, area in DRAFT_BATCHES:
        prompt = draft_user_prompt(area, n)
        sha = hashlib.sha256((DRAFT_SYSTEM + "\n" + prompt).encode("utf-8")).hexdigest()[:16]
        hit = batches.get(key)
        if hit and hit.get("prompt_sha") == sha and not redraft:
            continue
        import llm_client  # only imported when a call is needed
        model = llm_client.DEFAULT_MODEL
        llm_client.require_api_key(model, "destination draft")
        temp = 0.0 if llm_client.supports_temperature(model) else None
        rows = None
        for attempt in range(1, 4):
            resp = llm_client.complete(model, DRAFT_SYSTEM, prompt, max_tokens=32000,
                                       temperature=temp, schema=DRAFT_SCHEMA, timeout_s=300.0,
                                       label=f"dest-draft-{key}")
            calls += 1
            for k, v in (resp.usage or {}).items():
                usage_new[k] += v or 0
            try:
                rows = json.loads(resp.text)["destinations"]
                break
            except (ValueError, KeyError, TypeError):
                print(f"  draft {key}: unparsable response (attempt {attempt})", flush=True)
        if rows is None:
            raise SystemExit(f"draft {key}: no parsable response")
        batches[key] = {"prompt_sha": sha, "model": model, "usage": dict(resp.usage or {}),
                        "rows": rows}
    if calls:
        cache["note"] = ("LLM-drafted travel destinations (spec 11 §2). Every row is "
                         "reviewed: false. Regenerate with build_destinations.py --redraft.")
        with open(LLM_DRAFT, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    tot = Counter()
    for b in batches.values():
        tot.update(b.get("usage") or {})
    log.append(f"LLM draft: {calls} model calls this run; cached batches {len(batches)}; "
               f"cumulative draft usage " + ", ".join(f"{k} {v}" for k, v in sorted(tot.items())))
    out = []
    for key, _, _ in DRAFT_BATCHES:
        for i, r in enumerate(batches[key]["rows"]):
            out.append({**r, "_batch": key, "_idx": i})
    return out


# ---------------------------------------------------------------------------
# GeoNames name matching (allCountries, filtered once per set of wanted names)
# ---------------------------------------------------------------------------

_MATCH_CLASSES = {"P", "A", "L", "T", "S", "H"}


def _quick_key(s: str) -> str:
    if s.isascii():
        return " ".join(s.lower().replace("-", " ").split())
    return fold(s)


def geonames_index(wanted: set[str], log: list[str]) -> dict[str, list[dict]]:
    """fold(name) -> GeoNames features (any of name / asciiname / alternatenames). Streams
    allCountries.zip once and caches the rows matching ``wanted``."""
    if os.path.exists(MATCH_CACHE):
        cache = _load_json(MATCH_CACHE)
        if wanted <= set(cache["keys"]):
            log.append(f"GeoNames match index: {len(wanted)} names from cache")
            return {k: cache["rows"].get(k, []) for k in wanted}
        wanted = wanted | set(cache["keys"])
    print(f"streaming allCountries for {len(wanted)} names (one-off, a few minutes)...",
          flush=True)
    rows: dict[str, list] = defaultdict(list)
    zf = zipfile.ZipFile(bgi.ensure("allCountries.zip"))
    with zf.open("allCountries.txt") as fh:
        for raw in io.TextIOWrapper(fh, encoding="utf-8"):
            f = raw.split("\t")
            if f[6] not in _MATCH_CLASSES:
                continue
            names = {f[1], f[2]}
            if f[3]:
                names.update(f[3].split(","))
            hit = {k for k in (_quick_key(n) for n in names if n) if k in wanted}
            if not hit:
                continue
            rec = {"gid": int(f[0]), "name": f[1], "lat": float(f[4]), "lon": float(f[5]),
                   "fclass": f[6], "fcode": f[7], "cc": f[8], "pop": int(f[14] or 0),
                   "primary": fold(f[1]) in hit or fold(f[2]) in hit}
            for k in hit:
                rows[k].append(rec)
    for k in rows:
        rows[k].sort(key=lambda r: r["gid"])
    os.makedirs(bgi.CACHE_DIR, exist_ok=True)
    with open(MATCH_CACHE, "w", encoding="utf-8") as fh:
        json.dump({"keys": sorted(wanted), "rows": rows}, fh, ensure_ascii=False)
    log.append(f"GeoNames match index: streamed allCountries for {len(wanted)} names")
    return {k: rows.get(k, []) for k in wanted}


def _usable(r: dict) -> bool:
    fc = r["fcode"]
    if r["fclass"] == "P" and fc in ("PPLX", "PPLH", "PPLQ", "PPLW", "PPLCH"):
        return False
    return not (r["fclass"] == "A" and fc.endswith("H"))


def match_geonames(item: dict, index: dict[str, list[dict]], countries: set[str]) -> dict | None:
    """Best GeoNames feature for a curated / drafted row, or None."""
    kind = item["kind"]
    names = [item["name"], *item.get("geonames_names", [])]
    max_km = MATCH_KM[kind]
    if kind == "region":
        tiers = [("L", "T", "A"), ("P",)]
    else:
        tiers = [("P",), ("S", "T", "L", "H", "A")]
    for tier in tiers:
        for nm in names:
            cands = []
            for r in index.get(fold(nm), []):
                if r["fclass"] not in tier or not _usable(r):
                    continue
                d = haversine_km(item["lat"], item["lon"], r["lat"], r["lon"])
                if d > max_km:
                    continue
                same_cc = r["cc"] == item["country"]
                if not same_cc and d > 50.0:
                    continue
                cands.append((r, d, same_cc))
            if cands:
                if tier == ("P",):
                    key = lambda c: (c[2], c[0]["primary"], c[0]["pop"], -c[1], -c[0]["gid"])
                else:
                    key = lambda c: (c[2], c[0]["primary"], -c[1], c[0]["pop"], -c[0]["gid"])
                return max(cands, key=key)[0]
    return None


# ---------------------------------------------------------------------------
# Geometry: coastline distance, Mediterranean distance, admin-1, climate
# ---------------------------------------------------------------------------

def _segments(lines) -> np.ndarray:
    """(n, 4) array of x1, y1, x2, y2 (degrees) from LineStrings / polygon boundaries."""
    segs = []
    for g in lines:
        parts = getattr(g, "geoms", [g])
        for p in parts:
            c = np.asarray(p.coords)
            if len(c) >= 2:
                segs.append(np.hstack([c[:-1, :2], c[1:, :2]]))
    return np.vstack(segs)


class SegIndex:
    """Nearest distance (km) from a point to a set of segments. Local equirectangular
    projection around the point; segments pre-sorted by their southern latitude."""

    def __init__(self, segs: np.ndarray):
        ylo = np.minimum(segs[:, 1], segs[:, 3])
        order = np.argsort(ylo, kind="stable")
        self.s = segs[order]
        self.ylo = ylo[order]
        self.hmax = float(np.max(np.abs(segs[:, 1] - segs[:, 3])))

    def dist_km(self, lat: float, lon: float) -> float:
        for deg in (1.0, 3.0, 9.0, 27.0, 180.0):
            i0 = np.searchsorted(self.ylo, lat - deg - self.hmax, "left")
            i1 = np.searchsorted(self.ylo, lat + deg, "right")
            s = self.s[i0:i1]
            if len(s):
                d = self._min_dist(s, lat, lon)
                if d <= deg * 110.5 or deg >= 180.0:
                    return d
        return float("inf")

    @staticmethod
    def _min_dist(s: np.ndarray, lat: float, lon: float) -> float:
        kx = 111.320 * math.cos(math.radians(lat))
        ky = 110.574
        x1 = ((s[:, 0] - lon + 180.0) % 360.0 - 180.0) * kx
        # x2 from x1 + the segment's own (wrapped) extent: a segment near the antipodal
        # meridian must not straddle the local wrap and span the globe
        x2 = x1 + ((s[:, 2] - s[:, 0] + 180.0) % 360.0 - 180.0) * kx
        y1 = (s[:, 1] - lat) * ky
        y2 = (s[:, 3] - lat) * ky
        dx, dy = x2 - x1, y2 - y1
        l2 = dx * dx + dy * dy
        t = np.where(l2 > 0, -(x1 * dx + y1 * dy) / np.where(l2 > 0, l2, 1.0), 0.0)
        t = np.clip(t, 0.0, 1.0)
        px, py = x1 + t * dx, y1 + t * dy
        return float(np.sqrt(np.min(px * px + py * py)))


CONTINENT_MIN_KM2 = 3.0e6        # landmasses at least this big are continents
ISLAND_SNAP_KM = 50.0              # a point just offshore belongs to the nearest landmass
REVIEW_OVERLAY = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "destinations_review_decisions.csv")


def island_index():
    """(STRtree, geoms, is_continent flags) over Natural Earth 1:50m land polygons."""
    import math as _m
    from shapely.strtree import STRtree
    feats = bgi.read_shp("ne_50m_land.zip")
    geoms, cont = [], []
    for _, g in feats:
        for poly in bgi.polygons(shapely.make_valid(g)):
            c = poly.representative_point()
            km2 = poly.area * (111.32 ** 2) * _m.cos(_m.radians(c.y))
            geoms.append(poly)
            cont.append(km2 >= CONTINENT_MIN_KM2)
    return STRtree(geoms), geoms, cont


def on_island(idx, lat: float, lon: float) -> bool:
    """True when the point is not on (or within ISLAND_SNAP_KM of) a continental landmass.
    A point far from every 1:50m polygon is a small island missing at that scale."""
    tree, geoms, cont = idx
    pt = shapely.points(lon, lat)
    hits = tree.query(pt, predicate="intersects")
    if len(hits):
        return not any(cont[i] for i in hits)
    j = tree.nearest(pt)
    deg = geoms[j].distance(pt)
    if deg * 111.32 <= ISLAND_SNAP_KM:
        return not cont[j]
    return True


def coast_index() -> SegIndex:
    feats = bgi.read_shp("ne_10m_coastline.zip")
    return SegIndex(_segments([g for _, g in feats]))


def med_index(log: list[str]) -> tuple[SegIndex, object]:
    feats = bgi.read_shp("ne_10m_geography_marine_polys.zip")
    keep = [(a["name"], g) for a, g in feats if (a.get("name") or "") in MED_SEAS]
    found = sorted({n for n, _ in keep})
    log.append(f"Mediterranean subset (Natural Earth marine polys): {', '.join(found)}; "
               f"not present: {', '.join(sorted(set(MED_SEAS) - set(found))) or '-'}")
    union = unary_union([shapely.make_valid(g) for _, g in keep])
    polys = bgi.polygons(union)
    rings = []
    for p in polys:
        rings.append(p.exterior)
        rings.extend(p.interiors)
    shapely.prepare(union)
    return SegIndex(_segments(rings)), union


def climate_grid() -> np.ndarray:
    from PIL import Image
    zf = zipfile.ZipFile(bgi.ensure("wc2.1_10m_bio.zip"))
    im = Image.open(io.BytesIO(zf.read("wc2.1_10m_bio_1.tif")))
    a = np.array(im, dtype=np.float64)
    a[a < -1e30] = np.nan
    return a            # (1080, 2160), row 0 = 90N, col 0 = 180W, 10' cells


def climate_at(grid: np.ndarray, lat: float, lon: float) -> tuple[float | None, str]:
    nr, nc = grid.shape
    step = 180.0 / nr
    r = min(nr - 1, max(0, int((90.0 - lat) / step)))
    c = int((lon + 180.0) / step) % nc
    v = grid[r, c]
    if not np.isnan(v):
        return float(v), "cell"
    best = None
    k = 4
    for dr in range(-k, k + 1):
        rr = r + dr
        if not 0 <= rr < nr:
            continue
        for dc in range(-k * 3, k * 3 + 1):
            cc = (c + dc) % nc
            w = grid[rr, cc]
            if np.isnan(w):
                continue
            clat = 90.0 - (rr + 0.5) * step
            clon = -180.0 + (cc + 0.5) * step
            d = haversine_km(lat, lon, clat, clon)
            if d <= CLIMATE_SEARCH_KM and (best is None or (d, rr, cc) < best[:3]):
                best = (d, rr, cc, float(w))
    if best is None:
        return None, "none"
    return best[3], "nearest"


def climate_class(t: float | None) -> str | None:
    if t is None:
        return None
    return "warm" if t >= WARM_C else ("mild" if t >= MILD_C else "cold")


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def gather_seeds(log: list[str], redraft: bool) -> tuple[list[dict], dict]:
    """-> (seed items, context). A seed item has: seed, gid, name, name_tr (or None),
    kind, lat, lon, cc, pop, fcode, radius_km, appeal, slug_hint."""
    rows = bg.read_cities15000()
    by_gid = {r["gid"]: r for r in rows}
    gaz = _load_json(os.path.join(_HERE, "gazetteer.json"))["cities"]
    gaz_by_gid = {int(c["id"][3:]): c for c in gaz}
    diaspora_ids = {d[0] for d in bg.DIASPORA}
    items: list[dict] = []

    def gn_item(seed: str, r: dict) -> dict:
        return {"seed": seed, "gid": r["gid"], "name": r["name"], "name_tr": None,
                "kind": "city", "lat": r["lat"], "lon": r["lon"], "cc": r["cc"],
                "pop": r["pop"], "radius_km": 0, "appeal": None}

    n_prov = n_dia = 0
    for c in gaz:
        g = int(c["id"][3:])
        al = set(c["aliases"])
        if any(re.fullmatch(r"tr-\d\d", a) for a in al):
            items.append(gn_item("tr_province", by_gid[g]))
            n_prov += sum(1 for a in al if re.fullmatch(r"tr-\d\d", a))
        if al & diaspora_ids:
            items.append(gn_item("diaspora", by_gid[g]))
            n_dia += len(al & diaspora_ids)
    if n_prov != 81:
        raise SystemExit(f"gazetteer: {n_prov} province ids (expected 81)")
    log.append(f"gazetteer: 81 province ids on {sum(1 for i in items if i['seed'] == 'tr_province')} "
               f"cities; {n_dia} v1 diaspora ids on "
               f"{sum(1 for i in items if i['seed'] == 'diaspora')} cities")
    for r in rows:
        if r["fcode"] == "PPLC":
            items.append(gn_item("capital", r))
        if r["pop"] >= POP_MIN and r["fcode"] != "PPLX":
            items.append(gn_item("geonames_200k", r))

    curated = [{"name": n, "name_tr": tr, "country": "TR", "kind": k, "lat": la, "lon": lo,
                "radius_km": rad, "appeal": ap, "geonames_names": gn, "_slug": s}
               for s, n, tr, k, la, lo, rad, ap, gn in TR_CURATED]
    drafted = llm_draft(redraft, log)
    wanted = set()
    for it in curated + drafted:
        for nm in [it["name"], *it.get("geonames_names", [])]:
            if nm and nm.strip():
                wanted.add(fold(nm))
    index = geonames_index(wanted, log)
    unresolved = []
    for seed, lst in (("tr_curated", curated), ("llm_draft", drafted)):
        for it in lst:
            it = dict(it)
            it["country"] = (it.get("country") or "").strip().upper()
            it["kind"] = it["kind"] if it["kind"] in MATCH_KM else "city"
            m = match_geonames(it, index, set())
            if m is None:
                unresolved.append(f"{seed}: {it['name']} ({it['country']}, {it['kind']})")
                continue
            try:
                appeal = int(it.get("appeal"))
            except (TypeError, ValueError):
                appeal = None
            radius = float(it.get("radius_km") or 0) if it["kind"] == "region" else 0.0
            items.append({
                "seed": seed, "gid": m["gid"], "name": it["name"].strip(),
                "name_tr": (it.get("name_tr") or "").strip() or None,
                "kind": it["kind"], "lat": m["lat"], "lon": m["lon"], "cc": m["cc"],
                "pop": m["pop"], "radius_km": int(round(min(300.0, max(10.0, radius))))
                if it["kind"] == "region" else 0,
                "appeal": appeal if appeal in (1, 2, 3) else None,
                "match": f"{m['fclass']}.{m['fcode']} {m['name']}",
            })
    log.append(f"curated TR rows {len(curated)}, drafted rows {len(drafted)}; unresolved "
               f"(no GeoNames match, dropped) {len(unresolved)}")
    for u in unresolved:
        log.append(f"  unresolved {u}")
    return items, {"cities15000": rows, "gaz_by_gid": gaz_by_gid}


def merge(items: list[dict], log: list[str]) -> list[dict]:
    rank = {s: i for i, s in enumerate(SEED_ORDER)}
    items = sorted(items, key=lambda i: (rank[i["seed"]], i["gid"], i["name"]))
    by_gid: dict[int, dict] = {}
    for it in items:
        rec = by_gid.get(it["gid"])
        if rec is None:
            by_gid[it["gid"]] = {**it, "seeds": {it["seed"]}}
            continue
        rec["seeds"].add(it["seed"])
        # items arrive in seed precedence: the first appeal / Turkish name seen wins
        if rec["appeal"] is None:
            rec["appeal"] = it["appeal"]
        if it["name_tr"] and "name_tr_hint" not in rec:
            rec["name_tr_hint"] = (it["seed"], it["name_tr"])
        if rec["kind"] == "region" and it["kind"] == "region":
            rec["radius_km"] = max(rec["radius_km"], it["radius_km"])
        rec.setdefault("match", it.get("match"))
    for rec in by_gid.values():
        if rec["name_tr"] is not None and "name_tr_hint" not in rec:
            rec["name_tr_hint"] = (rec["seed"], rec["name_tr"])
    recs = sorted(by_gid.values(), key=lambda r: (rank[min(r["seeds"], key=rank.get)], r["gid"]))
    # regions: de-duplicate < 25 km
    kept: list[dict] = []
    dropped = []
    for r in recs:
        if r["kind"] == "region":
            dup = next((k for k in kept if k["kind"] == "region" and
                        haversine_km(r["lat"], r["lon"], k["lat"], k["lon"]) < REGION_DEDUP_KM),
                       None)
            if dup is not None:
                dup["seeds"] |= r["seeds"]
                dropped.append(f"{r['name']} -> {dup['name']}")
                continue
        kept.append(r)
    log.append(f"merged: {len(items)} seed items -> {len(by_gid)} by geonameid -> {len(kept)} "
               f"after region de-dup (< {REGION_DEDUP_KM:.0f} km: {len(dropped)})")
    for d in dropped:
        log.append(f"  region de-dup: {d}")
    return kept


def assign_admin1(recs: list[dict], ctx: dict, countries: dict, regions: dict,
                  log: list[str]) -> None:
    """admin1_id + country. Gazetteer cities reuse the gazetteer's admin1_id; others use the
    gazetteer's rule (point-in-polygon within the GeoNames country's regions, nearest
    ≤ 0.25°; else any region). A point inside a Northern Cyprus region gets country XN."""
    by_iso: dict[str, tuple[list, list]] = defaultdict(lambda: ([], []))
    all_geoms, all_ids = [], []
    for attrs, geom in sorted(bgi.read_shp(bgi.ADMIN1), key=lambda f: f[0]["adm1_code"]):
        rid = attrs["adm1_code"]
        if rid in regions:
            by_iso[regions[rid]["iso_a2"]][0].append(geom)
            by_iso[regions[rid]["iso_a2"]][1].append(rid)
            all_geoms.append(geom)
            all_ids.append(rid)
    gaz = ctx["gaz_by_gid"]
    todo: dict[str, list[dict]] = defaultdict(list)
    how = Counter()
    for r in recs:
        if r["gid"] in gaz:
            r["admin1_id"] = gaz[r["gid"]]["admin1_id"]
            how["gazetteer"] += 1
        else:
            todo[r["cc"] if r["cc"] in countries else ""].append(r)
    for cc in sorted(todo):
        members = todo[cc]
        geoms, ids = by_iso[cc] if cc else (all_geoms, all_ids)
        lon = np.array([m["lon"] for m in members])
        lat = np.array([m["lat"] for m in members])
        adm, hw = bgi.assign(lon, lat, geoms, ids) if geoms else (
            np.array([""] * len(members), dtype=object), np.full(len(members), 2))
        for m, a, h in zip(members, adm, hw):
            m["admin1_id"] = a or None
            how[("polygon", "nearest", "unresolved")[int(h)]] += 1
    miss = [r for r in recs if not r.get("admin1_id")]
    if miss:
        adm, _ = bgi.assign(np.array([m["lon"] for m in miss]), np.array([m["lat"] for m in miss]),
                            all_geoms, all_ids)
        for m, a in zip(miss, adm):
            m["admin1_id"] = a or None
            log.append(f"  admin1 outside own country: {m['name']} ({m['cc']}) -> {a or 'null'}")
    # XN: GeoNames codes Northern Cyprus places CY; the Turkey-POV index has them in XN
    xn = [r for r in recs if r["cc"] == "CY" and r["gid"] not in gaz]
    if xn:
        adm, hw = bgi.assign(np.array([m["lon"] for m in xn]), np.array([m["lat"] for m in xn]),
                             *by_iso["XN"], max_deg=0.0)
        for m, a in zip(xn, adm):
            if a:
                m["admin1_id"] = a
                m["cc_pov"] = "XN"
    for r in recs:
        cc = r.pop("cc_pov", None) or r["cc"]
        if cc not in countries:
            reg = regions.get(r.get("admin1_id") or "")
            cc = reg["iso_a2"] if reg else cc
        r["country"] = cc
    log.append("admin1_id: " + ", ".join(f"{k} {v}" for k, v in sorted(how.items())) +
               f"; null {sum(1 for r in recs if not r.get('admin1_id'))}")
    remapped = Counter((r["cc"], r["country"]) for r in recs if r["cc"] != r["country"])
    for (a, b), n in sorted(remapped.items()):
        log.append(f"  country GeoNames {a} -> index {b}: {n}")


def region_size(r: dict, cities: list[dict], cc_arr, lat_arr, lon_arr, pop_arr) -> tuple[int, str]:
    rad = max(float(r["radius_km"]), REGION_DEDUP_KM)
    m = cc_arr == r["cc"]
    if not m.any():
        return r["pop"], "self"
    la, lo, po = lat_arr[m], lon_arr[m], pop_arr[m]
    p1, p2 = np.radians(r["lat"]), np.radians(la)
    a = (np.sin((p2 - p1) / 2) ** 2 +
         np.cos(p1) * np.cos(p2) * np.sin(np.radians(lo - r["lon"]) / 2) ** 2)
    d = 2 * 6371.0 * np.arcsin(np.minimum(1.0, np.sqrt(a)))
    inside = d <= rad
    if not inside.any():
        return r["pop"], "self"
    return int(max(int(po[inside].max()), r["pop"])), "largest city"


def build(redraft: bool, review_path: str | None) -> tuple[dict, dict, list[str], list[dict]]:
    log: list[str] = ["# build_destinations.log (ACG spec 11 §2–§4)", ""]
    countries = {c["iso_a2"]: c for c in _load_json(os.path.join(_HERE, "countries.json"))}
    regions = {r["admin1_id"]: r for r in _load_json(os.path.join(_HERE, "regions.json"))}
    policy = _load_json(POLICY)
    regions_map = build_regions_map(countries)

    items, ctx = gather_seeds(log, redraft)
    seed_counts = Counter(i["seed"] for i in items)
    recs = merge(items, log)
    assign_admin1(recs, ctx, countries, regions, log)

    tr_names = bgi.tr_alternate_names()
    gaz = ctx["gaz_by_gid"]
    c15 = ctx["cities15000"]
    cc_arr = np.array([r["cc"] for r in c15])
    lat_arr = np.array([r["lat"] for r in c15])
    lon_arr = np.array([r["lon"] for r in c15])
    pop_arr = np.array([r["pop"] for r in c15])

    print("coastline / Mediterranean / climate ...", flush=True)
    coast = coast_index()
    med, med_union = med_index(log)
    islands = island_index()
    clim = climate_grid()
    rank = {s: i for i, s in enumerate(SEED_ORDER)}
    how_tr = Counter()
    how_clim = Counter()
    out = []
    for r in recs:
        seeds = sorted(r["seeds"], key=rank.get)
        # name_tr: gazetteer > curated manual > GeoNames tr > drafted > name
        hint = r.get("name_tr_hint")
        if r["gid"] in gaz:
            name_tr, src = gaz[r["gid"]]["name_tr"], "gazetteer"
        elif hint and hint[0] == "tr_curated":
            name_tr, src = hint[1], "curated"
        elif r["gid"] in tr_names and r["kind"] == "city":
            name_tr, src = tr_names[r["gid"]], "geonames_tr"
        elif hint:
            name_tr, src = hint[1], hint[0]
        elif r["gid"] in tr_names:
            name_tr, src = tr_names[r["gid"]], "geonames_tr"
        else:
            name_tr, src = r["name"], "name"
        how_tr[src] += 1
        if r["kind"] == "region":
            pop, _ = region_size(r, c15, cc_arr, lat_arr, lon_arr, pop_arr)
        else:
            pop = r["pop"]
        size = size_of(pop)
        coast_km = round(coast.dist_km(r["lat"], r["lon"]), 1)
        island = on_island(islands, r["lat"], r["lon"])
        pt = shapely.points(r["lon"], r["lat"])
        if med_union.contains(pt):
            med_km = 0.0
        else:
            med_km = round(med.dist_km(r["lat"], r["lon"]), 1)
        med_km = med_km if med_km <= MED_NULL_KM else None
        t, how = climate_at(clim, r["lat"], r["lon"])
        how_clim[how] += 1
        if r["kind"] == "city":
            purposes = ["living", "travel"] if size in ("big", "mid") else ["living"]
            if r["seeds"] & TRAVEL_SEEDS and "travel" not in purposes:
                purposes.append("travel")
        else:
            purposes = ["travel"]
        appeal = r["appeal"]
        if appeal is None:
            appeal = 2 if (r["seeds"] & {"capital", "diaspora"} or size == "big") else 3
        out.append({
            "id": None, "name": r["name"], "name_tr": name_tr, "country": r["country"],
            "admin1_id": r.get("admin1_id"), "kind": r["kind"],
            "lat": round(r["lat"], 4), "lon": round(r["lon"], 4),
            "radius_km": int(r["radius_km"]), "population": int(pop), "size": size,
            "coast_km": coast_km, "med_coast_km": med_km, "island": island,
            "purposes": purposes,
            "climate": climate_class(t), "appeal": int(appeal), "exclude": False,
            "exclude_reason": None, "geonameid": int(r["gid"]),
            "reviewed": bool(r["seeds"] & REVIEWED_SEEDS), "seed_sources": seeds,
            "_bio1": t, "_match": r.get("match"),
        })
    log.append("name_tr source: " + ", ".join(f"{k} {v}" for k, v in sorted(how_tr.items())))

    # ids: "dst-<slug>"; on a clash the most populous keeps the plain slug, then -<cc>,
    # then -<cc>-<geonameid>
    base = defaultdict(list)
    for d in out:
        base[slugify(d["name"])].append(d)
    for slug, grp in base.items():
        grp.sort(key=lambda d: (-d["population"], d["geonameid"]))
        for i, d in enumerate(grp):
            d["id"] = f"dst-{slug}" if i == 0 else f"dst-{slug}-{d['country'].lower()}"
    seen = defaultdict(list)
    for d in out:
        seen[d["id"]].append(d)
    for i, grp in seen.items():
        if len(grp) > 1:
            grp.sort(key=lambda d: (-d["population"], d["geonameid"]))
            for d in grp[1:]:
                d["id"] = f"{i}-{d['geonameid']}"
    ids = [d["id"] for d in out]
    assert len(set(ids)) == len(ids), "duplicate destination ids"

    # Radul's recorded review decisions (committed; applied on every build), then an
    # optional filled review sheet on top
    if os.path.exists(REVIEW_OVERLAY):
        apply_review(out, REVIEW_OVERLAY, log)
    if review_path:
        apply_review(out, review_path, log)

    # policy (§3) at build time
    import acg_destinations as ad
    rule_counts = Counter()
    for d in out:
        ok, rule = ad.evaluate_policy(d, policy)
        rule_counts[(rule, ok)] += 1
        if not ok:
            d["exclude"] = True
            d["exclude_reason"] = f"policy:{rule}"
        elif (d["exclude_reason"] or "").startswith("policy:"):
            d["exclude"], d["exclude_reason"] = False, None

    # Radul's bulk decision (destinations_review_policy.json): approve every row the
    # policy allows and no review has excluded
    rp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "destinations_review_policy.json")
    if os.path.exists(rp):
        with open(rp, encoding="utf-8") as fh:
            rpol = json.load(fh)
        if rpol.get("approve_policy_allowed"):
            n = 0
            for d in out:
                if not d["exclude"] and not d["reviewed"]:
                    d["reviewed"] = True
                    n += 1
            log.append(f"review policy ({rpol.get('decided_by')}, {rpol.get('date')}): "
                       f"approved {n} policy-allowed destinations")

    out.sort(key=lambda d: d["id"])
    dests = [{k: v for k, v in d.items() if not k.startswith("_")} for d in out]
    data = {"schema_version": SCHEMA_VERSION, "policy": POLICY_ID, "attribution": ATTRIBUTION,
            "destinations": dests}

    # ---- log -------------------------------------------------------------------
    log.append("")
    log.append("## Counts")
    log.append(f"destinations: {len(dests)}")
    log.append("seed items by source (before merge): " +
               ", ".join(f"{s} {seed_counts[s]}" for s in SEED_ORDER))
    per_seed = Counter(s for d in dests for s in d["seed_sources"])
    log.append("destinations by seed source (a row can have several): " +
               ", ".join(f"{s} {per_seed[s]}" for s in SEED_ORDER))
    only = Counter(d["seed_sources"][0] for d in dests if len(d["seed_sources"]) == 1)
    log.append("destinations with a single seed source: " +
               ", ".join(f"{s} {only[s]}" for s in SEED_ORDER))
    log.append("by kind: " + ", ".join(f"{k} {v}" for k, v in
                                       sorted(Counter(d["kind"] for d in dests).items())))
    log.append("by size: " + ", ".join(f"{k} {v}" for k, v in
                                       sorted(Counter(d["size"] for d in dests).items())))
    log.append("by policy rule (allowed / excluded): " + ", ".join(
        f"P{n} {rule_counts[(f'P{n}', True)]}/{rule_counts[(f'P{n}', False)]}"
        for n in range(1, 8)))
    log.append(f"excluded total: {sum(1 for d in dests if d['exclude'])}")
    rv = Counter(d["reviewed"] for d in dests)
    log.append(f"reviewed: true {rv[True]}, false {rv[False]} (true = seeded by the 81 province "
               "centres or the v1 diaspora list; no auto-approval)")
    rva = sum(1 for d in dests if d["reviewed"] and not d["exclude"])
    log.append(f"reviewed and not excluded (recommendable today): {rva}")
    cl = Counter(d["climate"] for d in dests)
    log.append(f"climate: warm {cl['warm']}, mild {cl['mild']}, cold {cl['cold']}, null "
               f"{cl[None]}; WorldClim cell {how_clim['cell']}, nearest valid ≤ "
               f"{CLIMATE_SEARCH_KM:.0f} km {how_clim['nearest']}, none {how_clim['none']}")
    for d in out:
        if d["climate"] is None:
            log.append(f"  climate null: {d['id']} ({d['lat']}, {d['lon']})")
    ck = [d["coast_km"] for d in dests]
    log.append(f"coast_km: {len(ck)}/{len(dests)} set; ≤ 10 km {sum(c <= 10 for c in ck)}, "
               f"≤ 100 km {sum(c <= 100 for c in ck)}, max {max(ck)}")
    log.append(f"med_coast_km: set (≤ {MED_NULL_KM:.0f} km) {sum(d['med_coast_km'] is not None for d in dests)}, "
               f"null {sum(d['med_coast_km'] is None for d in dests)}")
    log.append("")
    log.append("## Curated / drafted rows: GeoNames match")
    for d in sorted(out, key=lambda d: d["id"]):
        if d["_match"] and set(d["seed_sources"]) <= TRAVEL_SEEDS:
            log.append(f"  {d['id']} ({d['country']}, {d['kind']}): {d['_match']} "
                       f"gn {d['geonameid']}")
    log.append("")
    log.append("## Policy exclusions by country (policy rule: count)")
    ex = Counter((d["exclude_reason"], d["country"]) for d in dests if d["exclude"])
    for (reason, cc), n in sorted(ex.items()):
        log.append(f"  {reason} {cc}: {n}")
    return data, regions_map, log, out


REVIEW_COLS = ["id", "name", "name_tr", "country", "kind", "size", "climate", "coast_km",
               "purposes", "appeal", "exclude", "exclude_reason", "reviewed", "seed_sources"]


def review_rows(dests: list[dict]) -> list[list[str]]:
    """Sorted for review: pending (reviewed=false, not policy-excluded) first, then by
    country, kind, appeal, name; policy-excluded rows last."""
    def key(d):
        pol = (d["exclude_reason"] or "").startswith("policy:")
        return (pol, d["reviewed"], d["country"], d["kind"], d["appeal"], d["name"], d["id"])
    out = []
    for d in sorted(dests, key=key):
        out.append([d["id"], d["name"], d["name_tr"], d["country"], d["kind"], d["size"],
                    d["climate"] or "", f"{d['coast_km']:.1f}", ";".join(d["purposes"]),
                    str(d["appeal"]), "true" if d["exclude"] else "false",
                    d["exclude_reason"] or "", "true" if d["reviewed"] else "false",
                    ";".join(d["seed_sources"])])
    return out


def apply_review(out: list[dict], path: str, log: list[str]) -> None:
    """Merge a filled review sheet: reviewed, exclude / exclude_reason (non-policy), appeal,
    purposes, name_tr. Policy exclusions are always recomputed."""
    by_id = {d["id"]: d for d in out}
    n = Counter()
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            d = by_id.get(row.get("id", ""))
            if d is None:
                n["unknown id"] += 1
                continue
            if row.get("reviewed", "").strip().lower() in ("true", "false"):
                d["reviewed"] = row["reviewed"].strip().lower() == "true"
            reason = (row.get("exclude_reason") or "").strip()
            if row.get("exclude", "").strip().lower() == "true" and not reason.startswith("policy:"):
                d["exclude"], d["exclude_reason"] = True, reason or "review"
            if (row.get("appeal") or "").strip() in ("1", "2", "3"):
                d["appeal"] = int(row["appeal"])
            pur = [p for p in (row.get("purposes") or "").split(";") if p in ("living", "travel")]
            if pur:
                d["purposes"] = sorted(set(pur), key=["living", "travel"].index)
            if (row.get("name_tr") or "").strip():
                d["name_tr"] = row["name_tr"].strip()
            n["applied"] += 1
    log.append(f"review sheet {os.path.basename(path)}: " +
               ", ".join(f"{k} {v}" for k, v in sorted(n.items())))


def dumps(data: dict) -> str:
    head = {k: v for k, v in data.items() if k != "destinations"}
    lines = ["{"]
    for k, v in head.items():
        lines.append(f" {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)},")
    lines.append(' "destinations": [')
    lines.append(",\n".join(" " + json.dumps(d, ensure_ascii=False, separators=(",", ":"))
                            for d in data["destinations"]))
    lines.append(" ]")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Build destinations.json (ACG spec 11 §2).")
    ap.add_argument("--redraft", action="store_true", help="re-run the LLM draft (model calls)")
    ap.add_argument("--review", metavar="CSV", help="merge a filled destinations_review.csv")
    args = ap.parse_args()
    data, regions_map, log, _ = build(args.redraft, args.review)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(dumps(data))
    with open(REGIONS_MAP, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("{\n" + ",\n".join(f" {json.dumps(k)}: {json.dumps(v)}"
                                   for k, v in regions_map.items()) + "\n}\n")
    with open(REVIEW_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(REVIEW_COLS)
        w.writerows(review_rows(data["destinations"]))
    log.append("")
    log.append("## Files")
    for p in (OUT, REVIEW_CSV, REGIONS_MAP, LLM_DRAFT):
        if os.path.exists(p):
            log.append(f"{os.path.basename(p)}: {os.path.getsize(p):,} bytes")
    with open(LOG, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(log) + "\n")
    print(f"{len(data['destinations'])} destinations -> {os.path.basename(OUT)}")


if __name__ == "__main__":
    main()
