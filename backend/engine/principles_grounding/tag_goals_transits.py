#!/usr/bin/env python3
"""
tag_goals_transits.py - goal tags on modern predictive records (CAL_02 §2).

It generalises tag_goals_acg.py (ACG_07 §5) to the transit corpus and reuses its
Tagger, output validation, batch parsing and cache-key logic. Only the prompt,
the record selection and the output location differ.

Per decision Q3 (Calendar/CAL_EXPLORATION_REPORT.md) the shared corpus file is NOT
modified. Tags go to a sidecar ``transit_goal_tags.json``
({principle_id: goal_effects}), which the calendar reads.

Scope: ``--scope transits`` (default) = every modern transit record in the CAL index
(both Hand copies, incl. transits to ASC/MC and transiting-Moon aspects) plus the
generic lunation / eclipse / station records.

    python principles_grounding/tag_goals_transits.py --dry-run
    python principles_grounding/tag_goals_transits.py --limit 40
    python principles_grounding/tag_goals_transits.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (ROOT, HERE, os.path.join(ROOT, "Astrocartography"), os.path.join(ROOT, "Calendar")):
    if p not in sys.path:
        sys.path.insert(0, p)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import cal_corpus  # noqa: E402
import llm_client  # noqa: E402
from acg_constants import GOAL_ORDER, GOAL_POLARITIES, GOALS, MAX_GOALS_PER_RECORD  # noqa: E402
from tag_goals_acg import SCHEMA, Tagger, cache_key, canonical  # noqa: E402

OUT = os.path.join(HERE, "transit_goal_tags.json")
REPORT = os.path.join(HERE, "transit_goal_tagging_report.json")
WORK_DIR = os.path.join(ROOT, "TXT", "extracted_predictive")
CACHE = os.path.join(WORK_DIR, "transit_goal_tag_cache.json")
BATCH = 20
FIELD = "goal_effects"

_GOAL_LINES = "\n".join(f"- {g}: {GOALS[g][2]}" for g in GOAL_ORDER)

SYSTEM = f"""You tag astrological transit interpretation records with life goals.

Each record describes what a period brings to a person while a transiting planet forms an aspect
to a point of their birth chart (or, for a few records, what a new/full moon, eclipse or
planetary station falling on a birth-chart point brings). For each record decide which life goals
its meaning DIRECTLY concerns and, for each tagged goal, whether the record is supportive,
challenging or mixed for that goal during the period.

The goals are a closed set. Use only these keys, with exactly these definitions (a record must
directly concern what the definition lists):
{_GOAL_LINES}

Rules:
1. Tag a goal ONLY if the record's meaning directly concerns it, per its definition. Do not infer
   goals from loose associations or from the planet's general symbolism when the record's text
   does not speak to them.
   A record concerns a goal in either direction: text about pressure, strain, tension, crisis,
   low vitality or exhaustion directly concerns rest (challenging); text about financial
   restriction or loss directly concerns money (challenging); text about quarrels with or
   separation from a partner directly concerns love (challenging).
   Travel and relocation are RARE for transit records. Tag travel only when the text explicitly
   mentions journeys, trips or travel. Tag relocation only when the text explicitly mentions
   changing residence, moving house or settling in a new place; growth, change, new beginnings,
   home life or family do NOT make a record about relocation (home life is family).
2. At most {MAX_GOALS_PER_RECORD} goals per record; choose the most direct ones. An empty object
   {{}} is valid when no goal is directly concerned.
3. The polarity is PER GOAL: "supportive" (the period favours that goal), "challenging" (it
   hinders or strains that goal), or "mixed" (it clearly does both for that goal). A record can
   be supportive for one goal and challenging for another.
4. Judge only from the record's rule, conditions and judgment. Return one result per input
   record, with its principle_id copied exactly, and no other records.

