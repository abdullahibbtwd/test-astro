#!/usr/bin/env python3
"""
test_l4.py — tests for the deterministic core of Layer 4 (routing §3, validation
§7, assembly §6, render) plus an end-to-end run against a synthetic chart.

The generation calls (§4/§5) are model-driven and not unit-tested here; an
injected FakeGenerator exercises the assembly + contract-validation plumbing
without an API. The chart is synthetic (no personal data): Scorpio rising, so
the chart has both a traditional ruler (Mars) and a modern co-ruler (Pluto); the
Sun straddles a cusp so its Placidus (9) and whole-sign (8) houses differ.

Run:  python -m pytest test_l4.py -q
"""

from __future__ import annotations

import json
import os

import pytest

from l4_generate import SectionDraft
from l4_interpret import _assemble, _ground_source, interpret, load_personal
from l4_render import render, section_title
from l4_routing import (
    chart_ruler,
    chart_rulers,
    domain_section_for_house,
    house_of,
    houses_ruled,
    route,
    section_for_point,
    section_houses,
)
from l4_sections import (
    HOUSE_DOMAIN, MOVEMENT, MOVEMENT_1, MOVEMENT_2, SECTION_HOUSE, SECTION_ORDER,
    RoutedPrinciple,
)
from l4_validate import PRECISION_TIER, SCHEMA_VERSION, validate

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
_PERSONAL = os.path.join(_PARENT, "principles_grounding", "personal_principles.json")
_CORPUS = os.path.join(_HERE, "all_principles.grounded.json")


# ---------------------------------------------------------------------------
# Synthetic chart fixture
# ---------------------------------------------------------------------------

_POINTS = [  # name, sign, placidus house, whole-sign house
    ("Sun", "Gemini", 9, 8),
    ("Moon", "Pisces", 5, 5),
    ("Mercury", "Gemini", 8, 8),
    ("Venus", "Taurus", 7, 7),
    ("Mars", "Aries", 6, 6),
    ("Jupiter", "Cancer", 9, 9),
    ("Saturn", "Capricorn", 3, 3),
    ("Uranus", "Capricorn", 3, 3),
    ("Neptune", "Capricorn", 3, 3),
    ("Pluto", "Scorpio", 1, 1),
    ("North Node", "Aquarius", 4, 4),
    ("South Node", "Leo", 10, 10),
]
_CUSP_SIGNS = ["Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces", "Aries",
               "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra"]
_RULER = {"Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon",
          "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars",
          "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn",
          "Pisces": "Jupiter"}
_MODERN = {**_RULER, "Scorpio": "Pluto", "Aquarius": "Uranus", "Pisces": "Neptune"}


def _synthetic_chart() -> dict:
    pts = {n: {"name": n, "sign": sg, "traditional": n not in ("Uranus", "Neptune", "Pluto"),
               "sector": {"placidus": pl, "whole_sign": ws}, "classifications": None,
               "degree_in_sign": 10.0, "retrograde": False}
           for n, sg, pl, ws in _POINTS}

    def rulers(system):
        out = {}
        for i, sign in enumerate(_CUSP_SIGNS):
            r, m = _RULER[sign], _MODERN[sign]
            out[str(i + 1)] = {
                "sign_on_cusp": sign, "ruler": r, "ruler_sign": pts[r]["sign"],
                "ruler_sector": pts[r]["sector"][system],
                "modern_ruler": m, "modern_ruler_sign": pts[m]["sign"],
                "modern_ruler_sector": pts[m]["sector"][system]}
        return out

    return {
        "confidence": "exact",
        "points": list(pts.values()),
        "axes": {"ascendant": {"sign": "Scorpio", "degree_in_sign": 12.0},
                 "mc": {"sign": "Leo", "degree_in_sign": 20.0}},
        "is_diurnal": True,
        "derived_points": {"fortune": {"sign": "Aries", "degree_in_sign": 1.0},
                           "spirit": {"sign": "Leo", "degree_in_sign": 1.0}},
        "sector_rulers": {"placidus": rulers("placidus"), "whole_sign": rulers("whole_sign")},
        "relations": [{"source": "Venus", "target": "Mars", "type": "trine",
                       "scheme": "modern", "orb": 1.2, "applying": True}],
    }


