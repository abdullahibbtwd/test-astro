#!/usr/bin/env python3
"""
test_s3.py — offline tests for the S3 pipeline (no API key required).

Covers the SYNASTRY_READING_SPEC invariants deterministically:
  - §4.1 floor: face receptions and outer-planet-only aspects drop.
  - §4.2 routing: records reach the right axes; attribution rides on `bound`.
  - §4.3 cap: no section exceeds the cap; overflow is logged.
  - §7/§10.2 attribution: the Mercury contact reads B->A, never reversed.
  - §10.3 mask + §10.4 no-score: the validator catches leaks.
  - end-to-end with an injected fake generator that echoes bound_statements.

Run:  python test_s3.py         (uses the real grounded input if present)
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from s3_generate import SectionDraft
from s3_profiles import GENERAL, PERSONAL, PROFESSIONAL, get_profile
from s3_routing import SECTION_CAP, below_floor, route, route_sections
from s3_sections import WHAT_EACH_BRINGS
from s3_validate import (
    find_mask_violations,
    find_score_violations,
    validate,
)

_INPUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "principles_grounding", "personal_relationship_principles.json")


def _rec(interaction, bound, *, matched=None, syn_extra=None, pid="x",
         bound_statement="stmt", tags=None):
    syn = {"interaction": interaction}
    if syn_extra:
        syn.update(syn_extra)
    r = {"principle_id": pid, "synastry": syn, "bound": bound,
         "bound_statement": bound_statement, "topic_tags": tags or []}
    if matched is not None:
        r["matched"] = matched
    return r


# ---------------------------------------------------------------------------
# Floor (§4.1)
# ---------------------------------------------------------------------------

def test_floor_face_reception():
    r = _rec("reception", {"grade": "face", "receiver_point": "Sun",
                           "received_point": "Moon"})
    assert below_floor(r) == "reception_face_grade"


def test_floor_keeps_graded_reception():
    r = _rec("reception", {"grade": "domicile", "receiver_point": "Venus",
                           "received_point": "Moon"})
    assert below_floor(r) is None


def test_floor_outer_only_aspect():
    r = _rec("aspect", {"p1_point": "Uranus", "p2_point": "Neptune",
                        "aspect": "trine"})
    assert below_floor(r) == "aspect_outer_planet_only"


def test_floor_keeps_significator_aspect():
    r = _rec("aspect", {"p1_point": "Venus", "p2_point": "Uranus",
                        "aspect": "trine"})
    assert below_floor(r) is None


# ---------------------------------------------------------------------------
# Routing (§4.2)
# ---------------------------------------------------------------------------

def test_venus_mars_square_feeds_attraction_and_friction():
    r = _rec("aspect", {"p1_point": "Venus", "p2_point": "Mars",
                        "aspect": "square"})
    secs = {s for s, _ in route_sections(r)}
    assert "attraction" in secs and "friction" in secs


def test_saturn_overlay_7th_feeds_commitment():
    r = _rec("house_overlay", {"mover_point": "Saturn", "home_house": 7})
    secs = {s for s, _ in route_sections(r)}
    assert "commitment" in secs


def test_mutual_reception_feeds_commitment():
    r = _rec("reception", {"grade": "domicile", "mutual": True,
                           "receiver_point": "Mars", "received_point": "Sun"})
    secs = {s for s, _ in route_sections(r)}
    assert "commitment" in secs


def test_air_compatibility_feeds_communication():
    r = _rec("compatibility", {"factors": ["air"]})
    secs = {s for s, _ in route_sections(r)}
    assert secs == {"communication"}


# ---------------------------------------------------------------------------
# Mask + score validation (§10.3, §10.4)
# ---------------------------------------------------------------------------

def test_mask_hard_terms():
    assert find_mask_violations("bu bir domicile durumu")
    assert find_mask_violations("a strong reception here")


def test_mask_tradition_framing_caught():
    # naming the tradition/apparatus IS a leak
    assert find_mask_violations("this is classical astrology")
    assert find_mask_violations("geleneksel astrolojide bu böyledir")
    assert find_mask_violations("klasik yaklaşımda")
    assert find_mask_violations("in the traditional view")


def test_mask_allows_tradition_adjective_as_content():
    # bare tradition adjectives describing the couple are legitimate content
    assert not find_mask_violations("paylaştığınız geleneksel değerler sizi bağlar")
    assert not find_mask_violations("geleneksel bir bağlılık anlayışınız var")
    assert not find_mask_violations("you are a modern couple with traditional values")


def test_mask_allows_ordinary_romantic_english():
    # 'fall', 'face', 'bound' as ordinary words must NOT trip the mask.
    assert not find_mask_violations("you two fall in love and face life, bound together")


def test_mask_catches_ordinal_house_leak():
    assert find_mask_violations("your energy lands in their 10th house")
    assert find_mask_violations("enerjin onun 7. evinde")


def test_score_detection():
    assert find_score_violations("compatibility is 87%")
    assert find_score_violations("uyum: 8/10")
    assert not find_score_violations("your bond is warm and steady")


# ---------------------------------------------------------------------------
# Fake generator for the end-to-end pass
# ---------------------------------------------------------------------------

class FakeGenerator:
    """Echoes each section's bound_statements as clean prose (no banned terms),
    emits tr+en, and produces one statement per routed record."""
    usage = {"input_tokens": 0, "output_tokens": 0,
             "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
             "calls": 0}

    def __init__(self, routed_by_section):
        self._routed = routed_by_section

    def section_all(self, routed_by_section, *, houses_valid):
        out = []
        for key, recs in routed_by_section.items():
            # Deliberately plain text; avoid any bound_statement scaffolding.
            body = f"Bu bolum icin {len(recs)} tema islendi. Baglariniz sicak."
            out.append(SectionDraft(key=key, text_tr=body))
        return out

    def synthesize(self, drafts):
        return [{"key": d.key,
                 "text_tr": d.text_tr,
                 "text_en": f"This section wove {d.key} warmly."}
                for d in drafts]

    def extract_statements(self, final_sections, allowed_ids_by_section):
        stmts = []
        for s in final_sections:
            ids = allowed_ids_by_section.get(s["key"], [])
            if ids:
                stmts.append({"section": s["key"],
                              "text_tr": "Ornek atomik ifade.",
                              "text_en": "Sample atomic statement.",
                              "source_ids": [ids[0]]})
        return stmts


def test_end_to_end_all_three_profiles():
    if not os.path.exists(_INPUT):
        print("  (skipped end-to-end: grounded input not found)")
        return
    from read_relationship import read_relationship
    payload = json.load(open(_INPUT, encoding="utf-8"))
    for rtype, profile in [("general", GENERAL), ("personal", PERSONAL),
                           ("professional", PROFESSIONAL)]:
        routing = route(payload, profile)
        gen = FakeGenerator(routing.non_empty())
        output, statements_doc, report, errors = read_relationship(
            payload, generator=gen, reading_type=rtype, houses_valid=True)
        assert not errors, f"[{rtype}] unexpected contract errors: {errors}"
        assert output["reading_type"] == rtype
        keys = [s["key"] for s in output["sections"]]
        assert WHAT_EACH_BRINGS in keys
        # emitted keys must all belong to this profile (§7.3 consistency)
        for k in keys:
            assert k in profile.section_order, f"[{rtype}] stray key {k}"
        for s in output["sections"]:
            assert s["text_tr"] and s["text_en"] and s["source_ids"]
        assert report["reading_type"] == rtype


def test_cap_and_attribution_on_real_input():
    if not os.path.exists(_INPUT):
        print("  (skipped real-input checks: input not found)")
        return
    payload = json.load(open(_INPUT, encoding="utf-8"))
    # §4.3 cap holds under a personal reading
    per = route(payload, PERSONAL)
    for sec in PERSONAL.axis_keys:
        assert len(per.sections[sec]) <= SECTION_CAP, f"{sec} over cap"
    # §10.2 attribution: the Mercury-in-10th contact (career -> professional
    # context) reads B's Mercury -> A's public life. Check it in a general
    # reading (admits all) and confirm it is professional-eligible, personal-not.
    gen = route(payload, GENERAL)
    merc = [r for recs in gen.sections.values() for r in recs
            if "mercury-in-10th" in r.record_id]
    assert merc, "expected the Mercury-in-10th overlay in the general routing"
    b = merc[0].bound
    assert b.get("mover_person") == "B" and b.get("home_person") == "A", \
        f"attribution wrong: {b}"
    # §7.1 eligibility: this professional-tagged record is absent from personal.
    per_ids = {r.record_id for recs in per.sections.values() for r in recs}
    assert not any("mercury-in-10th" in i for i in per_ids)
    # §4.1 floor actually fired
    reasons = {d["reason"] for d in gen.floor_drops}
    assert "reception_face_grade" in reasons


# ---------------------------------------------------------------------------
# Profile fork (SYNASTRY_READING_PROFILES.md)
# ---------------------------------------------------------------------------

def test_context_filter_eligibility():
    # §2 / §7.1: personal excludes professional-only; professional excludes
    # personal-only; general admits everything.
    from s3_profiles import admits
    prof_only = {"synastry": {"contexts": ["professional"]}}
    pers_only = {"synastry": {"contexts": ["personal"]}}
    universal = {"synastry": {"contexts": ["universal"]}}
    assert not admits(PERSONAL.admitted_contexts, prof_only)
    assert admits(PERSONAL.admitted_contexts, pers_only)
    assert not admits(PROFESSIONAL.admitted_contexts, pers_only)
    assert admits(PROFESSIONAL.admitted_contexts, prof_only)
    for p in (GENERAL, PERSONAL, PROFESSIONAL):
        assert admits(p.admitted_contexts, universal)


def test_profile_key_sets_disjoint_semantics():
    # each profile exposes exactly its 8 keys, opener first
    for p in (GENERAL, PERSONAL, PROFESSIONAL):
        assert p.section_order[0] == WHAT_EACH_BRINGS
        assert len(p.axis_keys) == 7
        assert len(p.section_order) == 8
    # professional has its bespoke keys
    assert "roles_leadership" in PROFESSIONAL.axis_keys
    assert "shared_goals" in PROFESSIONAL.axis_keys


def test_professional_routing():
    # a Saturn aspect routes to reliability; Mars-Saturn to conflict_style
    r = _rec("aspect", {"p1_point": "Saturn", "p2_point": "Mercury",
                        "aspect": "trine"})
    secs = {s for s, _ in PROFESSIONAL.route(r)}
    assert "reliability" in secs and "decision_making" in secs
    # a 10th-house overlay routes to roles_leadership
    ov = _rec("house_overlay", {"mover_point": "Sun", "home_house": 10})
    assert "roles_leadership" in {s for s, _ in PROFESSIONAL.route(ov)}


def test_professional_reading_rejects_personal_key():
    # §7.3: a personal-only key must not validate under a professional reading
    bad = {
        "schema_version": "s3.v1", "reading_type": "professional",
        "sections": [
            {"key": "attraction", "movement": 1, "text_tr": "x", "text_en": "y",
             "source_ids": ["z"]},
        ],
    }
    errors = validate(bad)
    assert any("attraction" in e for e in errors), errors


def test_context_filter_reduces_professional_pool():
    if not os.path.exists(_INPUT):
        print("  (skipped: input not found)")
        return
    payload = json.load(open(_INPUT, encoding="utf-8"))
    gen_res = route(payload, GENERAL)
    pro_res = route(payload, PROFESSIONAL)
    # professional drops the personal-only records via the context filter
    assert len(pro_res.context_drops) > 0
    assert len(gen_res.context_drops) == 0


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------

def _run():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} passed")
    return failed


if __name__ == "__main__":
    sys.exit(1 if _run() else 0)


# ---------------------------------------------------------------------------
# §5 split: Turkish synthesis + per-section translation on the cheap model
# ---------------------------------------------------------------------------

def test_synthesis_is_turkish_only_then_translated(monkeypatch):
    import llm_client
    from s3_generate import LLMGenerator, SYNTHESIS_SCHEMA, TRANSLATION_SCHEMA, SectionDraft
    from s3_profiles import get_profile
    gen = LLMGenerator("CONTRACT", get_profile("general"), model="gemini-3.7-flash",
                       translation_model="gpt-6-luna")
    calls = []

    def fake_call(model, system, user, *, temperature, max_tokens, label, schema=None):
        calls.append((model, label))
        if schema is SYNTHESIS_SCHEMA:
            assert "text_en" not in json.dumps(schema)
            return {"sections": [{"key": "a", "text_tr": "Sıcak bir bağ."},
                                 {"key": "b", "text_tr": "Gerilim de var."}]}
        assert schema is TRANSLATION_SCHEMA and model == "gpt-6-luna"
        return {"key": "x", "text_en": "EN"}
    monkeypatch.setattr(gen, "_call_json", fake_call)
    out = gen.synthesize([SectionDraft("a", "d1"), SectionDraft("b", "d2")])
    assert out == [{"key": "a", "text_tr": "Sıcak bir bağ.", "text_en": "EN"},
                   {"key": "b", "text_tr": "Gerilim de var.", "text_en": "EN"}]
    assert calls[0] == ("gemini-3.7-flash", "synthesis")
    assert sorted(c[1] for c in calls[1:]) == ["translate[a]", "translate[b]"]


def test_translation_falls_back_to_synthesis_model(monkeypatch):
    import llm_client
    from s3_generate import LLMGenerator
    from s3_profiles import get_profile
    gen = LLMGenerator("CONTRACT", get_profile("general"), model="gemini-3.7-flash",
                       translation_model="gpt-6-luna")
    seen = []

    def fake_call(model, system, user, **kw):
        seen.append(model)
        if model == "gpt-6-luna":
            raise llm_client.ProviderQuotaError("no credits")
        return {"key": "a", "text_en": "EN"}
    monkeypatch.setattr(gen, "_call_json", fake_call)
    assert gen.translate("a", "Merhaba.") == "EN"
    assert seen == ["gpt-6-luna", "gemini-3.7-flash"] and gen.fallbacks == 1
