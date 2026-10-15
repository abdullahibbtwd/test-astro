#!/usr/bin/env python3
"""test_acg.py — ACG spec 01 (compute) + spec 02 (locate / relocate / scan) invariants.

    python -m pytest -q Astrocartography/test_acg.py
"""

from __future__ import annotations

import copy
import json
import math
import os
import sys

import numpy as np
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, os.path.join(_ROOT, "d_layer")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import swisseph as swe  # noqa: E402
from compute_chart import BirthData, compute_chart  # noqa: E402

from acg_constants import BODY_ORDER  # noqa: E402
from acg_geo import n180  # noqa: E402
import compute_acg as ca  # noqa: E402

# Fixture: 1985-03-14 09:30 UT (11:30 local, Istanbul), exact time.
FIXTURE_BD = BirthData(year=1985, month=3, day=14, hour=11, minute=30,
                       latitude=41.0082, longitude=28.9784, time_precision="exact")


@pytest.fixture(scope="module")
def chart():
    return compute_chart(FIXTURE_BD)


@pytest.fixture(scope="module")
def acg(chart):
    return ca.compute_acg(chart)


def _bodies(acg):
    return {b["body"]: b for b in acg["bodies"]}


def _eq(b):
    e = b["equatorial"]
    return e["ra"], e["dec"], e["dist"]


# ---------------------------------------------------------------------------
# Spec 01 §9
# ---------------------------------------------------------------------------

def test_jd_matches_l1(chart, acg):
    from compute_chart import julian_day_ut
    from datetime import datetime
    assert acg["meta"]["jd_ut"] == julian_day_ut(datetime.fromisoformat(chart["meta"]["utc"]))
    assert acg["meta"]["node_type"] == chart["meta"]["node_type"] == "mean"
    assert [b["body"] for b in acg["bodies"]] == list(BODY_ORDER)


def test_c1_mc_line_armc_equals_ra(acg):
    jd = acg["meta"]["jd_ut"]
    for b in acg["bodies"]:
        ra, _, _ = _eq(b)
        lon = b["lines"]["MC"]["vertices"][0][0]
        for lat in (-60.0, 0.0, 41.0, 60.0):
            armc = swe.houses_ex(jd, lat, lon, b"P")[1][2]
            assert abs(n180(armc - ra)) < 1e-6, (b["body"], lat)


def test_c2_ic_is_mc_plus_180(acg):
    for b in acg["bodies"]:
        mc = b["lines"]["MC"]["vertices"]
        ic = b["lines"]["IC"]["vertices"]
        assert len(mc) == len(ic)
        for (lm, _), (li, _) in zip(mc, ic):
            assert abs(n180(li - n180(lm + 180.0))) < 1e-9


def test_c3_asc_dsc_true_altitude_zero(acg):
    jd = acg["meta"]["jd_ut"]
    for b in acg["bodies"]:
        ra, dec, dist = _eq(b)
        for angle in ("ASC", "DSC"):
            for lon, lat in b["lines"][angle]["vertices"]:
                alt = swe.azalt(jd, swe.EQU2HOR, (lon, lat, 0.0), 0.0, 0.0, (ra, dec, dist))[1]
                assert abs(alt) < 1e-6, (b["body"], angle, lat)


def test_c4_hour_angle_side(acg):
    gast = acg["meta"]["gast_deg"]
    for b in acg["bodies"]:
        ra, _, _ = _eq(b)
        for angle, sign in (("ASC", -1), ("DSC", 1)):
            for lon, lat in b["lines"][angle]["vertices"]:
                h = n180(gast + lon - ra)
                if abs(abs(h) - 180.0) < 1e-9:      # the IC join: H = ±180 is both sides
                    continue
                assert sign * h >= -1e-9, (b["body"], angle, lat, h)


def test_c5_no_vertex_beyond_circumpolar_limit(acg):
    for b in acg["bodies"]:
        lim = b["circumpolar_lat_limit"]
        for angle in ("ASC", "DSC"):
            for _, lat in b["lines"][angle]["vertices"]:
                assert abs(lat) <= lim + 1e-9


