#!/usr/bin/env python3
"""
test_grounding.py — the 8 adversarial validation tests of
PRINCIPLE_GROUNDING_SPEC.md §7. These verify DROPS, not just keeps: the live
retrieval failures are used as fixtures against the working chart
(Libra ascendant, North Node in whole-sign house 5).

Run:  python test_grounding.py      (plain asserts; also pytest-compatible)
"""

from __future__ import annotations

import copy
import json
import os

from backfill import (
    BUILD_FLOORS,
    UNCLASSIFIED_CEILING,
    backfill,
    diff_factor_types,
    tier1_deterministic,
    validate_invariants,
)
from ground import InvariantViolation, ground
from grounding_schema import invariant_violation, validate_about
from reclassify import (
    load_rules,
    reclassify,
    reclassify_record,
    structural_residual_check,
)

HERE = os.path.dirname(os.path.abspath(__file__))
CHART = os.path.join(os.path.dirname(HERE), "retrival_contract", "chart.json")
CLEAN = os.path.join(HERE, "all_principles.clean.json")


class _NullExtractor:
    """Tier-2 disabled: tests run on the DETERMINISTIC tier only, so they are
    fully offline and independent of any live LLM run (which the rev-3 ceiling
    needs). Gate fixtures that require an LLM-extracted subject are constructed
    explicitly in the test."""

    def extract(self, record):
        return None


def _load_chart() -> dict:
    with open(CHART, encoding="utf-8") as fh:
        return json.load(fh)


_GROUNDED_CACHE: list[dict] | None = None


def _grounded_list() -> list[dict]:
    """The full deterministic pipeline (backfill + reclassify post-pass) over the
    clean corpus, generated in-memory and cached so the suite never depends on an
    accepted artifact file."""
    global _GROUNDED_CACHE
    if _GROUNDED_CACHE is None:
        with open(CLEAN, encoding="utf-8") as fh:
            records = json.load(fh)
        grounded = backfill(records, _NullExtractor())
        _GROUNDED_CACHE, _ = reclassify(grounded, load_rules())
    return _GROUNDED_CACHE


def _load_grounded() -> dict:
    return {r["principle_id"]: r for r in _grounded_list()}


def _ground_one(record: dict, chart: dict, reading: str = "natal",
                house_policy=None):
    """Run the gate on a single record; return (kept_bool, drop_or_None).

    Default ``house_policy=None`` honors each record's declared house_system
    (needed for whole_sign vs placidus divergence checks). Pass
    ``house_policy="placidus"`` to exercise the production Placidus-only policy.
    """
    res = ground([record], chart, reading=reading, house_policy=house_policy)
    if res.kept:
        return True, None
    return False, res.drops[0]


# ---------------------------------------------------------------------------
# Test 1 — domain leak: non-natal records dropped by gate A
# ---------------------------------------------------------------------------

def test_1_domain_leak():
    chart = _load_chart()
    idx = _load_grounded()
    # 8 predictive + 2 horary + 1 mundane leaked records (any non-natal sample).
    leaked = [r for r in idx.values()
              if r.get("domain") in ("predictive", "horary", "mundane")][:11]
    res = ground(leaked, chart, reading="natal")
    assert len(res.kept) == 0, "non-natal records must not survive"
    assert all(d.gate == "A" for d in res.drops), "must drop at gate A"
    print("test_1_domain_leak: PASS (0 non-natal survive)")


# ---------------------------------------------------------------------------
# Test 2 — wrong-house node dropped by gate B (house mismatch)
# ---------------------------------------------------------------------------

def test_2_wrong_house_node():
    chart = _load_chart()
    idx = _load_grounded()
    for pid in ("north-node-7th-women", "north-node-2nd-wealth",
                "north-node-8th-life-strength"):
        rec = idx[pid]
        kept, drop = _ground_one(rec, chart)
        assert not kept, f"{pid} should be dropped (node is in house 5)"
        assert drop.gate == "B"
        assert "house mismatch" in drop.reason, drop.reason
        print(f"test_2: {pid} dropped at B -> {drop.reason}")
    print("test_2_wrong_house_node: PASS")


# ---------------------------------------------------------------------------
# Test 3 — false ascendant dropped by gate B (keystone)
# ---------------------------------------------------------------------------

