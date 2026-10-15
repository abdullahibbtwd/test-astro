#!/usr/bin/env python3
"""
read_relationship.py — S3 orchestrator (SYNASTRY_READING_SPEC.md).

Pipeline:
    personal_relationship_principles.json (+ the two charts' precision)
      -> floor + route + order + cap  (§4, deterministic — s3_routing)
      -> 7 axis calls + 1 opener call, in parallel  (§5)
      -> single synthesis pass -> final tr+en per section  (§5, §6)
      -> statements extraction -> atomic self-scorable claims  (§11)
      -> validate the contract  (§10); fail rather than ship a violation
      -> emit the four artifacts (§11)

Artifacts written next to --out:
  relationship_reading.tr.txt      primary
  relationship_reading.en.txt      faithful translation
  relationship_statements.json     atomic statements for S4/eval
  relationship_reading_routing.json  the audit trail

The reading is authored in Turkish (the quality target) with English produced by
a faithful pass in the same synthesis call (§5).

Run
---
    python read_relationship.py                          # dry run: routing only
    python read_relationship.py --model gemini-3.7-flash  # real generation
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

from s3_generate import DEFAULT_MODEL, make_generator
from s3_prompts import build_contract
from s3_profiles import DEFAULT_READING_TYPE, READING_TYPES, get_profile
from s3_routing import route
from s3_validate import SCHEMA_VERSION, clean_statements, validate

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
_DEFAULT_INPUT = os.path.join(
    _PARENT, "principles_grounding", "personal_relationship_principles.json")


def _load_json(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Precision gate (§9). Both charts must be exact for house overlays to be trusted.
# ---------------------------------------------------------------------------

def _resolve_precision(payload: dict, search_root: str) -> tuple[bool, dict]:
    """Determine houses_valid from the two charts' meta.time_precision. Charts
    are located by the filenames in the payload (they live under runs/); if a
    chart can't be found, fall back to overlay presence (grounding omits overlays
    when birth times are not exact, §9)."""
    detail: dict = {}
    both_exact = True
    found_any = False
    for key in ("chart_a", "chart_b"):
        fname = payload.get(key)
        detail[key] = {"file": fname, "time_precision": None}
        if not fname:
            both_exact = False
            continue
        matches = glob.glob(os.path.join(search_root, "**", fname), recursive=True)
        if not matches:
            detail[key]["time_precision"] = "unresolved"
            both_exact = False
            continue
        found_any = True
        meta = (_load_json(matches[0]).get("meta") or {})
        tp = meta.get("time_precision")
        detail[key]["time_precision"] = tp
        if tp != "exact":
            both_exact = False

    if not found_any:
        # Couldn't read either chart; trust the grounded overlays as the signal.
        has_overlay = any(
            (r.get("synastry") or {}).get("interaction") == "house_overlay"
            for r in payload.get("synastry") or []
        )
        return has_overlay, {**detail, "inferred_from": "overlay_presence"}
    return both_exact, detail


# ---------------------------------------------------------------------------
# Assembly (§6 / §11)
# ---------------------------------------------------------------------------

def _assemble(synth_sections: list[dict], routed_ids: dict[str, set[str]],
              houses_valid: bool, profile) -> dict:
    by_key = {s.get("key"): s for s in synth_sections}
    movement = profile.movement
    sections: list[dict] = []
    for key in profile.section_order:
        s = by_key.get(key)
        if not s:
            continue
        sections.append({
            "key": key,
            "movement": movement[key],
            "text_tr": s.get("text_tr", ""),
            "text_en": s.get("text_en", ""),
            # Grounding trace: the record pool this section was built from
            # (structural, from routing §4). Retained for QA, stripped at render.
            "source_ids": sorted(routed_ids.get(key, set())),
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "reading": "relationship",
        "reading_type": profile.reading_type,
        "houses_valid": houses_valid,
        "sections": sections,
    }


def _statements_doc(statements: list[dict], reading_type: str) -> dict:
    numbered = []
    for i, st in enumerate(statements, 1):
        numbered.append({
            "id": f"st-{i:03d}",
            "section": st.get("section"),
            "text_tr": st.get("text_tr", ""),
            "text_en": st.get("text_en", ""),
            "source_ids": st.get("source_ids", []),
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "reading": "relationship",
        "reading_type": reading_type,
        "statements": numbered,
    }


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def read_relationship(payload: dict, *, generator=None,
                      reading_type: str = "general",
                      model: str = DEFAULT_MODEL,
                      synthesis_model: str | None = None,
                      statements_model: str | None = "default",
                      translation_model: str | None = "default",
                      label_a: str = "sen", label_b: str = "partnerin",
                      houses_valid: bool | None = None,
                      precision_detail: dict | None = None,
                      **gen_kwargs):
    """Run the full S3 pipeline for one ``reading_type`` (general / personal /
    professional, PROFILES §1). ``generator`` may be injected (tests); otherwise
    the Anthropic runner is constructed. Returns (output, statements_doc, report,
    errors)."""
    profile = get_profile(reading_type)
    routing = route(payload, profile, houses_valid=houses_valid)
    routed_by_section = routing.non_empty()
    routed_ids = routing.routed_ids()
    floored_ids = {d["record_id"] for d in routing.floor_drops}

    contract = build_contract(payload.get("framing"),
                              reading_stance=profile.stance,
                              label_a=label_a, label_b=label_b)
    if statements_model != "default":       # None = same as the synthesis model
        gen_kwargs["statements_model"] = statements_model
    if translation_model != "default":
        gen_kwargs["translation_model"] = translation_model
    gen = generator or make_generator(
        contract, profile, model=model, synthesis_model=synthesis_model,
        label_a=label_a, label_b=label_b, **gen_kwargs)

    drafts = gen.section_all(routed_by_section, houses_valid=routing.houses_valid)
    synth = gen.synthesize(drafts)
    output = _assemble(synth, routed_ids, routing.houses_valid, profile)

    allowed = {k: sorted(v) for k, v in routed_ids.items()}
    raw_statements = gen.extract_statements(output["sections"], allowed)
    # Enforce §10.6 by cleaning: untraceable / mask- or score-leaking statements
    # are dropped, not allowed to sink the (already-validated) reading.
    statements, stmt_clean = clean_statements(raw_statements, routed_ids)
    statements_doc = _statements_doc(statements, profile.reading_type)

    errors = validate(output, statements_doc, routed_ids, floored_ids)

    report = routing.report()
    report["backend"] = type(gen).__name__
    report["sections_emitted"] = [s["key"] for s in output["sections"]]
    report["statements_count"] = len(statements)
    report["statements_cleaning"] = stmt_clean
    if precision_detail is not None:
        report["precision"] = precision_detail
    if getattr(gen, "usage", None):
        report["token_usage"] = gen.usage
    return output, statements_doc, report, errors


def main() -> None:
    ap = argparse.ArgumentParser(description="S3 relationship reading generation.")
    ap.add_argument("--input", default=_DEFAULT_INPUT,
                    help="personal_relationship_principles.json (grounded, §2)")
    ap.add_argument("--charts-root", default=_PARENT,
                    help="root to search for the two chart files (precision gate)")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"section-call model (default {DEFAULT_MODEL})")
    ap.add_argument("--reading-type", choices=list(READING_TYPES),
                    default=DEFAULT_READING_TYPE,
                    help="[1] general (default) — the connection as a whole; "
                         "[2] personal — romantic / life partnership; "
                         "[3] professional — business / working partnership")
    ap.add_argument("--synthesis-model", default=None,
                    help="synthesis model (default: same as --model)")
    ap.add_argument("--translation-model", default="default",
                    help="English translation model (default: the cheap model, "
                         "gpt-6-luna; 'same' = the synthesis model)")
    ap.add_argument("--statements-model", default="default",
                    help="statements-extraction model (default: the cheap model, "
                         "gpt-6-luna; 'same' = the synthesis model)")
    ap.add_argument("--label-a", default="sen",
                    help="display label for person A (default: 'sen')")
    ap.add_argument("--label-b", default="partnerin",
                    help="display label for person B (default: 'partnerin')")
    ap.add_argument("--max-tokens", type=int, default=None)
    ap.add_argument("--synthesis-max-tokens", type=int, default=None)
    ap.add_argument("--out-dir", default=_HERE,
                    help="directory for the four artifacts")
    ap.add_argument("--dry-run", action="store_true",
                    help="route only; write the routing report, no model calls")
    args = ap.parse_args()

    payload = _load_json(args.input)
    houses_valid, precision = _resolve_precision(payload, args.charts_root)
    profile = get_profile(args.reading_type)
    print(f"loaded {len(payload.get('synastry') or [])} synastry records; "
          f"reading_type={args.reading_type}; houses_valid={houses_valid}")

    out_json = os.path.join(args.out_dir, "relationship_reading.json")
    report_path = os.path.join(args.out_dir, "relationship_reading_routing.json")
    statements_path = os.path.join(args.out_dir, "relationship_statements.json")
    run_meta_path = os.path.join(args.out_dir, "run_meta.json")

    # Stamp reading_type + provenance so every run is self-describing (§1, §7.3).
    run_meta = {
        "reading": "relationship", "reading_type": args.reading_type,
        "input": os.path.abspath(args.input), "houses_valid": houses_valid,
        "precision": precision, "model": args.model,
        "labels": {"A": args.label_a, "B": args.label_b},
    }
    with open(run_meta_path, "w", encoding="utf-8") as fh:
        json.dump(run_meta, fh, ensure_ascii=False, indent=2)

    if args.dry_run:
        routing = route(payload, profile, houses_valid=houses_valid)
        report = routing.report()
        report["precision"] = precision
        with open(report_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
        print("section counts:", report["section_counts"])
        print(f"context drops: {len(report['context_drops'])}  "
              f"floor drops: {len(report['floor_drops'])}  "
              f"overflow: {len(report['overflow_drops'])}  "
              f"unrouted: {len(report['unrouted'])}")
        print(f"dry run -> routing report {report_path}")
        return

    gen_kwargs = {}
    if args.max_tokens is not None:
        gen_kwargs["max_tokens"] = args.max_tokens
    if args.synthesis_max_tokens is not None:
        gen_kwargs["synthesis_max_tokens"] = args.synthesis_max_tokens

    try:
        output, statements_doc, report, errors = read_relationship(
            payload, reading_type=args.reading_type,
            model=args.model, synthesis_model=args.synthesis_model,
            statements_model=(None if args.statements_model == "same"
                              else args.statements_model),
            translation_model=(None if args.translation_model == "same"
                               else args.translation_model),
            label_a=args.label_a, label_b=args.label_b,
            houses_valid=houses_valid, precision_detail=precision, **gen_kwargs)
    except RuntimeError as err:
        print(f"\n{err}", file=sys.stderr)
        sys.exit(2)

    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(f"backend={report['backend']}  sections={len(output['sections'])}  "
          f"statements={report['statements_count']}  report -> {report_path}")
    if report.get("token_usage"):
        u = report["token_usage"]
        print(f"tokens: input={u['input_tokens']:,} output={u['output_tokens']:,} "
              f"cache_read={u['cache_read_input_tokens']:,} over {u['calls']} calls")

    if errors:
        # Never discard an expensive generation: dump it (and the errors) to a
        # .rejected file for inspection / a cheap fix, but do NOT ship it as the
        # validated reading.
        rejected_path = os.path.join(args.out_dir,
                                     "relationship_reading.rejected.json")
        with open(rejected_path, "w", encoding="utf-8") as fh:
            json.dump({"errors": errors, "output": output,
                       "statements": statements_doc}, fh,
                      ensure_ascii=False, indent=2)
        print(f"\nCONTRACT VIOLATION - {len(errors)} error(s), NOT writing "
              f"reading (rejected draft -> {rejected_path}):", file=sys.stderr)
        for e in errors[:40]:
            print("  -", e, file=sys.stderr)
        sys.exit(1)

    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(output, fh, ensure_ascii=False, indent=2)
    with open(statements_path, "w", encoding="utf-8") as fh:
        json.dump(statements_doc, fh, ensure_ascii=False, indent=2)
    print(f"validated OK -> {out_json}")
    print(f"statements -> {statements_path}")

    from s3_render import write_readable
    for path in write_readable(output, args.out_dir):
        print(f"readable text -> {path}")


if __name__ == "__main__":
    main()