def test_c6_curves_close_on_meridians(acg):
    for b in acg["bodies"]:
        _, dec, _ = _eq(b)
        lim = b["circumpolar_lat_limit"]
        sgn = math.copysign(1.0, dec)
        mc_lon = b["lines"]["MC"]["vertices"][0][0]
        ic_lon = b["lines"]["IC"]["vertices"][0][0]
        for angle in ("ASC", "DSC"):
            line = b["lines"][angle]
            verts = {lat: lon for lon, lat in line["vertices"]}
            mc_at, ic_at = -sgn * lim, sgn * lim
            if -80.0 <= mc_at <= 80.0:
                assert line["joins"]["MC_at_lat"] == pytest.approx(mc_at, abs=1e-12)
                assert abs(n180(verts[mc_at] - mc_lon)) < 1e-6
            else:
                assert line["joins"]["MC_at_lat"] is None
            if -80.0 <= ic_at <= 80.0:
                assert line["joins"]["IC_at_lat"] == pytest.approx(ic_at, abs=1e-12)
                assert abs(n180(verts[ic_at] - ic_lon)) < 1e-6
            else:
                assert line["joins"]["IC_at_lat"] is None


def test_c7_time_sensitivity(chart, acg):
    later = copy.deepcopy(chart)
    from datetime import datetime, timedelta
    t = datetime.fromisoformat(chart["meta"]["utc"]) + timedelta(minutes=4)
    later["meta"]["utc"] = t.isoformat()
    acg2 = ca.compute_acg(later)
    b1, b2 = _bodies(acg), _bodies(acg2)
    for name in BODY_ORDER:
        d_ra = n180(b2[name]["equatorial"]["ra"] - b1[name]["equatorial"]["ra"])
        moved = n180(b2[name]["lines"]["MC"]["vertices"][0][0]
                     - b1[name]["lines"]["MC"]["vertices"][0][0])
        assert moved == pytest.approx(-1.002738 + d_ra, abs=1e-4), name
    # the spec's worked examples
    sun = n180(b2["sun"]["lines"]["MC"]["vertices"][0][0] - b1["sun"]["lines"]["MC"]["vertices"][0][0])
    moon = n180(b2["moon"]["lines"]["MC"]["vertices"][0][0] - b1["moon"]["lines"]["MC"]["vertices"][0][0])
    assert sun == pytest.approx(-1.0, abs=2e-3)
    assert moon == pytest.approx(-0.96, abs=2e-2)


def test_c8_determinism(chart):
    assert ca.dumps(ca.compute_acg(chart)) == ca.dumps(ca.compute_acg(chart))
    g1 = json.dumps(ca.to_geojson(ca.compute_acg(chart)))
    g2 = json.dumps(ca.to_geojson(ca.compute_acg(chart)))
    assert g1 == g2


def test_c9_geojson_no_antimeridian_jumps(acg):
    gj = ca.to_geojson(acg)
    assert len(gj["features"]) == 44
    for f in gj["features"]:
        assert f["geometry"]["type"] == "MultiLineString"
        for part in f["geometry"]["coordinates"]:
            for (l1, _), (l2, _) in zip(part, part[1:]):
                assert abs(l2 - l1) <= 180.0


def test_split_antimeridian_inserts_edge_vertices():
    from acg_geo import split_antimeridian
    parts = split_antimeridian([[170.0, 0.0], [179.0, 1.0], [-179.0, 2.0], [-170.0, 3.0]])
    assert len(parts) == 2
    assert parts[0][-1][0] == 180.0 and parts[1][0][0] == -180.0
    assert parts[0][-1][1] == pytest.approx(1.5) and parts[1][0][1] == pytest.approx(1.5)


def test_c10_non_exact_is_absent(chart):
    approx = copy.deepcopy(chart)
    approx["meta"]["time_precision"] = "approximate"
    a = ca.compute_acg(approx)
    assert a["status"] == "absent" and a["bodies"] == []
    assert a["absence"]["reason"] == "birth_time_not_exact"
    ca.validate_acg(a)
    assert ca.to_geojson(a) == {"type": "FeatureCollection", "features": []}
    no_utc = copy.deepcopy(chart)
    del no_utc["meta"]["utc"]
    assert ca.compute_acg(no_utc)["absence"]["reason"] == "missing_utc_instant"


def test_c11_schema_valid(acg, tmp_path):
    ca.validate_acg(acg)
    ca.write_acg(acg, str(tmp_path / "acg.json"), str(tmp_path / "acg.geojson"))
    with open(tmp_path / "acg.json", encoding="utf-8") as fh:
        assert json.load(fh)["status"] == "ok"


def test_nodes_drawn_not_read(acg):
    node = _bodies(acg)["north_node"]
    assert node["read_in_v1"] is False and node["out_of_scope"] == "acg_nodes_v1"
    assert all(b["read_in_v1"] for b in acg["bodies"] if b["body"] != "north_node")


# ---------------------------------------------------------------------------
# Spec 02 §8 — locate / relocate / gazetteer / scan
# ---------------------------------------------------------------------------