@pytest.fixture(scope="module")
def chart() -> dict:
    return _synthetic_chart()


@pytest.fixture(scope="module")
def kept(chart) -> list[dict]:
    # §1 Input 2 via the fallback path: ground the real corpus against the
    # synthetic chart (Placidus policy).
    with open(_CORPUS, encoding="utf-8") as fh:
        source = json.load(fh)
    return _ground_source(source, chart, "natal")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _principle(pid: str, factor_type: str, **about) -> dict:
    about = {"factor_type": factor_type,
             "extraction_confidence": about.pop("confidence", "high"),
             "extraction_source": "deterministic", **about}
    return {"principle_id": pid, "tradition": about.pop("tradition", "modern"),
            "rule": "r", "topic_tags": [], "about": about, "requires": []}


def _general(pid, tags, conf="low"):
    return {
        "principle_id": pid, "tradition": "modern", "rule": "r",
        "topic_tags": tags,
        "about": {"factor_type": "general", "extraction_confidence": conf,
                  "extraction_source": "deterministic"},
        "requires": []}


def _routed_pids(res, key) -> set[str]:
    return {rp.principle_id for rp in res.sections.get(key, [])}


def _sections_of(res, pid) -> set[str]:
    return {k for k, lst in res.sections.items() if any(rp.principle_id == pid for rp in lst)}


def _texture(res, key, pid):
    for rp in res.sections.get(key, []):
        if rp.principle_id == pid:
            return rp.texture
    return "<absent>"


def _salience(res, key, pid):
    for rp in res.sections.get(key, []):
        if rp.principle_id == pid:
            return rp.salience
    return "<absent>"


class FakeGenerator:
    """Test double for the LLM runner. Returns canned, contract-valid drafts so
    the assembly + validation plumbing can be tested without an API."""

    def __init__(self):
        self.synth_low_salience = None

    def section_all(self, routed_by_section, chart):
        return [
            SectionDraft(key=key, text_tr=f"{key}: " + " ".join(
                f"dayanak {i}." for i in range(1, len(routed) + 1)) or key)
            for key, routed in routed_by_section.items()
        ]

    def synthesize(self, drafts, chart, low_salience_ids=None):
        self.synth_low_salience = low_salience_ids
        return [{"key": d.key, "text_tr": d.text_tr,
                 "text_en": d.text_tr.replace("dayanak", "basis")}
                for d in drafts]


# ---------------------------------------------------------------------------
# §2 section model
# ---------------------------------------------------------------------------

def test_section_order_and_movements():
    assert SECTION_ORDER == MOVEMENT_1 + MOVEMENT_2
    assert len(SECTION_ORDER) == 17 and len(set(SECTION_ORDER)) == 17
    assert MOVEMENT_1[:3] == ["core_identity", "sun_house", "moon_house"]
    assert all(MOVEMENT[k] == 1 for k in MOVEMENT_1)
    assert all(MOVEMENT[k] == 2 for k in MOVEMENT_2)


def test_one_section_per_house():
    assert sorted(HOUSE_DOMAIN) == list(range(1, 13))
    assert len(set(HOUSE_DOMAIN.values())) == 12            # no paired houses
    assert [HOUSE_DOMAIN[h] for h in range(1, 13)] == MOVEMENT_2   # house order
    assert SECTION_HOUSE["identity"] == 1
    assert SECTION_HOUSE["subconscious_solitude"] == 12
    assert domain_section_for_house(2) == "values_money"
    assert domain_section_for_house(8) == "transformation_intimacy"
    assert domain_section_for_house(6) == "health_routine_pets"
    assert domain_section_for_house(10) == "status_vocation"


