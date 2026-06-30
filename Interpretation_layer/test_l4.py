#!/usr/bin/env python3
"""
test_l4.py — tests for the deterministic core of Layer 4 (routing §3, validation
§7) plus an end-to-end pipeline run against the real chart.

The generation calls (§4/§5) are model-driven and not unit-tested here; an
injected FakeGenerator exercises the assembly + contract-validation plumbing
without an API.

Run:  python -m pytest test_l4.py -q
"""

from __future__ import annotations

import json
import os

import pytest

from l4_generate import SectionDraft
from l4_interpret import _assemble, _ground_source, interpret, load_personal
from l4_routing import (
    chart_ruler,
    domain_section_for_house,
    house_of,
    houses_ruled,
    route,
    section_for_point,
)
from l4_sections import SECTION_ORDER
from l4_validate import PRECISION_TIER, SCHEMA_VERSION, validate

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
_PERSONAL = os.path.join(_PARENT, "principles_grounding", "personal_principles.json")


_CHART = os.path.join(_PARENT, "d_layer", "chart.json")  # single source (§1)


@pytest.fixture(scope="module")
def chart() -> dict:
    with open(_CHART, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def kept(chart) -> list[dict]:
    # §1 Input 2: read personal_principles.json; fall back to grounding the
    # corpus if that L3 artifact is not present.
    if os.path.exists(_PERSONAL):
        return load_personal(_PERSONAL)
    with open(os.path.join(_HERE, "all_principles.grounded.json"),
              encoding="utf-8") as fh:
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


def _routed_pids(res, key) -> set[str]:
    return {rp.principle_id for rp in res.sections.get(key, [])}


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
    the assembly + validation plumbing can be tested without an API. Each routed
    principle becomes one claim citing its own id; synthesis is identity."""

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
        # bilingual: stub English mirrors the stub Turkish (text only, no claims)
        return [{"key": d.key, "text_tr": d.text_tr,
                 "text_en": d.text_tr.replace("dayanak", "basis")}
                for d in drafts]


# ---------------------------------------------------------------------------
# §3.0 chart helpers
# ---------------------------------------------------------------------------

def test_chart_ruler_is_venus(chart):
    assert chart_ruler(chart) == "Venus"


def test_house_of_uses_placidus(chart):
    pts = {p["name"]: p for p in chart["points"]}
    assert house_of("Venus", pts) == 8      # placidus sector
    assert house_of("Saturn", pts) == 4


def test_houses_ruled_placidus(chart):
    assert houses_ruled("Venus", chart) == [1, 8]
    assert houses_ruled("Saturn", chart) == [4, 5]


def test_section_for_point_chart_ruler_has_dual_home(chart):
    # Venus is the chart ruler AND a personal planet -> both homes.
    assert section_for_point("Venus", chart) == {"core_identity", "inner_drives"}
    assert section_for_point("Sun", chart) == {"core_identity"}
    assert section_for_point("Saturn", chart) == {"chart_shape"}


def test_domain_section_pairs():
    assert domain_section_for_house(2) == domain_section_for_house(8) == "resources_values"
    assert domain_section_for_house(3) == domain_section_for_house(9) == "mind_communication"
    assert domain_section_for_house(11) == domain_section_for_house(12) == "community_meaning"
    assert domain_section_for_house(6) == "daily_work"
    assert domain_section_for_house(10) == "vocation_public"


# ---------------------------------------------------------------------------
# §3.1 / §3.0 routing rules (synthetic, isolated)
# ---------------------------------------------------------------------------

def test_planet_in_sign_routes_to_point_home(chart):
    rec = _principle("p", "planet_in_sign", point="Sun", sign="Gemini")
    res = route([rec], chart)
    assert "p" in _routed_pids(res, "core_identity")


def test_whole_sign_house_is_classical_texture(chart):
    # A whole-sign house claim lands in the WS domain as texture, and in the
    # placidus-occupied domain as primary. Mercury occupies placidus 8
    # (resources_values) and rules placidus 9/12; a WS house 7 (relationships)
    # is reached ONLY via the WS rule, so it stays classical there.
    rec = _principle("ws", "planet_in_house", point="Mercury", house=7,
                     house_system="whole_sign")
    res = route([rec], chart)
    assert _texture(res, "relationships", "ws") == "classical"   # WS-only domain
    assert _texture(res, "resources_values", "ws") is None       # placidus occ


def test_placidus_house_is_primary(chart):
    rec = _principle("pl", "planet_in_house", point="Mars", house=6,
                     house_system="placidus")
    res = route([rec], chart)
    assert _texture(res, "daily_work", "pl") is None


def test_dignity_is_classical_everywhere(chart):
    rec = _principle("d", "dignity", point="Saturn", dignity="domicile")
    res = route([rec], chart)
    # point home + occupancy/rulership, all classical
    assert _texture(res, "chart_shape", "d") == "classical"
    assert _texture(res, "home_roots", "d") == "classical"
    assert _texture(res, "creativity_pleasure", "d") == "classical"


def test_house_lord_relative_routes_to_subject_house_domain(chart):
    rec = _principle("lr", "house_lord_relative", subject_house=1,
                     subject_house_system="whole_sign", placement_house=8,
                     placement_house_system="whole_sign")
    res = route([rec], chart)
    assert _texture(res, "identity_body", "lr") == "classical"   # subject_house=1
    # routed on subject_house, never placement_house (8 -> resources_values)
    assert "lr" not in _routed_pids(res, "resources_values")


def test_aspect_routes_both_endpoints_and_chart_shape(chart):
    rec = _principle("a", "aspect",
                     aspect={"source": "Venus", "target": "Mars", "type": "trine"})
    res = route([rec], chart)
    assert "a" in _routed_pids(res, "inner_drives")   # both endpoints personal
    assert "a" in _routed_pids(res, "chart_shape")    # configuration
    # Venus occupies placidus 8 -> resources_values; Mars placidus 6 -> daily_work
    assert "a" in _routed_pids(res, "resources_values")
    assert "a" in _routed_pids(res, "daily_work")


def test_house_domain_polymorphic(chart):
    by_point = _principle("hp", "house_domain", point="Mars")
    by_house = _principle("hh", "house_domain", house=10, house_system="placidus")
    res = route([by_point, by_house], chart)
    assert "hp" in _routed_pids(res, "inner_drives")       # Movement 1
    assert "hh" in _routed_pids(res, "vocation_public")    # Movement 2


def _general(pid, tags, conf="low"):
    return {
        "principle_id": pid, "tradition": "modern", "rule": "r",
        "topic_tags": tags,
        "about": {"factor_type": "general", "extraction_confidence": conf,
                  "extraction_source": "deterministic"},
        "requires": []}


# ---------------------------------------------------------------------------
# §3.1.11 general sub-routing ladder (first match wins)
# ---------------------------------------------------------------------------

def test_general_chart_ruler_to_core_identity(chart):
    rec = _general("g", ["ascendant ruler", "chart ruler", "vocation"])
    res = route([rec], chart)
    # rung 1 wins over the 'vocation' tag (rung 2 would be vocation_public)
    assert "g" in _routed_pids(res, "core_identity")
    assert "g" not in _routed_pids(res, "vocation_public")


def test_general_mc_to_vocation(chart):
    rec = _general("g", ["Midheaven", "MC ruler", "career"])
    res = route([rec], chart)
    assert "g" in _routed_pids(res, "vocation_public")


def test_general_house_lord_to_domain(chart):
    rec = _general("g", ["lord of 2nd house", "wealth", "finance"])
    res = route([rec], chart)
    assert "g" in _routed_pids(res, "resources_values")   # H2 domain


def test_general_generational_low_salience(chart):
    rec = _general("g", ["Uranus", "Neptune", "Pluto", "generational factors"])
    res = route([rec], chart)
    assert "g" in _routed_pids(res, "chart_shape")
    assert _salience(res, "chart_shape", "g") == "low"


def test_general_personal_point_to_point_home(chart):
    rec = _general("g", ["Sun", "Mars", "vitality", "courage"])
    res = route([rec], chart)
    assert "g" in _routed_pids(res, "core_identity")   # Sun
    assert "g" in _routed_pids(res, "inner_drives")    # Mars


def test_general_many_personal_points_falls_to_default(chart):
    # naming 3+ personal points = class-level methodology -> default chart_shape
    rec = _general("g", ["Sun", "Moon", "Mercury", "Venus", "Mars",
                         "aspect importance"])
    res = route([rec], chart)
    assert "g" in _routed_pids(res, "chart_shape")
    assert "g" not in _routed_pids(res, "inner_drives")


def test_general_default_low_conf_is_low_salience(chart):
    rec = _general("g", ["elements", "fire", "earth", "balance"], conf="low")
    res = route([rec], chart)
    assert _salience(res, "chart_shape", "g") == "low"


def test_general_default_high_conf_is_normal_salience(chart):
    rec = _general("g", ["elements", "balance", "synthesis"], conf="high")
    res = route([rec], chart)
    assert "g" in _routed_pids(res, "chart_shape")
    assert _salience(res, "chart_shape", "g") is None


# ---------------------------------------------------------------------------
# §3.2 fallback
# ---------------------------------------------------------------------------

def test_unclassified_high_to_chart_shape(chart):
    rec = _principle("u", "unclassified", unclassified_reason="no_subject_in_text",
                     confidence="high")
    res = route([rec], chart)
    assert "u" in _routed_pids(res, "chart_shape")
    assert res.drops == []


def test_unclassified_low_is_dropped(chart):
    rec = _principle("ul", "unclassified",
                     unclassified_reason="no_subject_in_text", confidence="low")
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
    # one general principle -> only chart_shape is non-empty
    res = route([_principle("g", "general")], chart)
    assert list(res.non_empty().keys()) == ["chart_shape"]


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


def test_empty_principle_ids_fails():
    out = _valid_output()
    out["sections"][0]["principle_ids"] = []
    errs = validate(out, {"core_identity": {"p1"}})
    assert any("empty principle_ids" in e for e in errs)


def test_forbidden_tradition_token_fails():
    out = _valid_output()
    out["sections"][0]["text_tr"] = "Bu modern bir okuma."
    errs = validate(out, {"core_identity": {"p1"}})
    assert any("forbidden tradition token" in e for e in errs)


def test_stray_principle_id_fails():
    out = _valid_output()
    out["sections"][0]["principle_ids"] = ["p1", "ghost"]
    errs = validate(out, {"core_identity": {"p1"}})
    assert any("synthesis adds nothing" in e for e in errs)


def test_wrong_precision_tier_fails():
    out = _valid_output()
    out["precision_tier"] = "approximate"
    errs = validate(out, {"core_identity": {"p1"}})
    assert any("precision_tier" in e for e in errs)


def test_unrouted_section_fails():
    out = _valid_output()
    errs = validate(out, {})   # core_identity was not routed anything
    assert any("was not routed" in e for e in errs)


def test_empty_text_fails():
    out = _valid_output()
    out["sections"][0]["text_tr"] = "   "
    errs = validate(out, {"core_identity": {"p1"}})
    assert any("text_tr is empty" in e for e in errs)


def test_empty_text_en_fails():
    out = _valid_output()
    out["sections"][0]["text_en"] = ""
    errs = validate(out, {"core_identity": {"p1"}})
    assert any("text_en is empty" in e for e in errs)


def test_forbidden_token_in_text_en_fails():
    out = _valid_output()
    out["sections"][0]["text_en"] = "This is a traditional reading."
    errs = validate(out, {"core_identity": {"p1"}})
    assert any("text_en" in e and "forbidden" in e for e in errs)


# ---------------------------------------------------------------------------
# §6 assembly + end-to-end (fake generator)
# ---------------------------------------------------------------------------

def test_assemble_canonical_order():
    synth = [{"key": "relationships", "text_tr": "t", "text_en": "t"},
             {"key": "core_identity", "text_tr": "t", "text_en": "t"}]
    out = _assemble(synth, {"relationships": {"a"}, "core_identity": {"b"}})
    keys = [s["key"] for s in out["sections"]]
    assert keys == ["core_identity", "relationships"]   # canonical, not input order
    # grounding is attached from routing, per section
    assert out["sections"][0]["principle_ids"] == ["b"]


def test_end_to_end_with_fake_validates(chart, kept):
    output, report, errors = interpret(chart, kept, generator=FakeGenerator())
    assert errors == []
    assert output["schema_version"] == SCHEMA_VERSION
    assert output["precision_tier"] == PRECISION_TIER
    assert report["backend"] == "FakeGenerator"
    # every emitted section key is a locked §2 key, canonical order
    keys = [s["key"] for s in output["sections"]]
    assert keys == [k for k in SECTION_ORDER if k in keys]


def test_fake_every_section_grounded(chart, kept):
    output, _, _ = interpret(chart, kept, generator=FakeGenerator())
    for sec in output["sections"]:
        assert sec["principle_ids"]            # §7.1 — section-level grounding
        assert "text_en" in sec and sec["text_en"]


def test_low_salience_ids_passed_to_synthesis(chart, kept):
    gen = FakeGenerator()
    interpret(chart, kept, generator=gen)
    # the routed low-salience set is handed to synthesis for §5.5 pruning
    assert gen.synth_low_salience is not None
    assert len(gen.synth_low_salience) > 0


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
    # every kept record is routed somewhere or explicitly dropped — nothing lost
    routed_ids = {rp.principle_id for lst in res.sections.values() for rp in lst}
    dropped_ids = {d["principle_id"] for d in res.drops}
    assert {r["principle_id"] for r in kept} <= routed_ids | dropped_ids
