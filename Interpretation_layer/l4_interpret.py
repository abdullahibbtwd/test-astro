#!/usr/bin/env python3
"""
l4_interpret.py — Layer 4 orchestrator (L4_INTERPRETATION_SPEC.md).

Pipeline:
    chart + grounded_principles
      -> route (§3, deterministic)
      -> per-section generation calls (§4, parallel)
      -> single synthesis pass (§5)
      -> assemble §6 output, in canonical section order
      -> validate the contract (§7); fail rather than ship a violation
      -> emit l4_output.json (+ a routing report for QA)

Inputs (§1):
  Input 1  the full chart object (compute_chart.py output).
  Input 2  personal_principles.json — this chart's kept principles, the per-chart
           output of L3 grounding (ground.py). L4 routes the `principles` array;
           `bundled_by_factor` is convenience-only and is NOT routed off; the
           grounding_report.json diagnostic sibling is ignored. `kept_count` must
           equal len(principles) — asserted on load.

If personal_principles.json is absent, --grounded-source lets this script run
ground() itself on the source corpus to produce the kept set (convenience so it
is runnable out of the box).

Run
---
    python l4_interpret.py                            # reads personal_principles.json
    python l4_interpret.py --personal path/to/personal_principles.json
    python l4_interpret.py --model gemini-3.7-flash   # real generation (needs GEMINI_API_KEY)
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from l4_generate import DEFAULT_MODEL, DEFAULT_TRANSLATION_MODEL, make_generator
from l4_routing import route, section_houses
from l4_sections import MOVEMENT, SECTION_ORDER
from l4_validate import PRECISION_TIER, SCHEMA_VERSION, validate

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------

def _load_json(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_personal(path: str) -> list[dict]:
    """Read personal_principles.json (§1 Input 2). Returns the kept `principles`
    array; asserts the kept_count contract."""
    payload = _load_json(path)
    principles = payload.get("principles")
    if not isinstance(principles, list):
        raise ValueError(f"{path}: missing `principles` array")
    kept_count = payload.get("kept_count")
    if kept_count is not None and kept_count != len(principles):
        raise ValueError(
            f"{path}: kept_count {kept_count} != len(principles) {len(principles)} (§1)"
        )
    return principles


def _ground_source(source: list[dict], chart: dict, reading: str) -> list[dict]:
    """Run L3 grounding to get this chart's kept set from the source dataset."""
    if _PARENT not in sys.path:
        sys.path.insert(0, _PARENT)
    grounding_dir = os.path.join(_PARENT, "principles_grounding")
    if grounding_dir not in sys.path:
        sys.path.insert(0, grounding_dir)
    from ground import ground  # type: ignore
    # Placidus-only reading: every house claim is verified in Placidus (ground.py).
    return ground(source, chart, reading=reading, house_policy="placidus").kept


# ---------------------------------------------------------------------------
# Assembly (§6)
# ---------------------------------------------------------------------------

def _assemble(synth_sections: list[dict],
              routed_ids: dict[str, set[str]] | None = None,
              houses: dict[str, int] | None = None) -> dict:
    routed_ids = routed_ids or {}
    houses = houses or {}
    by_key = {s.get("key"): s for s in synth_sections}
    sections: list[dict] = []
    for key in SECTION_ORDER:          # canonical order (§6)
        s = by_key.get(key)
        if not s:
            continue                    # omitted sections simply do not appear
        entry = {
            "key": key,
            "movement": MOVEMENT[key],
        }
        if key in houses:               # §6: house sections + luminary notes
            entry["house"] = houses[key]
        entry.update({
            "text_tr": s.get("text_tr", ""),
            "text_en": s.get("text_en", ""),
            # Grounding trace: the principle pool this section was built from
            # (structural, from routing §3). Retained for QA, stripped at render.
            "principle_ids": sorted(routed_ids.get(key, set())),
        })
        sections.append(entry)
    return {
        "schema_version": SCHEMA_VERSION,
        "precision_tier": PRECISION_TIER,
        "sections": sections,
    }


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def interpret(chart: dict, kept: list[dict], *, generator=None,
              model: str = DEFAULT_MODEL,
              synthesis_model: str | None = None,
              **gen_kwargs) -> tuple[dict, dict, list[str]]:
    """Run the full L4 pipeline. ``generator`` may be injected (tests); otherwise
    the model runner is constructed (extra kwargs — e.g. max_tokens,
    synthesis_max_tokens — pass through to it). Returns (output, routing_report,
    validation_errors)."""
    routing = route(kept, chart)
    routed_by_section = routing.non_empty()
    routed_ids = {
        key: {rp.principle_id for rp in routed}
        for key, routed in routed_by_section.items()
    }

    gen = generator or make_generator(model=model,
                                      synthesis_model=synthesis_model,
                                      **gen_kwargs)
    drafts = gen.section_all(routed_by_section, chart)
    synth = gen.synthesize(drafts, chart,
                           low_salience_ids=sorted(routing.low_salience_ids()))

    houses = section_houses(chart)
    output = _assemble(synth, routed_ids, houses)
    errors = validate(output, routed_ids)
    report = routing.report()
    report["house_policy"] = "placidus"
    report["luminary_houses"] = {k: houses[k] for k in ("sun_house", "moon_house")
                                 if k in houses}
    report["backend"] = type(gen).__name__
    report["sections_emitted"] = [s["key"] for s in output["sections"]]
    if getattr(gen, "usage", None):
        report["token_usage"] = gen.usage      # real input/output tokens, all calls
    if getattr(gen, "fallbacks", 0):
        report["cheap_model_fallbacks"] = gen.fallbacks
    return output, report, errors


