#!/usr/bin/env python3
"""
tag_goals_acg.py — ACG corpus goal tags (spec ``ACG/ACG_07_CHANGE_ORDER_V3.md`` §5), a separate,
idempotent post-pass over ``acg_principles.grounded.json``. Nothing is re-extracted.

For every record in the scopes ``line``, ``planet_general``, ``angle_frame`` and ``paran``
(``ACG/ACG_10_PARANS_SPEC.md`` §5; the one ``acg_method`` record filed under scope paran is tagged
too, normally ``{}``) the model returns
``goal_effects: {<goal>: "supportive" | "challenging" | "mixed"}`` over the closed goal enum of
``ACG/ACG_08_GOAL_SCORING_SPEC.md`` §1 (``Astrocartography/acg_constants.GOALS``; the definitions
go into the prompt verbatim). Rules: tag a goal only when the record's meaning directly concerns
it; at most 3 goals; ``{}`` is valid; the polarity is per goal.

  * batches of 20 records per call, temperature 0 (when the model accepts one), JSON-schema
    constrained output ``{results: [{principle_id, goal_effects}]}``
  * deterministic post-validation (goal enum, <= 3 keys, polarity enum, ids == the batch);
    an invalid record is retried once (in a batch of the failures), then left ``{}`` and logged
    (a failure is not cached, so the next run retries it)
  * cache ``TXT/extracted_acg/goal_tag_cache.json`` keyed
    ``principle_id + ":" + sha256(rule + json(conditions) + judgment)``; a re-run only calls
    the model for changed or uncached records
  * write-back: ``goal_effects`` on every record of the tagged scopes (possibly ``{}``), placed
    right after ``source_span`` — in ``acg_principles.grounded.json`` (+ refreshed ``.sha256``) and
    mirrored into ``acg_principles.clean.json``, which ``finish_acg.build`` carries through, so the
    C-8 rebuild stays byte-identical and a finish re-run does not drop the tags. Other scopes
    are untouched.
  * report ``principles_grounding/acg_goal_tagging_report.json``

    python principles_grounding/tag_goals_acg.py --dry-run      # batches, zero calls
    python principles_grounding/tag_goals_acg.py --limit 20     # first 20 pending records
    python principles_grounding/tag_goals_acg.py                # all pending records
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
for p in (ROOT, HERE, os.path.join(ROOT, "Astrocartography")):
    if p not in sys.path:
        sys.path.insert(0, p)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import llm_client  # noqa: E402
from acg_constants import (GOAL_ORDER, GOAL_POLARITIES, GOALS,  # noqa: E402
                           MAX_GOALS_PER_RECORD)

GROUNDED = os.path.join(HERE, "acg_principles.grounded.json")
CLEAN = os.path.join(HERE, "acg_principles.clean.json")
REPORT = os.path.join(HERE, "acg_goal_tagging_report.json")
WORK_DIR = os.path.join(ROOT, "TXT", "extracted_acg")
CACHE = os.path.join(WORK_DIR, "goal_tag_cache.json")

TAG_SCOPES = ("line", "planet_general", "angle_frame", "paran")
LINE_SCOPES = ("line", "planet_general", "angle_frame")   # the C-9 soft thresholds (07 §5)
BATCH = 20
FIELD = "goal_effects"
ANCHOR = "source_span"          # goal_effects goes right after this key

# ---------------------------------------------------------------------------
# Prompt + schema
# ---------------------------------------------------------------------------

_GOAL_LINES = "\n".join(f"- {g}: {GOALS[g][2]}" for g in GOAL_ORDER)

SYSTEM = f"""You tag astrocartography interpretation records with life goals.

Each record describes what a planet on an angle (a "line"), a planet's lines in general, an
angle in general, or a paran (the latitude band where two planets are simultaneously on angles)
brings to a person living in or visiting a place. For each record decide which
life goals its meaning DIRECTLY concerns and, for each tagged goal, whether the record is
supportive, challenging or mixed for that goal.

The goals are a closed set. Use only these keys, with exactly these definitions (a record must
directly concern what the definition lists):
{_GOAL_LINES}