def test_3_false_ascendant():
    chart = _load_chart()
    # asc-scorpio-mars-primary-ruler is a LABEL-style id (the LLM tier types it
    # `ascendant`/Scorpio); deterministic capture leaves it unclassified. The
    # keystone test is about the GATE, so we supply the subject the LLM produces
    # and assert the gate drops the false Scorpio ascendant against the Libra asc.
    rec = {
        "principle_id": "asc-scorpio-mars-primary-ruler", "domain": "natal",
        "tradition": "traditional", "rule": "x", "judgment": "y", "conditions": [],
        "about": {"factor_type": "ascendant", "ascendant_sign": "Scorpio",
                  "extraction_confidence": "medium", "extraction_source": "llm"},
        "requires": [{"kind": "ascendant"}],
    }
    kept, drop = _ground_one(rec, chart)
    assert not kept, "false ascendant (Scorpio vs Libra) must be dropped"
    assert drop.gate == "B"
    assert "ascendant mismatch" in drop.reason, drop.reason
    print(f"test_3_false_ascendant: PASS -> {drop.reason}")


# ---------------------------------------------------------------------------
# Test 4 — true-positive survival: genuine delineations are NOT over-filtered
# ---------------------------------------------------------------------------

def test_4_true_positive_survival():
    chart = _load_chart()
    idx = _load_grounded()
    # Records the strict tiers classify correctly and that are true of the chart.
    for pid in ("mars-sign-aries-delineation", "moon-sign-pisces-delineation"):
        kept, drop = _ground_one(idx[pid], chart)
        assert kept, f"{pid} is true of the chart and must be kept ({drop})"
        print(f"test_4: {pid} kept")

    # A placidus house-8 Venus delineation (spec's venus-house-pleasure-domain):
    # the offline heuristic can't name its subject, so we supply the corrected
    # `about` the LLM tier would produce and assert the GATE keeps it. Venus is
    # in placidus house 8 on this chart.
    venus_h8 = {
        "principle_id": "venus-house-pleasure-domain",
        "domain": "natal", "tradition": "modern",
        "rule": "x", "judgment": "y", "conditions": [],
        "about": {
            "factor_type": "planet_in_house", "point": "Venus",
            "house": 8, "house_system": "placidus",
            "extraction_confidence": "medium", "extraction_source": "llm",
        },
        "requires": [{"kind": "point_house", "point": "Venus"}],
    }
    kept, drop = _ground_one(venus_h8, chart)
    assert kept, f"Venus placidus h8 must be kept ({drop})"
    print("test_4_true_positive_survival: PASS")


# ---------------------------------------------------------------------------
# Test 5 — dependency drop by gate C with reason unsatisfiable: native_gender
# ---------------------------------------------------------------------------

def test_5_dependency_drop():
    chart = _load_chart()
    # A record that PASSES gate B (Venus in Taurus, true of chart) but carries a
    # native_gender dependency the chart cannot satisfy -> must drop at gate C.
    rec = {
        "principle_id": "synthetic-gender-dependent",
        "domain": "natal", "tradition": "modern",
        "rule": "x", "judgment": "y", "conditions": ["sex of native"],
        "about": {
            "factor_type": "planet_in_sign", "point": "Venus", "sign": "Taurus",
            "extraction_confidence": "high", "extraction_source": "id_parse",
        },
        "requires": [
            {"kind": "point_sign", "point": "Venus"},
            {"kind": "native_gender"},
        ],
    }
    kept, drop = _ground_one(rec, chart)
    assert not kept, "gender-dependent record must be dropped"
    assert drop.gate == "C"
    assert drop.reason == "unsatisfiable: native_gender", drop.reason
    print(f"test_5_dependency_drop: PASS -> {drop.reason}")


# ---------------------------------------------------------------------------
# Test 6 — unclassified safety: never reaches Layer 3
# ---------------------------------------------------------------------------