Output JSON only: {{"results": [{{"principle_id": "...", "goal_effects": {{"<goal>": "<polarity>"}}}}]}}"""

_POINT_NAME = {"asc": "Ascendant", "mc": "Midheaven"}


def subject_of(r: dict) -> str:
    k = cal_corpus.transit_key_of(r)
    if k:
        t, a, n = k
        return f"transiting {t.title()} {a} natal {_POINT_NAME.get(n, n.title())}"
    for kind, ids in cal_corpus.GENERIC_IDS.items():
        if r["principle_id"] in ids:
            return f"general statement about {kind.replace('_', ' ')}s"
    return "transit"


def user_prompt(batch: list[dict]) -> str:
    items = [{"principle_id": r["principle_id"], "subject": subject_of(r), "rule": r["rule"],
              "conditions": r.get("conditions") or [], "judgment": r.get("judgment")}
             for r in batch]
    return ("Tag each of these records.\n\n"
            + json.dumps({"records": items}, ensure_ascii=False, indent=1))


def _dump(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _write(path: str, payload: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(payload)
    os.replace(tmp, path)


def load_cache() -> dict:
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def save_cache(cache: dict) -> None:
    os.makedirs(WORK_DIR, exist_ok=True)
    _write(CACHE, _dump(dict(sorted(cache.items()))))


def select(scope: str) -> list[dict]:
    idx, modern = cal_corpus.load()
    if scope != "transits":
        raise SystemExit(f"unknown scope {scope!r} (supported: transits)")
    return [modern[i] for i in cal_corpus.tag_scope_ids(idx)]


def main() -> None:
    ap = argparse.ArgumentParser(description="Tag modern predictive records with goal_effects (CAL_02 §2).")
    ap.add_argument("--scope", default="transits")
    ap.add_argument("--model", default=llm_client.DEFAULT_CHEAP_MODEL,
                    help="default gpt-6-luna: gemini-3.7-flash over-tagged relocation in the trial")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    targets = select(args.scope)
    cache = load_cache()
    pending = [r for r in targets if cache_key(r) not in cache]
    if args.limit:
        pending = pending[:args.limit]
    batches = [pending[i:i + BATCH] for i in range(0, len(pending), BATCH)]
    print(f"{len(targets)} records in scope {args.scope!r}; cached {len(targets) - len([r for r in targets if cache_key(r) not in cache])}; "
          f"to tag {len(pending)} in {len(batches)} batch(es); model {args.model}")
    if args.dry_run:
        if batches:
            print("\n--- system prompt ---\n" + SYSTEM)
            print("\n--- first user prompt (truncated) ---\n" + user_prompt(batches[0])[:2000])
        print("\ndry run: no model calls, nothing written.")
        return

    if batches:
        llm_client.require_api_key(args.model, "transit goal tagging")
    tagger = Tagger(args.model, system=SYSTEM, schema=SCHEMA, prompt_fn=user_prompt)
    invalid: dict = {}
    retried = 0
    lock = threading.Lock()

    def run(n_b):
        nonlocal retried
        n, b = n_b
        valid, bad, nr = tagger.tag(b, f"tgoals/{n:03d}")
        with lock:
            retried += nr
            for r in b:
                pid = r["principle_id"]
                if pid in valid:
                    cache[cache_key(r)] = {"principle_id": pid, FIELD: valid[pid], "model": tagger.model}
            invalid.update(bad)
            save_cache(cache)
        print(f"  batch {n:03d}: {len(valid)}/{len(b)} valid", flush=True)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        list(pool.map(run, enumerate(batches, 1)))

    tags = {}
    for r in targets:
        hit = cache.get(cache_key(r))
        if hit is not None:
            tags[r["principle_id"]] = canonical(hit[FIELD])
    payload = _dump(tags)
    _write(OUT, payload)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    transit_ids = [r["principle_id"] for r in targets if cal_corpus.transit_key_of(r)]
    per_goal = Counter(g for i in transit_ids for g in tags.get(i, {}))
    pol = {g: dict(Counter(tags[i][g] for i in transit_ids if g in tags.get(i, {}))) for g in GOAL_ORDER}
    share = sum(1 for i in transit_ids if tags.get(i)) / max(1, len(transit_ids))
    report = {
        "model": args.model, "scope": args.scope, "records": len(targets),
        "tagged": len(tags), "untagged": sorted(r["principle_id"] for r in targets if r["principle_id"] not in tags),
        "transit_records": len(transit_ids),
        "transit_records_with_goal_share": round(share, 4),
        "guard_share_ok": share >= 0.80,
        "records_per_goal": {g: per_goal.get(g, 0) for g in GOAL_ORDER},
        "guard_goals_below_20": sorted(g for g in GOAL_ORDER if per_goal.get(g, 0) < 20),
        "goal_polarity_counts": pol,
        "this_run": {"batches": len(batches), "calls": tagger.calls, "records_retried": retried,
                     "model_fallbacks": tagger.fallbacks, "invalid_left_empty": invalid,
                     "usage": tagger.usage, "seconds": round(time.time() - t0, 1)},
        "tags_sha256": digest,
    }
    _write(REPORT, _dump(report))
    print(f"tagged {len(tags)}/{len(targets)}; transit share with >=1 goal {share:.1%}; "
          f"per goal {report['records_per_goal']}; usage {tagger.usage}")
    if report["guard_goals_below_20"] or not report["guard_share_ok"]:
        print(f"GUARD (non-blocking): share_ok={report['guard_share_ok']} "
              f"goals<20={report['guard_goals_below_20']}")


if __name__ == "__main__":
    main()
