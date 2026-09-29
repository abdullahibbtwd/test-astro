#!/usr/bin/env python3
"""
test_forecast.py — proves forecast_types.py, forecast_schema.json, and the actual
output of compute_forecast() agree, and enforces every SPEC §13 invariant.

Fixtures (SPEC §15):
  * exact / approximate / unknown  precision tiers (Istanbul)
  * circumpolar exact              (Svalbard — Placidus undefined, must degrade
                                    house detection to whole-sign)
  * DST edge                       (New York, month spanning spring-forward)
  * retrograde triple-perfection   (a synthetic natal point on Saturn's retro
                                    band — one aspect perfects three times)
  * in-window eclipse + year Moon-exclusion (a YEAR run)

Run directly (`python test_forecast.py`) — writes forecast_report.json (counts +
invariant results) — or under pytest.

Determinism note: meta.generated_at / meta.run_id are the only non-deterministic
fields, so every fixture pins them via now=/run_id=; invariant 7 then hashes the
whole object.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone

from jsonschema import Draft202012Validator

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "d_layer")))

import swisseph as swe  # noqa: E402
from compute_chart import BirthData, compute_chart  # noqa: E402

from compute_forecast import (  # noqa: E402
    EPHE_FLAG, GROUNDING_KINDS, compute_forecast,
)

_SCHEMA_PATH = os.path.join(_HERE, "forecast_schema.json")
_FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
_FIXED_RUN = "20260101-000000_tst"

# Birth locations
_IST = dict(year=1990, month=6, day=15, latitude=41.0082, longitude=28.9784)
_SVB = dict(year=1990, month=6, day=15, latitude=78.2232, longitude=15.6267)
_NYC = dict(year=1990, month=6, day=15, latitude=40.7128, longitude=-74.0060)


# ---------------------------------------------------------------------------
# Natal charts
# ---------------------------------------------------------------------------
def _natal_exact_ist():
    return compute_chart(BirthData(time_precision="exact", hour=14, minute=30, **_IST))


def _natal_approx_ist():
    return compute_chart(BirthData(time_precision="approximate",
                                   approx_bucket="morning", **_IST))


def _natal_unknown_ist():
    return compute_chart(BirthData(time_precision="unknown", **_IST))


def _natal_circumpolar():
    return compute_chart(BirthData(time_precision="exact", hour=14, minute=30, **_SVB))


def _natal_nyc():
    return compute_chart(BirthData(time_precision="exact", hour=14, minute=30, **_NYC))


def _fc(natal, target, horizon, **kw):
    return compute_forecast(natal, target, horizon, now=_FIXED_NOW,
                            run_id=_FIXED_RUN, **kw)


# ---------------------------------------------------------------------------
# Retrograde-triple fixture: inject a natal point on Saturn's retrograde band so
# a single conjunction perfects three times inside a one-year window.
# ---------------------------------------------------------------------------
def _signed180(x: float) -> float:
    return ((x + 180.0) % 360.0) - 180.0


def _saturn_retro_longitude(year: int) -> float:
    """Mid-band longitude of Saturn's retrograde loop in `year` — a longitude the
    planet crosses forward, then backward (retro), then forward again = 3x."""
    lons_retro = []
    jd0 = swe.julday(year, 1, 1, 0.0)
    for d in range(0, 366):
        xx, _ = swe.calc_ut(jd0 + d, swe.SATURN, EPHE_FLAG)
        if xx[3] < 0:                     # retrograde (negative speed)
            lons_retro.append(xx[0] % 360.0)
    assert lons_retro, "no Saturn retrograde segment found in year"
    return 0.5 * (min(lons_retro) + max(lons_retro))


def _saturn_crossings(L: float, jd_start: float, days: int) -> list[float]:
    """JDs at which Saturn crosses longitude L (either direction) after jd_start."""
    out, prev = [], None
    for d in range(days + 1):
        jd = jd_start + d
        xx, _ = swe.calc_ut(jd, swe.SATURN, EPHE_FLAG)
        f = _signed180((xx[0] % 360.0) - L)
        if prev is not None and (prev[0] < 0) != (f < 0) and abs(prev[0]) + abs(f) < 180:
            out.append(0.5 * (prev[1] + jd))     # ~day precision is plenty here
        prev = (f, jd)
    return out


def _natal_with_triple_target(year: int):
    """A real Istanbul natal chart with one point relocated onto Saturn's retro
    band (so Saturn conjuncts it three times), plus a target_date whose 1-year
    window brackets all three crossings. Returns (natal, L, target_date)."""
    natal = _natal_exact_ist()
    L = _saturn_retro_longitude(year)
    for p in natal["points"]:            # Mars: a plain planet target, not an angle
        if p["name"] == "Mars":
            p["longitude"] = round(L, 4)
    # Find the first cluster of three crossings and start the window 15 days before
    # the first so the whole ~7-month retrograde loop falls inside one year.
    crossings = _saturn_crossings(L, swe.julday(year, 1, 1, 0.0), 900)
    assert len(crossings) >= 3, f"expected >=3 Saturn crossings of {L}, got {len(crossings)}"
    first3 = crossings[:3]
    assert first3[2] - first3[0] < 350, "three crossings do not fit in a year"
    y, mo, d, _h = swe.revjul(first3[0] - 15, swe.GREG_CAL)
    target = f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    return natal, L, target


# ===========================================================================
# The fixture set actually exercised by the schema + invariant tests
# ===========================================================================
def _fixtures() -> dict[str, dict]:
    triple_natal, _, triple_target = _natal_with_triple_target(2026)
    return {
        "exact_day": _fc(_natal_exact_ist(), "2026-07-01", "day",
                         latitude=_IST["latitude"], longitude=_IST["longitude"]),
        "exact_month": _fc(_natal_exact_ist(), "2026-07-01", "month",
                           latitude=_IST["latitude"], longitude=_IST["longitude"]),
        "exact_year": _fc(_natal_exact_ist(), "2026-01-01", "year"),
        "approx_month": _fc(_natal_approx_ist(), "2026-07-01", "month"),
        "unknown_month": _fc(_natal_unknown_ist(), "2026-07-01", "month"),
        "circumpolar_month": _fc(_natal_circumpolar(), "2026-07-01", "month"),
        "dst_month": _fc(_natal_nyc(), "2026-03-01", "month"),
        "triple_year": _fc(triple_natal, triple_target, "year"),
    }


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _load_validator() -> Draft202012Validator:
    with open(_SCHEMA_PATH, encoding="utf-8") as fh:
        schema = json.load(fh)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _parse(dt: str) -> datetime:
    return datetime.fromisoformat(dt)


# ===========================================================================
# SCHEMA CONFORMANCE
# ===========================================================================
def test_all_fixtures_validate() -> None:
    v = _load_validator()
    for kind, fc in _fixtures().items():
        errors = sorted(v.iter_errors(fc), key=lambda e: list(e.path))
        assert not errors, (
            f"[{kind}] failed schema validation:\n"
            + "\n".join(f"  - {e.json_path}: {e.message}" for e in errors))


# ===========================================================================
# SPEC §13 INVARIANTS
# ===========================================================================
def test_inv1_events_within_window() -> None:
    for kind, fc in _fixtures().items():
        start, end = _parse(fc["window"]["start"]), _parse(fc["window"]["end"])
        for e in fc["events"]:
            dt = _parse(e["datetime"])
            assert start <= dt < end, f"[{kind}] {e['event_id']} {dt} outside window"


def test_inv2_year_excludes_moon_and_ordinary_lunations() -> None:
    for kind in ("exact_year", "triple_year"):
        fc = _fixtures()[kind]
        for e in fc["events"]:
            # No Moon as a transiting body (transit/ingress noise).
            if e["family"] in ("transit_aspect", "ingress_sign", "ingress_house"):
                assert e["bodies"]["transiting"] != "Moon", \
                    f"[{kind}] Moon transiting event leaked into YEAR"
            # No ordinary lunations — eclipses only.
            assert e["family"] != "lunation", \
                f"[{kind}] ordinary lunation leaked into YEAR"


def test_inv3_day_no_separating_or_standing() -> None:
    fc = _fixtures()["exact_day"]
    for e in fc["events"]:
        assert e["phase"] != "separating", f"DAY has separating event {e['event_id']}"
        assert e["standing"] is False, f"DAY has standing event {e['event_id']}"


def test_inv4_transit_aspects_have_phase_and_stage() -> None:
    for kind, fc in _fixtures().items():
        for e in fc["events"]:
            if e["family"] == "transit_aspect":
                assert e["phase"] is not None, f"[{kind}] null phase"
                assert e["cycle_stage"] in range(1, 9), f"[{kind}] bad cycle_stage"


def test_inv5_day_has_rulers_month_year_do_not() -> None:
    fx = _fixtures()
    assert "rulers" in fx["exact_day"]
    assert fx["exact_day"]["rulers"]["planetary_day"] is not None
    for kind in ("exact_month", "exact_year"):
        assert "rulers" not in fx[kind], f"[{kind}] must not carry rulers"


def test_inv6_low_precision_suppresses_house_and_angle() -> None:
    fc = _fixtures()["unknown_month"]
    assert fc["meta"]["degraded"] is True
    assert fc["meta"]["suppressed_families"]
    for e in fc["events"]:
        assert e["family"] != "ingress_house", "house ingress under unknown tier"
        # no angle-target aspects (natal target would be an angle name)
        if e["family"] == "transit_aspect":
            assert e["bodies"]["natal"] not in ("Ascendant", "MC", "Descendant", "IC")
        # lunations carry no house under unknown tier
        if e["family"] in ("lunation", "eclipse"):
            assert e["house_placidus"] is None and e["house_wholesign"] is None


def test_inv7_determinism_byte_identical() -> None:
    a = _fc(_natal_exact_ist(), "2026-07-01", "month",
            latitude=_IST["latitude"], longitude=_IST["longitude"])
    b = _fc(_natal_exact_ist(), "2026-07-01", "month",
            latitude=_IST["latitude"], longitude=_IST["longitude"])
    ha = hashlib.sha256(json.dumps(a, sort_keys=True).encode()).hexdigest()
    hb = hashlib.sha256(json.dumps(b, sort_keys=True).encode()).hexdigest()
    assert ha == hb, "identical inputs produced different output"


def test_inv8_grounding_kind_allowed_and_other_has_tags() -> None:
    for kind, fc in _fixtures().items():
        for e in fc["events"]:
            g = e["grounding"]
            assert g["kind"] in GROUNDING_KINDS, f"[{kind}] bad kind {g['kind']}"
            if g["kind"] == "other":
                assert len(g["topic_tags"]) >= 1, f"[{kind}] 'other' with no tags"


def test_inv9_counts_reconcile() -> None:
    for kind, fc in _fixtures().items():
        n = len(fc["events"])
        assert sum(fc["counts"]["by_family"].values()) == n, f"[{kind}] family count"
        assert sum(fc["counts"]["by_segment"].values()) == n, f"[{kind}] segment count"


def test_inv10_retrograde_triple_perfection() -> None:
    natal, L, target = _natal_with_triple_target(2026)
    fc = _fc(natal, target, "year")
    perfs = [e for e in fc["events"]
             if e["family"] == "transit_aspect"
             and e["bodies"]["transiting"] == "Saturn"
             and e["bodies"]["natal"] == "Mars"
             and e["aspect"] == "conjunction"
             and not e["standing"]]
    assert len(perfs) == 3, (
        f"expected 3 Saturn-conjunct-natal-Mars perfections, got {len(perfs)} "
        f"(natal Mars at {L:.3f}deg)")


def test_eclipse_present_in_year() -> None:
    fc = _fixtures()["exact_year"]
    eclipses = [e for e in fc["events"] if e["family"] == "eclipse"]
    assert eclipses, "2026 year run should contain at least one eclipse"


def test_window_tz_current_location() -> None:
    """CAL_00 §6: a DAY forecast anchored in the current-location tz. Istanbul vs Tokyo
    cover different UTC windows for the same calendar date; the default (no window_tz)
    is still the birth tz."""
    natal = _natal_exact_ist()
    ist = _fc(natal, "2026-10-10", "day", window_tz="Europe/Istanbul")
    tyo = _fc(natal, "2026-10-10", "day", window_tz="Asia/Tokyo")
    utc = lambda s: _parse(s).astimezone(timezone.utc)  # noqa: E731
    assert utc(ist["window"]["start"]).isoformat() == "2026-10-09T21:00:00+00:00"
    assert utc(tyo["window"]["start"]).isoformat() == "2026-10-09T15:00:00+00:00"
    assert utc(ist["window"]["end"]) != utc(tyo["window"]["end"])
    assert (ist["window"]["tz"], tyo["window"]["tz"]) == ("Europe/Istanbul", "Asia/Tokyo")
    default = _fc(natal, "2026-10-10", "day")
    assert default["window"]["tz"] == natal["meta"]["timezone"]


def test_circumpolar_house_ingress_placidus_null() -> None:
    fc = _fixtures()["circumpolar_month"]
    # Placidus is undefined at Svalbard; any house ingress must fall back to
    # whole-sign (placidus null, whole-sign an int).
    for e in fc["events"]:
        if e["family"] == "ingress_house":
            assert e["house_placidus"] is None
            assert isinstance(e["house_wholesign"], int)


# ===========================================================================
# REPORT (SPEC §15)
# ===========================================================================
def _write_report() -> dict:
    fx = _fixtures()
    v = _load_validator()
    report: dict = {"fixtures": {}, "invariants": {}}
    for kind, fc in fx.items():
        report["fixtures"][kind] = {
            "events": len(fc["events"]),
            "by_family": fc["counts"]["by_family"],
            "by_segment": fc["counts"]["by_segment"],
            "degraded": fc["meta"]["degraded"],
            "schema_ok": not list(v.iter_errors(fc)),
        }
    checks = [
        ("inv1_events_within_window", test_inv1_events_within_window),
        ("inv2_year_excludes_moon", test_inv2_year_excludes_moon_and_ordinary_lunations),
        ("inv3_day_no_separating", test_inv3_day_no_separating_or_standing),
        ("inv4_phase_and_stage", test_inv4_transit_aspects_have_phase_and_stage),
        ("inv5_day_rulers", test_inv5_day_has_rulers_month_year_do_not),
        ("inv6_low_precision", test_inv6_low_precision_suppresses_house_and_angle),
        ("inv7_determinism", test_inv7_determinism_byte_identical),
        ("inv8_grounding_kinds", test_inv8_grounding_kind_allowed_and_other_has_tags),
        ("inv9_counts", test_inv9_counts_reconcile),
        ("inv10_retro_triple", test_inv10_retrograde_triple_perfection),
        ("eclipse_in_year", test_eclipse_present_in_year),
        ("circumpolar_placidus_null", test_circumpolar_house_ingress_placidus_null),
        ("schema_validate", test_all_fixtures_validate),
    ]
    for name, fn in checks:
        try:
            fn()
            report["invariants"][name] = "PASS"
        except AssertionError as exc:
            report["invariants"][name] = f"FAIL: {exc}"
    with open(os.path.join(_HERE, "forecast_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return report


if __name__ == "__main__":
    rep = _write_report()
    print("Fixtures:")
    for k, v in rep["fixtures"].items():
        print(f"  {k:20s} events={v['events']:4d} schema={'ok' if v['schema_ok'] else 'FAIL'} "
              f"by_family={v['by_family']}")
    print("Invariants:")
    ok = True
    for k, r in rep["invariants"].items():
        print(f"  {'OK  ' if r == 'PASS' else 'FAIL'} {k}: {r if r != 'PASS' else ''}")
        ok = ok and r == "PASS"
    print("\nWrote forecast_report.json")
    raise SystemExit(0 if ok else 1)