def test_6_unclassified_safety():
    chart = _load_chart()
    idx = _load_grounded()
    # Every natal unclassified record must be dropped at gate B.
    natal_unclassified = [
        r for r in idx.values()
        if r.get("domain") == "natal"
        and r["about"]["factor_type"] == "unclassified"
    ]
    assert natal_unclassified, "expected some unclassified natal records to test"
    res = ground(natal_unclassified, chart, reading="natal")
    assert len(res.kept) == 0, "no unclassified record may reach Layer 3"
    assert all(d.gate == "B" for d in res.drops)
    # And the full run: zero unclassified in the kept set.
    full = _grounded_list()
    res_full = ground(full, chart, reading="natal")
    assert all(r["about"]["factor_type"] != "unclassified" for r in res_full.kept)
    print(f"test_6_unclassified_safety: PASS "
          f"({len(natal_unclassified)} unclassified, all dropped)")


# ---------------------------------------------------------------------------
# Test 7 — FK casing rejected at schema validation (not silently accepted)
# ---------------------------------------------------------------------------

def test_7_fk_casing():
    bad = {
        "factor_type": "planet_in_sign", "point": "Venus", "sign": "taurus",
        "extraction_confidence": "medium", "extraction_source": "llm",
    }
    ok, errs = validate_about(bad)
    assert not ok, "lowercase 'taurus' must fail FK validation"
    # Builtin path says "sign off-vocabulary"; jsonschema says "is not one of".
    assert any(
        "sign off-vocabulary" in e or ("taurus" in e and "not one of" in e)
        for e in errs
    ), errs

    good = dict(bad, sign="Taurus")
    ok, errs = validate_about(good)
    assert ok, f"correctly-cased 'Taurus' must pass: {errs}"
    print("test_7_fk_casing: PASS (lowercase rejected, correct casing accepted)")


# ---------------------------------------------------------------------------
# Test 8 — house-system correctness: whole_sign reconciles vs whole_sign sector
# ---------------------------------------------------------------------------

def test_8_house_system_correctness():
    chart = _load_chart()
    # Pick a point whose placidus and whole_sign houses DIFFER. On this chart the
    # North Node is placidus 4 / whole_sign 5 (Moon is placidus 5 / whole_sign 6).
    pts = {p["name"]: p for p in chart["points"]}
    nn = pts["North Node"]
    assert nn["sector"]["placidus"] != nn["sector"]["whole_sign"], \
        "fixture requires divergent house systems"
    ws = nn["sector"]["whole_sign"]   # 5
    pl = nn["sector"]["placidus"]     # 4

    base = {
        "principle_id": "fixture-node-house", "domain": "natal",
        "tradition": "traditional", "rule": "x", "judgment": "y",
        "conditions": [], "requires": [{"kind": "point_house", "point": "North Node"}],
    }

    # whole_sign about with the whole_sign house -> KEEP
    rec_ws = copy.deepcopy(base)
    rec_ws["about"] = {
        "factor_type": "node", "point": "North Node", "house": ws,
        "house_system": "whole_sign",
        "extraction_confidence": "high", "extraction_source": "id_parse",
    }
    kept, drop = _ground_one(rec_ws, chart)
    assert kept, f"whole_sign h{ws} must reconcile against whole_sign sector ({drop})"

    # whole_sign about but with the PLACIDUS house number -> DROP (wrong system)
    rec_wrong = copy.deepcopy(rec_ws)
    rec_wrong["about"]["house"] = pl
    kept, drop = _ground_one(rec_wrong, chart)
    assert not kept and drop.gate == "B", \
        "using placidus number under whole_sign system must fail"

    # placidus about with the placidus house -> KEEP (correct other system)
    rec_pl = copy.deepcopy(base)
    rec_pl["about"] = {
        "factor_type": "node", "point": "North Node", "house": pl,
        "house_system": "placidus",
        "extraction_confidence": "high", "extraction_source": "id_parse",
    }
    kept, drop = _ground_one(rec_pl, chart)
    assert kept, f"placidus h{pl} must reconcile against placidus sector ({drop})"
    print("test_8_house_system_correctness: PASS "
          f"(whole_sign {ws} vs placidus {pl} disambiguated)")


# ---------------------------------------------------------------------------
# Aggregate: the observed 34-record retrieval output becomes trustworthy
# ---------------------------------------------------------------------------

