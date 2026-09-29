"""CAL_01 §5 acceptance tests (E1-E8).  Run: python -m pytest Calendar/test_cal_events.py -q"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timezone

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "d_layer"))

import cal_astro as A  # noqa: E402
import cal_constants as K  # noqa: E402
import collective_events as C  # noqa: E402
import personal_events as P  # noqa: E402
from compute_chart import BirthData, compute_chart  # noqa: E402


def _jd(iso: str) -> float:
    return A.jd_of(A.parse_iso_utc(iso))


@pytest.fixture(scope="module")
def coll_dir(tmp_path_factory):
    return str(tmp_path_factory.mktemp("collective"))


@pytest.fixture(scope="module")
def years(coll_dir):
    return {y: C.ensure_year(y, coll_dir) for y in (2026, 2027)}


@pytest.fixture(scope="module")
def natal():
    return compute_chart(BirthData(year=1979, month=3, day=30, hour=6, minute=30,
                                   latitude=42.6977, longitude=23.3219))


@pytest.fixture(scope="module")
def personal(natal, coll_dir, years):
    return P.build_personal_events(natal, "Europe/Sofia", date(2026, 9, 28), collective_dir=coll_dir)


def _all(years):
    return [e for y in sorted(years) for e in years[y]["events"]]


# E1 -----------------------------------------------------------------------------------
def test_e1_eclipses(years):
    got = {(e["t_utc"][:10], e["kind"], e["eclipse_kind"]) for e in _all(years)
           if e["kind"].endswith("_eclipse")}
    want = {("2026-02-17", "solar_eclipse", "annular"), ("2026-08-12", "solar_eclipse", "total"),
            ("2027-02-06", "solar_eclipse", "annular"), ("2027-08-02", "solar_eclipse", "total"),
            ("2026-03-03", "lunar_eclipse", "total"), ("2026-08-28", "lunar_eclipse", "partial"),
            ("2027-02-20", "lunar_eclipse", "penumbral"), ("2027-07-18", "lunar_eclipse", "penumbral"),
            ("2027-08-17", "lunar_eclipse", "penumbral")}
    assert got == want
    for e in _all(years):
        if e["kind"].endswith("_eclipse"):
            assert e["lunation_id"] is not None


# E2 -----------------------------------------------------------------------------------
def test_e2_mercury_stations(years):
    got = [(e["kind"], e["t_utc"][:10]) for e in years[2026]["events"]
           if e["kind"].startswith("station_") and e["body"] == "mercury"]
    want = [("station_retrograde", "2026-02-26"), ("station_direct", "2026-03-21"),
            ("station_retrograde", "2026-06-29"), ("station_direct", "2026-07-24"),
            ("station_retrograde", "2026-10-24"), ("station_direct", "2026-11-13")]
    assert len(got) == len(want)
    for (k, d), (wk, wd) in zip(got, want):
        assert k == wk
        assert abs((date.fromisoformat(d) - date.fromisoformat(wd)).days) <= 1


# E3 -----------------------------------------------------------------------------------
def test_e3_lunation_and_station_precision(years):
    n = 0
    for e in _all(years):
        if e["kind"] in ("new_moon", "full_moon"):
            target = 0.0 if e["kind"] == "new_moon" else 180.0
            assert abs(A.signed180(A.elongation(_jd(e["t_utc"])) - target)) < 1e-4
            n += 1
        elif e["kind"].startswith("station_"):
            assert abs(A.lon_speed(_jd(e["t_utc"]), e["body"])[1]) < 1e-5
    assert n >= 24


# E4 -----------------------------------------------------------------------------------
def test_e4_voc(years):
    vocs = [e for e in years[2026]["events"] if e["kind"] == "voc_moon"]
    assert len(vocs) > 150
    elongs = [0, 60, 90, 120, 180, 240, 270, 300]
    for v in vocs[::10]:                                     # every 10th: dense check is slow
        s, t = _jd(v["start_utc"]), _jd(v["end_utc"])
        la = v["last_aspect"]
        sep = A.norm360(A.lon(s, "moon") - A.lon(s, la["body"]))
        assert min(abs(A.signed180(sep - e)) for e in elongs) < 1e-3
        # no Moon major aspect perfects strictly inside (start, end): 5-minute scan
        step = 5 / 1440
        j = s + 2 / 86400
        prev = None
        while j < t - 2 / 86400:
            cur = [A.signed180(A.lon(j, "moon") - A.lon(j, b) - e)
                   for b in K.VOC_BODIES for e in elongs]
            if prev is not None:
                for a, b in zip(prev, cur):
                    assert not ((a < 0) != (b < 0) and abs(a) + abs(b) < 180), v
            prev = cur
            j += step
        # end = the next Moon ingress (±1 s)
        assert A.sign_key(A.lon(t - 1 / 86400, "moon")) != A.sign_key(A.lon(t + 1 / 86400, "moon"))


# E5 -----------------------------------------------------------------------------------
def test_e5_transit_exacts_and_orbs(personal, natal):
    pts = P.natal_points(natal)
    tr = [e for e in personal["events"] if e["kind"] == "transit"]
    assert tr
    for e in tr:
        ang = K.ASPECTS[e["aspect"]]
        orb = K.TRANSIT_ORB[e["t_body"]]
        for x in e["exacts_utc"]:
            sep = abs(A.signed180(A.lon(_jd(x), e["t_body"]) - pts[e["n_point"]]))
            assert abs(sep - ang) < 1e-4
        if not e.get("truncated"):
            for edge in (e["start_utc"], e["end_utc"]):
                sep = abs(A.signed180(A.lon(_jd(edge), e["t_body"]) - pts[e["n_point"]]))
                assert abs(abs(sep - ang) - orb) < 1e-3


def test_e5_station_passes_merge():
    """A Saturn station within 1° of a point: the passes on both sides of the
    station stay inside one orb window, so they form one episode with 2 exacts."""
    jd0 = _jd("2026-06-01T00:00:00Z")
    (st_jd, d), = [s for s in A.stations("saturn", jd0, jd0 + 250) if s[1] == "R"][:1]
    point = A.norm360(A.lon(st_jd, "saturn") - 0.6)
    eps = [e for e in P.transit_episodes({"sun": point}, st_jd - 30, st_jd + 30)
           if e["t_body"] == "saturn" and e["aspect"] == "conjunction"]
    near = [e for e in eps if e["start"] <= st_jd <= e["end"]]
    assert len(near) == 1 and len(near[0]["exacts"]) == 2


def test_e5_triple_pass_merged(personal):
    """The outer-planet retrograde triple pass is one episode with 3 exacts
    (Pluto square natal Moon, 1979-03-30 Sofia chart)."""
    ep = [e for e in personal["events"] if e["id"].startswith("tr:pluto:square:moon:")]
    assert len(ep) == 1 and len(ep[0]["exacts_utc"]) == 3


# E6 -----------------------------------------------------------------------------------
def test_e6_local_dates():
    t = "2026-10-10T22:30:00Z"
    assert A.local_date_of_iso(t, "Europe/Istanbul") == "2026-10-11"
    assert A.local_date_of_iso(t, "Europe/London") == "2026-10-10"


# E7 -----------------------------------------------------------------------------------
def test_e7_determinism(years, natal, coll_dir, personal, tmp_path):
    assert C.dumps(C.build_year(2026)) == C.dumps(years[2026])
    again = P.build_personal_events(natal, "Europe/Sofia", date(2026, 9, 28), collective_dir=coll_dir)
    assert P.dumps(again) == P.dumps(personal)
    # collective files do not depend on any user: rebuilding into a second dir is identical
    other = C.ensure_year(2026, str(tmp_path))
    assert C.dumps(other) == C.dumps(years[2026])


def test_e7_tz_changes_only_local_fields(natal, coll_dir, personal):
    ist = P.build_personal_events(natal, "Europe/Istanbul", date(2026, 9, 28), collective_dir=coll_dir)
    utc_a = {e["id"]: e.get("exacts_utc") for e in personal["events"] if e["kind"] == "transit"}
    utc_b = {e["id"]: e.get("exacts_utc") for e in ist["events"] if e["kind"] == "transit"}
    common = set(utc_a) & set(utc_b)
    assert len(common) > 0.9 * len(utc_a)
    assert all(utc_a[k] == utc_b[k] for k in common)


# E8 -----------------------------------------------------------------------------------
def test_e8_importance():
    assert P.transit_importance("pluto", "conjunction", "sun")[0] == "major"
    assert P.transit_importance("sun", "sextile", "neptune")[0] == "minor"
    coll = [{"id": "lun:2026-10-10:new", "kind": "new_moon", "t_utc": "2026-10-10T15:50:07Z",
             "sign": "libra", "degree": 17.0, "eclipse_id": None}]
    mc = 6 * 30 + 17.0 + 1.2
    ev = P.lunation_events(coll, {"mc": mc}, None, _jd("2026-10-01T00:00:00Z"),
                           _jd("2026-11-01T00:00:00Z"), "Europe/Sofia")
    assert ev[0]["importance"] == "major" and ev[0]["hits"][0]["point"] == "mc"
