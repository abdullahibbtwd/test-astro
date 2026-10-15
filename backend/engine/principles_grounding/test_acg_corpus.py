"""
test_acg_corpus.py — guards C-1..C-9 of docs/acg/ACG_06_CORPUS_DELTA_SPEC.md over the built
ACG corpus (``acg_principles.clean.json`` / ``acg_principles.grounded.json``), plus the
backfill Tier-0 ``acg-*`` branch.

Tests that need the (gitignored, copyright) source text skip when it is absent.

    python -m pytest -q principles_grounding/test_acg_corpus.py
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from collections import Counter

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import extract_acg as ex  # noqa: E402
import finish_acg as fin  # noqa: E402
from backfill import (acg_requires, ground_record, tier0_acg,  # noqa: E402
                      validate_acg_about, validate_acg_requires, _NullExtractor)
from grounding_vocab import FACTOR_TYPES  # noqa: E402

CLEAN = os.path.join(HERE, "acg_principles.clean.json")
GROUNDED = os.path.join(HERE, "acg_principles.grounded.json")
REPORT = os.path.join(HERE, "acg_finish_report.json")

needs_source = pytest.mark.skipif(not os.path.exists(ex.SOURCE),
                                  reason="ACG source text (TXT/, gitignored) not present")
needs_corpus = pytest.mark.skipif(not os.path.exists(GROUNDED),
                                  reason="acg_principles.grounded.json not built yet")


@pytest.fixture(scope="module")
def grounded() -> list[dict]:
    return json.load(open(GROUNDED, encoding="utf-8"))


@pytest.fixture(scope="module")
def clean() -> list[dict]:
    return json.load(open(CLEAN, encoding="utf-8"))


# --- C-1: de-columning -------------------------------------------------------

@needs_source
def test_c1_decolumn_principle_6_contiguous():
    ok, msg = ex.c1_check(ex.decolumned_text("intro"))
    assert ok, msg


def test_c1_decolumn_synthetic_two_columns():
    left = ["6. How Close Do You Have to Be? The closer to the",
            "line, the more pronounced the effects, but some",
            "effects can be felt as far as 700 miles (1,000 kilo-",
            "meters) away. A line passing through a city might",
            "be felt far away, particularly if it were the only",
            "line in that vicinity. On the maps in this book the"]
    right = ["What has happened to them is generally well docu-",
             "mented so that a technique can be judged on the basis",
             "questioned by astrologers. Famous people exhibit",
             "certain advantages as objects for astrological study.",
             "of a known, historical past. And future developments",
             "can continue to be instructive as their lives unfold."]
    page = [f"{a:<66}{b}" for a, b in zip(left, right)]
    split = ex.estimate_split(page)
    lbuf, rbuf = ex.decolumn_page(page, split)
    text = "\n".join(t for t, _ in lbuf) + "\n" + "\n".join(t for t, _ in rbuf)
    ok, msg = ex.c1_check(text)
    assert ok, msg


# --- C-2: fixed ids + planet synopses ------------------------------------------

@needs_corpus
def test_c2_fixed_ids_present(grounded):
    ids = {g["principle_id"] for g in grounded}
    assert len(ex.FIXED_IDS) == 16
    missing = [f for f in ex.FIXED_IDS if f not in ids]
    assert not missing, missing
    for f, (scope, _) in ex.FIXED_IDS.items():
        rec = next(g for g in grounded if g["principle_id"] == f)
        assert rec["acg_scope"] == scope, (f, rec["acg_scope"])


@needs_corpus
def test_c2_planet_general_both_polarities(grounded):
    for p in ex.PLANETS:
        g = [r for r in grounded if r["principle_id"].startswith(f"acg-general-{p}-")]
        pols = {r["polarity"] for r in g}
        assert len(g) >= 2, (p, len(g))
        assert {"supportive", "challenging"} <= pols, (p, pols)
        assert all(r["about"] == {"factor_type": "acg_planet_general", "planet": p.capitalize(),
                                  "extraction_confidence": "high",
                                  "extraction_source": "deterministic"} for r in g)


# --- C-3: verbatim 8-gram guard ------------------------------------------------

@needs_source
@needs_corpus
def test_c3_no_verbatim_8gram(grounded):
    bad = {g["principle_id"]: fin.c3_hits(g)[:2] for g in grounded if fin.c3_hits(g)}
    assert not bad, bad


@needs_source
def test_c3_guard_catches_a_source_sentence():
    probe = {"rule": "Planets don't make things happen; rather, events linked by "
                     "similarity of basic theme seem to cluster together.",
             "judgment": None, "notes": None, "conditions": []}
    assert fin.c3_hits(probe)
    assert not fin.c3_hits({"rule": "Venus on the Descendant draws cooperative partners and "
                                    "pleasant social exchanges into the person's life.",
                            "judgment": None, "notes": None, "conditions": []})


# --- C-4: name guard -----------------------------------------------------------

@needs_source
@needs_corpus
def test_c4_no_names_or_places(grounded):
    bad = {g["principle_id"]: fin.c4_hits(g) for g in grounded if fin.c4_hits(g)}
    assert not bad, bad


@needs_source
def test_c4_guard_controls():
    def hits(text):
        return fin.c4_hits({"rule": text, "judgment": None, "notes": None, "conditions": [],
                            "topic_tags": []})
    assert "Kennedy" in hits("A career like that of Kennedy shows the effect.")
    assert "Jung" in hits("the work of Jung on the unconscious")
    assert "France" in hits("a person who settles in France")
    assert "Denver" in hits("someone who lived in Denver")           # source proper noun
    assert "1929" in hits("after the crash of 1929")                  # dates
    # planet names are never blocked; matching is case-sensitive whole words
    assert hits("Mars and Venus on the MC, Saturn on the IC, the Sun and Moon") == []
    assert hits("a king of the household, a young person, the price of love") == []


@needs_source
def test_c4_runs_without_gazetteer(monkeypatch, tmp_path):
    monkeypatch.setattr(fin, "GAZETTEER", str(tmp_path / "absent.json"))
    fin.blocklist.cache_clear()
    try:
        bl = fin.blocklist()
        assert bl["gazetteer"] is False
        assert "France" in bl["tokens"] and "Kennedy" in bl["tokens"]
    finally:
        fin.blocklist.cache_clear()


# --- C-5: planet/angle validity, no MH -----------------------------------------

@needs_corpus
def test_c5_line_records_valid(grounded):
    planets = {p.capitalize() for p in ex.PLANETS}
    for g in grounded:
        if g["acg_scope"] == "line":
            a = g["about"]
            assert a["factor_type"] == "planet_on_angle"
            assert a["planet"] in planets and a["angle"] in ex.ANGLES
            m = re.match(r"^acg-([a-z]+)-(asc|dsc|mc|ic)-\d{2}$", g["principle_id"])
            assert m and m.group(1) == a["planet"].lower() and m.group(2) == a["angle"].lower()
    blob = json.dumps(grounded, ensure_ascii=False)
    assert not re.search(r"\bMH\b|\bmh\b|-mh-", blob)


# --- C-6: coverage (report only, never blocking) -------------------------------

@needs_corpus
def test_c6_coverage_reported(grounded):
    per = Counter((g["about"]["planet"], g["about"]["angle"]) for g in grounded
                  if g["about"]["factor_type"] == "planet_on_angle")
    below2 = sorted(f"{p.capitalize()}|{a}" for p in ex.PLANETS for a in ex.ANGLES
                    if per.get((p.capitalize(), a), 0) < 2)
    report = json.load(open(REPORT, encoding="utf-8"))
    assert report["guards"]["C-6"]["below_2"] == below2
    assert report["guards"]["C-6"]["blocking"] is False


# --- C-7: ids unique, schema, domain -------------------------------------------

@needs_corpus
def test_c7_ids_schema_domain(grounded, clean):
    import jsonschema
    ids = [g["principle_id"] for g in grounded]
    assert len(ids) == len(set(ids))
    assert [c["principle_id"] for c in clean] == ids
    v = jsonschema.Draft202012Validator(fin.RECORD_SCHEMA)
    for g in grounded:
        errs = [e.message for e in v.iter_errors(g)]
        assert not errs, (g["principle_id"], errs)
        assert g["domain"] == "astrocartography" and g["tradition"] == "modern"
        assert g["source"] == "lewis_guttman_1989"
        ok, e1 = validate_acg_about(g["about"], g["acg_scope"])
        rok, e2 = validate_acg_requires(g["requires"])
        assert ok and rok, (g["principle_id"], e1, e2)
        assert list(g)[:len(fin.CLEAN_FIELDS)] == list(fin.CLEAN_FIELDS)
    for c in clean:
        assert "about" not in c and "requires" not in c


@needs_corpus
def test_c7_sensitivity_flags_hard_topics(grounded):
    for g in grounded:
        blob = " ".join(fin.record_text_fields(g))
        if ex._HIGH_RE.search(blob):
            assert g["sensitivity"] == "high", g["principle_id"]


# --- C-8: idempotence + sidecar ----------------------------------------------------

@needs_source
@needs_corpus
def test_c8_rebuild_is_byte_identical(clean):
    log = {"dropped_nonfixed_method": 0, "duplicate_fixed_dropped": 0, "reparaphrased": 0}
    c2, g2 = fin.build(clean, None, log)
    assert fin._dump(c2) == open(CLEAN, encoding="utf-8").read()
    assert fin._dump(g2) == open(GROUNDED, encoding="utf-8").read()
    assert log["reparaphrased"] == 0


@needs_corpus
def test_sha256_sidecar_matches():
    # the .sha256 sidecar is a local build artifact (gitignored: **/*.sha256), so a
    # fresh clone has none; the check only applies where the build ran
    if not os.path.exists(GROUNDED + ".sha256"):
        pytest.skip("no local .sha256 sidecar (not tracked in git)")
    payload = open(GROUNDED, "rb").read()
    first = open(GROUNDED + ".sha256", encoding="utf-8").readline().split()
    assert first == [hashlib.sha256(payload).hexdigest(), "acg_principles.grounded.json"]


# --- C-9: goal tags (07 §5) ----------------------------------------------------------

GOAL_SCOPES = ("line", "planet_general", "angle_frame", "paran")    # tagged (07 §5, 10 §5)
LINE_GOAL_SCOPES = ("line", "planet_general", "angle_frame")        # soft-threshold basis


@needs_corpus
def test_c9_goal_tags(grounded, clean):
    """Hard: every record in the tagged scopes (line, planet_general, angle_frame, paran)
    carries a valid goal_effects (possibly {}), other scopes carry none, and clean mirrors
    grounded. Report-only (07 §5, Radul decides): >= 80% of line records have >= 1 goal; each
    of the 11 goals on >= 15 line/planet_general/angle_frame records. Paran coverage (10 §5)
    is reported, never enforced."""
    import warnings
    sys.path.insert(0, os.path.join(ROOT, "Astrocartography"))
    from acg_constants import GOAL_ORDER, GOAL_POLARITIES, MAX_GOALS_PER_RECORD
    for g in grounded:
        if g["acg_scope"] in GOAL_SCOPES:
            ge = g.get("goal_effects")
            assert isinstance(ge, dict), g["principle_id"]
            assert len(ge) <= MAX_GOALS_PER_RECORD, g["principle_id"]
            assert set(ge) <= set(GOAL_ORDER), (g["principle_id"], ge)
            assert set(ge.values()) <= set(GOAL_POLARITIES), (g["principle_id"], ge)
        else:
            assert "goal_effects" not in g, g["principle_id"]
    assert [c.get("goal_effects") for c in clean] == [g.get("goal_effects") for g in grounded]

    lines = [g for g in grounded if g["acg_scope"] == "line"]
    share = sum(1 for g in lines if g["goal_effects"]) / max(1, len(lines))
    per_goal = Counter(k for g in grounded if g["acg_scope"] in LINE_GOAL_SCOPES
                       for k in g["goal_effects"])
    parans = [g for g in grounded if g["acg_scope"] == "paran"
              and (g.get("about") or {}).get("factor_type") == "acg_paran"]
    par_share = sum(1 for g in parans if g["goal_effects"]) / max(1, len(parans))
    par_goal = Counter(k for g in parans for k in g["goal_effects"])
    below = {k: per_goal.get(k, 0) for k in GOAL_ORDER if per_goal.get(k, 0) < 15}
    msg = (f"C-9: line records with >=1 goal {share:.1%} (target >= 80%); "
           f"records per goal {dict((k, per_goal.get(k, 0)) for k in GOAL_ORDER)}; "
           f"goals below 15: {below or 'none'}")
    print(msg)
    print(f"C-9 (report only): paran pair records {len(parans)}, with >=1 goal "
          f"{par_share:.1%}; paran records per goal "
          f"{dict((k, par_goal.get(k, 0)) for k in GOAL_ORDER)}")
    if share < 0.80 or below:
        warnings.warn("C-9 threshold missed (report only, not blocking): " + msg)


# --- Tier-0 backfill branch --------------------------------------------------------

def _rec(pid, scope, conditions=None):
    return {"principle_id": pid, "acg_scope": scope, "conditions": conditions or [],
            "domain": "astrocartography", "rule": "x" * 40}


def test_tier0_about_shapes():
    base = {"extraction_confidence": "high", "extraction_source": "deterministic"}
    assert tier0_acg(_rec("acg-venus-dsc-03", "line")) == \
        {"factor_type": "planet_on_angle", "planet": "Venus", "angle": "DSC", **base}
    assert tier0_acg(_rec("acg-angle-mc", "angle_frame")) == \
        {"factor_type": "acg_angle_frame", "angle": "MC", **base}
    assert tier0_acg(_rec("acg-general-saturn-02", "planet_general")) == \
        {"factor_type": "acg_planet_general", "planet": "Saturn", **base}
    assert tier0_acg(_rec("acg-method-orb-distance", "method")) == \
        {"factor_type": "acg_method", "slug": "orb-distance", **base}
    assert tier0_acg(_rec("acg-paran-mars-jupiter-01", "paran"))["planets"] == \
        ["Jupiter", "Mars"]
    assert tier0_acg(_rec("acg-zenith-04", "zenith"))["slug"] == "zenith-04"
    assert tier0_acg(_rec("acg-mundane-07", "mundane")) == {"factor_type": "acg_mundane", **base}
    with pytest.raises(ValueError):
        tier0_acg(_rec("acg-venus-mh-01", "line"))


def test_tier0_requires_mapping():
    conds = [{"natal_sign": {"point": "Venus", "sign": "Libra"}},
             {"natal_aspect": {"point": "Mars", "other": "Saturn", "aspect": "square"}},
             {"natal_aspect": {"point": "Mars", "other": "Saturn"}},
             {"natal_retrograde": {"point": "Mercury"}},
             {"natal_dignity": {"point": "Saturn", "dignity": "exaltation"}},
             {"relocated_house": {"point": "Moon", "house": 10}},
             {"relocated_angular": {"point": "Pluto"}},
             {"text": "when the person is under a heavy transit"},
             {"natal_sign": {"point": "Venus", "sign": "Nowhere"}}]
    req = acg_requires(_rec("acg-venus-dsc-01", "line", conds))
    assert req == [
        {"kind": "natal_point_sign", "point": "Venus", "sign": "Libra"},
        {"kind": "natal_point_aspect", "point": "Mars", "other": "Saturn", "aspect": "square"},
        {"kind": "natal_point_aspect", "point": "Mars", "other": "Saturn"},
        {"kind": "natal_point_retrograde", "point": "Mercury"},
        {"kind": "natal_point_dignity", "point": "Saturn", "dignity": "exaltation"},
        {"kind": "relocated_point_house", "point": "Moon", "house": 10},
        {"kind": "relocated_point_angular", "point": "Pluto"},
        {"kind": "unsupported", "text": "when the person is under a heavy transit"},
        {"kind": "unsupported",
         "text": '{"natal_sign": {"point": "Venus", "sign": "Nowhere"}}'},
    ]
    assert validate_acg_requires(req)[0]
    assert acg_requires(_rec("acg-venus-dsc-01", "line")) == []


def test_tier0_only_for_acg_ids():
    # the ACG vocab never leaks into the main schema, and a non-acg record keeps the
    # main cascade (its about is a main-vocab factor type)
    for ft in ("planet_on_angle", "acg_angle_frame", "acg_planet_general", "acg_method",
               "acg_paran", "acg_mundane"):
        assert ft not in FACTOR_TYPES
    rec = {"principle_id": "venus-7th-harmonious-partnerships", "domain": "natal",
           "topic_tags": ["Venus", "7th house"], "rule": "Venus in the 7th house ...",
           "conditions": {"planet": "Venus", "house": 7}, "judgment": None,
           "attribution_in_text": None, "notes": None, "tradition": "modern"}
    out = ground_record(rec, _NullExtractor())
    assert out["about"]["factor_type"] == "planet_in_house"
    assert out["requires"] and all(r["kind"] in ("point_house", "other") for r in out["requires"])


def test_acg_corpus_is_separate_from_main_corpus():
    main = os.path.join(HERE, "all_principles.grounded.json")
    if not os.path.exists(main):
        pytest.skip("main corpus absent")
    ids = [r["principle_id"] for r in json.load(open(main, encoding="utf-8"))]
    assert not any(i.startswith("acg-") for i in ids)