def test_9_house_domain_survival():
    """Rev 2: generic significations are house_domain and KEPT (pass on
    existence). Guard: the same record mistyped planet_in_house with a null
    house must raise INVARIANT_VIOLATION, never a silent drop (spec §7.9)."""
    chart = _load_chart()
    idx = _load_grounded()
    for pid in ("sun-house-vitality-domain", "venus-house-pleasure-domain",
                "third-house-significations"):
        rec = idx[pid]
        assert rec["about"]["factor_type"] == "house_domain"
        kept, drop = _ground_one(rec, chart)
        assert kept, f"{pid} (house_domain) must be kept ({drop})"
    # the whole planet×house matrix survives
    matrix = [r for r in idx.values()
              if r["about"]["factor_type"] == "house_domain"
              and r.get("domain") == "natal"]
    res = ground(matrix, chart, reading="natal")
    assert len(res.kept) == len(matrix), "all house_domain records must survive"

    # Guard: mistyped planet_in_house with null house -> INVARIANT_VIOLATION drop
    bad = {
        "principle_id": "mistyped-domain", "domain": "natal", "tradition": "modern",
        "rule": "x", "judgment": "y", "conditions": [],
        "about": {"factor_type": "planet_in_house", "point": "Sun",
                  "house_system": "placidus",
                  "extraction_confidence": "medium", "extraction_source": "llm"},
        "requires": [],
    }
    res = ground([bad], chart, reading="natal")
    assert len(res.kept) == 0
    assert res.drops[0].gate == "INVARIANT_VIOLATION", res.drops[0].gate
    assert "mismatch" not in res.drops[0].reason.lower(), \
        "must not log a None-mismatch"
    print(f"test_9_house_domain_survival: PASS ({len(matrix)} domain records kept)")


def test_10_house_lord_relative():
    """Rev 2: lord-of-house reconciliation via sector_rulers. Asc-lord (whole-sign
    h1=Libra) is Venus, in whole-sign h8. 'lord of 1st in 8th' kept; 'in 11th'
    dropped, reason naming the resolved lord + actual house (spec §7.10)."""
    chart = _load_chart()
    idx = _load_grounded()

    keep = idx["lord-asc-in-8th-natal"]
    kept, drop = _ground_one(keep, chart)
    assert kept, f"lord of 1st in 8th must be kept (Venus is in whole-sign h8): {drop}"

    drop_rec = idx["lord-asc-in-11th-natal"]
    kept, drop = _ground_one(drop_rec, chart)
    assert not kept, "lord of 1st in 11th must be dropped (Venus is in h8, not 11)"
    assert drop.gate == "B"
    assert "Venus" in drop.reason and "11" in drop.reason, drop.reason
    print(f"test_10_house_lord_relative: PASS -> {drop.reason}")


def test_11_invariant_tripwire():
    """Rev 2: a reconcilable factor_type with a null required field is a
    build-blocking error, and the gate flags INVARIANT_VIOLATION rather than a
    None-mismatch (spec §7.11). Uses planet_in_house with a null house (element
    was retired, so it can no longer serve as the fixture)."""
    chart = _load_chart()
    bad_about = {"factor_type": "planet_in_house", "point": "Sun",
                 "house_system": "placidus",
                 "extraction_confidence": "medium", "extraction_source": "llm"}

    # §2.3 validation flags it as build-blocking
    assert invariant_violation(bad_about) is not None
    report = validate_invariants([{
        "principle_id": "seed-bad-house", "domain": "natal", "about": bad_about,
    }])
    assert report["build_blocking"] >= 1 and not report["passes"]

    rec = {"principle_id": "seed-bad-house", "domain": "natal",
           "tradition": "modern", "rule": "x", "judgment": "y",
           "conditions": [], "about": bad_about, "requires": []}

    # non-strict gate: distinct INVARIANT_VIOLATION drop, not a None-mismatch
    res = ground([rec], chart, reading="natal")
    assert res.drops[0].gate == "INVARIANT_VIOLATION"
    assert "None" not in res.drops[0].reason and "mismatch" not in res.drops[0].reason.lower()

    # strict gate: raises
    raised = False
    try:
        ground([rec], chart, reading="natal", strict_invariants=True)
    except InvariantViolation:
        raised = True
    assert raised, "strict_invariants must raise InvariantViolation"
    print("test_11_invariant_tripwire: PASS (flagged, raised, no None-mismatch)")