import acg_locate as al  # noqa: E402


def _manual(lat, lon):
    place, ab = al.resolve_place(lat=lat, lon=lon)
    assert ab is None
    return place


def _near(acg, body, angle, lat, lon):
    for r in al.lines_near(acg, lat, lon):
        if r["body"] == body and r["angle"] == angle:
            return r
    return None


def test_lo1_place_on_mc_line_is_tight(acg):
    for b in acg["bodies"]:
        lon = b["lines"]["MC"]["vertices"][0][0]
        r = _near(acg, b["body"], "MC", 41.0, lon)
        assert r is not None and r["distance_km"] < 0.5 and r["tier"] == "tight"


def test_lo2_one_degree_east_of_meridian_at_equator(acg):
    b = _bodies(acg)["venus"]
    lon = b["lines"]["MC"]["vertices"][0][0]
    r = _near(acg, "venus", "MC", 0.0, n180(lon + 1.0))
    assert r["distance_km"] == pytest.approx(111.19, abs=0.2)
    assert r["side"] == "east"


def test_lo3_asc_vertex_and_meridional_offset(acg):
    b = _bodies(acg)["mars"]
    verts = b["lines"]["ASC"]["vertices"]
    lon, lat = next(v for v in verts if v[1] == 30.0)
    assert _near(acg, "mars", "ASC", lat, lon)["distance_km"] < 0.5
    r = _near(acg, "mars", "ASC", lat + 2.0, lon)
    assert r is not None and r["distance_km"] <= 222.4


def test_lo4_tier_boundaries():
    assert al.tier_for(149.9) == "tight"
    assert al.tier_for(150.1) == "strong"
    assert al.tier_for(399.9) == "strong"
    assert al.tier_for(999.9) == "wide"
    assert al.tier_for(1000.1) is None


def test_lines_near_sorted_and_within_orb(acg):
    rows = al.lines_near(acg, 38.42, 27.14)
    assert rows == sorted(rows, key=lambda r: r["distance_km"])
    assert all(r["distance_km"] <= 1000.0 for r in rows)


def test_r1_relocated_armc_on_mc_line(chart, acg):
    b = _bodies(acg)["jupiter"]
    lon = b["lines"]["MC"]["vertices"][0][0]
    reloc, block = al.relocate(chart, _manual(41.0, lon))
    assert block["status"] == "ok"
    jd = acg["meta"]["jd_ut"]
    armc = swe.houses_ex(jd, 41.0, lon, b"P")[1][2]
    assert abs(n180(armc - b["equatorial"]["ra"])) < 1e-6
    # the relocated chart's MC sits on Jupiter's zodiacal culmination: MC longitude
    # equals the ecliptic point of RA = ra_jupiter
    assert reloc["meta"]["utc"] == chart["meta"]["utc"]


def test_r2_place_on_asc_line_has_body_on_horizon(acg):
    b = _bodies(acg)["saturn"]
    ra, dec, dist = _eq(b)
    lon, lat = next(v for v in b["lines"]["ASC"]["vertices"] if v[1] == 20.0)
    alt = swe.azalt(acg["meta"]["jd_ut"], swe.EQU2HOR, (lon, lat, 0.0), 0.0, 0.0,
                    (ra, dec, dist))[1]
    assert abs(alt) < 1e-6


# Fields that legitimately depend on the location (exploration report C4): sect
# (Sun above/below the NEW horizon) flips the triplicity ruler; lots and the
# planetary hour are local by definition.
_SECT_DEPENDENT = ("triplicity_ruler", "in_triplicity")


def _strip_local(points):
    out = []
    for p in points:
        q = {k: v for k, v in p.items() if k != "sector"}
        if q.get("classifications"):
            q["classifications"] = {k: v for k, v in q["classifications"].items()
                                    if k not in _SECT_DEPENDENT}
        out.append(q)
    return out


def test_r3_relocation_changes_only_location_fields(chart):
    reloc, _ = al.relocate(chart, _manual(40.7128, -74.006))      # New York
    assert _strip_local(reloc["points"]) == _strip_local(chart["points"])
    assert reloc["relations"] == chart["relations"]
    assert reloc["axes"] != chart["axes"]


def test_r4_instant_kept_across_timezones(chart):
    reloc, _ = al.relocate(chart, _manual(40.7128, -74.006))
    assert reloc["meta"]["utc"] == chart["meta"]["utc"]
    assert reloc["meta"]["timezone"] == "America/New_York"
    from compute_chart import julian_day_ut
    from datetime import datetime
    assert (julian_day_ut(datetime.fromisoformat(reloc["meta"]["utc"]))
            == julian_day_ut(datetime.fromisoformat(chart["meta"]["utc"])))


