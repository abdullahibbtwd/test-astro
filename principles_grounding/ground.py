#!/usr/bin/env python3
"""
ground.py — the Layer 2 exit contract (PRINCIPLE_GROUNDING_SPEC.md §4-§5).

``ground(records, chart, reading="natal")`` is the deterministic filter applied
AFTER semantic retrieval and BEFORE handing off to Layer 3. It runs three
sequential gates and returns only principles whose subject is verifiably true of
the chart and whose dependencies the chart can satisfy:

    Gate A  domain pre-filter      — keep only the reader's allowed domains
    Gate B  subject reconciliation — `about` must be true of THIS chart
    Gate C  dependency satisfiability — every `requires` token resolvable here

Every drop is logged with its gate, reason, the offending `about`, and the
relevant chart fact (spec §4 logging). The function returns a ``GroundingResult``
carrying the kept records bundled-by-grounding-factor, the per-chart drop report,
and the chart — exactly what Layer 3 receives (spec §5). Layer 3 performs no
reconciliation.

Run
---
    python ground.py                  # grounded corpus + chart.json -> stdout report
    python ground.py --records retrieval_output.json --chart chart.json
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from typing import Any, Optional

from grounding_schema import invariant_violation
from grounding_vocab import DIGNITY_TO_CLASSIFICATION

# dignity -> the classifications ruler field that confirms a reception dignity
# ("{planet} in {other}'s {dignity}"). exaltation/detriment/fall have no
# ruler-of concept in the classifications block, so they are not ruler-verifiable.
_DIGNITY_RULER_FIELD = {
    "domicile": "sign_ruler",
    "bound": "bound_ruler",
    "face": "face_ruler",
    "triplicity": "triplicity_ruler",
}

# tradition -> aspect/house relation scheme (RETRIEVAL_CONTRACT.md §, spec §4).
_TRADITION_SCHEME = {"modern": "modern", "traditional": "whole_sign"}
# house_system -> the relation scheme that house system implies.
_HS_SCHEME = {"placidus": "modern", "whole_sign": "whole_sign"}


# ---------------------------------------------------------------------------
# Chart access helpers (points is a LIST keyed by name; see chart_types.py)
# ---------------------------------------------------------------------------

def _point_index(chart: dict) -> dict[str, dict]:
    return {p["name"]: p for p in chart.get("points", [])}


def _scheme_for_record(record: dict) -> str:
    return _TRADITION_SCHEME.get(record.get("tradition"), "modern")


# ---------------------------------------------------------------------------
# Drop logging
# ---------------------------------------------------------------------------

@dataclass
class DropLog:
    principle_id: str
    gate: str
    reason: str
    about: dict
    relevant_chart_fact: Any = None

    def as_dict(self) -> dict:
        return {
            "principle_id": self.principle_id,
            "gate": self.gate,
            "reason": self.reason,
            "about": self.about,
            "relevant_chart_fact": self.relevant_chart_fact,
        }


@dataclass
class GroundingResult:
    """What Layer 2 hands Layer 3 (spec §5)."""
    kept: list[dict]
    bundles: dict[str, list[dict]]      # kept records keyed by grounding factor
    drops: list[DropLog]
    chart: dict
    reading: str

    def report(self) -> dict:
        """Diagnostic report — drop accounting (secondary output)."""
        from collections import Counter
        return {
            "reading": self.reading,
            "kept": len(self.kept),
            "dropped": len(self.drops),
            "drops_by_gate": dict(Counter(d.gate for d in self.drops)),
            "bundles": {k: len(v) for k, v in self.bundles.items()},
            "drop_log": [d.as_dict() for d in self.drops],
        }

    def kept_payload(self) -> dict:
        """The Layer 2 -> Layer 3 contract (spec §5): the kept principles for THIS
        chart — full content, bundled by the chart factor that grounded them.
        This is the primary output: the personal principles true of the chart."""
        return {
            "reading": self.reading,
            "kept_count": len(self.kept),
            "principles": self.kept,                  # flat list of full records
            "bundled_by_factor": self.bundles,        # same records, grouped
        }


# ---------------------------------------------------------------------------
# Gate A — domain pre-filter
# ---------------------------------------------------------------------------

_READING_DOMAINS = {
    "natal": {"natal"},
    "natal+basics": {"natal", "basics"},
}


def _gate_a(record: dict, allowed: set[str]) -> Optional[str]:
    dom = record.get("domain")
    if dom not in allowed:
        return f"domain {dom!r} not in allowed {sorted(allowed)}"
    return None


# ---------------------------------------------------------------------------
# Gate B — subject reconciliation
# ---------------------------------------------------------------------------

def _relation_exists(chart: dict, a: str, b: str, typ: str, scheme: str) -> bool:
    for r in chart.get("relations", []):
        if r.get("scheme") != scheme or r.get("type") != typ:
            continue
        s, t = r.get("source"), r.get("target")
        if {s, t} == {a, b}:        # unordered (spec §3 aspect direction)
            return True
    return False


class InvariantViolation(Exception):
    """A reconcilable factor_type reached the gate with a null required field —
    the v1 defect. This is a fatal data error to fix in backfill, never a silent
    gate-B drop (spec §4 precondition, §7 test 11)."""


def _reconcile_house_lord_relative(about: dict, chart: dict,
                                   pts: dict[str, dict]) -> tuple[bool, str, Any]:
    """Spec §3.1: resolve the lord of subject_house from sector_rulers, then keep
    iff that lord's actual placement equals placement_house. The ruling planet is
    chart-derived (never stored), so this is a full reconciliation, not passthrough."""
    shs = about.get("subject_house_system")
    sh = about.get("subject_house")
    phs = about.get("placement_house_system")
    ph = about.get("placement_house")

    rulers = (chart.get("sector_rulers") or {}).get(shs) or {}
    block = rulers.get(str(sh))
    if block is None:
        return False, f"chart has no {shs} ruler for house {sh}", None
    ruler = block.get("ruler")
    p = pts.get(ruler)
    if p is None:
        return False, f"resolved lord {ruler!r} absent from chart", None
    actual = (p.get("sector") or {}).get(phs)
    fact = {"subject_house": sh, "resolved_lord": ruler,
            "placement_house_system": phs, "actual_house": actual}
    if actual is None:
        return False, f"chart has no {phs} sector for lord {ruler}", fact
    if actual == ph:
        return True, f"lord of {sh} ({ruler}) is in {ph}", fact
    return False, (
        f"house-lord-relative mismatch: lord of {sh} is {ruler}, in {actual} "
        f"not {ph}"
    ), fact


def _gate_b(record: dict, chart: dict, pts: dict[str, dict],
            strict_invariants: bool = False) -> tuple[bool, str, Any]:
    """Returns (passed, reason, relevant_chart_fact). Raises InvariantViolation
    (when strict) for a reconcilable type missing its required field; otherwise
    surfaces it as a distinct INVARIANT_VIOLATION drop, never a None-mismatch."""
    about = record.get("about") or {}
    ft = about.get("factor_type")

    # Precondition (spec §4): invariant check BEFORE any reconciliation, so we
    # never compare a real chart value against None and log a spurious mismatch.
    viol = invariant_violation(about)
    if viol:
        if strict_invariants:
            raise InvariantViolation(f"{record.get('principle_id')}: {viol}")
        return False, f"INVARIANT_VIOLATION: {viol}", {"about": about}

    if ft == "general":
        return True, "general: no subject to reconcile", None
    if ft in (None, "unclassified"):
        return False, "unclassified: cannot be verified", None

    if ft == "house_domain":
        # Passes on existence — the named point/house always exist in any chart,
        # so there is nothing to falsify; asserts no placement (spec §3, §4).
        point = about.get("point")
        if point is not None and point not in pts:
            return False, f"house_domain names absent point {point!r}", None
        if "house" in about and not (1 <= about["house"] <= 12):
            return False, f"house_domain names invalid house {about['house']}", None
        return True, "house_domain: passes on existence", \
            {"point": point, "house": about.get("house")}

    if ft == "house_lord_relative":
        return _reconcile_house_lord_relative(about, chart, pts)

    # --- placements: sign / house / both / node -----------------------------
    if ft in ("planet_in_sign", "planet_in_house", "planet_in_sign_and_house",
              "node", "dignity"):
        point = about.get("point")
        p = pts.get(point)
        if p is None:
            return False, f"point {point!r} absent from chart", None

    if ft in ("planet_in_sign",) or (ft == "node" and "sign" in about):
        p = pts[about["point"]]
        if p.get("sign") == about.get("sign"):
            return True, "sign matches", {"point": about["point"], "sign": p.get("sign")}
        return False, (
            f"sign mismatch: about {about.get('sign')} vs chart {p.get('sign')}"
        ), {"point": about["point"], "sign": p.get("sign")}

    if ft in ("planet_in_house",) or (ft == "node" and "house" in about):
        p = pts[about["point"]]
        hs = about.get("house_system")
        sector = (p.get("sector") or {}).get(hs)
        if sector is None:
            return False, f"chart has no {hs} sector for {about['point']}", \
                {"point": about["point"], "sector": p.get("sector")}
        if sector == about.get("house"):
            return True, "house matches", \
                {"point": about["point"], "house_system": hs, "sector": sector}
        return False, (
            f"house mismatch ({hs}): about {about.get('house')} vs chart {sector}"
        ), {"point": about["point"], "house_system": hs, "sector": sector}

    if ft == "planet_in_sign_and_house":
        p = pts[about["point"]]
        hs = about.get("house_system")
        sector = (p.get("sector") or {}).get(hs)
        fact = {"point": about["point"], "sign": p.get("sign"),
                "house_system": hs, "sector": sector}
        if p.get("sign") != about.get("sign"):
            return False, (
                f"sign mismatch: about {about.get('sign')} vs chart {p.get('sign')}"
            ), fact
        if sector != about.get("house"):
            return False, (
                f"house mismatch ({hs}): about {about.get('house')} vs chart {sector}"
            ), fact
        return True, "sign+house match", fact

    if ft == "aspect":
        a = about.get("aspect") or {}
        scheme = _scheme_for_record(record)
        ok = _relation_exists(chart, a.get("source"), a.get("target"),
                              a.get("type"), scheme)
        fact = {"aspect": a, "scheme": scheme}
        if ok:
            return True, "aspect relation present", fact
        return False, (
            f"no {scheme} {a.get('type')} between {a.get('source')} and "
            f"{a.get('target')}"
        ), fact

    if ft == "dignity":
        p = pts[about["point"]]
        cls = p.get("classifications")
        dig = about.get("dignity")
        ruler = about.get("dignity_ruler")
        if cls is None:
            return False, f"{about['point']} has no classifications (non-classical)", None
        # rev 3: "{planet} in {other}'s domicile/bound/..." reception — confirm the
        # subject sits in a sign the named ruler governs, via the ruler field.
        if ruler is not None:
            ruler_field = _DIGNITY_RULER_FIELD.get(dig)
            if ruler_field is None:
                return False, f"cannot verify reception dignity {dig!r} by ruler", \
                    {"point": about["point"], "dignity": dig}
            actual = cls.get(ruler_field)
            fact = {"point": about["point"], ruler_field: actual,
                    "expected_ruler": ruler}
            if dig == "triplicity":
                trip = cls.get("triplicity_rulers_all") or {}
                if ruler in trip.values():
                    return True, f"{about['point']} in {ruler}'s triplicity", fact
                return False, f"{about['point']} not in {ruler}'s triplicity", fact
            if actual == ruler:
                return True, f"{about['point']} in {ruler}'s {dig}", fact
            return False, (
                f"reception mismatch: {about['point']} in {actual}'s {dig}, "
                f"not {ruler}'s"
            ), fact
        # own essential dignity
        key = DIGNITY_TO_CLASSIFICATION.get(dig)
        if key and cls.get(key) is True:
            return True, f"dignity {dig} confirmed", {"point": about["point"], dig: True}
        return False, f"dignity {dig} not held by {about['point']}", \
            {"point": about["point"], "classifications": {k: cls.get(k) for k in (key,) if k}}

    if ft == "ascendant":
        asc = ((chart.get("axes") or {}).get("ascendant") or {}).get("sign")
        if asc is None:
            return False, "chart has no ascendant (no birth time)", None
        if asc == about.get("ascendant_sign"):
            return True, "ascendant matches", {"ascendant": asc}
        return False, (
            f"ascendant mismatch: about {about.get('ascendant_sign')} vs chart {asc}"
        ), {"ascendant": asc}

    if ft == "house_ruler":
        hs = about.get("house_system")
        house = about.get("house")
        rulers = (chart.get("sector_rulers") or {}).get(hs) or {}
        block = rulers.get(str(house))
        if block is None:
            return False, f"chart has no {hs} ruler for house {house}", None
        if block.get("ruler") == about.get("point"):
            return True, "house ruler matches", {"house": house, "ruler": block.get("ruler")}
        return False, (
            f"house-ruler mismatch ({hs} h{house}): about {about.get('point')} "
            f"vs chart {block.get('ruler')}"
        ), {"house": house, "ruler": block.get("ruler")}

    return False, f"unhandled factor_type {ft!r}", None


# ---------------------------------------------------------------------------
# Gate C — dependency satisfiability
# ---------------------------------------------------------------------------

def _chart_has_time(chart: dict) -> bool:
    return chart.get("confidence") != "unknown" and "axes" in chart


def _requirement_satisfiable(req: dict, chart: dict, pts: dict[str, dict]) -> tuple[bool, str]:
    kind = req.get("kind")
    point = req.get("point")

    if kind == "native_gender":
        return False, "unsatisfiable: native_gender"
    if kind == "birth_time":
        return (True, "") if _chart_has_time(chart) else (False, "unsatisfiable: birth_time")
    if kind == "ascendant":
        return (True, "") if "axes" in chart else (False, "unsatisfiable: ascendant (no birth time)")
    if kind == "house_ruler":
        return (True, "") if "sector_rulers" in chart else (False, "unsatisfiable: house_ruler")
    if kind in ("point_sign", "point_aspects"):
        # present in every chart tier; only fails if a named point is absent.
        if point and point not in pts:
            return False, f"unsatisfiable: {kind} for absent point {point}"
        return True, ""
    if kind == "point_house":
        if point and point in pts and "sector" not in pts[point]:
            return False, "unsatisfiable: point_house (no birth time)"
        return True, ""
    if kind == "point_dignity":
        if point and point in pts and not pts[point].get("classifications"):
            return False, f"unsatisfiable: point_dignity for non-classical {point}"
        return True, ""
    if kind == "sign_element":
        return True, ""
    # "other" and anything else: no specific dependency we can refute -> keep.
    return True, ""


def _gate_c(record: dict, chart: dict, pts: dict[str, dict]) -> tuple[bool, str]:
    for req in record.get("requires", []) or []:
        ok, reason = _requirement_satisfiable(req, chart, pts)
        if not ok:
            return False, reason
    return True, ""


# ---------------------------------------------------------------------------
# Bundling (spec §5: keyed by the chart factor that grounded them)
# ---------------------------------------------------------------------------

def _bundle_key(about: dict) -> str:
    ft = about.get("factor_type")
    if ft in ("planet_in_sign",) or (ft == "node" and "sign" in about and "house" not in about):
        return f"{about.get('point')} in {about.get('sign')}"
    if ft in ("planet_in_house",) or (ft == "node" and "house" in about):
        return f"{about.get('point')} in {about.get('house_system')} house {about.get('house')}"
    if ft == "planet_in_sign_and_house":
        return (f"{about.get('point')} in {about.get('sign')} / "
                f"{about.get('house_system')} house {about.get('house')}")
    if ft == "aspect":
        a = about.get("aspect") or {}
        return f"{a.get('source')} {a.get('type')} {a.get('target')}"
    if ft == "dignity":
        return f"{about.get('point')} in {about.get('dignity')}"
    if ft == "ascendant":
        return f"Ascendant {about.get('ascendant_sign')}"
    if ft == "house_ruler":
        return f"ruler of {about.get('house_system')} house {about.get('house')}"
    if ft == "house_domain":
        if about.get("point") is not None:
            return f"{about.get('point')} house-domain"
        return f"{about.get('house_system')} house {about.get('house')} domain"
    if ft == "house_lord_relative":
        return (f"lord of {about.get('subject_house_system')} house "
                f"{about.get('subject_house')} in house {about.get('placement_house')}")
    return "general"


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------

def ground(records: list[dict], chart: dict, reading: str = "natal",
           strict_invariants: bool = False) -> GroundingResult:
    """Run gates A→B→C. With ``strict_invariants`` an INVARIANT_VIOLATION raises
    (build-time tripwire); otherwise it is logged as a distinct drop gate so it
    can never masquerade as a subject mismatch (spec §4 precondition)."""
    allowed = _READING_DOMAINS.get(reading, {"natal"})
    pts = _point_index(chart)
    kept: list[dict] = []
    drops: list[DropLog] = []
    bundles: dict[str, list[dict]] = {}

    for rec in records:
        pid = rec.get("principle_id", "<no-id>")
        about = rec.get("about") or {}

        # Gate A
        reason = _gate_a(rec, allowed)
        if reason:
            drops.append(DropLog(pid, "A", reason, about, {"domain": rec.get("domain")}))
            continue

        # Gate B (with invariant precondition)
        ok, reason, fact = _gate_b(rec, chart, pts, strict_invariants=strict_invariants)
        if reason.startswith("INVARIANT_VIOLATION"):
            drops.append(DropLog(pid, "INVARIANT_VIOLATION", reason, about, fact))
            continue
        if not ok:
            drops.append(DropLog(pid, "B", reason, about, fact))
            continue

        # Gate C
        ok, reason = _gate_c(rec, chart, pts)
        if not ok:
            drops.append(DropLog(pid, "C", reason, about, None))
            continue

        kept.append(rec)
        bundles.setdefault(_bundle_key(about), []).append(rec)

    return GroundingResult(kept=kept, bundles=bundles, drops=drops,
                           chart=chart, reading=reading)


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Layer 2 grounding gate — emits the personal principles true "
                    "of the chart (spec §4/§5).")
    ap.add_argument("--records",
                    default=os.path.join(here, "all_principles.grounded.json"),
                    help="grounded principle records (post-backfill)")
    ap.add_argument("--chart",
                    default=os.path.normpath(os.path.join(here,
                                                          "..",
                                                          "d_layer",
                                                          "chart.json")))
    ap.add_argument("--reading", default="natal",
                    choices=list(_READING_DOMAINS.keys()))
    ap.add_argument("--out", default=os.path.join(here, "personal_principles.json"),
                    help="PRIMARY output: the kept personal principles for the chart")
    ap.add_argument("--drop-report", dest="drop_report",
                    default=os.path.join(here, "grounding_report.json"),
                    help="secondary diagnostic: per-drop accounting (use '' to skip)")
    args = ap.parse_args()

    with open(args.records, encoding="utf-8") as fh:
        records = json.load(fh)
    with open(args.chart, encoding="utf-8") as fh:
        chart = json.load(fh)

    result = ground(records, chart, reading=args.reading)

    # PRIMARY output — the kept personal principles, bundled by chart factor.
    payload = result.kept_payload()
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)

    # Secondary diagnostic (drops) — optional.
    if args.drop_report:
        with open(args.drop_report, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(result.report(), fh, ensure_ascii=False, indent=2)

    print(f"reading={result.reading}: {len(result.kept)} personal principles "
          f"grounded to the chart ({len(result.drops)} dropped)")
    print(f"-> {args.out}")
    print("\ngrounded principles by chart factor:")
    for factor, recs in result.bundles.items():
        print(f"  [{factor}]")
        for r in recs:
            print(f"      - {r.get('principle_id')}")


if __name__ == "__main__":
    main()