Rules:
1. Tag a goal ONLY if the record's meaning directly concerns it, per its definition. Do not infer
   goals from loose associations or from the planet's general symbolism when the record's text
   does not speak to them.
   A record concerns a goal in either direction: text about pressure, strain, turmoil, crisis or
   exhaustion directly concerns rest (challenging); text about financial restriction or loss
   directly concerns money (challenging); text about quarrels with or loss of a partner directly
   concerns love (challenging).
   Every record is about a place, so do not tag travel or relocation merely because of that: tag
   travel only when the text speaks of visiting, short stays, exploration or movement, and
   relocation only when it speaks of long-term residence, settling, belonging or making a home.
2. At most {MAX_GOALS_PER_RECORD} goals per record; choose the most direct ones. An empty object
   {{}} is valid when no goal is directly concerned.
3. The polarity is PER GOAL: "supportive" (the record favours that goal), "challenging" (it
   hinders or harms that goal), or "mixed" (it clearly does both for that goal). A record can be
   supportive for one goal and challenging for another.
4. Judge only from the record's rule, conditions and judgment. Return one result per input
   record, with its principle_id copied exactly, and no other records.

Output JSON only: {{"results": [{{"principle_id": "...", "goal_effects": {{"<goal>": "<polarity>"}}}}]}}"""

SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "principle_id": {"type": "string"},
                    "goal_effects": {
                        "type": "object",
                        "properties": {g: {"type": "string", "enum": list(GOAL_POLARITIES)}
                                       for g in GOAL_ORDER},
                        "additionalProperties": False,
                    },
                },
                "required": ["principle_id", "goal_effects"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["results"],
    "additionalProperties": False,
}


def subject_of(r: dict) -> str:
    a = r.get("about") or {}
    ft = a.get("factor_type")
    if ft == "planet_on_angle":
        return f"{a['planet']} on the {a['angle']} (line)"
    if ft == "acg_planet_general":
        return f"{a['planet']} lines in general"
    if ft == "acg_angle_frame":
        return f"any planet on the {a['angle']} (angle in general)"
    if ft == "acg_paran":
        p1, p2 = a["planets"]
        return f"paran of {p1} and {p2} (the latitude where both are on angles at once)"
    if ft == "acg_method":
        return "astrocartography method note (parans / line crossings)"
    return r["acg_scope"]


def user_prompt(batch: list[dict]) -> str:
    items = [{"principle_id": r["principle_id"], "subject": subject_of(r), "rule": r["rule"],
              "conditions": r.get("conditions") or [], "judgment": r.get("judgment")}
             for r in batch]
    return ("Tag each of these records.\n\n"
            + json.dumps({"records": items}, ensure_ascii=False, indent=1))


# ---------------------------------------------------------------------------
# Cache key + validation
# ---------------------------------------------------------------------------

def content_hash(r: dict) -> str:
    blob = ((r.get("rule") or "")
            + json.dumps(r.get("conditions") or [], ensure_ascii=False, sort_keys=True)
            + (r.get("judgment") or ""))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def cache_key(r: dict) -> str:
    return f"{r['principle_id']}:{content_hash(r)}"


def canonical(ge: dict) -> dict:
    return {g: ge[g] for g in GOAL_ORDER if g in ge}


def validate_effects(ge) -> list[str]:
    """Problems with one record's goal_effects ([] = valid)."""
    if not isinstance(ge, dict):
        return ["goal_effects is not an object"]
    errs = [f"unknown goal {k!r}" for k in ge if k not in GOALS]
    errs += [f"bad polarity {k}={v!r}" for k, v in ge.items() if v not in GOAL_POLARITIES]
    if len(ge) > MAX_GOALS_PER_RECORD:
        errs.append(f"{len(ge)} goals > {MAX_GOALS_PER_RECORD}")
    return errs