def test_aggregate_run():
    """A sanity check that on the full corpus the gate keeps genuine natal
    delineations (incl. house_domain + house_lord_relative) and drops the
    leaks/wrong-house/false-ascendant. Corpus-wide invariant count is zero."""
    chart = _load_chart()
    full = _grounded_list()

    # corpus-wide: zero reconcilable-with-null-field records (spec §7 footer)
    val = validate_invariants(full)
    assert val["reconcilable_with_null_field"] == 0, val["reconcilable_with_null_field"]

    # Honor each record's declared house_system so whole_sign node/house
    # principles bundle under their own system (production default is placidus).
    res = ground(full, chart, reading="natal", house_policy=None)
    kept_ids = {r["principle_id"] for r in res.kept}
    # keeps
    assert "mars-sign-aries-delineation" in kept_ids
    assert "moon-sign-pisces-delineation" in kept_ids
    assert "sun-house-vitality-domain" in kept_ids        # house_domain
    assert "lord-asc-in-8th-natal" in kept_ids            # house_lord_relative
    assert "North Node in whole_sign house 5" in res.bundles
    # drops
    assert "north-node-7th-women" not in kept_ids
    assert "asc-scorpio-mars-primary-ruler" not in kept_ids
    assert "lord-asc-in-11th-natal" not in kept_ids
    # no non-natal, no unclassified, no invariant violations among kept
    assert all(r["domain"] == "natal" for r in res.kept)
    assert all(r["about"]["factor_type"] != "unclassified" for r in res.kept)
    assert not any(d.gate == "INVARIANT_VIOLATION" for d in res.drops)
    print(f"test_12_aggregate_run: PASS (kept={len(res.kept)}, "
          f"dropped={len(res.drops)})")


def test_0_backfill_roundtrip():
    """Backfill is additive and schema-valid: original fields untouched, every
    record gets a valid about + requires (spec §8)."""
    with open(CLEAN, encoding="utf-8") as fh:
        records = json.load(fh)
    sample = records[:50]
    grounded = backfill(copy.deepcopy(sample), _NullExtractor())
    for orig, g in zip(sample, grounded):
        for k in ("principle_id", "rule", "judgment", "conditions", "domain"):
            assert g.get(k) == orig.get(k), f"original field {k} changed"
        assert "about" in g and "requires" in g
        ok, errs = validate_about(g["about"])
        assert ok, f"{g['principle_id']}: invalid about {errs}"
    print(f"test_0_backfill_roundtrip: PASS ({len(grounded)} records, additive)")


# ===========================================================================
# Rev-3 backfill-integrity tests (run on the dataset, not a chart) — §7.12-16
# ===========================================================================

# Clean-ID records that determinism must capture (never unclassified, §7.12).
_CLEAN_ID_SAMPLES = {
    "mars-sign-aries-delineation": "planet_in_sign",
    "venus-sign-aquarius-delineation": "planet_in_sign",
    "sun-house-vitality-domain": "house_domain",
    "third-house-significations": "house_domain",
    "lord-asc-in-8th-natal": "house_lord_relative",
    "saturn-in-own-domicile-natal": "dignity",
}


def test_12_deterministic_lock():
    """§7.12: every Tier-1 signal record is captured deterministically with the
    expected factor_type and source, and is never unclassified."""
    idx = _load_grounded()
    for pid, expected_ft in _CLEAN_ID_SAMPLES.items():
        rec = idx.get(pid)
        assert rec is not None, f"missing fixture {pid}"
        about = rec["about"]
        assert about["factor_type"] == expected_ft, \
            f"{pid}: {about['factor_type']} != {expected_ft}"
        assert about["extraction_source"] == "deterministic", \
            f"{pid}: source {about['extraction_source']} (must be deterministic)"
        assert about["factor_type"] != "unclassified"
    print(f"test_12_deterministic_lock: PASS ({len(_CLEAN_ID_SAMPLES)} locked)")


