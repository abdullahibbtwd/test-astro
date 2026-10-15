#!/usr/bin/env python3
"""synastry_run.py — the interactive orchestrator for the RELATIONSHIP pipeline.

The two-person analogue of run.py. One entry point that takes two people's birth
data, runs the whole synastry pipeline end to end, and writes every artifact of
one run into its own id'd folder under ``synastry_run/`` — the same manner as the
natal ``runs/`` folders.

Pipeline (all stages part of one run):
    L1  chart x2        compute_chart.compute_chart          (one per person)
    wheel x2            Chart_wheel/cli.js                   (deterministic SVGs)
    L2/L3 grounding     ground_relationship.ground_relationship  (both charts)
    S3  reading         read_relationship.read_relationship + s3_render.write_readable

Shared plumbing (input prompts, geocoding, run-id, the birth-date suffix rule,
the Node chart-wheel shell-out, JSON writing) is imported from run.py so the two
orchestrators stay in lock-step. Only the two-person sequencing lives here.

The reading is authored in Turkish (English produced by a faithful pass). Needs
ANTHROPIC_API_KEY for the S3 stage (the grounding + wheels are offline).

    python synastry_run.py
    python synastry_run.py --model claude-opus-4-8 --synthesis-model claude-opus-4-8
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

ENGINE_ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(ENGINE_ROOT))  # repo root (Chart_wheel, run caches)
# Layer packages live under backend/engine; keep ENGINE as the import root.
_ENGINE = ENGINE_ROOT

# The synastry reading modules live in synastry_reading/ and import each other by
# bare name; put that dir on sys.path before importing them. run.py (imported
# below) already inserts d_layer / principles_grounding / Interpretation_layer.
for _d in ("d_layer", "principles_grounding", "synastry_reading", "Interpretation_layer"):
    _p = os.path.join(ENGINE_ROOT, _d)
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Reuse the natal orchestrator's building blocks verbatim (DRY): input collection,
# geocoding, the birth-date suffix rule, the wheel renderer, run-id minting.
import run  # noqa: E402
from run import (  # noqa: E402
    collect_input, geocode, mint_run_id, render_chart_wheels,
    suffixed, WheelError, _write_json,
)

# Relationship corpus: the analogue of all_principles.grounded.json (§2). The
# TAGGED corpus — every record carries `synastry.contexts` — is required for the
# reading-type fork; grounding's E6 invariant hard-fails on an untagged corpus.
REL_CORPUS_PATH = os.path.join(ENGINE_ROOT, "principles_grounding",
                               "combined_relationship_principles_tagged.json")
SYN_RUNS_DIR = os.path.join(REPO_ROOT, "synastry_run")

# Person B's default display label depends on the reading type — "partnerin"
# (your partner) must not import a romantic frame into professional/general.
_B_DEFAULT = {"personal": "partnerin", "professional": "iş ortağın",
              "general": "diğer kişi"}


def _collect_person(who: str) -> dict:
    """Prompt one person's birth data + geocode. Reuses run.collect_input /
    run.geocode (same validation, re-prompt, and confirmation behaviour)."""
    print(f"\n=== {who} ===")
    inp = collect_input()           # birth_date / birth_time_local / place_query (+ y/m/d/h/m)
    geo = geocode(inp["place_query"])
    return {"input": inp, "geocode": geo}


def _optional_label(who: str, default: str) -> str:
    raw = run._prompt(f"Display label for {who} (blank = '{default}'): ")
    return raw or default


def _compute_chart(person: dict):
    from compute_chart import compute_chart, BirthData
    inp, geo = person["input"], person["geocode"]
    bd = BirthData(
        year=inp["year"], month=inp["month"], day=inp["day"],
        hour=inp["hour"], minute=inp["minute"],
        latitude=geo["latitude"], longitude=geo["longitude"],
        time_precision="exact",
    )
    return compute_chart(bd)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Interactive synastry (two-chart) relationship pipeline.")
    ap.add_argument("--model", default=None, help="S3 section-call model")
    ap.add_argument("--synthesis-model", default=None, help="S3 synthesis model")
    ap.add_argument("--translation-model", default=None,
                    help="S3 English translation model (default: the cheap model, "
                         "gpt-6-luna; 'same' = the synthesis model)")
    ap.add_argument("--statements-model", default=None,
                    help="S3 statements-extraction model (default: the cheap model, "
                         "gpt-6-luna; 'same' = the synthesis model)")
    ap.add_argument("--max-tokens", type=int, default=None, help="S3 per-section budget")
    ap.add_argument("--synthesis-max-tokens", type=int, default=None,
                    help="S3 synthesis output budget")
    ap.add_argument("--reading-type", choices=["general", "personal", "professional"],
                    default=None, help="relationship reading focus; prompt if omitted")
    args = ap.parse_args()

    import llm_client
    from s3_generate import DEFAULT_MODEL as _S3_DEFAULT
    from s3_generate import DEFAULT_STATEMENTS_MODEL as _STATEMENTS_DEFAULT
    from s3_generate import DEFAULT_TRANSLATION_MODEL as _TRANSLATION_DEFAULT
    _synth = args.synthesis_model or args.model or _S3_DEFAULT
    _statements = (_synth if args.statements_model == "same"
                   else args.statements_model or _STATEMENTS_DEFAULT)
    _translation = (_synth if args.translation_model == "same"
                    else args.translation_model or _TRANSLATION_DEFAULT)
    _missing = llm_client.missing_key_message(
        [args.model or _S3_DEFAULT, _synth, _statements, _translation],
        "the S3 relationship reading")
    if _missing:
        print(_missing, file=sys.stderr)
        return 1
    if not os.path.exists(REL_CORPUS_PATH):
        print(f"Missing relationship corpus: {REL_CORPUS_PATH}", file=sys.stderr)
        return 1

    # --- reading-type fork: ground once (type-agnostic), fork in S3. Resolve the
    #     type up front (it drives person B's default label below). ---
    reading_type = args.reading_type
    if reading_type is None:
        print("\nWhich relationship reading?\n"
              "  [1] General        — the connection as a whole\n"
              "  [2] Personal focus — romantic / life partnership\n"
              "  [3] Professional   — business / working partnership")
        reading_type = {"1": "general", "2": "personal", "3": "professional",
                        "": "general"}.get(
                            run._prompt("Choose [1/2/3] (default 1): ").strip(), "general")
    print(f"reading_type = {reading_type}")

    # --- 1. collect both people's input (§1) ---
    person_a = _collect_person("Person A")
    person_b = _collect_person("Person B")
    label_a = _optional_label("Person A", "sen")
    label_b = _optional_label("Person B", _B_DEFAULT[reading_type])

    bd_a = person_a["input"]["birth_date"]
    bd_b = person_b["input"]["birth_date"]
    # One suffix shared by every file in the folder (both birth dates), so a file
    # lifted out is never confused with another run's — same rule as run.py.
    suffix = f"{bd_a}_{bd_b}"

    # --- 2. mint run_id, create synastry_run/<id>/. No file written before this. ---
    now_utc = datetime.now(timezone.utc)
    run_id = mint_run_id(now_utc, suffix)
    run_dir = os.path.join(SYN_RUNS_DIR, run_id)
    os.makedirs(run_dir, exist_ok=True)
    print(f"\nrun_id = {run_id}\nrun_dir = {run_dir}\n")

    artifacts: list[str] = []

    def artifact(*names: str) -> None:
        for n in names:
            if n not in artifacts:
                artifacts.append(n)

    def person_meta(person: dict) -> dict:
        return {
            "input": {
                "birth_date": person["input"]["birth_date"],
                "birth_time_local": person["input"]["birth_time_local"],
                "place_query": person["input"]["place_query"],
            },
            "geocode": {
                "provider": person["geocode"]["provider"],
                "display_name": person["geocode"]["display_name"],
                "latitude": person["geocode"]["latitude"],
                "longitude": person["geocode"]["longitude"],
            },
        }

    def write_meta(status: str, models: dict | None = None,
                   tz_a: str | None = None, tz_b: str | None = None,
                   counts: dict | None = None, houses_valid: bool | None = None) -> None:
        meta = {
            "run_id": run_id,
            "reading": "relationship",
            # Closure-captured (resolved before any write_meta call), so every run —
            # including the error-path ones — records which type was attempted (§5a).
            "reading_type": reading_type,
            "created_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": status,
            "person_a": {**person_meta(person_a), "label": label_a,
                         "resolved_timezone": tz_a},
            "person_b": {**person_meta(person_b), "label": label_b,
                         "resolved_timezone": tz_b},
            "time_precision": "exact",
            "houses_valid": houses_valid,
            "grounding_counts": counts or {},
            "models": models or {},
            "artifacts": list(artifacts),
        }
        _write_json(os.path.join(run_dir, suffixed("run_meta.json", suffix)), meta)

    # --- 3. L1: compute both charts -> chart_a.json / chart_b.json ---
    chart_a = _compute_chart(person_a)
    chart_b = _compute_chart(person_b)
    tz_a = (chart_a.get("meta") or {}).get("timezone")
    tz_b = (chart_b.get("meta") or {}).get("timezone")

    chart_a_name = suffixed("chart_a.json", suffix)
    chart_b_name = suffixed("chart_b.json", suffix)
    chart_a_path = os.path.join(run_dir, chart_a_name)
    chart_b_path = os.path.join(run_dir, chart_b_name)
    _write_json(chart_a_path, chart_a)
    _write_json(chart_b_path, chart_b)
    artifact(chart_a_name, chart_b_name)
    print(f"[L1] charts computed (A tz={tz_a}, B tz={tz_b})")

    # --- 3b. Chart wheels for both people (deterministic; offline; fail cheap) ---
    print("[wheel] rendering both charts' wheels (light + dark)...")
    try:
        wheels = (render_chart_wheels(chart_a_path, run_dir, suffix, stem="chart_wheel_a")
                  + render_chart_wheels(chart_b_path, run_dir, suffix, stem="chart_wheel_b"))
    except WheelError as err:
        print(f"\n[wheel] render failed: {err}", file=sys.stderr)
        write_meta("wheel_render_error", tz_a=tz_a, tz_b=tz_b)
        return 1
    for p in wheels:
        artifact(os.path.basename(p))
    print(f"[wheel] wrote {', '.join(os.path.basename(p) for p in wheels)}")

    # --- 4. L2/L3: ground the relationship corpus to BOTH charts ---
    from ground_relationship import ground_relationship

    with open(REL_CORPUS_PATH, encoding="utf-8") as fh:
        corpus = json.load(fh)
    # E6 safety net (GROUND_RELATIONSHIP_CONTEXTS.md §2): the reading-type fork
    # depends on every record carrying a valid `synastry.contexts`. grounding's
    # CLI enforces this, but ground_relationship() (called in-process) does not —
    # so guard here rather than let an untagged corpus silently mis-filter in S3.
    _VALID_CONTEXTS = {"universal", "personal", "professional"}
    for rec in corpus:
        ctx = (rec.get("synastry") or {}).get("contexts")
        if not (isinstance(ctx, list) and ctx and set(ctx) <= _VALID_CONTEXTS):
            print(f"[L2/L3] untagged corpus — {rec.get('principle_id', '?')} has invalid "
                  f"synastry.contexts ({ctx!r}). Tag the corpus before grounding "
                  f"(expected {os.path.basename(REL_CORPUS_PATH)}).", file=sys.stderr)
            write_meta("untagged_corpus", tz_a=tz_a, tz_b=tz_b)
            return 1
    result = ground_relationship(corpus, chart_a, chart_b)
    payload = result.payload()
    # Carry the chart basenames as provenance (precision gate / traceability, §9).
    payload["chart_a"] = chart_a_name
    payload["chart_b"] = chart_b_name
    counts = payload["counts"]

    pp_name = suffixed("personal_relationship_principles.json", suffix)
    _write_json(os.path.join(run_dir, pp_name), payload)
    artifact(pp_name)
    # Secondary diagnostic: the drop audit trail.
    drop_report = {
        "reading": "relationship",
        "counts": counts,
        "drops": [d.as_dict() if hasattr(d, "as_dict") else vars(d) for d in result.drops],
    }
    gr_name = suffixed("relationship_grounding_report.json", suffix)
    _write_json(os.path.join(run_dir, gr_name), drop_report)
    artifact(gr_name)
    # Surface the per-context split (§5b) so a thin professional slice is visible
    # before the expensive S3 call.
    ctx = counts.get("contexts", {}).get("synastry", {})
    print(f"[L2/L3] grounded: person_a={counts['person_a']} person_b={counts['person_b']} "
          f"synastry={counts['synastry']} framing={counts['framing']} "
          f"({counts['dropped']} dropped) | context split synastry {ctx} | "
          f"reading_type={reading_type}")

    # Both times are exact (fixed precision), so house overlays are trusted (§9).
    houses_valid = (tz_a is not None and tz_b is not None
                    and (chart_a.get("meta") or {}).get("time_precision") == "exact"
                    and (chart_b.get("meta") or {}).get("time_precision") == "exact")
    precision_detail = {
        "chart_a": {"file": chart_a_name,
                    "time_precision": (chart_a.get("meta") or {}).get("time_precision")},
        "chart_b": {"file": chart_b_name,
                    "time_precision": (chart_b.get("meta") or {}).get("time_precision")},
    }

    # --- 5. S3: relationship reading ---
    from read_relationship import read_relationship
    from s3_render import write_readable

    section_model = args.model  # None -> S3 DEFAULT_MODEL inside make_generator
    gen_kwargs: dict = {}
    if args.max_tokens is not None:
        gen_kwargs["max_tokens"] = args.max_tokens
    if args.synthesis_max_tokens is not None:
        gen_kwargs["synthesis_max_tokens"] = args.synthesis_max_tokens
    read_kwargs: dict = dict(gen_kwargs)
    if section_model is not None:
        read_kwargs["model"] = section_model
    if args.synthesis_model is not None:
        read_kwargs["synthesis_model"] = args.synthesis_model
    if args.statements_model is not None:
        read_kwargs["statements_model"] = (
            None if args.statements_model == "same" else args.statements_model)
    if args.translation_model is not None:
        read_kwargs["translation_model"] = (
            None if args.translation_model == "same" else args.translation_model)

    print("[S3] generating relationship reading (real model calls — takes a while)...")
    try:
        output, statements_doc, report, errors = read_relationship(
            payload, reading_type=reading_type,
            label_a=label_a, label_b=label_b,
            houses_valid=houses_valid, precision_detail=precision_detail,
            **read_kwargs)
    except RuntimeError as err:
        print(f"\n[S3] generation failed: {err}", file=sys.stderr)
        write_meta("s3_generation_error", tz_a=tz_a, tz_b=tz_b,
                   counts=counts, houses_valid=houses_valid)
        return 2

    from s3_generate import DEFAULT_MODEL as S3_DEFAULT
    resolved_section = section_model or S3_DEFAULT
    models = {"section": resolved_section,
              "synthesis": args.synthesis_model or resolved_section,
              "statements": _statements,
              "translation": _translation}

    # The routing report is a QA artifact even on a violation — write it either way.
    report_name = suffixed("relationship_reading_routing.json", suffix)
    _write_json(os.path.join(run_dir, report_name), report)
    artifact(report_name)

    if errors:
        # S3 contract violation: do NOT write the reading / statements (§10).
        print(f"\n[S3] CONTRACT VIOLATION — {len(errors)} error(s); "
              "not writing the reading:", file=sys.stderr)
        for e in errors[:40]:
            print("  -", e, file=sys.stderr)
        write_meta("s3_contract_violation", models=models, tz_a=tz_a, tz_b=tz_b,
                   counts=counts, houses_valid=houses_valid)
        return 1

    # errors == [] : now write the reading + statements + readable text.
    reading_name = suffixed("relationship_reading.json", suffix)
    statements_name = suffixed("relationship_statements.json", suffix)
    _write_json(os.path.join(run_dir, reading_name), output)
    _write_json(os.path.join(run_dir, statements_name), statements_doc)
    artifact(reading_name, statements_name)
    reading_paths = write_readable(output, run_dir,
                                   stem=suffixed("relationship_reading", suffix))
    for p in reading_paths:
        artifact(os.path.basename(p))
    print(f"[S3] {len(output['sections'])} sections, "
          f"{report.get('statements_count', len(statements_doc['statements']))} statements; "
          f"readable -> {', '.join(os.path.basename(p) for p in reading_paths)}")

    # --- 6. manifest + summary ---
    artifact(suffixed("run_meta.json", suffix))
    write_meta("complete", models=models, tz_a=tz_a, tz_b=tz_b,
               counts=counts, houses_valid=houses_valid)

    print("\n" + "=" * 70)
    print(f"SYNASTRY RUN COMPLETE — {run_dir}")
    print(f"  {label_a} ({bd_a})  x  {label_b} ({bd_b})  [{reading_type}]")
    print("Artifacts:")
    for a in artifacts:
        print(f"  - {a}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