def parse_batch(text: str, ids: list[str]) -> tuple[dict, dict]:
    """Model text -> ({id: goal_effects} valid, {id: [problems]} invalid). Ids outside the
    batch are ignored (logged as 'foreign'); a duplicated or missing id is invalid."""
    valid: dict = {}
    bad: dict = {}
    try:
        data = json.loads(text)
        results = data["results"]
        assert isinstance(results, list)
    except Exception as exc:  # noqa: BLE001 — any malformed payload fails the whole batch
        return {}, {i: [f"unparseable output: {exc}"] for i in ids}
    want = set(ids)
    seen = Counter(x.get("principle_id") for x in results if isinstance(x, dict))
    for x in results:
        if not isinstance(x, dict):
            continue
        pid = x.get("principle_id")
        if pid not in want:
            bad.setdefault("__foreign__", []).append(str(pid))
            continue
        if seen[pid] > 1:
            bad[pid] = ["duplicated id in output"]
            continue
        errs = validate_effects(x.get("goal_effects"))
        if errs:
            bad[pid] = errs
        else:
            valid[pid] = canonical(x["goal_effects"])
    for pid in ids:
        if pid not in valid and pid not in bad:
            bad[pid] = ["missing from output"]
    return valid, bad


# ---------------------------------------------------------------------------
# Model calls
# ---------------------------------------------------------------------------

class Tagger:
    """Batch goal tagger. The prompt pieces are injectable so other corpora reuse it
    (tag_goals_transits.py, CAL_02 §2). The defaults are the ACG prompt."""

    def __init__(self, model: str, *, system: str | None = None, schema: dict | None = None,
                 prompt_fn=None):
        self.model = model
        self.system = SYSTEM if system is None else system
        self.schema = SCHEMA if schema is None else schema
        self.prompt_fn = user_prompt if prompt_fn is None else prompt_fn
        self.fallback = llm_client.DEFAULT_MODEL
        self.usage = {k: 0 for k in llm_client.USAGE_KEYS}
        self.calls = 0
        self.fallbacks = 0
        self.lock = threading.Lock()

    def _call_one(self, model: str, batch: list[dict], label: str) -> str:
        temp = 0.0 if llm_client.supports_temperature(model) else None
        last: Exception | None = None
        for attempt in range(1, 4):
            try:
                resp = llm_client.complete(model, self.system, self.prompt_fn(batch),
                                           max_tokens=8000, temperature=temp, schema=self.schema,
                                           timeout_s=180.0, label=label)
                with self.lock:
                    self.calls += 1
                    for k in self.usage:
                        self.usage[k] += (resp.usage or {}).get(k, 0)
                if resp.stop_reason == "max_tokens":
                    return ""      # truncated -> parse fails -> the records are retried
                return resp.text
            except llm_client.ProviderQuotaError:
                raise
            except llm_client.transient_errors(model) as exc:
                last = exc
                time.sleep(5 * attempt)
        raise RuntimeError(f"{label}: transient failures x3: {last}")

    def call(self, batch: list[dict], label: str) -> str:
        """One batch call on the chosen model; if that model fails outright, fall back to
        llm_client.DEFAULT_MODEL."""
        try:
            return self._call_one(self.model, batch, label)
        except Exception as exc:  # noqa: BLE001
            if self.model == self.fallback:
                raise
            print(f"  {label}: {self.model} failed ({exc}); falling back to {self.fallback}",
                  flush=True)
            with self.lock:
                self.fallbacks += 1
            return self._call_one(self.fallback, batch, label)

    def tag(self, batch: list[dict], label: str) -> tuple[dict, dict, int]:
        """-> ({id: goal_effects}, {id: problems} after the one retry, records retried)."""
        ids = [r["principle_id"] for r in batch]
        try:
            valid, bad = parse_batch(self.call(batch, label), ids)
        except Exception as exc:  # noqa: BLE001
            valid, bad = {}, {i: [f"call failed: {exc}"] for i in ids}
        foreign = bad.pop("__foreign__", [])
        retry = [r for r in batch if r["principle_id"] in bad]
        if retry:
            print(f"  {label}: {len(retry)} invalid record(s) -> retry once "
                  f"({sorted(bad)[:3]}…)", flush=True)
            rids = [r["principle_id"] for r in retry]
            try:
                v2, b2 = parse_batch(self.call(retry, label + "/retry"), rids)
            except Exception as exc:  # noqa: BLE001
                v2, b2 = {}, {i: [f"call failed: {exc}"] for i in rids}
            foreign += b2.pop("__foreign__", [])
            valid.update(v2)
            bad = {i: b2[i] for i in rids if i in b2}
        if foreign:
            bad["__foreign__"] = foreign
        return valid, bad, len(retry)


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------

