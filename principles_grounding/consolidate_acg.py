#!/usr/bin/env python3
"""
consolidate_acg.py — ACG corpus delta, step 2 (spec ``ACG/ACG_06_CORPUS_DELTA_SPEC.md`` §6).

Reads ``TXT/extracted_acg/acg_raw.jsonl`` (from ``extract_acg.py``), buckets the
records, and merges near-duplicates:

  * fixed Introduction ids (spec §4.1)   -> passed through verbatim (never renamed/merged)
  * ``line`` (planet, angle)             -> ONE LLM merge call per bucket, target 4-10
  * ``planet_general`` (planet)          -> ONE LLM merge call per planet
  * paran / zenith / ccg / mundane       -> deterministic (exact-duplicate removal only);
                                            preserved, excluded from v1 retrieval

The model only rewrites text and says which input indices each merged record covers;
everything countable is computed in code: ``citation_count`` = sum over the merged
inputs, ``source_span`` = page envelope, ``conditions`` = union of the inputs'
conditions (the prompt forbids merging differing conditions; any union is logged),
``sensitivity`` = high if any input is high. Supportive and challenging inputs are
kept apart (a merge that mixes them is logged and marked ``mixed``). Buckets with
fewer than 4 inputs are kept as they are. Never pads.

Outputs:
    TXT/extracted_acg/acg_consolidated.json            (pre-guard text: stays gitignored)
    principles_grounding/acg_consolidation_report.json (counts only; for the review gate)
Per-bucket LLM results are cached under TXT/extracted_acg/consolidate/ keyed by an
input hash, so re-runs are free and deterministic.

    python principles_grounding/consolidate_acg.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import llm_client  # noqa: E402
from extract_acg import (ANGLES, PLANETS, POLARITIES, WORK_DIR, RAW_OUT,  # noqa: E402
                         mh_to_mc, sensitivity_of, _tags)

CACHE_DIR = os.path.join(WORK_DIR, "consolidate")
CONS_OUT = os.path.join(WORK_DIR, "acg_consolidated.json")
REPORT_OUT = os.path.join(HERE, "acg_consolidation_report.json")

ANGLE_WORD = {"ASC": "Ascendant (ASC)", "DSC": "Descendant (DSC)", "MC": "Midheaven (MC)",
              "IC": "IC (Imum Coeli)"}
DISCARD_REASONS = ("biographical", "not_generalisable", "off_bucket", "noise")

MERGE_SYSTEM = """You consolidate astrocartography (ACG) principles that were extracted \
from many case studies of one book. All input items belong to ONE bucket: {bucket}.

Produce the consolidated set:
1. Merge near-duplicates (items that state essentially the same meaning) into ONE record \
whose wording is a fresh, neutral synthesis of those items. Keep genuinely distinct \
meanings as separate records.
2. NEVER merge a "supportive" item with a "challenging" item. "mixed" items may join \
either side only if the meaning truly matches; otherwise keep them apart.
3. NEVER merge items whose conditions differ (conditions are shown per item).
4. Target {target} output records. If there are fewer distinct meanings, output fewer. \
Never pad, never invent content that is not in the inputs.
5. Every output record lists "sources": the indices of the input items it covers. Each \
input index appears in AT MOST one output record. An input that is purely biographical, \
not generalisable, or not about this bucket goes in "discarded" with a reason \
(biographical | not_generalisable | off_bucket | noise) instead.
6. Wording rules: no personal names, place names, dates or events; third person, present \
tense, never "you"; planet names in full; angles as ASC/DSC/MC/IC; no "MH". rule = 1-3 \
sentences; judgment = one sentence; notes = nuance or "". topic_tags = 3-6 lower-case theme \
tags (no planet/angle names).
7. polarity per output: supportive | challenging | mixed. sensitivity: "high" if the \
meaning involves death, violence, accident, injury, illness, crime, addiction or \
victimisation, else "normal"."""

MERGE_USER = """INPUT ITEMS ({n}):
{items}