# ---------------------------------------------------------------------------
# §3.0 chart helpers
# ---------------------------------------------------------------------------

def test_chart_rulers_include_modern_co_ruler(chart):
    assert chart_ruler(chart) == "Mars"                 # traditional 1st-house ruler
    assert chart_rulers(chart) == {"Mars", "Pluto"}     # + modern co-ruler of Scorpio


def test_house_of_uses_placidus(chart):
    pts = {p["name"]: p for p in chart["points"]}
    assert house_of("Sun", pts) == 9      # placidus 9, NOT whole-sign 8
    assert house_of("Moon", pts) == 5


def test_houses_ruled_includes_modern_ruler(chart):
    assert houses_ruled("Mars", chart) == [1, 6]
    assert houses_ruled("Pluto", chart) == [1]          # modern co-ruler of Scorpio cusp
    assert houses_ruled("Saturn", chart) == [3, 4]
    assert houses_ruled("Uranus", chart) == [4]         # modern co-ruler of Aquarius cusp
    assert houses_ruled("Neptune", chart) == [5]
    assert houses_ruled("Jupiter", chart) == [2, 5]


def test_section_for_point_dual_homes(chart):
    assert section_for_point("Mars", chart) == {"inner_drives", "core_identity"}
    assert section_for_point("Pluto", chart) == {"chart_shape", "core_identity"}
    assert section_for_point("Sun", chart) == {"core_identity"}
    assert section_for_point("Saturn", chart) == {"chart_shape"}


def test_section_houses_map(chart):
    hs = section_houses(chart)
    assert hs["sun_house"] == 9 and hs["moon_house"] == 5
    assert hs["identity"] == 1 and hs["subconscious_solitude"] == 12
    assert "core_identity" not in hs


# ---------------------------------------------------------------------------
# §3.1 routing rules (synthetic, isolated)
# ---------------------------------------------------------------------------

def test_planet_in_sign_routes_to_point_home(chart):
    res = route([_principle("p", "planet_in_sign", point="Sun", sign="Gemini")], chart)
    # + occupancy (Sun in H9) + rulership (Sun rules the Leo cusp of H10)
    assert _sections_of(res, "p") == {"core_identity", "travel_philosophy", "status_vocation"}


def test_sun_house_record_feeds_luminary_note_not_core(chart):
    # Declared whole_sign: irrelevant — grounding verified the house in Placidus.
    rec = _principle("s9", "planet_in_house", point="Sun", house=9,
                     house_system="whole_sign", tradition="traditional")
    res = route([rec], chart)
    assert "s9" in _routed_pids(res, "sun_house")
    assert "s9" in _routed_pids(res, "travel_philosophy")     # H9 section
    assert "s9" not in _routed_pids(res, "core_identity")
    assert _texture(res, "sun_house", "s9") is None            # no whole-sign texture
    assert _texture(res, "travel_philosophy", "s9") is None


def test_moon_house_record_feeds_moon_note(chart):
    rec = _principle("m5", "planet_in_house", point="Moon", house=5, house_system="placidus")
    res = route([rec], chart)
    # luminary note + occupied H5 + the Cancer cusp of H9 the Moon rules
    assert _sections_of(res, "m5") == {"moon_house", "joy_creativity_children",
                                       "travel_philosophy"}


def test_planet_in_house_non_luminary(chart):
    rec = _principle("pl", "planet_in_house", point="Mars", house=6,
                     house_system="whole_sign")
    res = route([rec], chart)
    # point home, occupied house, and the houses Mars rules (1 and 6)
    assert _sections_of(res, "pl") == {"inner_drives", "core_identity",
                                       "health_routine_pets", "identity"}
    assert _texture(res, "health_routine_pets", "pl") is None


def test_house_domain_grounds_luminary_notes(chart):
    h9 = _principle("h9", "house_domain", house=9, house_system="placidus")
    h5 = _principle("h5", "house_domain", house=5, house_system="placidus")
    h2 = _principle("h2", "house_domain", house=2, house_system="placidus")
    res = route([h9, h5, h2], chart)
    assert _sections_of(res, "h9") == {"travel_philosophy", "sun_house"}
    assert _sections_of(res, "h5") == {"joy_creativity_children", "moon_house"}
    assert _sections_of(res, "h2") == {"values_money"}


