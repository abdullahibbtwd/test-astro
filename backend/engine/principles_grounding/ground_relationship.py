#!/usr/bin/env python3
"""
ground_relationship.py — the two-chart (synastry) grounding gate.

Layer-2 exit contract for a RELATIONSHIP reading. Takes the combined relationship
corpus (all `domain: relationship`, each record carrying a `synastry` block) and a
PAIR of charts (A, B), and emits only the principles true of this couple —
person-attributed, deduplicated, routed, and re-derivable.

Implements SYNASTRY_GROUNDING_FIXES.md A–E:
  A  role binding      — bind corpus person_a/person_b roles to REAL persons per
                         match direction; emit `bound` + `bound_statement` (no
                         literal "person A/B" leaks).
  B  dedup by fact-key — collapse records grounding to the same physical fact,
                         keeping a survivor and an audit `superseded` list.
  C  route not dump    — planet_role -> per-person placements; compatibility ->
                         match element/modality balance; general -> stance allowlist.
  D  echo points       — every `matched` entry names its concrete point(s)+person(s).
  E  exit invariants   — halt on: unre-derivable fact, duplicate fact-key, A/B leak,
                         un-allowlisted framing, or a drop without an enum reason.

Cross-chart aspect/overlay math mirrors d_layer/compute_chart.py verbatim.
Reception is explicitly out of scope (see the spec).

Run
---
    python ground_relationship.py --chart-a A.json --chart-b B.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from ground import _gate_b, _point_index

# --------------------------------------------------------------------------- #
# Aspect conventions — verbatim from d_layer/compute_chart.py
# --------------------------------------------------------------------------- #
MODERN_ASPECTS = {
    "conjunction": (0, 8), "sextile": (60, 6), "square": (90, 8),
    "trine": (120, 8), "opposition": (180, 8),
}
SIGN_DISTANCE_ASPECT = {0: "conjunction", 2: "sextile", 3: "square",
                        4: "trine", 6: "opposition"}
CLASSICAL_SEVEN = {"Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"}
_TRADITION_SCHEME = {"modern": "modern", "traditional": "whole_sign"}
_RELATIONSHIP_DOMAINS = {"relationship"}

# points used for element/modality balance (planets + angles)
_BALANCE_PLANETS = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter",
                    "Saturn", "Uranus", "Neptune", "Pluto")
SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
_ELEMENT = {s: e for e, group in {
    "fire": ("Aries", "Leo", "Sagittarius"), "earth": ("Taurus", "Virgo", "Capricorn"),
    "air": ("Gemini", "Libra", "Aquarius"), "water": ("Cancer", "Scorpio", "Pisces"),
}.items() for s in group}
_MODALITY = {s: m for m, group in {
    "cardinal": ("Aries", "Cancer", "Libra", "Capricorn"),
    "fixed": ("Taurus", "Leo", "Scorpio", "Aquarius"),
    "mutable": ("Gemini", "Virgo", "Sagittarius", "Pisces"),
}.items() for s in group}

# FIX C — genuine interpretive-stance `general` principles (the ONLY records that
# may enter `framing`). Editable allowlist, kept small (spec: <= ~12).
STANCE_ALLOWLIST = {
    "syn-horoscopic-comparison-scope",
    "syn-sun-sign-only-insufficient",
    "syn-planet-position-five-factors",
    "syn-two-major-areas-aspects-and-overlays",
    "syn-natal-strength-governs-comparative-significance",
    "syn-relationship-type-determines-planet-priority",
    "syn-orb-allowances-for-cross-chart-aspects",
    "syn-favorable-aspects-insufficient-without-psychological-compatibility",
    "syn-rule-natal-chart-strength-limits-comparative-influence",
    "syn-house-comparison-three-methods",
    "syn-house-overlay-interpretation-basis",
    "syn-rule-evolutionary-level-compatibility",
}

# FIX E/F + reception — closed drop-reason enum.
DROP_REASONS = {"no_matching_fact", "unbindable_role", "factors_mismatch",
                "not_on_stance_allowlist", "superseded_by_fact_key",
                "factor_below_threshold", "reception_no_matching_fact"}

# --- Reception (RECEPTION_BUILD.md) — dignity lords & significator classes ----
# Exaltation lord per sign index (the one dignity not carried in `classifications`).
EXALTATION_LORD = {0: "Sun", 1: "Moon", 5: "Mercury", 11: "Venus",
                   9: "Mars", 3: "Jupiter", 6: "Saturn"}
GRADE_WEIGHT = {"domicile": 1.0, "exaltation": 0.9, "triplicity": 0.6,
                "bound": 0.4, "face": 0.2}
_GRADES = ("domicile", "exaltation", "triplicity", "bound", "face")
PERSONAL_SIGNIFICATORS = ("Sun", "Moon", "Venus", "Mars", "Mercury")
LUMINARIES = {"Sun", "Moon"}
RECEIVER_CLASS = {"benefic": {"Venus", "Jupiter"},
                  "malefic": {"Mars", "Saturn"},
                  "luminary": {"Sun", "Moon"}}


class RelInvariantViolation(Exception):
    """Exit-invariant breach (SYNASTRY_GROUNDING_FIXES.md §E). Halts the build."""


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #

def _norm360(x: float) -> float:
    return x % 360.0


def _angular_sep(a: float, b: float) -> float:
    d = abs(_norm360(a) - _norm360(b)) % 360.0
    return d if d <= 180 else 360 - d


def _house_of(lon: float, cusps: list) -> int:
    lon = _norm360(lon)
    for i in range(12):
        start = _norm360(cusps[i])
        span = _norm360(_norm360(cusps[(i + 1) % 12]) - start)
        if _norm360(lon - start) < span:
            return i + 1
    return 12


def _resolve_point(chart: dict, pts: dict[str, dict], name: str) -> Optional[dict]:
    if name in pts:
        return pts[name]
    axes = chart.get("axes") or {}
    if name in ("Ascendant", "Asc"):
        a = axes.get("ascendant")
        return dict(a, name="Ascendant", speed=0.0) if a else None
    if name in ("Midheaven", "MC"):
        m = axes.get("mc")
        return dict(m, name="Midheaven", speed=0.0) if m else None
    return None


def _aspect_holds(pa: dict, pb: dict, aspect: str, scheme: str) -> tuple[bool, dict]:
    if scheme == "whole_sign":
        if pa.get("name") not in CLASSICAL_SEVEN or pb.get("name") not in CLASSICAL_SEVEN:
            return False, {}
        dist = abs(pa["sign_index"] - pb["sign_index"])
        dist = min(dist, 12 - dist)
        return (SIGN_DISTANCE_ASPECT.get(dist) == aspect), {"sign_distance": dist}
    angle, orb_allow = MODERN_ASPECTS[aspect]
    sep = _angular_sep(pa["longitude"], pb["longitude"])
    delta = abs(sep - angle)
    return (delta <= orb_allow), {"orb": round(delta, 3), "separation": round(sep, 3)}


# --------------------------------------------------------------------------- #
# FIX A — bind the corpus person_a/person_b roles to the resolved persons.
# For A>B (corpus role A == real A) nothing changes. For B>A we swap A<->B in the
# rule text. The corpus rules use "person A/B", possessive "A's/B's", and bare
# subject "A"/"B" — but bare "A" also collides with the English article
# ("A square between…"). So on a swap we:
#   - swap "person A/B" and possessives "A's/B's"      (unambiguous)
#   - swap bare "B" -> "A" always                       ("B" is never an article)
#   - swap bare "A" -> "B" only before a verb/modal     (else it's the article)
# The authoritative person binding is the structured `bound`; this only cleans
# the human-readable statement.
# --------------------------------------------------------------------------- #
_APOS = "['’`]"
_PERSON_RE = re.compile(rf"[Pp]erson\s+([AB])\b")
_POSS_RE = re.compile(rf"\b([AB]){_APOS}s\b")
# words that mark a following bare "A"/"B" as a SUBJECT (person), not the article.
_PERSON_VERB_LEAD = {
    "can", "could", "may", "might", "will", "would", "must", "should", "shall",
    "is", "was", "has", "had", "does", "tends", "tend", "becomes", "seeks",
    "wants", "needs", "feels", "sees", "gains", "benefits", "provides", "exerts",
    "helps", "energizes", "energises", "generates", "gives", "brings", "offers",
    "encourages", "supports", "influences", "affects", "dominates", "controls",
    "stimulates", "often", "frequently", "usually", "typically", "generally",
    "tends", "also", "then", "both", "and", "or",
}
_BARE_RE = re.compile(r"\b([AB])\b(\s+)(\w+)?")


def _bind_statement(rule: str, swap: bool) -> str:
    if not rule:
        return rule
    if not swap:
        # identity: corpus A/B already == real A/B, but still strip the literal
        # "person A/B" wrapper so E3 cannot leak it (some rules use that phrasing).
        return _PERSON_RE.sub(lambda m: m.group(1), rule)
    flip = {"A": "B", "B": "A"}
    text = _PERSON_RE.sub(lambda m: flip[m.group(1)], rule)
    text = _POSS_RE.sub(lambda m: f"{flip[m.group(1)]}'s", text)

    def bare(m: re.Match) -> str:
        letter, ws, nxt = m.group(1), m.group(2), m.group(3)
        if letter == "B":                       # never an article -> always person
            return f"A{ws}{nxt or ''}"
        # letter == 'A': swap only if the next word marks it a subject
        if nxt and nxt.lower() in _PERSON_VERB_LEAD:
            return f"B{ws}{nxt}"
        return m.group(0)                        # article "A ..." -> leave

    return _BARE_RE.sub(bare, text)


# --------------------------------------------------------------------------- #
# Result container
# --------------------------------------------------------------------------- #

@dataclass
class RelDrop:
    principle_id: str
    interaction: str
    reason: str            # must be in DROP_REASONS
    detail: str = ""

    def as_dict(self) -> dict:
        return {"principle_id": self.principle_id, "interaction": self.interaction,
                "reason": self.reason, "detail": self.detail}


@dataclass
class RelResult:
    person_a: list[dict] = field(default_factory=list)
    person_b: list[dict] = field(default_factory=list)
    synastry: list[dict] = field(default_factory=list)
    framing: list[dict] = field(default_factory=list)
    drops: list[RelDrop] = field(default_factory=list)

    def payload(self) -> dict:
        def _ctx_split(bucket):
            out = {"universal": 0, "personal": 0, "professional": 0}
            for rec in bucket:
                for c in (rec.get("synastry") or {}).get("contexts", []):
                    if c in out:
                        out[c] += 1
            return out
        return {
            "reading": "relationship",
            "counts": {"person_a": len(self.person_a), "person_b": len(self.person_b),
                       "synastry": len(self.synastry), "framing": len(self.framing),
                       "dropped": len(self.drops),
                       # per-context eligibility tallies (a record tagged both
                       # personal+professional counts in both — not a partition).
                       "contexts": {"synastry": _ctx_split(self.synastry),
                                    "person_a": _ctx_split(self.person_a),
                                    "person_b": _ctx_split(self.person_b)}},
            "person_a": self.person_a, "person_b": self.person_b,
            "synastry": self.synastry, "framing": self.framing,
        }


# --------------------------------------------------------------------------- #
# Per-interaction grounding
# --------------------------------------------------------------------------- #

def _natal_about(syn: dict) -> dict:
    keep = ("factor_type", "point", "sign", "house", "house_system", "dignity",
            "dignity_ruler", "aspect", "ascendant_sign", "subject_house",
            "subject_house_system", "placement_house", "placement_house_system",
            "generational")
    return {k: syn[k] for k in keep if k in syn}


def _placement(chart, pts, point) -> dict:
    p = _resolve_point(chart, pts, point)
    if not p:
        return {}
    out = {"point": point, "sign": p.get("sign")}
    if isinstance(p.get("sector"), dict):
        out["house"] = p["sector"].get("placidus")
    return out


def _ground_natal_relational(rec, cA, pA, cB, pB, result):
    about = _natal_about(rec["synastry"])
    shim = {"principle_id": rec["principle_id"], "about": about,
            "tradition": rec.get("tradition")}
    hit = False
    for person, chart, pts, bucket in (("A", cA, pA, result.person_a),
                                       ("B", cB, pB, result.person_b)):
        ok, _, _ = _gate_b(shim, chart, pts)
        if ok:
            bucket.append({**rec, "bound": {"person": person, **_natal_about(rec["synastry"])}})
            hit = True
    if not hit:
        result.drops.append(RelDrop(rec["principle_id"], "natal_relational",
                                    "no_matching_fact", "subject true of neither chart"))


def _ground_planet_role(rec, cA, pA, cB, pB, result):
    """FIX C: bind a planet's comparative role to each person's real placement."""
    point = rec["synastry"].get("person_a_point")
    if not point:
        result.drops.append(RelDrop(rec["principle_id"], "planet_role",
                                    "unbindable_role", "no person_a_point"))
        return
    bound_any = False
    for person, chart, pts, bucket in (("A", cA, pA, result.person_a),
                                       ("B", cB, pB, result.person_b)):
        pl = _placement(chart, pts, point)
        if pl:
            bucket.append({**rec, "bound": {"person": person, **pl}})
            bound_any = True
    if not bound_any:
        result.drops.append(RelDrop(rec["principle_id"], "planet_role",
                                    "unbindable_role", f"{point} absent from both charts"))


def _mk_overlay(rec, direction, mover_person, mover_point, home_person, home_house, hs):
    swap = (direction == "B>A")
    return {
        **rec,
        "matched": [{"direction": direction, "house_system": hs,
                     "house": home_house, "person": mover_person, "point": mover_point}],
        "bound": {"kind": "overlay", "mover_person": mover_person,
                  "mover_point": mover_point, "home_person": home_person,
                  "home_house": home_house, "house_system": hs},
        "bound_statement": _bind_statement(rec.get("rule", ""), swap),
    }


def _ground_house_overlay(rec, cA, pA, cB, pB, result, candidates):
    syn = rec["synastry"]
    point, house = syn.get("person_a_point"), syn.get("overlay_house")
    hs = syn.get("overlay_house_system", "placidus")
    if not (point and house):
        result.drops.append(RelDrop(rec["principle_id"], "house_overlay",
                                    "unbindable_role", "incomplete overlay subject"))
        return
    cusp_key = "placidus_cusps" if hs == "placidus" else "whole_sign_cusps"
    matched_any = False
    # mover=A/home=B  and  mover=B/home=A
    for direction, mover, mv_chart, mv_pts, home, home_chart in (
        ("A>B", "A", cA, pA, "B", cB), ("B>A", "B", cB, pB, "A", cA)):
        p = _resolve_point(mv_chart, mv_pts, point)
        cusps = (home_chart.get("sectors") or {}).get(cusp_key)
        if p is None or not cusps:
            continue
        if _house_of(p["longitude"], cusps) == house:
            candidates.append(_mk_overlay(rec, direction, mover, point, home, house, hs))
            matched_any = True
    if not matched_any:
        result.drops.append(RelDrop(rec["principle_id"], "house_overlay",
                                    "no_matching_fact",
                                    f"{point} in neither partner's house {house}"))


def _mk_aspect(rec, direction, p1_person, p1_point, p2_person, p2_point, aspect, scheme, fact):
    swap = (direction == "B>A")
    return {
        **rec,
        "matched": [{"direction": direction, "scheme": scheme,
                     "orb": fact.get("orb"), "separation": fact.get("separation"),
                     "a": {"person": p1_person, "point": p1_point},
                     "b": {"person": p2_person, "point": p2_point}}],
        "bound": {"kind": "aspect", "p1_person": p1_person, "p1_point": p1_point,
                  "aspect": aspect, "p2_person": p2_person, "p2_point": p2_point,
                  "scheme": scheme},
        "bound_statement": _bind_statement(rec.get("rule", ""), swap),
    }


def _ground_aspect(rec, cA, pA, cB, pB, result, candidates):
    syn = rec["synastry"]
    a_pt, b_pt, aspect = syn.get("person_a_point"), syn.get("person_b_point"), syn.get("aspect")
    scheme = _TRADITION_SCHEME.get(rec.get("tradition"), "modern")
    if not (a_pt and b_pt and aspect):
        result.drops.append(RelDrop(rec["principle_id"], "aspect", "unbindable_role",
                                    "aspect subject missing a point"))
        return
    matched_any = False
    # direction left=person_a_point owner, right=person_b_point owner
    for direction, p1_person, c1, i1, p2_person, c2, i2 in (
        ("A>B", "A", cA, pA, "B", cB, pB), ("B>A", "B", cB, pB, "A", cA, pA)):
        p1 = _resolve_point(c1, i1, a_pt)
        p2 = _resolve_point(c2, i2, b_pt)
        if p1 is None or p2 is None:
            continue
        ok, fact = _aspect_holds(p1, p2, aspect, scheme)
        if ok:
            candidates.append(_mk_aspect(rec, direction, p1_person, a_pt,
                                         p2_person, b_pt, aspect, scheme, fact))
            matched_any = True
    if not matched_any:
        result.drops.append(RelDrop(rec["principle_id"], "aspect", "no_matching_fact",
                                    f"no {scheme} {aspect} between {a_pt} and {b_pt}"))


# --- compatibility: match `factors` against the POOLED two-chart placement set.
# FIX F (locked): seven classical planets per chart (14 total); angles EXCLUDED.
# sign factor grounds at >= 3 pooled; element/modality bucket at >= 5, or the
# strict single-highest bucket with a >= 2 margin over the next.
_ELEMENTS = ("fire", "earth", "air", "water")
_MODALITIES = ("cardinal", "fixed", "mutable")


def _chart_balance(chart) -> tuple[dict, dict, dict]:
    elem, modal, sign = {}, {}, {}
    for p in chart.get("points", []):
        if p.get("name") in CLASSICAL_SEVEN:          # 7 classical planets, no angles
            s = p.get("sign")
            sign[s] = sign.get(s, 0) + 1
            elem[_ELEMENT[s]] = elem.get(_ELEMENT[s], 0) + 1
            modal[_MODALITY[s]] = modal.get(_MODALITY[s], 0) + 1
    return elem, modal, sign


def _pooled_balance(cA, cB) -> tuple[dict, dict, dict]:
    eA, mA, sA = _chart_balance(cA)
    eB, mB, sB = _chart_balance(cB)
    pool = lambda a, b: {k: a.get(k, 0) + b.get(k, 0) for k in set(a) | set(b)}
    return pool(eA, eB), pool(mA, mB), pool(sA, sB)


def _bucket_present(key: str, counts: dict) -> bool:
    v = counts.get(key, 0)
    if v >= 5:                                        # pooled bucket >= 5 of 14
        return True
    vals = sorted(counts.values(), reverse=True)
    top = vals[0] if vals else 0
    second = vals[1] if len(vals) > 1 else 0
    return v == top and vals.count(top) == 1 and (top - second) >= 2


def _factor_present(factor, elem_c: dict, modal_c: dict, sign_c: dict) -> bool:
    if factor in SIGNS:
        return sign_c.get(factor, 0) >= 3
    fl = str(factor).lower()
    if fl in _ELEMENTS:
        return _bucket_present(fl, elem_c)
    if fl in _MODALITIES:
        return _bucket_present(fl, modal_c)
    return False                                      # abstract factor: unverifiable


def _ground_compatibility(rec, cA, cB, candidates, result):
    factors = rec["synastry"].get("factors") or []
    if not factors:
        result.drops.append(RelDrop(rec["principle_id"], "compatibility",
                                    "factors_mismatch", "no factors"))
        return
    elem_c, modal_c, sign_c = _pooled_balance(cA, cB)
    absent = [f for f in factors if not _factor_present(f, elem_c, modal_c, sign_c)]
    if absent:
        result.drops.append(RelDrop(rec["principle_id"], "compatibility",
                                    "factor_below_threshold",
                                    f"factors {absent} below pooled threshold"))
        return
    candidates.append({
        **rec,
        "matched": [{"kind": "compatibility", "factors": factors,
                     "pooled_elements": elem_c, "pooled_modalities": modal_c,
                     "pooled_signs": {k: v for k, v in sign_c.items() if v}}],
        "bound": {"kind": "compatibility", "factors": factors},
        "bound_statement": _bind_statement(rec.get("rule", ""), swap=False),
    })


# --------------------------------------------------------------------------- #
# RECEPTION — Part A: compute cross_reception facts
# --------------------------------------------------------------------------- #

def _significators(chart: dict, pts: dict[str, dict]) -> dict[str, set]:
    """{planet: {roles}} — personal luminaries/benefics + asc-ruler + 7th-ruler."""
    sig: dict[str, set] = {}
    for p in PERSONAL_SIGNIFICATORS:
        if p in pts:
            sig.setdefault(p, set()).add("personal")
    for lum in LUMINARIES:
        if lum in pts:
            sig.setdefault(lum, set()).add("luminary")
    rulers = (chart.get("sector_rulers") or {}).get("whole_sign") or {}
    asc = (rulers.get("1") or {}).get("ruler")           # domicile ruler of asc sign
    seventh = (rulers.get("7") or {}).get("ruler")       # ...of the descendant sign
    if asc:
        sig.setdefault(asc, set()).add("ascendant_ruler")
    if seventh:
        sig.setdefault(seventh, set()).add("seventh_ruler")
    return sig


def _lord_of(pts: dict[str, dict], planet: str, grade: str) -> Optional[str]:
    """Lord of the sign `planet` occupies, at `grade`, in this chart — reusing the
    planet's own classifications (domicile/triplicity/bound/face are sect- and
    degree-correct) plus the exaltation table."""
    pt = pts.get(planet)
    if not pt:
        return None
    if grade == "exaltation":
        return EXALTATION_LORD.get(pt.get("sign_index"))
    cls = pt.get("classifications") or {}
    return {"domicile": cls.get("sign_ruler"),
            "triplicity": cls.get("triplicity_ruler"),
            "bound": cls.get("bound_ruler"),
            "face": cls.get("face_ruler")}.get(grade)


def compute_reception_facts(cA, pA, cB, pB) -> list[dict]:
    sigA, sigB = _significators(cA, pA), _significators(cB, pB)
    facts: list[dict] = []
    # each ordered pair (received=X, receiver=Y)
    for xchart, xpts, xsig, xp, ychart, ypts, ysig, yp in (
        (cA, pA, sigA, "A", cB, pB, sigB, "B"),
        (cB, pB, sigB, "B", cA, pA, sigA, "A")):
        for P, roles_P in xsig.items():
            pt = xpts.get(P)
            if not pt or not pt.get("classifications"):
                continue
            best: dict[str, dict] = {}          # A.4 — strongest grade per receiver
            for grade in _GRADES:
                L = _lord_of(xpts, P, grade)
                if not L or L not in ysig:
                    continue
                w = GRADE_WEIGHT[grade]
                if L not in best or w > best[L]["weight"]:
                    best[L] = {
                        "kind": "reception",
                        "receiver_person": yp, "receiver_point": L,
                        "receiver_roles": sorted(ysig[L]),
                        "received_person": xp, "received_point": P,
                        "received_roles": sorted(roles_P),
                        "received_sign": pt.get("sign"), "grade": grade,
                        "weight": w, "mutual": False, "receiver_debilitated": False}
            facts.extend(best.values())

    # A.6 — receiver debilitated (detriment/fall in the receiver's own chart)
    for f in facts:
        rpts = pA if f["receiver_person"] == "A" else pB
        cls = (rpts.get(f["receiver_point"]) or {}).get("classifications") or {}
        f["receiver_debilitated"] = bool(cls.get("in_detriment") or cls.get("in_fall"))

    # A.5 — mutual (reverse fact at domicile/exaltation) + weight bonus
    idx = {(f["receiver_person"], f["receiver_point"],
            f["received_person"], f["received_point"]): f for f in facts}
    for f in facts:
        rev = idx.get((f["received_person"], f["received_point"],
                       f["receiver_person"], f["receiver_point"]))
        # strict mutual reception: BOTH directions at domicile/exaltation (A.5)
        if (f["grade"] in ("domicile", "exaltation")
                and rev and rev["grade"] in ("domicile", "exaltation")):
            f["mutual"] = True
            f["weight"] = min(1.0, f["weight"] + 0.2)

    # C.1 — mutual pairs emit once: keep the stronger-grade direction, drop reverse
    facts.sort(key=lambda f: (GRADE_WEIGHT[f["grade"]], f["weight"]), reverse=True)
    seen_pairs, collapsed = set(), []
    for f in facts:
        if f["mutual"]:
            pk = frozenset({(f["receiver_person"], f["receiver_point"]),
                            (f["received_person"], f["received_point"])})
            if pk in seen_pairs:
                continue
            seen_pairs.add(pk)
        collapsed.append(f)
    return collapsed


# --------------------------------------------------------------------------- #
# RECEPTION — Part B: matcher + role binding
# --------------------------------------------------------------------------- #

def _reception_matches(syn: dict, f: dict) -> bool:
    if syn.get("received_point") and syn["received_point"] != f["received_point"]:
        return False
    if syn.get("receiver_point") and syn["receiver_point"] != f["receiver_point"]:
        return False
    rc = syn.get("receiver_class")
    if rc and f["receiver_point"] not in RECEIVER_CLASS.get(rc, set()):
        return False
    rr = syn.get("received_role")
    if rr and rr not in f["received_roles"]:
        return False
    g = syn.get("grade", "any")
    if g and g != "any" and g != f["grade"]:
        return False
    m = syn.get("mutual")
    if m is not None and bool(m) != bool(f["mutual"]):
        return False
    if syn.get("receiver_debilitated") and not f["receiver_debilitated"]:
        return False
    return True


def _reception_specificity(syn: dict) -> int:
    s = 0
    if syn.get("received_point"):
        s += 2
    if syn.get("receiver_point"):
        s += 2
    if syn.get("receiver_class"):
        s += 1
    if syn.get("received_role"):
        s += 1
    if syn.get("grade", "any") not in (None, "any"):
        s += 1
    if syn.get("mutual") is not None:
        s += 1
    if syn.get("receiver_debilitated"):
        s += 1
    return s


def _mk_reception(rec: dict, f: dict) -> dict:
    label = {"A": "A", "B": "B"}
    stmt = (rec.get("rule", "") or "").replace("{RECEIVER}", label[f["receiver_person"]]) \
                                       .replace("{RECEIVED}", label[f["received_person"]])
    return {
        **rec,
        "matched": [{"kind": "reception", "grade": f["grade"], "mutual": f["mutual"],
                     "weight": f["weight"],
                     "receiver": {"person": f["receiver_person"], "point": f["receiver_point"]},
                     "received": {"person": f["received_person"], "point": f["received_point"]}}],
        "bound": {"kind": "reception",
                  "receiver_person": f["receiver_person"], "receiver_point": f["receiver_point"],
                  "received_person": f["received_person"], "received_point": f["received_point"],
                  "received_sign": f["received_sign"], "grade": f["grade"],
                  "mutual": f["mutual"]},
        "bound_statement": stmt,
        "_specificity": _reception_specificity(rec.get("synastry") or {}),
    }


def _dedup_reception(candidates: list[dict], result: RelResult) -> list[dict]:
    """C.1 — one survivor per reception fact-key, most-specific principle wins."""
    groups: dict[tuple, list[dict]] = {}
    for rec in candidates:
        groups.setdefault(_fact_key(rec), []).append(rec)
    kept = []
    for _key, group in groups.items():
        group.sort(key=lambda r: (r.get("_specificity", 0), _rank(r)), reverse=True)
        survivor, losers = group[0], group[1:]
        superseded = sorted({r["principle_id"] for r in losers
                             if r["principle_id"] != survivor["principle_id"]})
        if superseded:
            survivor = {**survivor, "superseded": superseded}
            for pid in superseded:
                result.drops.append(RelDrop(pid, "reception", "superseded_by_fact_key",
                                            f"same reception fact as {survivor['principle_id']}"))
        survivor.pop("_specificity", None)
        kept.append(survivor)
    return kept


# --------------------------------------------------------------------------- #
# FIX B — dedup emitted synastry candidates by physical fact-key
# --------------------------------------------------------------------------- #

def _fact_key(rec) -> Optional[tuple]:
    """Physical fact-key for dedup (SYNASTRY_GROUNDING_FIXES.md §B). Defined for
    overlay and aspect only; compatibility records are distinct interpretations
    that may share an element/sign condition, so they are not fact-keyed."""
    b = rec.get("bound") or {}
    if b.get("kind") == "overlay":
        return ("house_overlay", b["mover_point"], b["home_house"],
                rec["matched"][0]["direction"], b["house_system"])
    if b.get("kind") == "aspect":
        return ("aspect", frozenset({b["p1_point"], b["p2_point"]}), b["aspect"],
                frozenset({b["p1_person"], b["p2_person"]}))
    if b.get("kind") == "compatibility":              # FIX H — one per factor set
        return ("compatibility", frozenset(str(f) for f in b.get("factors", [])))
    if b.get("kind") == "reception":                  # C.1 — one per reception fact
        return ("reception", b["receiver_point"], b["received_point"],
                b["grade"], b["receiver_person"])
    return None


def _rank(rec) -> tuple:
    pid = rec.get("principle_id", "")
    not_general = 0 if pid.endswith("-general") else 1
    conf_order = {"high": 2, "medium": 1, "low": 0}
    conf = conf_order.get((rec.get("about") or {}).get("extraction_confidence"), 0)
    return (not_general, conf, len(rec.get("rule", "")))


def _dedup(candidates: list[dict], result: RelResult) -> list[dict]:
    groups: dict[tuple, list[dict]] = {}
    passthrough = []
    for rec in candidates:
        key = _fact_key(rec)
        if key is None:                       # not fact-keyed -> keep as-is
            passthrough.append(rec)
        else:
            groups.setdefault(key, []).append(rec)
    kept = list(passthrough)
    for key, group in groups.items():
        group.sort(key=_rank, reverse=True)
        survivor, losers = group[0], group[1:]
        superseded = sorted({r["principle_id"] for r in losers
                             if r["principle_id"] != survivor["principle_id"]})
        if superseded:
            survivor = {**survivor, "superseded": superseded}
            for pid in superseded:
                result.drops.append(RelDrop(pid, survivor["synastry"]["interaction"],
                                            "superseded_by_fact_key",
                                            f"same fact as {survivor['principle_id']}"))
        kept.append(survivor)
    return kept


def _dedup_planet_roles(bucket: list[dict], result: RelResult) -> list[dict]:
    """FIX I — planet_role is generic scaffolding; keep at most one line per
    (person, point). natal_relational (chart-specific) is left untouched."""
    roles: dict[tuple, list[dict]] = {}
    out = []
    for rec in bucket:
        if (rec.get("synastry") or {}).get("interaction") == "planet_role":
            key = (rec["bound"].get("person"), rec["bound"].get("point"))
            roles.setdefault(key, []).append(rec)
        else:
            out.append(rec)                            # natal_relational etc.
    for _key, group in roles.items():
        group.sort(key=_rank, reverse=True)
        survivor, losers = group[0], group[1:]
        superseded = sorted({r["principle_id"] for r in losers
                             if r["principle_id"] != survivor["principle_id"]})
        if superseded:
            survivor = {**survivor, "superseded": superseded}
            for pid in superseded:
                result.drops.append(RelDrop(pid, "planet_role",
                                            "superseded_by_fact_key",
                                            f"same role as {survivor['principle_id']}"))
        out.append(survivor)
    return out


# --------------------------------------------------------------------------- #
# FIX E — exit invariants (halt on violation)
# --------------------------------------------------------------------------- #

def _rederive_ok(rec, cA, pA, cB, pB) -> tuple[bool, str]:
    b = rec["bound"]
    chart = {"A": cA, "B": cB}
    pts = {"A": pA, "B": pB}
    if b["kind"] == "overlay":
        mv = _resolve_point(chart[b["mover_person"]], pts[b["mover_person"]], b["mover_point"])
        cusp_key = "placidus_cusps" if b["house_system"] == "placidus" else "whole_sign_cusps"
        cusps = (chart[b["home_person"]].get("sectors") or {}).get(cusp_key)
        if not mv or not cusps:
            return False, "point/cusps unresolved"
        got = _house_of(mv["longitude"], cusps)
        return (got == b["home_house"], f"{b['mover_point']} in house {got}, want {b['home_house']}")
    if b["kind"] == "aspect":
        p1 = _resolve_point(chart[b["p1_person"]], pts[b["p1_person"]], b["p1_point"])
        p2 = _resolve_point(chart[b["p2_person"]], pts[b["p2_person"]], b["p2_point"])
        if not p1 or not p2:
            return False, "point unresolved"
        ok, _ = _aspect_holds(p1, p2, b["aspect"], b.get("scheme", "modern"))
        return ok, f"{b['p1_point']}-{b['p2_point']} {b['aspect']} not within orb"
    if b["kind"] == "compatibility":                  # FIX G — re-derive threshold
        elem_c, modal_c, sign_c = _pooled_balance(cA, cB)
        absent = [f for f in b.get("factors", [])
                  if not _factor_present(f, elem_c, modal_c, sign_c)]
        return (not absent), f"factors {absent} below pooled threshold"
    if b["kind"] == "reception":                      # C.2 — re-derive lord-at-grade
        recd_pts = pts[b["received_person"]]
        lord = _lord_of(recd_pts, b["received_point"], b["grade"])
        return (lord == b["receiver_point"],
                f"lord of {b['received_point']}'s sign at {b['grade']} is "
                f"{lord}, not {b['receiver_point']}")
    return True, ""


def _check_invariants(result: RelResult, cA, pA, cB, pB) -> None:
    seen_keys = set()
    for rec in result.synastry:
        pid = rec.get("principle_id")
        # E3 — bound + bound_statement present, no literal A/B leak
        if "bound" not in rec or "bound_statement" not in rec:
            raise RelInvariantViolation(f"{pid}: synastry record missing bound/bound_statement")
        stmt = rec["bound_statement"] or ""
        if re.search(r"[Pp]erson\s+[AB]\b", stmt):
            raise RelInvariantViolation(f"{pid}: bound_statement leaks literal 'person A/B'")
        if "{RECEIVER}" in stmt or "{RECEIVED}" in stmt:
            raise RelInvariantViolation(f"{pid}: bound_statement leaks a {{RECEIVER}}/{{RECEIVED}} token")
        # E2 — no duplicate fact-keys (overlay/aspect; compatibility not fact-keyed)
        k = _fact_key(rec)
        if k is not None:
            if k in seen_keys:
                raise RelInvariantViolation(f"{pid}: duplicate fact-key {k}")
            seen_keys.add(k)
        # E1 — re-derivation against the two charts
        ok, why = _rederive_ok(rec, cA, pA, cB, pB)
        if not ok:
            raise RelInvariantViolation(f"{pid}: bound fact not true of charts ({why})")
    # E4 — framing only allowlisted general
    for rec in result.framing:
        if rec.get("principle_id") not in STANCE_ALLOWLIST:
            raise RelInvariantViolation(f"{rec.get('principle_id')}: non-allowlisted in framing")
    # E5 — every drop has an enum reason
    for d in result.drops:
        if d.reason not in DROP_REASONS:
            raise RelInvariantViolation(f"{d.principle_id}: drop reason {d.reason!r} not in enum")


# --------------------------------------------------------------------------- #
# The gate
# --------------------------------------------------------------------------- #

def ground_relationship(records: list[dict], chart_a: dict, chart_b: dict) -> RelResult:
    pA, pB = _point_index(chart_a), _point_index(chart_b)
    result = RelResult()
    syn_candidates: list[dict] = []          # aspect/overlay/compatibility, pre-dedup
    recep_candidates: list[dict] = []        # reception, pre-dedup
    recep_facts = compute_reception_facts(chart_a, pA, chart_b, pB)   # Part A

    for rec in records:
        if rec.get("domain") not in _RELATIONSHIP_DOMAINS:
            result.drops.append(RelDrop(rec.get("principle_id", "?"), "-",
                                        "no_matching_fact", "domain not relationship"))
            continue
        interaction = (rec.get("synastry") or {}).get("interaction")
        if interaction == "natal_relational":
            _ground_natal_relational(rec, chart_a, pA, chart_b, pB, result)
        elif interaction == "planet_role":
            _ground_planet_role(rec, chart_a, pA, chart_b, pB, result)
        elif interaction == "aspect":
            _ground_aspect(rec, chart_a, pA, chart_b, pB, result, syn_candidates)
        elif interaction == "house_overlay":
            _ground_house_overlay(rec, chart_a, pA, chart_b, pB, result, syn_candidates)
        elif interaction == "compatibility":
            _ground_compatibility(rec, chart_a, chart_b, syn_candidates, result)
        elif interaction == "reception":
            syn = rec.get("synastry") or {}
            hits = [f for f in recep_facts if _reception_matches(syn, f)]
            if hits:
                for f in hits:
                    recep_candidates.append(_mk_reception(rec, f))
            else:
                result.drops.append(RelDrop(rec.get("principle_id", "?"), "reception",
                                            "reception_no_matching_fact", "no reception fact"))
        elif interaction == "general":
            if rec.get("principle_id") in STANCE_ALLOWLIST:
                result.framing.append(rec)
            else:
                result.drops.append(RelDrop(rec.get("principle_id", "?"), "general",
                                            "not_on_stance_allowlist", "not a stance principle"))
        else:
            result.drops.append(RelDrop(rec.get("principle_id", "?"), str(interaction),
                                        "unbindable_role", "unknown interaction"))

    # FIX B/H — dedup aspect/overlay/compatibility candidates by fact-key;
    # C.1 — dedup reception candidates (most-specific principle per fact).
    result.synastry = (_dedup(syn_candidates, result)
                       + _dedup_reception(recep_candidates, result)
                       + result.synastry)
    # FIX I — collapse planet_role scaffolding to one line per (person, point)
    result.person_a = _dedup_planet_roles(result.person_a, result)
    result.person_b = _dedup_planet_roles(result.person_b, result)
    # FIX E — halt on any invariant breach
    _check_invariants(result, chart_a, pA, chart_b, pB)
    return result


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description="Two-chart (synastry) grounding gate.")
    ap.add_argument("--records",
                    default=os.path.join(here, "combined_relationship_principles_tagged.json"),
                    help="tagged corpus (every record carries synastry.contexts)")
    ap.add_argument("--chart-a", dest="chart_a", required=True)
    ap.add_argument("--chart-b", dest="chart_b", required=True)
    ap.add_argument("--out",
                    default=os.path.join(here, "personal_relationship_principles.json"))
    ap.add_argument("--drop-report", dest="drop_report",
                    default=os.path.join(here, "relationship_grounding_report.json"),
                    help="secondary diagnostic (use '' to skip)")
    args = ap.parse_args()

    with open(args.records, encoding="utf-8") as fh:
        records = json.load(fh)

    # E6 — fail fast on an untagged corpus. `synastry.contexts` is the contract
    # S3's reading-type filter depends on; an untagged/partial corpus would let
    # S3 silently mis-filter. Corpus-level property -> checked once at load.
    _VALID_CONTEXTS = {"universal", "personal", "professional"}
    for rec in records:
        ctx = (rec.get("synastry") or {}).get("contexts")
        if not (isinstance(ctx, list) and ctx and set(ctx) <= _VALID_CONTEXTS):
            raise RelInvariantViolation(
                f"{rec.get('principle_id', '?')}: missing or invalid synastry.contexts "
                f"(got {ctx!r}); corpus must be tagged before grounding")

    with open(args.chart_a, encoding="utf-8") as fh:
        chart_a = json.load(fh)
    with open(args.chart_b, encoding="utf-8") as fh:
        chart_b = json.load(fh)

    result = ground_relationship(records, chart_a, chart_b)
    payload = result.payload()
    payload["chart_a"] = os.path.basename(args.chart_a)
    payload["chart_b"] = os.path.basename(args.chart_b)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    if args.drop_report:
        from collections import Counter
        with open(args.drop_report, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"dropped": len(result.drops),
                       "by_reason": dict(Counter(d.reason for d in result.drops)),
                       "drops": [d.as_dict() for d in result.drops]},
                      fh, ensure_ascii=False, indent=2)

    c = payload["counts"]
    print(f"relationship grounding: personA={c['person_a']} personB={c['person_b']} "
          f"synastry={c['synastry']} framing={c['framing']} (dropped {c['dropped']})")
    print(f"-> {args.out}")
    print("\nsynastry facts (bound):")
    for r in result.synastry[:25]:
        print(f"  {r['principle_id']}: {r['bound_statement'][:90]}")


if __name__ == "__main__":
    main()
