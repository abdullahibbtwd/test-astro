#!/usr/bin/env python3
"""
finish_delta.py — corpus delta Step 4 (generalised from finish_predictive.py).

Grounds a CLEAN delta (adds ``about`` + ``requires`` with backfill's
deterministic tiers only — no LLM), applies a delta-appropriate gate, then
appends the grounded delta to the grounded corpus and its consumers:

    principles_grounding/all_principles.grounded.json          (+ .sha256 sidecar)
    Interpretation_layer/all_principles.grounded.json          (byte-identical mirror)
    principles_grounding/all_principles_grounded.with_predictive.json  (superset used
                                                                by the forecast pipeline)
    principles_grounding/all_principles_grounded_reclassified.json     (reclassify post-pass)

Why not ``backfill.py --in delta``: its build gate measures corpus-wide natal
floors, so a delta-only run is always "rejected" (that is what happened to the
predictive delta). The gate here is the one that makes sense for a delta: every
record classified at high confidence with the expected factor type, schema-valid,
no invariant violation, no id collision, count parity with the clean delta.

    python principles_grounding/finish_delta.py                      # houses delta
    python principles_grounding/finish_delta.py --delta-clean X.json --tag mytag \\
        --expect planet_in_house --house-system placidus
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
# Windows consoles may run a legacy code page; never let a report glyph abort the run.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from backfill import _NullExtractor, backfill          # noqa: E402
from grounding_schema import invariant_violation, validate_about  # noqa: E402
import reclassify as rc                                  # noqa: E402

GROUNDED = os.path.join(HERE, "all_principles.grounded.json")
GROUNDED_MIRROR = os.path.join(ROOT, "Interpretation_layer", "all_principles.grounded.json")
WITH_PREDICTIVE = os.path.join(HERE, "all_principles_grounded.with_predictive.json")
RECLASS_OUT = os.path.join(HERE, "all_principles_grounded_reclassified.json")

GROUNDED_FIELDS = {"principle_id", "domain", "topic_tags", "rule", "conditions",
                   "judgment", "attribution_in_text", "notes", "tradition",
                   "about", "requires"}


def _indent_of(path: str) -> int:
    """Preserve the on-disk indent style of an existing JSON array file."""
    with open(path, encoding="utf-8") as fh:
        fh.readline()
        second = fh.readline()
    return len(second) - len(second.lstrip(" ")) or 1


def _write_json(path: str, data, indent: int) -> str:
    payload = json.dumps(data, ensure_ascii=False, indent=indent)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(payload)
    return payload


def main() -> None:
    ap = argparse.ArgumentParser(description="Ground a clean delta and append it to the corpus.")
    ap.add_argument("--delta-clean", default=os.path.join(HERE, "houses_delta.clean.json"))
    ap.add_argument("--tag", default="houses", help="backup suffix + output stem")
    ap.add_argument("--expect", default="planet_in_house",
                    help="factor_type every delta record must resolve to ('' = any)")
    ap.add_argument("--house-system", default="placidus",
                    help="house_system every delta record must carry ('' = don't check)")
    args = ap.parse_args()

    if not os.path.exists(args.delta_clean):
        sys.exit(f"{args.delta_clean} not found — run the merge step first.")
    delta_clean = json.load(open(args.delta_clean, encoding="utf-8"))
    existing = json.load(open(GROUNDED, encoding="utf-8"))
    eids = {p["principle_id"] for p in existing}
    dids = [p["principle_id"] for p in delta_clean]
    if eids & set(dids):
        sys.exit(f"delta already present in the grounded corpus (double run?): "
                 f"{sorted(eids & set(dids))[:5]} ...")

    # --- ground the delta (deterministic tiers only) -------------------------
    grounded_delta = backfill(delta_clean, _NullExtractor())

    # --- delta gate ----------------------------------------------------------
    problems: list[str] = []
    if len(grounded_delta) != len(delta_clean):
        problems.append(f"count {len(grounded_delta)} != clean {len(delta_clean)}")
    if len(set(dids)) != len(dids):
        problems.append("duplicate ids inside the delta")
    ft_counter = Counter()
    for p in grounded_delta:
        about = p.get("about") or {}
        pid = p.get("principle_id")
        ft_counter[about.get("factor_type")] += 1
        if set(p) != GROUNDED_FIELDS:
            problems.append(f"{pid}: field set {sorted(set(p) ^ GROUNDED_FIELDS)}")
        if args.expect and about.get("factor_type") != args.expect:
            problems.append(f"{pid}: factor_type {about.get('factor_type')!r} != {args.expect!r}")
        if about.get("extraction_confidence") != "high":
            problems.append(f"{pid}: confidence {about.get('extraction_confidence')!r}")
        if args.house_system and about.get("house_system") != args.house_system:
            problems.append(f"{pid}: house_system {about.get('house_system')!r}")
        viol = invariant_violation(about)
        if viol:
            problems.append(f"{pid}: invariant {viol}")
        ok, errs = validate_about(about)
        if not ok:
            problems.append(f"{pid}: schema {errs}")
        if not p.get("requires"):
            problems.append(f"{pid}: empty requires")
    print("DELTA GATE")
    print(f"  factor types: {dict(ft_counter)}")
    if problems:
        for pr in problems[:25]:
            print("  [x]", pr)
        rejected = os.path.join(HERE, f"{args.tag}_delta.grounded.rejected.json")
        _write_json(rejected, grounded_delta, 2)
        sys.exit(f"{len(problems)} problem(s) — nothing appended; see {os.path.basename(rejected)}")
    print(f"  [ok] {len(grounded_delta)} records: high confidence, "
          f"{args.expect or 'any type'}, {args.house_system or 'any system'}, schema-valid, "
          f"0 invariant violations, no id collisions")
    delta_out = os.path.join(HERE, f"{args.tag}_delta.grounded.json")
    _write_json(delta_out, grounded_delta, 2)

    # --- append to the grounded corpus (+ sidecar, mirror) -------------------
    backup = GROUNDED.replace(".json", f".backup-pre-{args.tag}.json")
    if not os.path.exists(backup):
        shutil.copy2(GROUNDED, backup)
    full = existing + grounded_delta
    payload = _write_json(GROUNDED, full, _indent_of(GROUNDED))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    with open(GROUNDED + ".sha256", "w", encoding="utf-8") as fh:
        fh.write(f"{digest}  {os.path.basename(GROUNDED)}\n"
                 f"out_of_scope={sum(1 for r in full if r.get('out_of_scope'))} "
                 f"invariant_violations=0 records={len(full)}\n")
    shutil.copyfile(GROUNDED, GROUNDED_MIRROR)

    # --- keep the forecast pipeline's superset corpus a superset -------------
    if os.path.exists(WITH_PREDICTIVE):
        wp = json.load(open(WITH_PREDICTIVE, encoding="utf-8"))
        wp_ids = {p["principle_id"] for p in wp}
        add = [p for p in grounded_delta if p["principle_id"] not in wp_ids]
        wp_backup = WITH_PREDICTIVE.replace(".json", f".backup-pre-{args.tag}.json")
        if add:
            if not os.path.exists(wp_backup):
                shutil.copy2(WITH_PREDICTIVE, wp_backup)
            _write_json(WITH_PREDICTIVE, wp + add, _indent_of(WITH_PREDICTIVE))
        print(f"  with_predictive: +{len(add)} -> {len(wp) + len(add)}")

    # --- deterministic reclassify post-pass over the full corpus -------------
    rules = json.load(open(os.path.join(HERE, "reclassify_rules.json"), encoding="utf-8"))
    reclassed, changelog = rc.reclassify(full, rules)
    _write_json(RECLASS_OUT, reclassed, 2)

    # --- final corpus checks -------------------------------------------------
    idc = Counter(p["principle_id"] for p in full)
    dups = [k for k, c in idc.items() if c > 1]
    if dups:
        sys.exit(f"duplicate principle_id after append: {dups[:5]}")
    natal = Counter((p.get("about") or {}).get("factor_type") for p in full if p.get("domain") == "natal")
    print(f"\nappended {len(grounded_delta)} -> {len(full)} grounded records "
          f"(backup: {os.path.basename(backup)}); mirror refreshed; sha256 {digest[:16]}…")
    print(f"reclassify post-pass: {len(changelog)} record(s) -> {os.path.basename(RECLASS_OUT)}")
    print(f"natal factor types now: {dict(natal)}")
    print("\nALL GATES PASSED.")


if __name__ == "__main__":
    main()
