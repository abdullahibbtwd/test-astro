#!/usr/bin/env python3
"""
test_forecast_reading.py — offline tests for the predictive reading layer (no API key).

Covers the PREDICTIVE_READING_SPEC §11 invariants deterministically, plus the sparse path
(§9) and the profile reframe plumbing (§3), end-to-end through an injected fake generator
that emits clean Turkish-length filler so the structure/lint/word-count logic is exercised
without a model.

Run:  python test_forecast_reading.py        (or: pytest test_forecast_reading.py)
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pr_events import (
    HORIZON_KEYS, astro_descriptor, grounded_event_count, is_sparse, serialize_event,
)
from pr_profiles import get_profile
from pr_validate import (
    ValidationContext, find_modern, find_planet_mentions, find_tech, find_tier_a,
    validate, word_count,
)
from read_forecast import run_reading

# ---------------------------------------------------------------------------
# Fixture builders — a "grounded forecast": compute_forecast shape + matched_principles.
# ---------------------------------------------------------------------------
_FILLER = ["bugün", "dönem", "içsel", "duygu", "sabır", "adım", "denge", "zaman",
           "yakınlık", "emek", "umut", "huzur", "güven", "akış", "yön", "ışık",
           "değişim", "destek", "uyum", "olgunluk", "netlik", "cesaret"]


def _words(n: int, *, extra: str = "") -> str:
    body = " ".join(_FILLER[i % len(_FILLER)] for i in range(max(n, 1)))
    return (extra + " " + body).strip() if extra else body


def _ev(family, segment, *, natal=None, transiting="Saturn", house=None,
        aspect="square", phase="applying", dignity=None, judgment="bir tema",
        speed="slow", standing=False):
    return {
        "event_id": f"{family}-{segment}-{natal or transiting}",
        "family": family, "segment": segment, "standing": standing,
        "bodies": {"transiting": transiting, "natal": natal},
        "aspect": aspect if family == "transit_aspect" else None,
        "phase": phase if family == "transit_aspect" else None,
        "cycle_stage": 3 if family == "transit_aspect" else None,
        "speed_class": speed,
        "house_placidus": house, "house_wholesign": house,
        "sign": "Aries", "dignity": dignity,
        "grounding": {"kind": "point_aspects", "topic_tags": ["full moon"]
                      if family in ("lunation", "eclipse") else ["transit"]},
        "matched_principles": [{"principle_id": "p1", "judgment": judgment}],
    }


def _forecast(horizon, events, *, target="2026-07-01",
              start="2026-07-01T00:00:00+03:00", end="2026-08-01T00:00:00+03:00"):
    return {
        "meta": {"horizon": horizon, "target_date": target,
                 "natal_ref": "sha256:deadbeef", "run_id": "20260708-000000_abc"},
        "window": {"start": start, "end": end, "tz": "Europe/Istanbul"},
        "events": events,
        "counts": {"by_family": {}, "by_segment": {}},
    }


def _month_forecast():
    dig_strong = {"transiting": None, "natal": {"in_domicile": True, "in_detriment": False,
                  "in_exaltation": False, "in_fall": False, "sign": "Cancer", "sign_ruler": "Moon"}}
    return _forecast("month", [
        _ev("transit_aspect", "early", natal="Moon", house=4, judgment="yakın bağlar sınanır", dignity=dig_strong),
        _ev("transit_aspect", "early", natal="Sun", house=10, judgment="sorumluluk artar"),
        _ev("transit_aspect", "mid", natal="Venus", house=7, aspect="trine", phase="perfecting",
            transiting="Jupiter", judgment="ilişkilerde açılım gelir"),
        _ev("ingress_house", "mid", natal=None, transiting="Mars", house=6, judgment="günlük düzen değişir"),
        _ev("lunation", "late", natal=None, transiting=None, house=4, judgment="bir şey doruğa ulaşır"),
        _ev("transit_aspect", "late", natal="Mercury", house=3, aspect="sextile", judgment="iletişim kolaylaşır"),
    ])


def _year_forecast():
    evs = []
    for q in ("q1", "q2", "q3", "q4"):
        evs.append(_ev("transit_aspect", q, natal="Sun", house=10, judgment="yapı kurulur"))
        evs.append(_ev("transit_aspect", q, natal="Venus", house=7, aspect="trine", judgment="destek gelir"))
    evs.append(_ev("eclipse", "q3", natal=None, transiting=None, house=1, judgment="yeni bir döngü başlar"))
    return _forecast("year", evs, end="2027-07-01T00:00:00+03:00")


def _day_forecast():
    return _forecast("day", [
        _ev("transit_aspect", None, natal="Moon", house=4, judgment="duygusal ton belirginleşir"),
        _ev("transit_aspect", None, natal="Mars", house=1, aspect="trine", judgment="enerji akar"),
    ], end="2026-07-02T00:00:00+03:00")


def _sparse_month_forecast():
    return _forecast("month", [
        _ev("transit_aspect", "mid", natal="Saturn", house=10, judgment="tek sakin tema"),
    ])


# ---------------------------------------------------------------------------
# Fake generator: emits clean Turkish-length filler that hits the requested range.
# ---------------------------------------------------------------------------
_RANGE_RES = [re.compile(r"(\d+)\s*[–-]\s*(\d+)\s*words"),
              re.compile(r"between\s+(\d+)\s+and\s+(\d+)\s+words")]


def _target_n(user: str) -> int:
    for rx in _RANGE_RES:
        m = rx.search(user)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            return (lo + hi) // 2
    return 60


def _profile_of(user: str) -> str:
    m = re.search(r"PROFILE:\s*(\w+)", user)
    return m.group(1) if m else "general"


class FakeGenerator:
    """Echoes correctly-sized, lint-clean sections. Injects a domain keyword into the
    focus paragraph for non-general profiles so §11.4 passes."""

    def day(self, user):
        return {"reading": _words(_target_n(user))}

    def beat(self, user, label):
        return _words(_target_n(user))

    def beats(self, jobs):
        return {key: self.beat(user, key) for key, user in jobs}

    def synthesize(self, user):
        n = _target_n(user)
        prof = _profile_of(user)
        kw = {"personal": "ilişki ve ev", "professional": "iş ve para"}.get(prof, "")
        return {"overview": _words(n), "focus": _words(n, extra=kw)}

    def reask(self, user, key):
        return _words(_target_n(user))


def _run(forecast, profile="general", **kw):
    return run_reading(forecast, reading_type=profile, generator=FakeGenerator(), **kw)


# ===========================================================================
# §11.1 — exact key set
# ===========================================================================
def test_inv1_exact_keyset_all_horizons():
    for fc, prof in ((_day_forecast(), "general"), (_month_forecast(), "personal"),
                     (_year_forecast(), "professional")):
        reading, errors, _ = _run(fc, prof)
        horizon = fc["meta"]["horizon"]
        assert set(reading.keys()) == set(HORIZON_KEYS[horizon]) | {"meta"}, \
            f"{horizon}/{prof}: keyset {set(reading.keys())}"
        assert not errors, f"{horizon}/{prof}: {errors}"


# ===========================================================================
# §11.2 — Tier-A (build-blocking) and Tier-B mask lint
# ===========================================================================
def test_inv2_tier_a_catches_classical_terms():
    assert find_tier_a("bu dönem senin profection yılın")      # profection
    assert find_tier_a("the Part of Fortune is strong")         # lot
    assert find_tier_a("triplicity ruler devrede")              # triplicity
    assert not find_tier_a("bu ay ilişkilerde bir açılım var")  # clean


def test_inv2_modern_and_tech_buckets():
    # MODERN bucket: aspect names, transit-driver phrasing (un-banned at modern+).
    assert find_modern("a square to your natal Sun")            # geometry + context
    assert find_modern("bu bir kavuşum dönemi")                 # conjunction (tr)
    assert find_modern("Mercury retrograde again")              # retrograde
    # TECH bucket: house numbers, phase machinery (un-banned only at technical).
    assert find_tech("your 10th house lights up")               # house number
    assert find_tech("an applying aspect builds")               # phase
    # both clean on ordinary prose
    assert not find_modern("bu ay evde huzur artıyor")
    assert not find_tech("bu ay evde huzur artıyor")


def test_astro_detail_levels():
    """The lint un-bans a bucket at the right level (plain → modern → technical)."""
    base, _, _ = _run(_month_forecast(), "general")   # modern, already valid
    prof = get_profile("general")

    def overview_errs(extra: str, detail: str) -> list[str]:
        r = dict(base)
        r["overview"] = base["overview"] + " " + extra
        ctx = ValidationContext(horizon="month", profile=prof, astro_detail=detail)
        return [e for e in validate(r, ctx) if "'overview'" in e]

    # aspect name: banned at plain, allowed from modern up
    assert any("MODERN" in e for e in overview_errs("bir kavuşum var", "plain"))
    assert not any("§11.2" in e for e in overview_errs("bir kavuşum var", "modern"))
    # classical term: build-blocking at modern, allowed only at technical
    assert any("TIER-A" in e for e in overview_errs("profection yılı", "modern"))
    assert not any("§11.2" in e for e in overview_errs("profection yılı", "technical"))
    # house number: banned at modern, allowed at technical
    assert any("TECH" in e for e in overview_errs("10. ev vurgulu", "modern"))
    assert not any("§11.2" in e for e in overview_errs("10. ev vurgulu", "technical"))


def test_astro_descriptor_in_serialization():
    e = _ev("transit_aspect", "early", natal="Venus", house=7, aspect="trine",
            transiting="Jupiter", judgment="ilişkide açılım")
    assert "[Jupiter trine natal Venus" in serialize_event(e, astro_detail="modern")
    assert "house 7" in astro_descriptor(e, "technical")       # numbered only at technical
    assert astro_descriptor(e, "plain") == ""                  # nothing surfaced when plain
    assert "[" not in serialize_event(e, astro_detail="plain")


# ===========================================================================
# §11.3 — word counts within tolerance
# ===========================================================================
def test_inv3_word_counts_in_range():
    reading, errors, _ = _run(_year_forecast(), "professional")
    assert not any("§11.3" in e for e in errors), errors


# ===========================================================================
# §11.4 — focus present & on-domain for non-general
# ===========================================================================
def test_inv4_focus_on_domain():
    reading, errors, _ = _run(_month_forecast(), "personal")
    assert reading["focus"].strip()
    assert not any("§11.4" in e for e in errors), errors
    # negative: strip the domain keyword -> §11.4 fires
    reading["focus"] = "bu ay genel bir sakinlik ve akış hâkim olacak gibi görünüyor"
    ctx = ValidationContext(horizon="month", profile=get_profile("personal"))
    assert any("§11.4" in e for e in validate(reading, ctx))


# ===========================================================================
# §11.5 — no fabricated planet / date
# ===========================================================================
def test_inv5_planet_and_date_leaks():
    reading, _, _ = _run(_month_forecast(), "general")
    # Neptune is not a target in the month fixture -> flagged when surfacing is ON.
    reading["overview"] += " Neptune araya giriyor ve 2019 yılına dönüyoruz"
    ctx = ValidationContext(horizon="month", profile=get_profile("general"),
                            surface_planets=True, allowed_planets={"Sun", "Moon", "Venus",
                            "Mercury"}, allowed_years={2026})
    errs = validate(reading, ctx)
    assert any("Neptune" in e for e in errs)
    assert any("2019" in e for e in errs)


def test_inv5_surface_off_bans_all_planets():
    ctx = ValidationContext(horizon="day", profile=get_profile("general"),
                            surface_planets=False, allowed_years={2026})
    reading = {"reading": _words(140) + " Mars güçleniyor", "meta": {}}
    assert any("surface_planets is OFF" in e for e in validate(reading, ctx))


# ===========================================================================
# §9 / §11.6 — sparse path
# ===========================================================================
def test_inv6_sparse_flag_and_floor():
    fc = _sparse_month_forecast()
    prof = get_profile("general")
    assert is_sparse(fc["events"], prof, "month")
    reading, errors, report = _run(fc, "general")
    assert reading["meta"]["sparse"] is True
    assert report["sparse"] is True
    # Fake still emits mid-range text, which must satisfy the (looser) sparse floor.
    assert not any("§11.3" in e for e in errors), errors


def test_grounded_count_and_material_filter():
    fc = _month_forecast()
    # add an UNgrounded event (no matched principle) -> must not count / surface
    fc["events"].append({**_ev("transit_aspect", "mid", natal="Pluto", house=8),
                         "matched_principles": []})
    prof = get_profile("general")
    assert grounded_event_count(fc["events"], prof) == 6   # the ungrounded one excluded


# ===========================================================================
# §3 — profile emphasis actually reorders the block
# ===========================================================================
def test_profile_emphasis_orders_lead_first():
    from pr_events import events_block
    fc = _month_forecast()
    personal = get_profile("personal")
    block = events_block(fc["events"], personal, segment="early")
    # early has a Moon(house 4, lead for personal) and a Sun(house 10, not lead) event;
    # the personal-lead Moon line must come first.
    first = block.splitlines()[0]
    assert "home and family" in first or "feeling" in first, block


def test_serialize_event_shape():
    e = _ev("transit_aspect", "early", natal="Venus", house=7, aspect="trine",
            phase="perfecting", judgment="x")
    line = serialize_event(e)
    assert line.startswith("- (early)")
    assert "close relationships" in line and "meaning:" in line


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"OK   {fn.__name__}")
            passed += 1
        except AssertionError as exc:
            print(f"FAIL {fn.__name__}: {exc}")
    print(f"\n{passed}/{len(fns)} passed")
    raise SystemExit(0 if passed == len(fns) else 1)
