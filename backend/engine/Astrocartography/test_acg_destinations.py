#!/usr/bin/env python3
"""test_acg_destinations.py — ACG spec 11 §9 (DV1–DV3: data + filters) and data guards.

    python -m pytest -q Astrocartography/test_acg_destinations.py
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import acg_destinations as ad  # noqa: E402
import acg_geodata as geo  # noqa: E402

FIELDS = ["id", "name", "name_tr", "country", "admin1_id", "kind", "lat", "lon", "radius_km",
          "population", "size", "coast_km", "med_coast_km", "island", "purposes", "climate", "appeal",
          "exclude", "exclude_reason", "geonameid", "reviewed", "seed_sources"]
SEEDS = {"tr_province", "diaspora", "capital", "geonames_200k", "tr_curated", "llm_draft"}


ALT_NAMES = {"Ulaanbaatar": ("Ulan Bator",)}      # GeoNames spelling


def find(name: str, country: str) -> dict:
    names = {name, *ALT_NAMES.get(name, ())}
    hits = [d for d in ad.load_destinations() if d["country"] == country and
            (d["name"] in names or d["name_tr"] in names)]
    assert len(hits) == 1, f"{name} ({country}): {len(hits)} rows"
    return hits[0]


# ---- schema / uniqueness / determinism ------------------------------------------

def test_file_header():
    with open(ad.DESTINATIONS_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["schema_version"] == "acg-destinations-1"
    assert data["policy"] == "viable_world_v1"
    assert "GeoNames" in data["attribution"] and "WorldClim" in data["attribution"]
    ids = [d["id"] for d in data["destinations"]]
    assert ids == sorted(ids)
    assert os.path.getsize(ad.DESTINATIONS_PATH) < 1_500_000


def test_record_schema():
    countries = {c["iso_a2"] for c in geo.load_countries()}
    regions = {r["admin1_id"] for r in geo.load_regions()}
    for d in ad.load_destinations():
        assert list(d) == FIELDS, d["id"]
        assert re.fullmatch(r"dst-[a-z0-9-]+", d["id"]), d["id"]
        assert d["name"] and d["name_tr"]
        assert d["country"] in countries, d["id"]
        assert d["admin1_id"] is None or d["admin1_id"] in regions, d["id"]
        assert d["kind"] in ("city", "resort", "region")
        assert -90 <= d["lat"] <= 90 and -180 <= d["lon"] <= 180
        assert (d["radius_km"] == 0) == (d["kind"] != "region"), d["id"]
        pop = d["population"]
        assert d["size"] == ("big" if pop >= 1_000_000 else "mid" if pop >= 200_000 else "small")
        assert isinstance(d["coast_km"], float) and d["coast_km"] >= 0
        assert d["med_coast_km"] is None or 0 <= d["med_coast_km"] <= 500
        assert isinstance(d["island"], bool)
        assert d["purposes"] and set(d["purposes"]) <= {"living", "travel"}
        assert d["climate"] in ("warm", "mild", "cold", None)
        assert d["appeal"] in (1, 2, 3)
        assert isinstance(d["exclude"], bool)
        assert (d["exclude_reason"] is None) == (not d["exclude"]), d["id"]
        assert isinstance(d["geonameid"], int)
        assert isinstance(d["reviewed"], bool)
        assert d["seed_sources"] and set(d["seed_sources"]) <= SEEDS


def test_unique_ids_and_geonameids():
    ds = ad.load_destinations()
    assert len({d["id"] for d in ds}) == len(ds)
    assert len({d["geonameid"] for d in ds}) == len(ds)


def test_reviewed_only_from_reviewed_seeds():
    """No auto-approval: reviewed=true iff seeded by the 81 province centres or v1 diaspora,
    or recorded as a review decision in destinations_review_decisions.csv."""
    import csv
    path = os.path.join(os.path.dirname(os.path.abspath(ad.__file__)),
                        "destinations_review_decisions.csv")
    decided = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            decided = {r["id"] for r in csv.DictReader(fh)
                       if r["reviewed"].strip().lower() == "true"}
    rp = os.path.join(os.path.dirname(os.path.abspath(ad.__file__)),
                      "destinations_review_policy.json")
    bulk = False
    if os.path.exists(rp):
        with open(rp, encoding="utf-8") as fh:
            bulk = bool(json.load(fh).get("approve_policy_allowed"))
    for d in ad.load_destinations():
        want = (bool({"tr_province", "diaspora"} & set(d["seed_sources"])) or d["id"] in decided
                or (bulk and not d["exclude"]))
        assert d["reviewed"] == want, d["id"]


def test_all_81_province_centres_present_and_reviewed():
    gaz = {int(c["id"][3:]): c for c in geo.load_cities()}
    by_gid = {d["geonameid"]: d for d in ad.load_destinations()}
    plates = set()
    for gid, c in gaz.items():
        p = {a for a in c["aliases"] if re.fullmatch(r"tr-\d\d", a)}
        if p:
            plates |= p
            d = by_gid[gid]
            assert d["reviewed"] and "tr_province" in d["seed_sources"]
            assert d["country"] == "TR" and d["name_tr"] == c["name_tr"]
            assert not d["exclude"]
    assert plates == {f"tr-{i:02d}" for i in range(1, 82)}


def test_policy_exclusions_marked():
    for d in ad.load_destinations():
        ok, rule = ad.policy_verdict(d)
        if not ok:
            assert d["exclude"] and d["exclude_reason"] == f"policy:{rule}", d["id"]
        else:
            assert not (d["exclude_reason"] or "").startswith("policy:"), d["id"]


def test_regions_map_covers_countries():
    rm = ad.load_regions_map()
    assert set(rm) == {c["iso_a2"] for c in geo.load_countries()}
    for cc, keys in rm.items():
        assert set(keys) <= set(ad.REGION_KEYS), cc
    assert set(rm["TR"]) == {"turkey", "europe", "mediterranean", "middle_east_gulf"}
    assert rm["XN"] == rm["CY"]
    assert rm["AQ"] == []


def test_review_sheet_matches():
    with open(os.path.join(_HERE, "destinations_review.csv"), encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert [*rows[0]] == ["id", "name", "name_tr", "country", "kind", "size", "climate",
                         "coast_km", "purposes", "appeal", "exclude", "exclude_reason",
                         "reviewed", "seed_sources"]
    assert sorted(r["id"] for r in rows) == [d["id"] for d in ad.load_destinations()]


def test_build_is_deterministic(tmp_path, monkeypatch):
    """A rebuild reproduces the committed files byte for byte and makes no model call
    (the LLM draft is cached). Skipped when the open-data cache is absent."""
    import build_geo_index as bgi
    need = ["cities15000.zip", "ne_10m_coastline.zip", "ne_10m_geography_marine_polys.zip",
            "wc2.1_10m_bio.zip", "ne_10m_admin_1_states_provinces.zip", "allCountries_dest_match.json"]
    if not all(os.path.exists(os.path.join(bgi.CACHE_DIR, n)) for n in need):
        pytest.skip("open-data cache (.cache/geodata) not present")
    import build_destinations as bd
    import llm_client

    def boom(*a, **k):
        raise AssertionError("model call during a cached rebuild")
    monkeypatch.setattr(llm_client, "complete", boom)
    data, regions_map, _, _ = bd.build(False, None)
    with open(ad.DESTINATIONS_PATH, encoding="utf-8") as fh:
        assert bd.dumps(data) == fh.read()
    assert regions_map == ad.load_regions_map()


# ---- DV1: policy fixtures ---------------------------------------------------------

EXCLUDED = [("Magnitogorsk", "RU", "P2"), ("Novosibirsk", "RU", "P2"),
            ("Ulaanbaatar", "MN", "P1"), ("Pyongyang", "KP", "P1"), ("Chengdu", "CN", "P3"),
            ("Casablanca", "MA", "P4"), ("Nairobi", "KE", "P4"), ("Tehran", "IR", "P5")]
ALLOWED = [("Moscow", "RU"), ("Saint Petersburg", "RU"), ("Shanghai", "CN"), ("Beijing", "CN"),
           ("Tangier", "MA"), ("Alexandria", "EG"), ("Tel Aviv", "IL"), ("Dubai", "AE"),
           ("Riyadh", "SA"), ("Jeddah", "SA"), ("Baku", "AZ"),
           ("Las Palmas de Gran Canaria", "ES")]


@pytest.mark.parametrize("name,cc,rule", EXCLUDED)
def test_dv1_excluded(name, cc, rule):
    d = find(name, cc)
    assert ad.policy_verdict(d) == (False, rule)
    assert d["exclude"] and d["exclude_reason"] == f"policy:{rule}"


@pytest.mark.parametrize("name,cc", ALLOWED)
def test_dv1_allowed(name, cc):
    d = find(name, cc)
    ok, rule = ad.policy_verdict(d)
    assert ok, (name, rule)
    assert not d["exclude"]


def test_dv1_rules_and_special_territories():
    base = {"size": "mid", "coast_km": 5.0, "med_coast_km": None, "geonameid": 0,
            "admin1_id": None}
    v = lambda **kw: ad.policy_verdict({**base, **kw})
    # Canaries / Ceuta / Melilla carry ES, Madeira PT: treated as Spain / Portugal
    assert v(country="ES") == (True, "P7")
    assert v(country="PT") == (True, "P7")
    assert v(country="HK", size="big", coast_km=0.0) == (True, "P7")
    assert v(country="MO") == (True, "P7") and v(country="TW") == (True, "P7")
    assert v(country="XN") == (True, "P7")
    assert v(country="CN", size="mid", coast_km=10.0) == (False, "P3")
    assert v(country="CN", size="big", coast_km=301.0) == (False, "P3")
    assert v(country="MA", med_coast_km=50.0) == (True, "P4")
    assert v(country="MA", med_coast_km=None) == (False, "P4")
    assert v(country="SN", med_coast_km=0.0) == (False, "P4")
    assert v(country="RU", admin1_id=None) == (False, "P2")
    assert v(country="RU", admin1_id="RUS-2324") == (True, "P2")       # Kaliningrad
    assert v(country="RU", admin1_id="RUS-2606") == (False, "P2")      # Buryatia (Far East)
    for cc in ("BH", "KW", "OM", "QA", "TR", "IL"):
        assert v(country=cc) == (True, "P5")
    for cc in ("IQ", "SY", "LB", "JO", "YE"):
        assert v(country=cc) == (False, "P5")
    assert v(country="KZ", geonameid=1526384) == (True, "P6")           # Almaty
    assert v(country="KZ", geonameid=1) == (False, "P6")


def test_dv1_central_asia_allow_list():
    allowed = {d["name"] for d in ad.load_destinations()
               if d["country"] in ("KZ", "UZ", "KG", "TJ", "TM") and not d["exclude"]}
    assert {"Astana", "Almaty", "Tashkent", "Samarkand", "Bukhara", "Bishkek", "Dushanbe",
            "Ashgabat"} <= allowed
    assert len(allowed) == 8


def test_no_asian_russia_or_interior_china_allowed():
    pol = {r["id"]: r for r in ad.load_policy()["rules"]}
    fd = pol["P2"]["federal_districts"]
    for d in ad.load_destinations():
        if d["exclude"]:
            continue
        if d["country"] == "RU":
            assert fd.get(d["admin1_id"]) in ("Central", "Northwestern", "Southern",
                                              "North Caucasian", "Volga"), d["id"]
        if d["country"] == "CN":
            assert d["size"] == "big" and d["coast_km"] <= 300, d["id"]


# ---- DV2: defaults -----------------------------------------------------------------

def test_dv2_defaults_echoed():
    f = ad.resolve_filters("career")
    assert ad.filters_applied(f) == {"regions": ["all"], "city_size": ["big"],
                                     "max_distance_km": None, "climate": None,
                                     "purpose": ["living"], "policy": "viable_world_v1"}
    assert json.loads(json.dumps(f)) == ad.filters_applied(f)
    assert ad.resolve_filters("travel")["purpose"] == ["travel"]
    assert ad.resolve_filters("rest")["purpose"] == ["travel"]
    assert ad.resolve_filters("love")["purpose"] == ["living", "travel"]
    assert ad.resolve_filters("career", purpose="both")["purpose"] == ["living", "travel"]
    for g in ("relocation", "career", "business", "money", "education", "family"):
        assert ad.DEFAULT_PURPOSE[g] == ["living"]


def test_dv2_resolved_values_and_home():
    f = ad.resolve_filters("relocation", regions="turkey,europe", city_size=["small", "big"],
                           max_distance_km=3000, home_latlon=(41.01, 28.97),
                           climate=["mild", "warm"])
    assert f["regions"] == ["europe", "turkey"]
    assert f["city_size"] == ["big", "small"]
    assert f["climate"] == ["warm", "mild"]
    assert f["max_distance_km"] == 3000.0
    assert f.home_latlon == (41.01, 28.97)
    with pytest.raises(ValueError):
        ad.resolve_filters("career", regions=["atlantis"])
    with pytest.raises(ValueError):
        ad.resolve_filters("career", max_distance_km=1000)
    with pytest.raises(ValueError):
        ad.resolve_filters("nope")


def test_default_candidates_are_viable():
    c = ad.candidates(ad.resolve_filters("career"))
    assert c
    for d in c:
        assert d["reviewed"] and not d["exclude"] and ad.policy_verdict(d)[0]
        assert d["size"] == "big" and "living" in d["purposes"]


def test_filters_narrow_only():
    f = ad.resolve_filters("love")
    base = {d["id"] for d in ad.candidates(f, include_unreviewed=True)}
    tr = ad.resolve_filters("love", regions=["turkey"])
    sub = ad.candidates(tr, include_unreviewed=True)
    assert sub and {d["id"] for d in sub} <= base
    assert all(d["country"] == "TR" for d in sub)
    near = ad.resolve_filters("love", max_distance_km=500, home_latlon=(41.01, 28.97))
    for d in ad.candidates(near, include_unreviewed=True):
        assert ad.great_circle_km(41.01, 28.97, d["lat"], d["lon"]) <= 500
    small = ad.candidates(ad.resolve_filters("travel"), ignore_size=True, country="TR",
                          include_unreviewed=True)
    assert any(d["size"] == "small" for d in small)


# ---- DV3: climate -------------------------------------------------------------------

def test_dv3_climate_only_when_set():
    f = ad.resolve_filters("relocation")
    assert f["climate"] is None
    all_ids = [d["id"] for d in ad.candidates(f, include_unreviewed=True)]
    climates = {d["climate"] for d in ad.candidates(f, include_unreviewed=True)}
    assert {"cold", "mild", "warm"} <= climates      # unfiltered keeps every climate
    warm = ad.candidates(ad.resolve_filters("relocation", climate=["warm"]),
                         include_unreviewed=True)
    assert warm and all(d["climate"] == "warm" for d in warm)
    assert len(warm) < len(all_ids)
    assert {d["id"] for d in warm} == {i for i in all_ids if ad.destination(i)["climate"] == "warm"}


def test_climate_and_coast_values_plausible():
    assert find("Dubai", "AE")["climate"] == "warm"
    assert find("Moscow", "RU")["climate"] == "cold"
    assert find("Ankara", "TR")["climate"] in ("mild", "cold")
    assert find("Barcelona", "ES")["coast_km"] < 10
    assert find("Madrid", "ES")["coast_km"] > 250
    assert find("Tangier", "MA")["med_coast_km"] <= 100
    assert find("Casablanca", "MA")["med_coast_km"] is None or \
        find("Casablanca", "MA")["med_coast_km"] > 100


# ---- DV4–DV8 -------------------------------------------------------------------------
# PLACEHOLDER: DV4–DV8 (line-first recommender, spec 11 §5–§8) are added by the
# recommender engineer against acg_recommend.py. Do not add them here from the data side.
