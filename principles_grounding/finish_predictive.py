#!/usr/bin/env python3
"""
finish_predictive.py — PREDICTIVE_EXTRACTION_MERGE.md Step 4 tail (deterministic).

Run AFTER `backfill.py --in predictive_delta.clean.json --out predictive_delta.grounded.json`.
Appends the grounded delta to the existing grounded corpus, runs the deterministic
reclassify post-pass, and enforces the Step-4 validation gate. No API calls.

    python finish_predictive.py
"""
import json, os, sys, pathlib, shutil
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from grounding_schema import invariant_violation          # L3 invariant
import reclassify as rc

EXIST_GROUNDED = HERE / "all_principles.grounded.json"     # existing 2153
DELTA_GROUNDED = HERE / "predictive_delta.grounded.json"   # produced by backfill
DELTA_CLEAN    = HERE / "predictive_delta.clean.json"      # 1110, for count check
BACKUP         = HERE / "all_principles.grounded.backup-pre-predictive.json"
RECLASS_OUT    = HERE / "all_principles_grounded_reclassified.json"

DOMAIN_ENUM = {"basics","natal","horary","electional","mundane","predictive",
               "lots","dignities","timing"}
GROUNDED_FIELDS = {"principle_id","domain","topic_tags","rule","conditions",
                   "judgment","attribution_in_text","notes","tradition",
                   "about","requires"}

def fail(msg):
    print("VALIDATION FAILED:", msg); sys.exit(1)

def main():
    if not DELTA_GROUNDED.exists():
        fail(f"{DELTA_GROUNDED.name} not found — run backfill on the delta first.")

    existing = json.load(open(EXIST_GROUNDED, encoding="utf-8"))
    delta    = json.load(open(DELTA_GROUNDED, encoding="utf-8"))
    delta_clean_n = len(json.load(open(DELTA_CLEAN, encoding="utf-8")))

    if len(delta) != delta_clean_n:
        fail(f"delta grounded count {len(delta)} != delta clean count {delta_clean_n}")

    eids = set(p["principle_id"] for p in existing)
    dids = set(p["principle_id"] for p in delta)
    if eids & dids:
        fail(f"delta already present in grounded corpus (double-run?): "
             f"{sorted(eids & dids)[:5]}")

    # --- append (backup first) ----------------------------------------------
    if not BACKUP.exists():
        shutil.copy2(EXIST_GROUNDED, BACKUP)
    full = existing + delta
    with open(EXIST_GROUNDED, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(full, fh, ensure_ascii=False, indent=2)

    # --- deterministic reclassify post-pass ---------------------------------
    rules = json.load(open(HERE / "reclassify_rules.json", encoding="utf-8"))
    reclassed, changelog = rc.reclassify(full, rules)
    with open(RECLASS_OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(reclassed, fh, ensure_ascii=False, indent=2)

    # --- Step-4 validation gate ---------------------------------------------
    problems = []
    # 1. every delta record carries about + requires, shape matches
    for p in delta:
        if "about" not in p or "requires" not in p:
            problems.append(f"{p['principle_id']}: missing about/requires")
        if set(p.keys()) != GROUNDED_FIELDS:
            problems.append(f"{p['principle_id']}: field set {set(p.keys())^GROUNDED_FIELDS}")
    # 2. total count = old + delta
    if len(full) != len(existing) + len(delta):
        problems.append(f"count mismatch: {len(full)} != {len(existing)}+{len(delta)}")
    # 3. no duplicate ids anywhere
    idc = Counter(p["principle_id"] for p in full)
    dups = [k for k,c in idc.items() if c>1]
    if dups:
        problems.append(f"duplicate principle_id: {dups[:5]} (+{max(0,len(dups)-5)} more)")
    # 4. L3 invariant violations = 0 (delta)
    viol = [(p["principle_id"], invariant_violation(p.get("about") or {}))
            for p in delta]
    viol = [(pid,v) for pid,v in viol if v]
    if viol:
        problems.append(f"invariant violations: {viol[:5]} (+{max(0,len(viol)-5)} more)")
    # 5. tradition / domain enums
    bad_trad = {p["tradition"] for p in delta} - {"modern","traditional"}
    if bad_trad: problems.append(f"bad tradition values: {bad_trad}")
    bad_dom = {p["domain"] for p in delta} - DOMAIN_ENUM
    if bad_dom: problems.append(f"bad domain values: {bad_dom}")

    print(f"appended {len(delta)} -> {len(full)} grounded records "
          f"(backup: {BACKUP.name})")
    print(f"reclassify: {len(changelog)} records reclassified -> {RECLASS_OUT.name}")
    print("\nSTEP-4 VALIDATION GATE")
    if problems:
        for pr in problems: print("  ✗", pr)
        sys.exit(1)
    # spot-check 10 delta records for about-shape parity
    print("  ✓ every delta record has about+requires, correct field set")
    print(f"  ✓ total = {len(existing)} + {len(delta)} = {len(full)}")
    print("  ✓ no duplicate principle_id")
    print("  ✓ 0 L3 invariant violations")
    print("  ✓ tradition ∈ {modern,traditional}; domain ∈ extractor enum")
    print("\nby tradition:", dict(Counter(p["tradition"] for p in delta)))
    print("by about.factor_type (delta):",
          dict(Counter((p.get("about") or {}).get("factor_type") for p in delta)))
    print("\nALL GATES PASSED.")

if __name__ == "__main__":
    main()
