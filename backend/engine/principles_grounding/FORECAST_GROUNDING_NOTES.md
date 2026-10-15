# FORECAST_GROUNDING_NOTES.md

Implementation notes for `ground_forecast.py` (built to `FORECAST_GROUNDING_SPEC.md`).
It is the deferred step both the compute and reading specs point to: it attaches
`matched_principles` to every forecast event.

## Files
- `ground_forecast.py` — the gate (Stage 1 structural + Stage 2 interface + CLI).
- `test_forecast_grounding.py` — offline tests for every §6 invariant (no LLM, no network).

## How to run
```
python ground_forecast.py --forecast <forecast.json> --chart <chart.json>
#   -> <forecast>.grounded.json          (forecast + matched_principles, primary output)
#   -> <forecast>.grounded.coverage.json (recall-visibility report, §1 secondary)

python test_forecast_grounding.py        # or: pytest test_forecast_grounding.py
```
The corpus defaults to the **merged** `all_principles_grounded.with_predictive.json`
(3,263 records; predictive slice = 1,589 predictive + 53 timing = 1,642), never the
pre-merge 2,153 file (§7).

## What it reuses from `ground.py` (§0)
Imported verbatim, subject-agnostic: `_gate_a` (domain filter), `_gate_c` /
`_requirement_satisfiable` (dependency satisfiability against the **natal** chart),
`_point_index`, and the `DropLog` shape; plus `grounding_schema.invariant_violation`. Only
Gate B changes — it reconciles `about` against each **event** instead of the chart. The
added reading key is the domain set `{predictive, timing}`.

## Stage 1 — the deterministic backbone (ships complete)
Two indices carry almost all real coverage (measured on the predictive slice):
- **aspect index** — 525 records, key `(source, target, type)` (directed: source =
  transiting). `Pluto △ natal Mercury` finds `pluto-trine-mercury` only, not
  `mercury-pluto-trine`. The event's transiting/natal roles are left untouched
  (§2 direction discipline; invariants 2–3). Unordered matching was a bug (CAL F6).
- **house index** — 168 `planet_in_house` records, key `(point, house, "placidus")`.
  Whole-sign is texture, never a match key.

`general` (105) and `unclassified` (844) records are **deliberately not indexed** — a
per-event gate cannot keep subject-less records or every event drowns in domain-neutral
text (§3). They are reachable only through Stage 2. On a real month forecast this grounds
~116 of 164 events; the rest are angle contacts, sign ingresses, and lunations that have no
structured predictive record and legitimately wait for Stage 2.

## Stage 2 — embedding residual (interface shipped, wiring DEFERRED)
The spec (§4) says to reuse the **existing L2 semantic-retrieval infra**. **That infra is
not present in this repo** — `grounding_vocab.py` only references a `retrival_contract/
retrieval.py` as a rationale; there is no embedding index, model, or retriever on disk.

Per the spec's explicit fallback ("If no embedding infra is available yet, ship Stage 1
alone … and gate Stage 2 behind a flag"), Stage 2 is implemented as a **clean injectable
interface**, not a second embedding space:
- `EmbeddingRetriever` Protocol: `query(text, k) -> [(record, similarity)]`.
- `ground_forecast(..., retriever=<your L2 adapter>)` runs the residual: query built from the
  event's `topic_tags` + a compact config gloss (§4.1), predictive-domain pre-filter,
  `similarity >= sim_floor` (default 0.35), dedupe vs structural, cap N with structural
  ranked ahead (§4.2–4.4).
- With no retriever (the current state) it is a no-op; `NullRetriever` is the explicit stand-in.
- The CLI `--enable-embeddings` flag prints an honest "no retriever wired, Stage 1 only"
  notice rather than pretending the residual ran.

**To finish Stage 2:** wire an adapter that implements `EmbeddingRetriever` over whatever
embedding index natal L2 retrieval ends up using, and pass it to `ground_forecast`. Nothing
else changes — angle/`general`/`unclassified`/lunation coverage lights up automatically.

## Output contract (what the reading layer consumes)
```jsonc
event["matched_principles"] = [
  { "principle_id", "judgment", "topic_tags", "tradition": "modern",
    "source_stage": "structural" | "embedding", "similarity": <float|null> }
]
```
`judgment` is copied straight from the grounded corpus record (the reading's `principle_gloss`
reads this field). Cap N=6, structural first, ties broken by `principle_id` sort → fully
deterministic (§5, invariant 9).

## Coverage report (recall visibility, §1)
`…coverage.json` carries `events_with_zero_matches` **as an explicit list** so the reading's
sparse path and the eval harness can tell a grounding **recall gap** from a genuinely
**quiet** period — plus per-event kept counts, the structural-vs-embedding split, and
`drops_by_gate`.

## Deferred (§7)
No LLM; no ZR/profection records (out of domain and gated off compute-side); no classical
predictive records (near-zero, out of domain); no corpus re-grounding (that is `backfill.py`).
Stage 2 embedding wiring, as above.