def test_r5_high_latitude_relocation_absent_lines_still_located(chart, acg):
    loc, reloc = al.build_locate(acg, chart, _manual(70.0, 25.0))
    assert reloc is None
    assert loc["status"] == "ok"
    assert loc["relocation"]["status"] == "absent"
    assert loc["relocation"]["absence"]["reason"] == "placidus_undefined_high_latitude"
    assert isinstance(loc["lines_near"], list)
    assert loc["house_diff"] == []


def test_r6_relocating_to_natal_coordinates_is_identity(chart, acg):
    loc, reloc = al.build_locate(acg, chart, _manual(41.0082, 28.9784))
    assert loc["house_diff"] == []
    assert reloc == chart


def test_default_compute_chart_unchanged(chart):
    assert compute_chart(FIXTURE_BD) == chart


def test_absent_acg_propagates_to_locate(chart):
    approx = copy.deepcopy(chart)
    approx["meta"]["time_precision"] = "approximate"
    loc, reloc = al.build_locate(ca.compute_acg(approx), approx, _manual(38.42, 27.14))
    assert loc["status"] == "absent" and reloc is None
    assert loc["absence"]["reason"] == "birth_time_not_exact"


def test_house_diff_shape(chart, acg):
    loc, reloc = al.build_locate(acg, chart, _manual(40.7128, -74.006))
    assert loc["house_diff"], "New York should move at least one planet"
    for d in loc["house_diff"]:
        assert d["natal_house"] != d["relocated_house"]
        assert d["angular_after"] == (d["relocated_house"] in (1, 4, 7, 10))


def test_resolve_place_gazetteer_and_geocoder_failure():
    gaz = al.load_gazetteer()
    p, ab = al.resolve_place("IZMIR", gazetteer=gaz)
    assert ab is None and p["source"] == "gazetteer" and p["name_tr"] == "İzmir"
    p, _ = al.resolve_place("münih", gazetteer=gaz)
    assert p["name"] == "Munich" and p["name_tr"] == "Münih"
    # v2: İzmit is its own city (Kocaeli's centre); the province name still resolves
    p, _ = al.resolve_place("Izmit", gazetteer=gaz)
    assert p["name_tr"] == "İzmit" and p["country_code"] == "TR"
    q, _ = al.resolve_place("Kocaeli", gazetteer=gaz)
    assert (q["lat"], q["lon"]) == (p["lat"], p["lon"])
    # v1 ids and v2 GeoNames ids resolve too
    izmir = al.gazetteer_lookup("tr-35", gaz)
    assert izmir["name_tr"] == "İzmir" and al.gazetteer_lookup(izmir["id"], gaz) is izmir
    assert al.gazetteer_lookup("de-munich", gaz)["name"] == "Munich"

    def boom(_q):
        raise RuntimeError("no location found")
    p, ab = al.resolve_place("Nowhereville", gazetteer=gaz, geocoder=boom)
    assert p is None and ab["reason"] == "place_not_found"


# v1 diaspora ids (spec 02 §6) — every one must still resolve in v2
_V1_DIASPORA = (
    "ae-dubai at-vienna au-melbourne au-sydney az-baku be-brussels bg-sofia ca-montreal "
    "ca-toronto ch-zurich cy-nicosia de-berlin de-cologne de-dusseldorf de-frankfurt "
    "de-hamburg de-munich de-stuttgart dk-copenhagen es-barcelona es-madrid fr-lyon "
    "fr-paris gb-london ge-tbilisi gr-athens it-milan it-rome jp-tokyo nl-amsterdam "
    "nl-rotterdam no-oslo pt-lisbon qa-doha ru-moscow sa-riyadh se-stockholm "
    "sg-singapore us-chicago us-los-angeles us-miami us-new-york us-san-francisco").split()