def test_e1_element_retired():
    """`element` is a RETIRED factor_type: it is gone from the enum and schema,
    no record carries it, and the element-template records are re-typed —
    single-planet significations -> house_domain (point only); relational /
    multi-factor -> general (no subject fields) — each tagged reclassified_from
    'element' + a reclassify_rule."""
    from grounding_vocab import FACTOR_TYPES
    # retired from the type system
    assert "element" not in FACTOR_TYPES
    ok, errs = validate_about({"factor_type": "element", "point": "Sun",
                               "extraction_confidence": "high",
                               "extraction_source": "deterministic"})
    # Builtin path says "off-vocabulary"; jsonschema says "is not one of".
    assert not ok and any(
        "off-vocabulary" in e or ("element" in e and "not one of" in e)
        for e in errs
    ), errs
    idx = _load_grounded()
    expect_house_domain = {
        "sun-element-motivation-recharge", "moon-element-instinct-security",
        "mercury-element-cognition-communication", "venus-element-affection-reception",
        "mars-element-assertion-physical-energy", "jupiter-element-faith-opportunity",
        "saturn-element-blockage-challenge",
    }
    expect_general = {
        "asc-sun-element-comparison", "sun-moon-element-compatibility",
        "ascendant-sign-element-compatibility-with-sun", "north-node-4th-element-sign",
        "saturn-jupiter-conjunction-sign-element-effects",
        "mars-lord-of-year-by-sign-element",
    }
    for pid in expect_house_domain:
        a = idx[pid]["about"]
        assert a["factor_type"] == "house_domain", f"{pid}: {a['factor_type']}"
        assert a.get("point") and "element" not in a and "sign" not in a, a
        assert idx[pid]["reclassified_from"] == "element"
        assert idx[pid]["reclassify_rule"] == "element_to_house_domain"
    for pid in expect_general:
        a = idx[pid]["about"]
        assert a["factor_type"] == "general", f"{pid}: {a['factor_type']}"
        assert set(a) == {"factor_type", "extraction_confidence", "extraction_source"}, a
        assert idx[pid]["reclassified_from"] == "element"
        assert idx[pid]["reclassify_rule"] == "element_to_general"
    # NO record carries factor_type element anywhere in the corpus
    survivors = [r["principle_id"] for r in _grounded_list()
                 if r["about"]["factor_type"] == "element"]
    assert not survivors, survivors
    # safety net: if an element record reappears, reclassify routes it away
    stray = {"principle_id": "mars-element-x", "domain": "natal",
             "about": {"factor_type": "element", "point": "Mars",
                       "extraction_confidence": "high",
                       "extraction_source": "deterministic"}}
    routed, rule = reclassify_record(stray, load_rules())
    assert routed["about"]["factor_type"] == "house_domain" and rule
    print("test_e1_element_retired: PASS (retired; 7 house_domain + 6 general)")


def test_13_no_manual_dump():
    """§7.13: no record is auto-tagged `manual`; any `manual` needs reviewer +
    reviewed_at (else build-blocking)."""
    grounded = _grounded_list()
    bad = [r["principle_id"] for r in grounded
           if r["about"].get("extraction_source") == "manual"
           and not (r["about"].get("reviewer") and r["about"].get("reviewed_at"))]
    assert not bad, f"{len(bad)} manual records without reviewer"
    # and the validator would block such a record
    seeded = {"principle_id": "x", "domain": "natal",
              "about": {"factor_type": "general", "extraction_confidence": "low",
                        "extraction_source": "manual"}}
    rep = validate_invariants([seeded])
    assert seeded["principle_id"] in rep["manual_without_reviewer"]
    assert not rep["passes"]
    print("test_13_no_manual_dump: PASS")


def test_14_unclassified_earned():
    """§7.14: every unclassified record carries an enum reason; a bare or
    `hard`/`unclear` reason fails validation."""
    grounded = _grounded_list()
    for r in grounded:
        if r["about"]["factor_type"] == "unclassified":
            assert r["about"].get("unclassified_reason"), \
                f"{r['principle_id']} unclassified with no reason"
    ok1, _ = validate_about({"factor_type": "unclassified",
                             "extraction_confidence": "low",
                             "extraction_source": "llm"})
    assert not ok1, "unclassified with no reason must fail"
    ok2, _ = validate_about({"factor_type": "unclassified",
                             "unclassified_reason": "hard",
                             "extraction_confidence": "low",
                             "extraction_source": "llm"})
    assert not ok2, "reason 'hard' is off-vocabulary and must fail"
    print("test_14_unclassified_earned: PASS")


