#!/usr/bin/env python3
"""
reclassify.py — RECLASSIFY_SPEC.md: a deterministic, count-free, idempotent
post-pass that re-routes backfill `unclassified` records into their honest homes.

Runs AFTER backfill and BEFORE the build's floor/ceiling checks. Makes **no LLM
calls** — every decision is a rule over fields already present
(`principle_id`, `rule`, `judgment`, existing `unclassified_reason`).

Five routes, strict precedence (§2):
    1. re-capture  (clean template, §3)        -> reconcilable type (house_domain only)
    2. stay (dependency)                        -> remain unclassified, keep reason
    3. out-of-scope (procedure signal, §4)      -> out_of_scope=true, factor_type kept
    4. widen to general (config signal, §5)     -> general, clear reason
    5. stay (honest)                            -> remain unclassified, no_subject_in_text

Design constraints (§1): no counts/targets; idempotent & order-independent; only
touches `unclassified` records (everything else stays byte-identical); conservative
re-capture (template-only, never a specific-value type); signal lists are editable
config (`reclassify_rules.json`), not code.

Run
---
    python reclassify.py --in all_principles.grounded.json --out <same> --report reclassify_report.json
    # or import and call reclassify(records)
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
from typing import Optional

from grounding_schema import invariant_violation, validate_about
from grounding_vocab import HOUSE_WORDS, canon_point

_HERE = os.path.dirname(os.path.abspath(__file__))
_RULES_PATH = os.path.join(_HERE, "reclassify_rules.json")


# ---------------------------------------------------------------------------
# Rule config (data, not code — §6). Loaded from reclassify_rules.json; a small
# embedded default keeps the module importable if the file is missing.
# ---------------------------------------------------------------------------
_EMBEDDED_DEFAULT: dict = {
    "recapture_templates": [
        {"rule_id": "planet_sign_function",
         "id_regex": r"^planet-sign-function-(sun|moon|mercury|venus|mars|"
                     r"jupiter|saturn|uranus|neptune|pluto|north-node|south-node)$",
         "target": "house_domain", "point_from_group": 1},
    ],
    "dependency_signals": ["native gender", "sex of the native"],
    "procedure_signals": ["hilaj", "alcocoden", "length of life"],
    "config_signals": ["element-emphasis", "asc-ruler", "any planet"],
    "fixed_subject_guard_id_regex":
        r"^asc-(aries|taurus|gemini|cancer|leo|virgo|libra|scorpio|"
        r"sagittarius|capricorn|aquarius|pisces)-",
}


def load_rules(path: str | None = None) -> dict:
    path = path or _RULES_PATH
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return _EMBEDDED_DEFAULT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _blob(record: dict) -> str:
    """Hyphen-normalized, lowercased id + rule + judgment for signal matching."""
    parts = [record.get("principle_id") or "", record.get("rule") or "",
             record.get("judgment") or ""]
    return " ".join(parts).lower().replace("-", " ")


def _any_signal(blob: str, signals: list[str]) -> Optional[str]:
    for s in signals:
        if s.lower().replace("-", " ") in blob:
            return s
    return None


def _tradition_house_system(record: dict) -> str:
    return "whole_sign" if record.get("tradition") == "traditional" else "placidus"


# ---------------------------------------------------------------------------
# Route 1 — conservative re-capture (templates only -> house_domain)
# ---------------------------------------------------------------------------

def _route1_recapture(record: dict, rules: dict) -> Optional[dict]:
    pid = (record.get("principle_id") or "").lower()
    for tmpl in rules.get("recapture_templates", []):
        m = re.match(tmpl["id_regex"], pid)
        if not m:
            continue
        target = tmpl.get("target", "house_domain")
        if target != "house_domain":
            # spec §3: re-capture targets ONLY house_domain (no specific-value type)
            continue
        about = {
            "factor_type": "house_domain",
            "extraction_confidence": "high",
            "extraction_source": "deterministic",
        }
        if "point_from_group" in tmpl:
            point = canon_point(m.group(tmpl["point_from_group"]).replace("-", " "))
            if not point:
                continue
            about["point"] = point
        elif "house_from_group" in tmpl:
            house = HOUSE_WORDS.get(m.group(tmpl["house_from_group"]))
            if not house:
                continue
            about["house"] = house
            about["house_system"] = _tradition_house_system(record)
        else:
            continue
        # the house_domain invariant must hold by construction (§3)
        if invariant_violation(about) is not None:
            continue
        ok, _ = validate_about(about)
        if not ok:
            continue
        return about
    return None


# ---------------------------------------------------------------------------
# The pass
# ---------------------------------------------------------------------------

def _route_element_violation(record: dict, rules: dict) -> Optional[tuple[dict, str]]:
    """Re-type an `element` record that carries no concrete element value (an
    invariant violation — element has no fixed value by nature). Driven by the
    rule 'factor_type == element and element absent', then routed by sub-shape:
    a single planet's sign-element significations -> house_domain on the point;
    a relational / multi-factor element record -> general. Returns (new_about,
    rule_id) or None. No hardcoded id list."""
    about = record.get("about") or {}
    if about.get("factor_type") != "element" or about.get("element") is not None:
        return None
    cfg = rules.get("element_violation", {})
    pid = (record.get("principle_id") or "").lower()
    single_re = cfg.get("single_planet_id_regex")
    conf = about.get("extraction_confidence", "high")
    if single_re and re.match(single_re, pid) and about.get("point"):
        new_about = {
            "factor_type": "house_domain",
            "point": about["point"],
            "extraction_confidence": conf,
            "extraction_source": "deterministic",
        }
        if invariant_violation(new_about) is None and validate_about(new_about)[0]:
            return new_about, "element_to_house_domain"
    # relational / multi-factor: strip all subject fields -> general
    new_about = {
        "factor_type": "general",
        "extraction_confidence": conf,
        "extraction_source": "deterministic",
    }
    return new_about, "element_to_general"


def reclassify_record(record: dict, rules: dict) -> tuple[dict, Optional[str]]:
    """Return (possibly-new record, route_id|None). Alters `unclassified` records
    (the five routes) and `element`-with-null-value records (re-type); everything
    else is returned byte-identical (same object)."""
    about = record.get("about") or {}

    # Element invariant fix (runs regardless of unclassified): a value-less
    # `element` record is re-typed, with audit, before the build's invariant check.
    elem = _route_element_violation(record, rules)
    if elem is not None:
        new_about, rule_id = elem
        out = copy.deepcopy(record)
        out["about"] = new_about
        out["reclassified_from"] = "element"
        out["reclassify_rule"] = rule_id
        return out, rule_id

    if about.get("factor_type") != "unclassified":
        return record, None

    blob = _blob(record)
    reason = about.get("unclassified_reason")

    # --- Route 1: re-capture (highest precedence) ---------------------------
    recaptured = _route1_recapture(record, rules)
    if recaptured is not None:
        out = copy.deepcopy(record)
        out["about"] = recaptured
        out["reclassified_from"] = "unclassified"
        out["reclassify_rule"] = "1"
        return out, "1"

    # --- Route 2: stay (dependency) -----------------------------------------
    if reason == "dependency_unsatisfiable" or _any_signal(
            blob, rules.get("dependency_signals", [])):
        # remain unclassified; ensure the reason is set, else byte-identical
        if reason != "dependency_unsatisfiable":
            out = copy.deepcopy(record)
            out["about"] = dict(about, unclassified_reason="dependency_unsatisfiable")
            return out, None
        return record, None

    # --- Route 3: out-of-scope (procedure) ----------------------------------
    if _any_signal(blob, rules.get("procedure_signals", [])):
        out = copy.deepcopy(record)
        out["out_of_scope"] = True
        out["scope_note"] = "classical_procedure"
        out["reclassified_from"] = "unclassified"
        out["reclassify_rule"] = "3"
        # factor_type stays `unclassified` (spec §4); reason preserved
        return out, "3"

    # --- Route 4: widen to general (config / chart-level) --------------------
    fixed_guard = rules.get("fixed_subject_guard_id_regex")
    is_fixed_subject = bool(
        fixed_guard and re.match(fixed_guard, (record.get("principle_id") or "").lower())
    )
    if not is_fixed_subject and _any_signal(blob, rules.get("config_signals", [])):
        out = copy.deepcopy(record)
        out["about"] = {
            "factor_type": "general",
            "extraction_confidence": "low",
            "extraction_source": "deterministic",
        }
        out["reclassified_from"] = "unclassified"
        out["reclassify_rule"] = "4"
        return out, "4"

    # --- Route 5: stay (honest) ---------------------------------------------
    if reason != "no_subject_in_text":
        out = copy.deepcopy(record)
        out["about"] = dict(about, unclassified_reason="no_subject_in_text")
        return out, None
    return record, None


def reclassify(records: list[dict], rules: dict | None = None) -> tuple[list[dict], list[dict]]:
    """Apply the post-pass to a dataset. Returns (new_records, routing_log).
    The log lists only records routed by 1/3/4 (auditability, §2)."""
    rules = rules if rules is not None else load_rules()
    out: list[dict] = []
    log: list[dict] = []
    for rec in records:
        new, route = reclassify_record(rec, rules)
        out.append(new)
        if route is not None:   # routes 1/3/4 and element re-types (2/5 return None)
            log.append({
                "principle_id": rec.get("principle_id"),
                "domain": rec.get("domain"),
                "route": route,
                "reclassified_from": new.get("reclassified_from"),
                "to_factor_type": new["about"]["factor_type"],
                "out_of_scope": new.get("out_of_scope", False),
            })
    return out, log


def structural_residual_check(records: list[dict], rules: dict | None = None) -> dict:
    """Spec §7 recommendation: replace the hard count ceiling with a STRUCTURAL
    check — every remaining `unclassified` must (a) carry a valid reason and
    (b) match NO route-1/3/4 signal (else it should have moved). Count-free."""
    rules = rules if rules is not None else load_rules()
    no_reason, still_routable = [], []
    for r in records:
        about = r.get("about") or {}
        if about.get("factor_type") != "unclassified":
            continue
        if not about.get("unclassified_reason"):
            no_reason.append(r.get("principle_id"))
        # Delegate to the router so PRECEDENCE is honored: a record legitimately
        # kept by route 2 (dependency) returns None and is NOT flagged, even if it
        # also matches a later route's signal. A record still routable to 1/4
        # (or to 3 when not yet out_of_scope) is a genuine miss.
        _, route = reclassify_record(r, rules)
        if route in ("1", "4"):
            still_routable.append(r.get("principle_id"))
        elif route == "3" and not r.get("out_of_scope"):
            still_routable.append(r.get("principle_id"))
    return {
        "unclassified_without_reason": no_reason,
        "unclassified_still_route_matchable": still_routable,
        "passes": not no_reason and not still_routable,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Deterministic reclassify post-pass.")
    ap.add_argument("--in", dest="inp",
                    default=os.path.join(_HERE, "all_principles.grounded.json"))
    ap.add_argument("--out", dest="out", default=None,
                    help="default: overwrite --in")
    ap.add_argument("--rules", default=_RULES_PATH)
    ap.add_argument("--report", dest="report",
                    default=os.path.join(_HERE, "reclassify_report.json"))
    args = ap.parse_args()

    with open(args.inp, encoding="utf-8") as fh:
        records = json.load(fh)
    rules = load_rules(args.rules)

    new_records, log = reclassify(records, rules)
    structural = structural_residual_check(new_records, rules)

    out_path = args.out or args.inp
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(new_records, fh, ensure_ascii=False, indent=1)
    report = {
        "routed": len(log),
        "by_route": {r: sum(1 for x in log if x["route"] == r) for r in ("1", "3", "4")},
        "structural_residual_check": structural,
        "routing": log,   # diagnostic, no count assertions
    }
    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    print(f"reclassify: routed {len(log)} of {len(records)} "
          f"(route1={report['by_route']['1']}, route3={report['by_route']['3']}, "
          f"route4={report['by_route']['4']}) -> {out_path}")
    print(f"structural residual check: "
          f"{'PASS' if structural['passes'] else 'FAIL'} "
          f"(no-reason={len(structural['unclassified_without_reason'])}, "
          f"still-routable={len(structural['unclassified_still_route_matchable'])})")


if __name__ == "__main__":
    main()
