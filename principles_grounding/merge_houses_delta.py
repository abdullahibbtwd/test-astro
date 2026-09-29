#!/usr/bin/env python3
"""
merge_houses_delta.py — corpus delta Step 3 for the planets-in-houses set
(mirrors TXT/PREDICTIVE_EXTRACTION_MERGE.md §3 and merge_predictive.py).

Takes ``houses_delta.raw.json`` (from extract_houses.py), checks every record
against the shape the pipeline relies on, resolves principle_id collisions
(within the delta AND against the clean corpus) by suffixing -2/-3 — never
overwriting — flags near-duplicates of existing natal records for human review
(report only; default KEEP), then appends the delta to BOTH copies of the
pre-grounding clean corpus (TXT/ and principles_grounding/), backing each up
first. Writes ``houses_delta.clean.json`` (the exact records appended) for
``finish_delta.py``.

Re-running after a successful merge is refused (the delta ids are already in
the corpus), so a double-append cannot happen by accident.

    python principles_grounding/merge_houses_delta.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

RAW = os.path.join(HERE, "houses_delta.raw.json")
DELTA_CLEAN = os.path.join(HERE, "houses_delta.clean.json")
CLEAN_FILES = [os.path.join(ROOT, "TXT", "all_principles.clean.json"),
               os.path.join(HERE, "all_principles.clean.json")]
BACKUP_SUFFIX = ".backup-pre-houses.json"
MERGE_REPORT = os.path.join(HERE, "houses_delta.merge_report.json")
NEARDUP_REPORT = os.path.join(HERE, "houses_delta.near_dupes_review.json")

FIELDS = ["principle_id", "domain", "topic_tags", "rule", "conditions",
          "judgment", "attribution_in_text", "notes", "tradition"]
PLANETS = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
           "Uranus", "Neptune", "Pluto")
_ID_RE = re.compile(r"^(sun|moon|mercury|venus|mars|jupiter|saturn|uranus|neptune|pluto)"
                    r"-(\d{1,2})(st|nd|rd|th)-[a-z0-9-]+$")


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def check_shape(r: dict) -> list[str]:
    """Everything backfill Tier-1 and the natal gate key on. Returns problems."""
    p: list[str] = []
    if set(r) != set(FIELDS):
        p.append(f"field set {sorted(set(r) ^ set(FIELDS))}")
    if r.get("domain") != "natal":
        p.append(f"domain {r.get('domain')!r}")
    if r.get("tradition") != "modern":
        p.append(f"tradition {r.get('tradition')!r}")
    cond = r.get("conditions")
    if not (isinstance(cond, dict) and cond.get("planet") in PLANETS
            and isinstance(cond.get("house"), int) and 1 <= cond["house"] <= 12):
        p.append(f"conditions {cond!r}")
        return p
    planet, house = cond["planet"], cond["house"]
    m = _ID_RE.match(r.get("principle_id") or "")
    if not m or m.group(1) != planet.lower() or int(m.group(2)) != house:
        p.append(f"id {r.get('principle_id')!r} does not encode {planet} / house {house}")
    tags = [str(t) for t in (r.get("topic_tags") or [])]
    if planet not in tags or f"{ordinal(house)} house" not in tags:
        p.append(f"tags lack {planet!r} / '{ordinal(house)} house'")
    if len((r.get("rule") or "").strip()) < 40:
        p.append("rule too short")
    return p


def suffix_free(base: str, taken: set[str]) -> str:
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


def tags_of(r: dict) -> set[str]:
    return {t.lower().strip() for t in (r.get("topic_tags") or []) if isinstance(t, str)}


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Merge the planets-in-houses delta into the clean corpus.")
    ap.add_argument("--dry-run", action="store_true",
                    help="run every check and print the report; write nothing")
    ap.add_argument("--expect-units", type=int, default=120,
                    help="refuse to merge unless this many (planet, house) placements are covered")
    args = ap.parse_args()

    if not os.path.exists(RAW):
        sys.exit(f"{os.path.relpath(RAW, ROOT)} not found — run extract_houses.py first")
    delta = json.load(open(RAW, encoding="utf-8"))
    covered = {((r.get("conditions") or {}).get("planet"), (r.get("conditions") or {}).get("house"))
               for r in delta}
    if args.expect_units and len(covered) != args.expect_units:
        sys.exit(f"delta covers {len(covered)} placements, expected {args.expect_units} — "
                 f"extraction incomplete? (re-run extract_houses.py; pass --expect-units to override)")
    corpora = {p: json.load(open(p, encoding="utf-8")) for p in CLEAN_FILES}
    canonical = corpora[CLEAN_FILES[1]]
    corpus_ids = {r.get("principle_id") for r in canonical}

    # refuse a double merge
    already = sum(1 for r in delta if r.get("principle_id") in corpus_ids
                  and any(c.get("rule") == r.get("rule") for c in canonical
                          if c.get("principle_id") == r.get("principle_id")))
    if already:
        sys.exit(f"{already} delta record(s) are already in the clean corpus with identical "
                 f"text — this delta was merged before. Nothing done.")

    # shape gate (hard): a malformed record would silently miss Tier-1 later
    problems = {r.get("principle_id"): check_shape(r) for r in delta}
    problems = {k: v for k, v in problems.items() if v}
    if problems:
        for k, v in list(problems.items())[:15]:
            print(f"  ✗ {k}: {'; '.join(v)}")
        sys.exit(f"{len(problems)} malformed record(s) — fix the extractor output first.")

    # id uniqueness: within delta and against the corpus
    taken = set(corpus_ids)
    renames = []
    for r in delta:
        orig = r["principle_id"]
        new = suffix_free(orig, taken)
        if new != orig:
            renames.append({"original": orig, "renamed_to": new,
                            "reason": "collision with corpus" if orig in corpus_ids
                                      else "collision within delta"})
            r["principle_id"] = new
        taken.add(r["principle_id"])

    # near-duplicate flagging against existing NATAL records (report only)
    natal = [c for c in canonical if c.get("domain") == "natal"]
    by_point_house = defaultdict(list)
    for c in natal:
        cond = c.get("conditions")
        if isinstance(cond, dict) and cond.get("planet") and cond.get("house"):
            by_point_house[(str(cond["planet"]), int(cond["house"]) if str(cond["house"]).isdigit() else cond["house"])].append(c)
    near = []
    for r in delta:
        key = (r["conditions"]["planet"], r["conditions"]["house"])
        dtags = tags_of(r) - {r["conditions"]["planet"].lower(), f"{ordinal(key[1])} house"}
        cands = []
        for c in by_point_house.get(key, []):
            ctags = tags_of(c) - {key[0].lower(), f"{ordinal(key[1])} house"}
            jac = len(dtags & ctags) / len(dtags | ctags) if (dtags | ctags) else 0.0
            if jac >= 0.5:
                cands.append({"corpus_id": c.get("principle_id"), "tradition": c.get("tradition"),
                              "score": round(jac, 3)})
        if cands:
            cands.sort(key=lambda x: x["score"], reverse=True)
            near.append({"delta_id": r["principle_id"], "candidates": cands[:5]})

    # append to both clean corpora (backup first), same formatting as before
    if not args.dry_run:
        for path, corpus in corpora.items():
            backup = path.replace(".json", BACKUP_SUFFIX)
            if not os.path.exists(backup):
                shutil.copy2(path, backup)
            merged = corpus + delta
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(merged, fh, ensure_ascii=False, indent=2)
        with open(DELTA_CLEAN, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(delta, fh, ensure_ascii=False, indent=2)

    per_placement = Counter((r["conditions"]["planet"], r["conditions"]["house"]) for r in delta)
    report = {
        "clean_corpus_before": len(canonical),
        "delta_records": len(delta),
        "merged_total": len(canonical) + len(delta),
        "placements_covered": len(per_placement),
        "records_per_placement": {"min": min(per_placement.values()),
                                  "max": max(per_placement.values()),
                                  "mean": round(sum(per_placement.values()) / len(per_placement), 2)},
        "by_planet": dict(Counter(r["conditions"]["planet"] for r in delta)),
        "id_collisions_renamed": len(renames),
        "renames": renames,
        "near_dupes_flagged": len(near),
        "backups": [p.replace(".json", BACKUP_SUFFIX) for p in CLEAN_FILES],
    }
    if not args.dry_run:
        json.dump(report, open(MERGE_REPORT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        json.dump(near, open(NEARDUP_REPORT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("STEP 3 — MERGE (planets-in-houses delta)" + ("  [DRY RUN — nothing written]" if args.dry_run else ""))
    for k in ("clean_corpus_before", "delta_records", "merged_total", "placements_covered",
              "records_per_placement", "id_collisions_renamed", "near_dupes_flagged"):
        print(f"  {k}: {report[k]}")
    print(f"  by_planet: {report['by_planet']}")
    verb = "would append" if args.dry_run else "appended"
    print(f"  -> {verb} to {len(CLEAN_FILES)} clean corpus files; delta saved as "
          f"{os.path.basename(DELTA_CLEAN)}; reports: {os.path.basename(MERGE_REPORT)}, "
          f"{os.path.basename(NEARDUP_REPORT)}")


if __name__ == "__main__":
    main()