def test_house_domain_point_is_movement_one(chart):
    res = route([_principle("hp", "house_domain", point="Mars")], chart)
    assert "hp" in _routed_pids(res, "inner_drives")


def test_dignity_is_classical_everywhere(chart):
    rec = _principle("d", "dignity", point="Saturn", dignity="domicile")
    res = route([rec], chart)
    assert _texture(res, "chart_shape", "d") == "classical"           # point home
    assert _texture(res, "communication_learning", "d") == "classical"  # occupies H3
    assert _texture(res, "family_home", "d") == "classical"           # rules H4


def test_house_lord_relative_routes_to_subject_house(chart):
    rec = _principle("lr", "house_lord_relative", subject_house=1,
                     subject_house_system="whole_sign", placement_house=6,
                     placement_house_system="whole_sign")
    res = route([rec], chart)
    assert _texture(res, "identity", "lr") == "classical"   # subject_house=1
    assert "lr" not in _routed_pids(res, "health_routine_pets")   # not placement


def test_aspect_routes_endpoints_and_chart_shape(chart):
    rec = _principle("a", "aspect",
                     aspect={"source": "Venus", "target": "Mars", "type": "trine"})
    res = route([rec], chart)
    assert "a" in _routed_pids(res, "inner_drives")      # both endpoints personal
    assert "a" in _routed_pids(res, "chart_shape")       # configuration
    assert "a" in _routed_pids(res, "partnerships")      # Venus occupies H7
    assert "a" in _routed_pids(res, "health_routine_pets")   # Mars occupies H6


def test_ascendant_routes_to_core_and_house_one(chart):
    res = route([_principle("asc", "ascendant", ascendant_sign="Scorpio")], chart)
    assert _sections_of(res, "asc") == {"core_identity", "identity"}


def test_node_with_house(chart):
    rec = _principle("nn", "node", point="North Node", house=4, house_system="whole_sign")
    res = route([rec], chart)
    assert _sections_of(res, "nn") == {"chart_shape", "family_home"}
    assert _texture(res, "family_home", "nn") is None


# --- §3.1.11 general ladder ---

def test_general_chart_ruler_to_core_identity(chart):
    res = route([_general("g", ["ascendant ruler", "chart ruler", "vocation"])], chart)
    assert _sections_of(res, "g") == {"core_identity"}


def test_general_mc_to_status_vocation(chart):
    res = route([_general("g", ["Midheaven", "MC ruler", "career"])], chart)
    assert _sections_of(res, "g") == {"status_vocation"}


def test_general_house_lord_to_house_section(chart):
    res = route([_general("g", ["lord of 2nd house", "wealth", "finance"])], chart)
    assert _sections_of(res, "g") == {"values_money"}


def test_general_outer_planet_is_a_full_planet(chart):
    # Pluto: point home (chart_shape) + chart co-ruler (core_identity) + the
    # house it occupies and rules (H1 -> identity). Normal salience, not backdrop.
    res = route([_general("g", ["Pluto", "power", "transformation"])], chart)
    assert _sections_of(res, "g") == {"chart_shape", "core_identity", "identity"}
    assert _salience(res, "chart_shape", "g") is None


def test_general_two_outer_planets_land_in_their_houses(chart):
    res = route([_general("g", ["Uranus", "Neptune", "generational"])], chart)
    # both occupy H3; Uranus co-rules H4 (Aquarius cusp), Neptune co-rules H5 (Pisces)
    assert _sections_of(res, "g") == {"chart_shape", "communication_learning",
                                      "family_home", "joy_creativity_children"}