Return JSON {{"records": [...], "discarded": [...]}}."""

MERGE_SCHEMA = {
    "type": "object",
    "properties": {
        "records": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "sources": {"type": "array", "items": {"type": "integer"}},
                "rule": {"type": "string"},
                "judgment": {"type": "string"},
                "notes": {"type": "string"},
                "topic_tags": {"type": "array", "items": {"type": "string"}},
                "polarity": {"type": "string", "enum": list(POLARITIES)},
                "sensitivity": {"type": "string", "enum": ["normal", "high"]},
            },
            "required": ["sources", "rule", "judgment", "notes", "topic_tags", "polarity",
                         "sensitivity"]}},
        "discarded": {"type": "array", "items": {
            "type": "object",
            "properties": {"index": {"type": "integer"},
                           "reason": {"type": "string", "enum": list(DISCARD_REASONS)}},
            "required": ["index", "reason"]}},
    },
    "required": ["records", "discarded"],
}


def load_raw(path: str = RAW_OUT) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(ln) for ln in fh if ln.strip()]


def bucket_key(r: dict) -> tuple:
    if r.get("_fixed_id"):
        return ("fixed", r["_fixed_id"])
    s = r["acg_scope"]
    if s == "line":
        return ("line", r["_planet"], r["_angle"])
    if s == "planet_general":
        return ("planet_general", r["_planet"])
    if s == "paran":
        return ("paran",) + tuple(r["_planets"])
    if s == "zenith":
        return ("zenith", r.get("_planet") or "")
    if s == "ccg":
        return ("ccg",)
    return (s,)


def key_str(k: tuple) -> str:
    return "|".join(x for x in k if x)


def _cond_key(c: list) -> str:
    return json.dumps(c or [], sort_keys=True, ensure_ascii=False)


def _render_cond(c: list) -> str:
    if not c:
        return "none"
    parts = []
    for item in c:
        (k, v), = item.items()
        parts.append(f"{k}: {v}" if not isinstance(v, dict)
                     else f"{k}(" + ", ".join(f"{a}={b}" for a, b in v.items()) + ")")
    return "; ".join(parts)


def _render_items(recs: list[dict]) -> str:
    out = []
    for i, r in enumerate(recs):
        out.append(f"[{i}] polarity={r['polarity']} sensitivity={r['sensitivity']} "
                   f"conditions={_render_cond(r['conditions'])}\n"
                   f"    rule: {r['rule']}\n    judgment: {r.get('judgment') or ''}"
                   + (f"\n    notes: {r['notes']}" if r.get("notes") else ""))
    return "\n".join(out)


def _bucket_label(k: tuple) -> str:
    if k[0] == "line":
        return f"{k[1].capitalize()} on the {ANGLE_WORD[k[2]]} line"
    return f"the general locational meaning of {k[1].capitalize()} (planet synopsis and " \
           f"profession tendencies) when it dominates a location"


def _hash(system: str, user: str, model: str) -> str:
    return hashlib.sha256(f"{model}\n{system}\n{user}".encode("utf-8")).hexdigest()[:16]


def merge_bucket(k: tuple, recs: list[dict], model: str) -> dict:
    """Return the (cached) model output for one bucket."""
    target = "4-10" if k[0] == "line" else "3-8 (at least one supportive and one challenging)"
    system = MERGE_SYSTEM.replace("{bucket}", _bucket_label(k)).replace("{target}", target)
    user = MERGE_USER.format(n=len(recs), items=_render_items(recs))
    h = _hash(system, user, model)
    path = os.path.join(CACHE_DIR, f"{key_str(k).replace('|', '_')}.json")
    if os.path.exists(path):
        cached = json.load(open(path, encoding="utf-8"))
        if cached.get("hash") == h:
            return cached
    usage = {kk: 0 for kk in llm_client.USAGE_KEYS}
    last: Exception | None = None
    for attempt in range(1, 4):
        try:
            resp = llm_client.complete(model, system, user, max_tokens=16000,
                                       temperature=0.2, schema=MERGE_SCHEMA, timeout_s=300.0,
                                       label=f"acg-merge/{key_str(k)}")
            for kk in usage:
                usage[kk] += (resp.usage or {}).get(kk, 0)
            if resp.stop_reason == "max_tokens":
                raise RuntimeError("output truncated")
            data = json.loads(resp.text)
            if not data.get("records"):
                raise RuntimeError("no records returned")
            out = {"bucket": key_str(k), "hash": h, "model": model, "usage": usage,
                   "n_in": len(recs), "result": data}
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(out, fh, ensure_ascii=False, indent=2)
            return out
        except (json.JSONDecodeError, RuntimeError) as exc:
            last = exc
            time.sleep(2 * attempt)
        except llm_client.transient_errors(model) as exc:
            last = exc
            time.sleep(5 * attempt)
    raise RuntimeError(f"{key_str(k)}: merge failed after 3 attempts: {last}")


def _lead_tags(r: dict) -> list[str]:
    lead = ["astrocartography"]
    if r["_planet"] and r["acg_scope"] != "paran":
        lead.append(r["_planet"].capitalize())
    for p in r.get("_planets") or []:
        lead.append(p.capitalize())
    if r["_angle"]:
        lead.append(r["_angle"])
    return lead


def apply_merge(k: tuple, recs: list[dict], out: dict, log: dict) -> list[dict]:
    data = out["result"]
    used: set[int] = set()
    merged: list[dict] = []
    for item in data.get("records") or []:
        srcs = []
        for i in item.get("sources") or []:
            if isinstance(i, int) and 0 <= i < len(recs) and i not in used:
                srcs.append(i)
                used.add(i)
        rule = mh_to_mc((item.get("rule") or "").strip())
        if not srcs or len(rule) < 40:
            for i in srcs:
                used.discard(i)
            continue
        src = [recs[i] for i in srcs]
        pols = {s["polarity"] for s in src}
        if {"supportive", "challenging"} <= pols:
            polarity = "mixed"
            log["polarity_mixed_merges"].append(key_str(k))
        elif len(pols) == 1:
            polarity = next(iter(pols))
        else:
            polarity = item.get("polarity") if item.get("polarity") in POLARITIES else "mixed"
        conds: list = []
        for s in src:
            for c in s["conditions"] or []:
                if c not in conds:
                    conds.append(c)
        if len({_cond_key(s["conditions"]) for s in src}) > 1:
            log["condition_unions"].append(key_str(k))
        judgment = mh_to_mc((item.get("judgment") or "").strip()) or None
        notes = mh_to_mc((item.get("notes") or "").strip()) or None
        blob = " ".join(filter(None, [rule, judgment, notes]))
        declared = "high" if (item.get("sensitivity") == "high" or
                              any(s["sensitivity"] == "high" for s in src)) else "normal"
        base = src[0]
        tags = _tags({"topic_tags": item.get("topic_tags")}, _lead_tags(base))
        if any("vocation" in (s.get("topic_tags") or []) for s in src) \
                and "vocation" not in tags:
            tags.append("vocation")
        merged.append({
            **{kk: base[kk] for kk in ("domain", "attribution_in_text", "tradition", "source",
                                       "acg_scope", "_planet", "_angle", "_planets")},
            "principle_id": None,
            "topic_tags": tags,
            "rule": rule,
            "conditions": conds,
            "judgment": judgment,
            "notes": notes,
            "polarity": polarity,
            "sensitivity": sensitivity_of(blob, declared),
            "citation_count": sum(s["citation_count"] for s in src),
            "source_span": {"page_start": min(s["source_span"]["page_start"] for s in src),
                            "page_end": max(s["source_span"]["page_end"] for s in src)},
            "_fixed_id": None,
            "_merged_from": sorted(s["principle_id"] for s in src),
        })
    discarded = {}
    for d in data.get("discarded") or []:
        i = d.get("index")
        if isinstance(i, int) and 0 <= i < len(recs) and i not in used:
            discarded[i] = d.get("reason") if d.get("reason") in DISCARD_REASONS else "noise"
    orphans = [i for i in range(len(recs)) if i not in used and i not in discarded]
    for i in orphans:                 # unaccounted inputs are kept, never silently lost
        merged.append({**recs[i], "principle_id": None, "_merged_from": [recs[i]["principle_id"]]})
    log["orphans_kept"] += len(orphans)
    for i, reason in sorted(discarded.items()):
        log["discarded"].append({"bucket": key_str(k), "raw_id": recs[i]["principle_id"],
                                 "reason": reason})
    return merged


def exact_dedupe(recs: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    out = []
    for r in recs:
        norm = re.sub(r"\W+", " ", r["rule"].lower()).strip()
        if norm in seen:
            keep = seen[norm]
            keep["citation_count"] += r["citation_count"]
            keep["_merged_from"].append(r["principle_id"])
            continue
        r = {**r, "_merged_from": [r["principle_id"]]}
        seen[norm] = r
        out.append(r)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Consolidate ACG raw records (spec 06 §6).")
    ap.add_argument("--model", default=llm_client.DEFAULT_MODEL)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    raw = load_raw()
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for r in raw:
        buckets[bucket_key(r)].append(r)
    llm_buckets = [k for k in buckets if k[0] in ("line", "planet_general") and len(buckets[k]) >= 4]
    print(f"{len(raw)} raw records in {len(buckets)} buckets; {len(llm_buckets)} LLM merge "
          f"call(s) needed (cached ones are free)")
    if llm_buckets:
        llm_client.require_api_key(args.model, "ACG consolidation")

    results: dict[tuple, dict] = {}
    failed: list[str] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(merge_bucket, k, buckets[k], args.model): k for k in llm_buckets}
        for fut in as_completed(futs):
            k = futs[fut]
            try:
                results[k] = fut.result()
                print(f"  ok {key_str(k):22s} {len(buckets[k]):3d} -> "
                      f"{len(results[k]['result'].get('records') or [])}", flush=True)
            except Exception as exc:          # noqa: BLE001
                failed.append(key_str(k))
                print(f"  FAILED {key_str(k)}: {exc}", flush=True)
    if failed:
        sys.exit(f"{len(failed)} bucket(s) failed; re-run (cached buckets are kept).")

    log = {"polarity_mixed_merges": [], "condition_unions": [], "orphans_kept": 0,
           "discarded": [], "general_polarity_fallbacks": []}
    consolidated: list[dict] = []
    per_bucket: dict[str, dict] = {}
    usage = {kk: 0 for kk in llm_client.USAGE_KEYS}
    for k in sorted(buckets, key=lambda x: tuple(str(y) for y in x)):
        recs = buckets[k]
        if k[0] == "fixed":
            out = [{**recs[0], "principle_id": k[1], "_merged_from": [recs[0]["principle_id"]]}]
        elif k in results:
            for kk in usage:
                usage[kk] += results[k]["usage"].get(kk, 0)
            out = apply_merge(k, recs, results[k], log)
            if k[0] == "planet_general":
                pols = {r["polarity"] for r in out}
                if not ({"supportive", "challenging"} <= pols):
                    log["general_polarity_fallbacks"].append(key_str(k))
                    out = exact_dedupe(recs)
        else:
            out = exact_dedupe(recs)
        consolidated.extend(out)
        per_bucket[key_str(k)] = {"before": len(recs), "after": len(out),
                                  "citations": sum(r["citation_count"] for r in out)}

    # every planet x angle, including empty ones
    for p in PLANETS:
        for a in ANGLES:
            per_bucket.setdefault(f"line|{p}|{a}", {"before": 0, "after": 0, "citations": 0})
    line_after = {k: v["after"] for k, v in per_bucket.items() if k.startswith("line|")}
    report = {
        "raw_records": len(raw),
        "consolidated_records": len(consolidated),
        "by_scope": dict(sorted(Counter(r["acg_scope"] for r in consolidated).items())),
        "line_buckets_below_4": sorted(k for k, v in line_after.items() if v < 4),
        "line_buckets_below_2": sorted(k for k, v in line_after.items() if v < 2),
        "per_bucket": dict(sorted(per_bucket.items())),
        "polarity_mixed_merges": log["polarity_mixed_merges"],
        "condition_unions": log["condition_unions"],
        "orphans_kept": log["orphans_kept"],
        "discarded_count": len(log["discarded"]),
        "discarded_by_reason": dict(Counter(d["reason"] for d in log["discarded"])),
        "discarded": log["discarded"],
        "general_polarity_fallbacks": log["general_polarity_fallbacks"],
        "merge_usage": usage,
        "model": args.model,
    }
    with open(CONS_OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(consolidated, fh, ensure_ascii=False, indent=2)
    with open(REPORT_OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(f"\n{len(raw)} raw -> {len(consolidated)} consolidated "
          f"-> {os.path.relpath(CONS_OUT, ROOT)}")
    print(f"by scope: {report['by_scope']}")
    print(f"line buckets < 4: {len(report['line_buckets_below_4'])} "
          f"{report['line_buckets_below_4']}")
    print(f"discarded: {report['discarded_by_reason']}; orphans kept: {log['orphans_kept']}; "
          f"mixed-polarity merges: {len(log['polarity_mixed_merges'])}; "
          f"condition unions: {len(log['condition_unions'])}")
    print(f"merge tokens: in={usage['input_tokens']:,} out={usage['output_tokens']:,}")


if __name__ == "__main__":
    main()