def test_15_floors_and_structural_ceiling():
    """§7.15 + RECLASSIFY §7: each natal floor is met by the deterministic tier
    (re-capture can only raise them), and the hard count ceiling is replaced by
    the STRUCTURAL residual check — every unclassified is honest."""
    grounded = _grounded_list()
    val = validate_invariants(grounded)
    for cat, floor in BUILD_FLOORS.items():
        have = val["natal_floors"][cat]["have"]
        assert have >= floor, f"floor {cat}: {have} < {floor}"
    sc = val["structural_residual_check"]
    assert sc["passes"], "structural residual check must pass after reclassify"
    assert val["passes"], "full deterministic+reclassify build must be acceptable"
    print(f"test_15_floors_and_structural_ceiling: PASS "
          f"(floors met; residual unclassified={val['natal_unclassified']} all honest)")


def test_16_rerun_stability():
    """§7.16: two backfill runs over the same input must agree (deterministic
    tier is reproducible); the diff shows no net movement into unclassified."""
    with open(CLEAN, encoding="utf-8") as fh:
        records = json.load(fh)
    run_a = backfill(copy.deepcopy(records), _NullExtractor())
    run_b = backfill(copy.deepcopy(records), _NullExtractor())
    diff = diff_factor_types(run_a, run_b)
    assert diff["changed"] == 0, f"deterministic runs disagree: {diff['changed']}"
    assert diff["net_into_unclassified"] == 0
    assert not diff["build_blocking_event"]
    print("test_16_rerun_stability: PASS (deterministic tier reproducible)")


# ===========================================================================
# RECLASSIFY_SPEC.md §8 — adversarial, count-free
# ===========================================================================

def _clean_records():
    with open(CLEAN, encoding="utf-8") as fh:
        return json.load(fh)


def _backfilled():
    return backfill(copy.deepcopy(_clean_records()), _NullExtractor())


def test_r1_idempotence():
    """§8.1: run twice -> byte-identical output, empty second-run diff."""
    rules = load_rules()
    once, _ = reclassify(_backfilled(), rules)
    twice, log2 = reclassify(copy.deepcopy(once), rules)
    assert json.dumps(once, sort_keys=True) == json.dumps(twice, sort_keys=True)
    print("test_r1_idempotence: PASS (byte-identical on re-run)")


def test_r2_non_destruction():
    """§8.2: every record that is neither `unclassified` nor a value-less
    `element` (the two things the pass is allowed to touch) is byte-identical."""
    base = _backfilled()
    after, _ = reclassify(copy.deepcopy(base), load_rules())
    after_by_id = {r["principle_id"]: r for r in after}
    for r in base:
        about = r["about"]
        touchable = (
            about["factor_type"] == "unclassified"
            or (about["factor_type"] == "element" and about.get("element") is None)
        )
        if not touchable:
            assert json.dumps(r, sort_keys=True) == \
                json.dumps(after_by_id[r["principle_id"]], sort_keys=True), \
                f"{r['principle_id']} was mutated"
    print("test_r2_non_destruction: PASS (only unclassified + element-violations touched)")


def test_r3_recapture_safety():
    """§8.3: no re-captured record has a null required field; none re-captured to a
    specific-value type. Canonical: planet-sign-function-sun -> house_domain."""
    after, _ = reclassify(_backfilled(), load_rules())
    idx = {r["principle_id"]: r for r in after}
    pf = idx["planet-sign-function-sun"]["about"]
    assert pf["factor_type"] == "house_domain", pf
    assert pf.get("point") == "Sun" and "sign" not in pf
    forbidden = {"planet_in_sign", "planet_in_house", "planet_in_sign_and_house",
                 "dignity", "aspect"}
    for r in after:
        if r.get("reclassify_rule") == "1":
            ft = r["about"]["factor_type"]
            assert ft == "house_domain", f"re-capture to {ft} forbidden"
            assert invariant_violation(r["about"]) is None
            assert ft not in forbidden
    print("test_r3_recapture_safety: PASS (template-only, no null fields)")