def test_general_personal_points_to_point_homes(chart):
    res = route([_general("g", ["Sun", "Mars", "vitality", "courage"])], chart)
    assert "g" in _routed_pids(res, "core_identity")   # Sun (and Mars as chart ruler)
    assert "g" in _routed_pids(res, "inner_drives")    # Mars
    assert "g" in _routed_pids(res, "travel_philosophy")   # Sun occupies H9


def test_general_many_planets_falls_to_default(chart):
    res = route([_general("g", ["Sun", "Moon", "Mercury", "Venus", "Mars",
                                "aspect importance"])], chart)
    assert _sections_of(res, "g") == {"chart_shape"}


def test_general_generational_alone_is_default_bucket(chart):
    res = route([_general("g", ["generational factors", "outer planets"], conf="high")], chart)
    assert _sections_of(res, "g") == {"chart_shape"}
    assert _salience(res, "chart_shape", "g") is None


def test_general_default_low_conf_is_low_salience(chart):
    res = route([_general("g", ["elements", "fire", "earth", "balance"], conf="low")], chart)
    assert _salience(res, "chart_shape", "g") == "low"


def test_general_default_high_conf_is_normal_salience(chart):
    res = route([_general("g", ["elements", "balance", "synthesis"], conf="high")], chart)
    assert _salience(res, "chart_shape", "g") is None


# --- §3.2 fallback ---

def test_unclassified_high_to_chart_shape(chart):
    rec = _principle("u", "unclassified", unclassified_reason="no_subject_in_text",
                     confidence="high")
    res = route([rec], chart)
    assert "u" in _routed_pids(res, "chart_shape")
    assert res.drops == []


def test_unclassified_low_is_dropped(chart):
    rec = _principle("ul", "unclassified", unclassified_reason="no_subject_in_text",
                     confidence="low")
    res = route([rec], chart)
    assert "ul" not in _routed_pids(res, "chart_shape")
    assert any(d["principle_id"] == "ul" for d in res.drops)


def test_unknown_factor_type_is_dropped(chart):
    rec = {"principle_id": "x", "tradition": "modern", "rule": "r",
           "topic_tags": [], "requires": [],
           "about": {"factor_type": "bogus", "extraction_confidence": "high",
                     "extraction_source": "deterministic"}}
    res = route([rec], chart)
    assert any(d["principle_id"] == "x" for d in res.drops)


def test_empty_section_omitted(chart):
    res = route([_principle("g", "general")], chart)
    assert list(res.non_empty().keys()) == ["chart_shape"]


def test_prompt_view_strips_house_system():
    rp = RoutedPrinciple(principle_id="p", tradition="traditional", rule="r",
                         topic_tags=[], requires=[],
                         about={"factor_type": "planet_in_house", "point": "Sun",
                                "house": 9, "house_system": "whole_sign"})
    d = rp.as_prompt_dict()
    assert d["about"] == {"factor_type": "planet_in_house", "point": "Sun", "house": 9}
    assert rp.about["house_system"] == "whole_sign"    # provenance untouched


# ---------------------------------------------------------------------------
# §7 validation
# ---------------------------------------------------------------------------

def _valid_output() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "precision_tier": PRECISION_TIER,
        "sections": [
            {"key": "core_identity", "movement": 1, "text_tr": "Sen güçlüsün.",
             "text_en": "You are strong.", "principle_ids": ["p1"]},
        ],
    }


def test_valid_output_passes():
    assert validate(_valid_output(), {"core_identity": {"p1"}}) == []


def test_house_field_validated():
    out = _valid_output()
    out["sections"][0]["house"] = 9
    assert validate(out, {"core_identity": {"p1"}}) == []
    out["sections"][0]["house"] = 13
    assert any("house" in e for e in validate(out, {"core_identity": {"p1"}}))


def test_unknown_key_fails():
    out = _valid_output()
    out["sections"][0]["key"] = "identity_body"      # pre-2026-09 key, no longer valid
    assert any("not one of" in e for e in validate(out, {"identity_body": {"p1"}}))