def test_g1_gazetteer_contents():
    """Change order v3 §2: ≥ 1,200 cities; all 81 provinces; every admin-0 country
    has a city or is logged; unique ids; name_tr non-empty."""
    import acg_geodata as gd
    gaz = al.load_gazetteer()
    assert len(gaz) >= 1200
    ids = [c["id"] for c in gaz]
    assert len(ids) == len(set(ids)) and all(i.startswith("gn-") for i in ids)
    assert ids == sorted(ids)
    fields = {"id", "name", "name_tr", "aliases", "country_code", "admin1_code",
              "admin1_id", "lat", "lon", "population"}
    for c in gaz:
        assert set(c) == fields
        assert c["name_tr"] and -90 <= c["lat"] <= 90 and -180 <= c["lon"] <= 180
        assert len(c["country_code"]) == 2 and c["country_code"].isupper()
    for plate in range(1, 82):
        hit = al.gazetteer_lookup(f"tr-{plate:02d}", gaz)
        assert hit is not None and hit["country_code"] == "TR" and hit["name_tr"], plate
    assert len({al.gazetteer_lookup(f"tr-{i:02d}", gaz)["id"] for i in range(1, 82)}) == 81
    for vid in _V1_DIASPORA:
        assert al.gazetteer_lookup(vid, gaz) is not None, vid
    regions = {r["admin1_id"] for r in gd.load_regions()}
    assert all(c["admin1_id"] in regions for c in gaz if c["admin1_id"])
    assert sum(1 for c in gaz if c["admin1_id"] is None) <= 10
    with open(os.path.join(_HERE, "build_gazetteer.log"), encoding="utf-8") as fh:
        logged = {ln.split(": ", 1)[1].split()[0] for ln in fh
                  if ln.startswith("no city ≥ threshold: ")}
    have = {gd.country_of_city(c)["iso_a2"] for c in gaz if gd.country_of_city(c)}
    for co in gd.load_countries():
        assert co["iso_a2"] in have or co["iso_a2"] in logged, co["iso_a2"]


def test_geo_index():
    import acg_geodata as gd
    countries = gd.load_countries()
    codes = [c["iso_a2"] for c in countries]
    assert len(codes) == len(set(codes)) and {"TR", "DE", "FR", "NO", "CY"} <= set(codes)
    for c in countries:
        assert c["name"] and c["name_tr"] and len(c["bbox"]) == 4
        assert c["bbox"][0] <= c["bbox"][2] and c["bbox"][1] <= c["bbox"][3]
    assert gd.country("TR")["name_tr"] == "Türkiye"
    regions = gd.load_regions()
    rids = [r["admin1_id"] for r in regions]
    assert len(rids) == len(set(rids))
    assert all(r["iso_a2"] in set(codes) and r["name_tr"] for r in regions)
    assert sum(1 for r in regions if r["iso_a2"] == "TR") == 81
    grid = gd.load_grid()
    n = len(grid["lat"])
    assert 40_000 <= n <= 70_000
    assert all(len(grid[k]) == n for k in ("lon", "iso_a2", "admin1_id"))
    assert grid["lat"].dtype == np.float64 and grid["lon"].dtype == np.float64
    assert grid["iso_a2"].dtype.kind == "U" and grid["admin1_id"].dtype.kind == "U"
    assert ((grid["lat"] >= -90) & (grid["lat"] <= 90)).all()
    grid_codes = set(grid["iso_a2"].tolist()) - {""}
    assert grid_codes <= set(codes)
    assert set(codes) <= grid_codes          # small countries got a representative point
    assert set(grid["admin1_id"].tolist()) - {""} <= set(rids)
    tr = grid["iso_a2"] == "TR"
    assert 100 < tr.sum() < 1000
    # country / region selection helpers (ACG_08 §5, V3-3)
    tr_cities = gd.cities_in("TR")
    assert len(tr_cities) >= 81 and all(gd.country_of_city(c)["iso_a2"] == "TR"
                                        for c in tr_cities)
    de = gd.cities_in("de")
    assert de and all(c["country_code"] == "DE" for c in de)
    izmir = al.gazetteer_lookup("tr-35", al.load_gazetteer())
    assert izmir in gd.cities_in(admin1_id=izmir["admin1_id"])
    assert gd.region(izmir["admin1_id"])["iso_a2"] == "TR"


def test_g2_city_scan_deterministic_and_offline(acg, monkeypatch):
    def no_network(*_a, **_k):
        raise AssertionError("city scan must not geocode")
    monkeypatch.setattr(al, "_default_geocoder", no_network)
    s1 = al.city_scan(acg)
    s2 = al.city_scan(acg)
    assert ca.dumps(s1) == ca.dumps(s2)
    assert len(s1["cities"]) == len(al.load_gazetteer())
    assert [c["city_id"] for c in s1["cities"]] == sorted(c["id"] for c in al.load_gazetteer())
    for c in s1["cities"]:
        assert all(r["tier"] in ("tight", "strong") and r["read_in_v1"] for r in c["lines_near"])
    for key, rows in s1["by_line"].items():
        assert len(rows) <= 5
        assert rows == sorted(rows, key=lambda e: (e["distance_km"], e["city_id"]))
