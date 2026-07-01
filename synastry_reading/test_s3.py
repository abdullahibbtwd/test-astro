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
from s3_routing import SECTION_CAP, below_floor, route, route_sections
from s3_sections import AXIS_ORDER, WHAT_EACH_BRINGS
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
    assert find_mask_violations("this is classical astrology")


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


def test_end_to_end_with_fake_generator():
    if not os.path.exists(_INPUT):
        print("  (skipped end-to-end: grounded input not found)")
        return
    from read_relationship import read_relationship
    payload = json.load(open(_INPUT, encoding="utf-8"))
    routing = route(payload)
    gen = FakeGenerator(routing.non_empty())
    output, statements_doc, report, errors = read_relationship(
        payload, generator=gen, houses_valid=True)
    assert not errors, f"unexpected contract errors: {errors}"
    assert output["schema_version"] == "s3.v1"
    # opener + 7 axes, all non-empty bilingual
    keys = [s["key"] for s in output["sections"]]
    assert WHAT_EACH_BRINGS in keys
    for s in output["sections"]:
        assert s["text_tr"] and s["text_en"] and s["source_ids"]
    assert statements_doc["statements"], "expected some statements"


def test_cap_and_attribution_on_real_input():
    if not os.path.exists(_INPUT):
        print("  (skipped real-input checks: input not found)")
        return
    payload = json.load(open(_INPUT, encoding="utf-8"))
    res = route(payload)
    # §4.3 cap
    for sec in AXIS_ORDER:
        assert len(res.sections[sec]) <= SECTION_CAP, f"{sec} over cap"
    # §10.2 attribution: the Mercury-in-10th contact reads B's Mercury -> A's
    # public life, never the reverse.
    merc = [r for recs in res.sections.values() for r in recs
            if "mercury-in-10th" in r.record_id]
    assert merc, "expected the Mercury-in-10th overlay in routing"
    b = merc[0].bound
    assert b.get("mover_person") == "B" and b.get("home_person") == "A", \
        f"attribution wrong: {b}"
    # §4.1 floor actually fired
    reasons = {d["reason"] for d in res.floor_drops}
    assert "reception_face_grade" in reasons


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