def test_empty_principle_ids_fails():
    out = _valid_output()
    out["sections"][0]["principle_ids"] = []
    assert any("empty principle_ids" in e for e in validate(out, {"core_identity": {"p1"}}))


def test_forbidden_tradition_token_fails():
    out = _valid_output()
    out["sections"][0]["text_tr"] = "Bu klasik bir yorum."
    assert any("forbidden" in e for e in validate(out, {"core_identity": {"p1"}}))


def test_forbidden_house_system_token_fails():
    out = _valid_output()
    out["sections"][0]["text_en"] = "In the Placidus system your Sun is in the 9th."
    assert any("forbidden" in e for e in validate(out, {"core_identity": {"p1"}}))


def test_stray_principle_id_fails():
    out = _valid_output()
    out["sections"][0]["principle_ids"] = ["p1", "zz"]
    assert any("not routed" in e for e in validate(out, {"core_identity": {"p1"}}))


def test_wrong_precision_tier_fails():
    out = _valid_output()
    out["precision_tier"] = "approximate"
    assert any("precision_tier" in e for e in validate(out, {"core_identity": {"p1"}}))


def test_unrouted_section_fails():
    assert any("not routed" in e for e in validate(_valid_output(), {}))


def test_empty_text_fails():
    out = _valid_output()
    out["sections"][0]["text_tr"] = "   "
    assert any("text_tr is empty" in e for e in validate(out, {"core_identity": {"p1"}}))


def test_empty_text_en_fails():
    out = _valid_output()
    out["sections"][0]["text_en"] = ""
    assert any("text_en is empty" in e for e in validate(out, {"core_identity": {"p1"}}))


# ---------------------------------------------------------------------------
# §6 assembly, render, end-to-end
# ---------------------------------------------------------------------------

def test_assemble_canonical_order_and_houses():
    synth = [{"key": "partnerships", "text_tr": "t", "text_en": "t"},
             {"key": "sun_house", "text_tr": "t", "text_en": "t"},
             {"key": "core_identity", "text_tr": "t", "text_en": "t"}]
    out = _assemble(synth, {"partnerships": {"a"}, "core_identity": {"b"}, "sun_house": {"c"}},
                    {"partnerships": 7, "sun_house": 9})
    keys = [s["key"] for s in out["sections"]]
    assert keys == ["core_identity", "sun_house", "partnerships"]
    by = {s["key"]: s for s in out["sections"]}
    assert "house" not in by["core_identity"]
    assert by["sun_house"]["house"] == 9 and by["sun_house"]["movement"] == 1
    assert by["partnerships"]["house"] == 7 and by["partnerships"]["movement"] == 2
    assert by["core_identity"]["principle_ids"] == ["b"]


def test_render_titles():
    assert section_title("travel_philosophy", "en") == "House 9 — Distant Travels and Philosophy"
    assert section_title("identity", "tr") == "1. Ev — Kimlik"
    assert section_title("sun_house", "en", 9) == "Sun in the 9th House"
    assert section_title("moon_house", "tr", 5) == "Ay 5. Evde"
    assert section_title("moon_house", "en", 2) == "Moon in the 2nd House"
    assert section_title("sun_house", "en") == "The Sun's House"       # no house known
    out = {"sections": [
        {"key": "sun_house", "movement": 1, "house": 9, "text_tr": "a", "text_en": "b"},
        {"key": "values_money", "movement": 2, "house": 2, "text_tr": "c", "text_en": "d"}]}
    txt = render(out, "en")
    assert "PART ONE" in txt and "Sun in the 9th House" in txt
    assert "PART TWO" in txt and "House 2 — Values and Money" in txt