def main() -> None:
    ap = argparse.ArgumentParser(description="Layer 4 interpretation (spec).")
    ap.add_argument("--chart",
                    default=os.path.join(_PARENT, "d_layer", "chart.json"),
                    help="full chart object from d_layer/compute_chart.py")
    ap.add_argument("--personal",
                    default=os.path.join(_PARENT, "principles_grounding",
                                         "personal_principles.json"),
                    help="personal_principles.json — L3 grounding output (§1 Input 2)")
    ap.add_argument("--grounded-source",
                    default=os.path.join(_HERE, "all_principles.grounded.json"),
                    help="fallback: full grounded corpus; ground() is run on it "
                         "only if --personal is missing")
    ap.add_argument("--reading", default="natal",
                    help="reading domain passed to ground() (fallback path only)")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"section-call model (default {DEFAULT_MODEL})")
    ap.add_argument("--synthesis-model", default=None,
                    help="synthesis-call model (default: same as --model)")
    ap.add_argument("--translation-model", default=DEFAULT_TRANSLATION_MODEL,
                    help=f"English translation + detox model (default "
                         f"{DEFAULT_TRANSLATION_MODEL}; 'same' = the synthesis model)")
    ap.add_argument("--max-tokens", type=int, default=None,
                    help="per-section output budget")
    ap.add_argument("--synthesis-max-tokens", type=int, default=None,
                    help="synthesis output budget (auto-grows on truncation)")
    ap.add_argument("--out", default=os.path.join(_HERE, "l4_output.json"))
    ap.add_argument("--report",
                    default=os.path.join(_HERE, "l4_routing_report.json"))
    args = ap.parse_args()

    chart = _load_json(args.chart)
    if os.path.exists(args.personal):
        kept = load_personal(args.personal)
        print(f"loaded {len(kept)} kept principles from {args.personal}")
    elif os.path.exists(args.grounded_source):
        source = _load_json(args.grounded_source)
        kept = _ground_source(source, chart, args.reading)
        print(f"personal_principles.json absent; grounded {len(kept)} from "
              f"{len(source)}-record corpus")
    else:
        ap.error(f"no input: neither {args.personal} nor {args.grounded_source} exists")

    gen_kwargs = {}
    gen_kwargs["translation_model"] = (None if args.translation_model == "same"
                                       else args.translation_model)
    if args.max_tokens is not None:
        gen_kwargs["max_tokens"] = args.max_tokens
    if args.synthesis_max_tokens is not None:
        gen_kwargs["synthesis_max_tokens"] = args.synthesis_max_tokens
    try:
        output, report, errors = interpret(
            chart, kept,
            model=args.model,
            synthesis_model=args.synthesis_model,
            **gen_kwargs,
        )
    except RuntimeError as err:
        print(f"\n{err}", file=sys.stderr)
        sys.exit(2)

    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(f"backend={report['backend']}  "
          f"sections={len(output['sections'])}  "
          f"routing report -> {args.report}")
    print("section counts:", report["section_counts"])
    if report.get("token_usage"):
        u = report["token_usage"]
        print(f"tokens: input={u['input_tokens']:,} output={u['output_tokens']:,} "
              f"over {u['calls']} calls")
    if report["dropped"]:
        print(f"routing dropped {report['dropped']} record(s) - see report")

    if errors:
        print(f"\nCONTRACT VIOLATION - {len(errors)} error(s), NOT writing output:",
              file=sys.stderr)
        for e in errors[:40]:
            print("  -", e, file=sys.stderr)
        sys.exit(1)

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(output, fh, ensure_ascii=False, indent=2)
    print(f"validated OK -> {args.out}")

    from l4_render import write_readable
    for path in write_readable(output, os.path.dirname(os.path.abspath(args.out))):
        print(f"readable text -> {path}")


if __name__ == "__main__":
    main()