def _dump(data) -> str:              # finish_acg._dump
    return json.dumps(data, ensure_ascii=False, indent=2)


def _write(path: str, payload: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(payload)


def load_cache() -> dict:
    if os.path.exists(CACHE):
        return json.load(open(CACHE, encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    os.makedirs(WORK_DIR, exist_ok=True)
    tmp = CACHE + ".tmp"
    _write(tmp, _dump(dict(sorted(cache.items()))))
    os.replace(tmp, CACHE)


def with_field(r: dict, ge: dict) -> dict:
    """Copy of r with goal_effects placed right after source_span (the position
    finish_acg.build emits it at, so the C-8 rebuild is byte-identical)."""
    out = {}
    for k, v in r.items():
        if k == FIELD:
            continue
        out[k] = v
        if k == ANCHOR:
            out[FIELD] = ge
    if FIELD not in out:
        out[FIELD] = ge
    return out


def apply(records: list[dict], effects: dict) -> list[dict]:
    return [with_field(r, effects.get(r["principle_id"], {}))
            if r["acg_scope"] in TAG_SCOPES else r for r in records]


def write_sidecar(gpath: str, payload: str) -> str:
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    name = os.path.basename(gpath)
    rest: list[str] = []
    side = gpath + ".sha256"
    if os.path.exists(side):
        rest = open(side, encoding="utf-8").read().splitlines()[1:]
    with open(side, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join([f"{digest}  {name}", *rest]) + "\n")
    return digest


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Tag ACG records with goal_effects (07 §5).")
    ap.add_argument("--model", default=llm_client.DEFAULT_MODEL,
                    help="tagging model (default llm_client.DEFAULT_MODEL; falls back to it)")
    ap.add_argument("--dry-run", action="store_true", help="print the batches; zero calls")
    ap.add_argument("--limit", type=int, default=0, help="only the first N pending records")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    grounded = json.load(open(GROUNDED, encoding="utf-8"))
    targets = [r for r in grounded if r["acg_scope"] in TAG_SCOPES]
    cache = load_cache()
    pending = [r for r in targets if cache_key(r) not in cache]
    if args.limit:
        pending = pending[:args.limit]
    batches = [pending[i:i + BATCH] for i in range(0, len(pending), BATCH)]
    cached = sum(1 for r in targets if cache_key(r) in cache)
    print(f"{len(targets)} records in scopes {TAG_SCOPES}; cached {cached}; "
          f"to tag {len(pending)} in {len(batches)} batch(es); model {args.model}")

    if args.dry_run:
        print(f"system prompt: {len(SYSTEM)} chars")
        for n, b in enumerate(batches, 1):
            scopes = Counter(r["acg_scope"] for r in b)
            print(f"  batch {n:02d}: {len(b)} records {dict(scopes)}; user prompt "
                  f"{len(user_prompt(b))} chars; {b[0]['principle_id']} .. {b[-1]['principle_id']}")
        if batches:
            print("\n--- system prompt ---\n" + SYSTEM)
            print("\n--- first user prompt (truncated) ---\n" + user_prompt(batches[0])[:1500])
        print("\ndry run: no model calls, nothing written.")
        return

    if batches:
        llm_client.require_api_key(args.model, "goal tagging")
    tagger = Tagger(args.model)
    invalid: dict = {}
    retried = 0
    lock = threading.Lock()

    def run(n_b):
        nonlocal retried
        n, b = n_b
        valid, bad, nr = tagger.tag(b, f"goals/{n:02d}")
        with lock:
            retried += nr
            for r in b:
                pid = r["principle_id"]
                if pid in valid:
                    cache[cache_key(r)] = {"principle_id": pid, FIELD: valid[pid],
                                           "model": tagger.model}
            for pid, errs in bad.items():
                invalid[pid] = errs
            save_cache(cache)
        print(f"  batch {n:02d}: {len(valid)}/{len(b)} valid", flush=True)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        list(pool.map(run, enumerate(batches, 1)))
    for pid, errs in sorted(invalid.items()):
        print(f"  INVALID -> {{}}: {pid}: {errs}")

    # --- write-back ------------------------------------------------------------
    effects = {}
    for r in targets:
        hit = cache.get(cache_key(r))
        if hit is not None:
            effects[r["principle_id"]] = canonical(hit[FIELD])
    new_grounded = apply(grounded, effects)
    g_payload = _dump(new_grounded)
    _write(GROUNDED, g_payload)
    digest = write_sidecar(GROUNDED, g_payload)
    if os.path.exists(CLEAN):
        clean = json.load(open(CLEAN, encoding="utf-8"))
        _write(CLEAN, _dump(apply(clean, effects)))

    # --- report ------------------------------------------------------------------
    tagged = [r for r in new_grounded if r["acg_scope"] in TAG_SCOPES]

    def polarity_counts(recs):
        out = {g: {p: 0 for p in GOAL_POLARITIES} for g in GOAL_ORDER}
        for r in recs:
            for g, pol in r[FIELD].items():
                out[g][pol] += 1
        return out

    line_scoped = [r for r in tagged if r["acg_scope"] in LINE_SCOPES]
    parans = [r for r in tagged if r["acg_scope"] == "paran"]
    counts = polarity_counts(line_scoped)          # C-9 basis: line/planet_general/angle_frame
    par_counts = polarity_counts(parans)
    zero = Counter(r["acg_scope"] for r in tagged if not r[FIELD])
    by_scope = Counter(r["acg_scope"] for r in tagged)
    lines = [r for r in tagged if r["acg_scope"] == "line"]
    line_cov = sum(1 for r in lines if r[FIELD]) / max(1, len(lines))
    per_goal = {g: sum(counts[g].values()) for g in GOAL_ORDER}
    par_pairs = [r for r in parans if (r.get("about") or {}).get("factor_type") == "acg_paran"]
    par_cov = sum(1 for r in par_pairs if r[FIELD]) / max(1, len(par_pairs))
    report = {
        "model": args.model,
        "records_in_scopes": dict(sorted(by_scope.items())),
        "untagged_no_cache_entry": sorted(r["principle_id"] for r in targets
                                          if r["principle_id"] not in effects),
        "goal_polarity_counts": counts,
        "records_per_goal": per_goal,
        "goals_per_record": dict(sorted(Counter(len(r[FIELD]) for r in tagged).items())),
        "zero_goal_records_by_scope": {s: zero.get(s, 0) for s in TAG_SCOPES},
        "line_records_with_goal_share": round(line_cov, 4),
        "c9_line_share_ok": line_cov >= 0.80,
        "c9_goals_below_15": sorted(g for g in GOAL_ORDER if per_goal[g] < 15),
        "c9_basis_scopes": list(LINE_SCOPES),
        "paran": {
            "records": len(parans),
            "pair_records": len(par_pairs),
            "pair_records_with_goal_share": round(par_cov, 4),
            "goal_polarity_counts": par_counts,
            "records_per_goal": {g: sum(par_counts[g].values()) for g in GOAL_ORDER},
            "goals_per_record": dict(sorted(Counter(len(r[FIELD]) for r in parans).items())),
        },
        "this_run": {
            "batches": len(batches), "records_sent": len(pending), "calls": tagger.calls,
            "records_retried": retried, "model_fallbacks": tagger.fallbacks,
            "invalid_left_empty": {k: v for k, v in sorted(invalid.items())},
            "usage": tagger.usage, "seconds": round(time.time() - t0, 1),
        },
        "grounded_sha256": digest,
    }
    _write(REPORT, _dump(report))
    print(f"calls {tagger.calls}; usage {tagger.usage}")
    print(f"line records with >=1 goal: {line_cov:.1%}; per goal {per_goal}")
    print(f"paran pair records with >=1 goal: {par_cov:.1%}; per goal "
          f"{report['paran']['records_per_goal']}")
    print(f"zero-goal records by scope: {report['zero_goal_records_by_scope']}")
    print(f"wrote {os.path.basename(GROUNDED)} (+ .sha256 {digest[:16]}…), "
          f"{os.path.basename(CLEAN)}, {os.path.basename(REPORT)}")


if __name__ == "__main__":
    main()