def test_end_to_end_with_fake_validates(chart, kept):
    output, report, errors = interpret(chart, kept, generator=FakeGenerator())
    assert errors == []
    assert output["schema_version"] == SCHEMA_VERSION
    assert output["precision_tier"] == PRECISION_TIER
    assert report["backend"] == "FakeGenerator"
    assert report["house_policy"] == "placidus"
    keys = [s["key"] for s in output["sections"]]
    assert keys == [k for k in SECTION_ORDER if k in keys]       # canonical order
    by = {s["key"]: s for s in output["sections"]}
    # the luminary notes are grounded (Sun-in-house record verified in Placidus 9,
    # Moon-in-house record in 5, plus the house-domain principles) and carry the house
    assert by["sun_house"]["house"] == 9 and by["moon_house"]["house"] == 5
    assert report["luminary_houses"] == {"sun_house": 9, "moon_house": 5}
    for key in MOVEMENT_2:
        assert key in by, f"house section {key} missing"
        assert by[key]["house"] == SECTION_HOUSE[key]
        assert by[key]["movement"] == 2


def test_fake_every_section_grounded(chart, kept):
    output, _, _ = interpret(chart, kept, generator=FakeGenerator())
    for sec in output["sections"]:
        assert sec["principle_ids"]            # §7.1 — section-level grounding
        assert sec["text_en"]


def test_kept_has_no_whole_sign_mismatch(chart, kept):
    """Every kept house claim agrees with the Placidus placement (grounding policy)."""
    pts = {p["name"]: p for p in chart["points"]}
    for r in kept:
        a = r["about"]
        if a.get("factor_type") == "planet_in_house":
            assert pts[a["point"]]["sector"]["placidus"] == a["house"], r["principle_id"]


def test_low_salience_ids_passed_to_synthesis(chart, kept):
    gen = FakeGenerator()
    interpret(chart, kept, generator=gen)
    assert gen.synth_low_salience is not None     # handed over (may be empty)


# ---------------------------------------------------------------------------
# §1 Input 2 — personal_principles.json loader
# ---------------------------------------------------------------------------

def test_load_personal_kept_count_mismatch(tmp_path):
    bad = tmp_path / "personal_principles.json"
    bad.write_text(json.dumps({
        "reading": "natal", "kept_count": 5,
        "principles": [{"principle_id": "p"}],  # len 1 != 5
        "bundled_by_factor": {},
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="kept_count"):
        load_personal(str(bad))


@pytest.mark.skipif(not os.path.exists(_PERSONAL),
                    reason="personal_principles.json not present")
def test_load_personal_real_file_routes_all_sections(chart):
    kept = load_personal(_PERSONAL)
    res = route(kept, chart)
    routed_ids = {rp.principle_id for lst in res.sections.values() for rp in lst}
    dropped_ids = {d["principle_id"] for d in res.drops}
    assert {r["principle_id"] for r in kept} <= routed_ids | dropped_ids


# ---------------------------------------------------------------------------
# cheap-model fallback (translation / detox never lose a finished reading)
# ---------------------------------------------------------------------------

def test_translation_falls_back_to_synthesis_model(monkeypatch):
    import llm_client
    from l4_generate import LLMGenerator
    gen = LLMGenerator(model="gemini-3.7-flash", translation_model="gpt-6-luna")
    calls = []

    def fake_call(model, system, user, **kw):
        calls.append((model, kw.get("label")))
        if model == "gpt-6-luna":
            raise llm_client.ProviderQuotaError("no credits")
        return {"text_en": "ok"}
    monkeypatch.setattr(gen, "_call_json", fake_call)
    assert gen.translate("identity", "Merhaba.") == "ok"
    assert [m for m, _ in calls] == ["gpt-6-luna", "gemini-3.7-flash"]
    assert calls[1][1] == "translate[identity]/fallback"
    assert gen.fallbacks == 1


def test_no_fallback_when_models_identical(monkeypatch):
    import llm_client
    from l4_generate import LLMGenerator
    gen = LLMGenerator(model="gemini-3.7-flash", translation_model="gemini-3.7-flash")

    def fake_call(model, system, user, **kw):
        raise llm_client.ProviderQuotaError("no credits")
    monkeypatch.setattr(gen, "_call_json", fake_call)
    with pytest.raises(llm_client.ProviderQuotaError):
        gen.translate("identity", "Merhaba.")