def test_r4_preservation():
    """§8.4: procedure records carry out_of_scope and stay in the dataset."""
    after, _ = reclassify(_backfilled(), load_rules())
    procs = [r for r in after if r.get("scope_note") == "classical_procedure"]
    assert procs, "expected some procedure records"
    for r in procs:
        assert r.get("out_of_scope") is True
        assert r["about"]["factor_type"] == "unclassified"  # kept, not deleted
    # a known procedure fixture
    idx = {r["principle_id"]: r for r in after}
    assert idx["life-length-hilaj-direction"].get("out_of_scope") is True
    print(f"test_r4_preservation: PASS ({len(procs)} procedures preserved)")


def test_r5_precedence():
    """§8.5: procedure+angle -> route 3 (before 4); recapture+meta -> route 1."""
    rules = load_rules()
    # procedure signal AND an angle/meta signal -> out-of-scope, not general
    proc_and_angle = {
        "principle_id": "hilaj-via-ascendant-ruler", "domain": "natal",
        "tradition": "traditional", "rule": "Direct the hilaj; the ascendant-ruler "
        "matters; any planet within orb.", "judgment": "",
        "about": {"factor_type": "unclassified",
                  "unclassified_reason": "no_subject_in_text",
                  "extraction_confidence": "low", "extraction_source": "llm"},
    }
    _, route = reclassify_record(proc_and_angle, rules)
    assert route == "3", f"procedure+angle must route 3, got {route}"
    # re-capture template AND a meta signal -> re-capture
    recap_and_meta = {
        "principle_id": "planet-sign-function-mars", "domain": "natal",
        "tradition": "modern", "rule": "The sign of Mars signifies its emphasis "
        "and gains in importance.", "judgment": "",
        "about": {"factor_type": "unclassified",
                  "unclassified_reason": "no_subject_in_text",
                  "extraction_confidence": "low", "extraction_source": "llm"},
    }
    new, route = reclassify_record(recap_and_meta, rules)
    assert route == "1" and new["about"]["factor_type"] == "house_domain", route
    print("test_r5_precedence: PASS (3-before-4, 1-first)")


def test_r6_no_hardcoded_counts():
    """§8.6: routing logic contains no hardcoded numeric thresholds."""
    import re as _re
    src = open(os.path.join(HERE, "reclassify.py"), encoding="utf-8").read()
    # strip route-id string literals ("1"/"3"/"4") and group indices, then assert
    # no comparison against an integer literal drives routing.
    offenders = _re.findall(r"(?:>=|<=|==|>|<)\s*\d+", src)
    assert not offenders, f"hardcoded numeric thresholds found: {offenders}"
    print("test_r6_no_hardcoded_counts: PASS (count-free routing)")


def test_r7_honest_residual():
    """§8.7: every remaining unclassified has a valid reason and matches no
    route-1/3/4 signal (structural check)."""
    after, _ = reclassify(_backfilled(), load_rules())
    sc = structural_residual_check(after)
    assert sc["passes"], (sc["unclassified_without_reason"][:5],
                          sc["unclassified_still_route_matchable"][:5])
    print("test_r7_honest_residual: PASS (residual is honest)")


def _run_all():
    tests = [
        test_0_backfill_roundtrip,
        test_1_domain_leak,
        test_2_wrong_house_node,
        test_3_false_ascendant,
        test_4_true_positive_survival,
        test_5_dependency_drop,
        test_6_unclassified_safety,
        test_7_fk_casing,
        test_8_house_system_correctness,
        test_9_house_domain_survival,
        test_10_house_lord_relative,
        test_11_invariant_tripwire,
        test_12_deterministic_lock,
        test_e1_element_retired,
        test_13_no_manual_dump,
        test_14_unclassified_earned,
        test_15_floors_and_structural_ceiling,
        test_16_rerun_stability,
        test_r1_idempotence,
        test_r2_non_destruction,
        test_r3_recapture_safety,
        test_r4_preservation,
        test_r5_precedence,
        test_r6_no_hardcoded_counts,
        test_r7_honest_residual,
        test_aggregate_run,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"{t.__name__}: FAIL -> {e}")
    print("=" * 60)
    print(f"{len(tests) - failed}/{len(tests)} passed")
    return failed


if __name__ == "__main__":
    raise SystemExit(1 if _run_all() else 0)
