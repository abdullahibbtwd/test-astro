# EVAL_HARNESS_SPEC.md — distill → scoresheet → readback

This is **pipeline stage L5** — an integral, non-optional part of every
orchestrated run (ORCHESTRATOR_SPEC.md §0, §4 step 7), not a tool run afterwards.
It covers two features:

- **Feature 2** — distill the final reading into clean, jargon-free statements
  about the person (English only).
- **Feature 3** — emit a fillable score sheet so those statements can be rated
  0–10, plus a readback script that turns a filled sheet into a tuning report.

The coding agent implements one module, `eval_harness/distill.py` (or wherever
the agent prefers), exposing the functions below. **`run.py` calls `distill(...)`
as stage L5 of the pipeline** — a run is not complete without its statements and
scoresheet. The same module is *also* runnable standalone (§8) for re-distilling
old runs, but standalone is a convenience, not the primary path.

The one piece that is necessarily deferred is `score_report.py` (§6): it consumes
scores a human enters into `scoresheet.csv` after the run, so it cannot execute in
the same automated pass. That seam is intrinsic to a human evaluation, not a
design choice.

---

## §1 Distiller input

- **Source: the final reading** — `l4_output.json` (decision locked). Not the
  grounded principles. This tests what the user actually reads, end to end.
- Use the **English** text only: each section's `text_en`. Ignore `text_tr`.
- Each `l4_output.json` section also carries `key`, `movement`, and
  `principle_ids` (the grounding trace). Carry these through as provenance — they
  are what lets a low score point back at a specific mis-grounded principle.

Function:
```python
def distill(l4_output: dict, out_dir: str, *, model: str = DEFAULT_MODEL) -> list[str]:
    """Distil the reading into clean statements. Writes statements.json,
    statements.txt, scoresheet.csv into out_dir. Returns the written paths."""
```

---

## §2 Distiller LLM contract

One Anthropic call (English, same key/setup as L4; Sonnet is fine). Feed the
model the per-section English text labelled by section key, and ask it to extract
**atomic claims about the person**. The output quality bar is the whole point of
this feature, so the prompt must enforce all of the following. A statement is
valid only if it is:

1. **Atomic** — one claim per line. Split compound sentences.
2. **About the person** — a description of who they are, how they think, what
   they value, how they behave. Drop anything about the chart, the method, or
   the reading itself.
3. **Jargon-free** — **no astrology terms whatsoever**: no planet, sign, house,
   aspect, element, dignity, sect, lot, ruler, "natal", "placement", etc. If a
   statement can't survive without such a word, rewrite it in plain psychological
   / behavioural language or drop it.
4. **Falsifiable / plain** — a statement the person could read and judge true or
   false about themselves. No hedging ("may sometimes perhaps"), no fluff, no
   poetry, no second-person sermonising. Declarative third-person: "Tends to…",
   "Values…", "Is drawn to…".
5. **Self-contained** — understandable without the surrounding paragraph.

The model must also:

- **Deduplicate near-identical claims across sections** into one statement, and
  record how many sections expressed it (`frequency`) plus which ones
  (`source_sections`). This frequency signal is deliberate: a single
  mis-grounded principle reinjected across sections shows up here as a
  high-frequency statement, which — if it also scores low — pinpoints the
  architectural failure mode rather than a random miss.
- Assign each statement one **category** from the closed enum in §4.

### Output discipline
Instruct the model to return **JSON only** (no prose, no markdown fences),
matching the §3 schema. Parse defensively (strip accidental fences before
`json.loads`, per the house pattern). On parse failure, retry once with a
"return JSON only" reminder, then fail loudly.

A strong starting prompt is the agent's to write from this contract; the contract
above is the spec it must satisfy, not optional flavour.

---

## §3 Output files

### `statements.json`
```json
{
  "run_id": "20260626-143002_a4f",
  "source": "l4_output.json",
  "language": "en",
  "count": 38,
  "statements": [
    {
      "id": "s001",
      "text": "Tends to analyse a problem thoroughly before acting.",
      "category": "cognitive_style",
      "source_sections": ["h3", "h9"],
      "principle_ids": ["P0421", "P1130"],
      "frequency": 2
    }
  ]
}
```
- `id` — stable `sNNN`, assigned in output order.
- `principle_ids` — union of the `principle_ids` of the `source_sections` the
  statement came from (best-effort provenance; may be empty if untraceable).
- `frequency` — number of distinct sections that expressed the claim.

### `statements.txt`
Plain bullets, one per line, nothing else — the human-readable companion:
```
- Tends to analyse a problem thoroughly before acting.
- Values independence over belonging to a group.
...
```

---

## §4 Category enum (closed)

Reuses the clustering from the earlier 42-statement evaluation so the readback
(§6) reproduces those groupings automatically:

```
cognitive_style      how they think / process / decide
values               what matters to them, priorities
behavioral           observable habits, tendencies, actions
emotional            inner emotional life, regulation, reactivity
relational           how they relate to others
motivational         drives, ambitions, what moves them
shadow               self-sabotage / fear / pathology-framing claims
other                valid statement that fits none of the above
```

`shadow` is broken out on purpose: it is the cluster that scored lowest before
and the suspected home of the reinjected mis-grounded principle. Keeping it a
first-class category makes that signal visible in the readback instead of buried.
(The vocabulary is a domain default — adjust the labels if you want different
buckets; keep it a closed enum so the readback can group on it.)

---

## §5 Score sheet — `scoresheet.csv`

**Format: CSV** (chosen over a markdown table or JSON). Rationale: opens directly
in Sheets/Excel for filling, sorts and filters trivially, and reads back
mechanically for §6. JSON is awkward to hand-edit; a markdown table doesn't load
into a spreadsheet cleanly.

Columns, in order:
```
id, statement, category, source_sections, frequency, score, comment
```
- `score` and `comment` are written **empty** — the user fills `score` with an
  integer 0–10 (10 = absolutely true), `comment` optional.
- `source_sections` rendered as a `;`-joined string (e.g. `h3;h9`).
- Quote fields properly (statements contain commas). Use the stdlib `csv` writer.
- One row per statement, in `statements.json` order.

Header row included. UTF-8.

---

## §6 Readback — `score_report.py`

A standalone script: filled `scoresheet.csv` → tuning report (stdout + optional
JSON). It must:

1. Parse the filled sheet; ignore rows with a blank `score`, report how many were
   scored vs skipped.
2. Compute and print:
   - **Overall mean** (and count) — comparable to the earlier 7.42 baseline.
   - **Per-category mean**, sorted ascending (worst first), reproducing the
     cognitive-style / values / shadow clustering.
   - **Lowest-N statements** (default N=10) with their score, category,
     `frequency`, and `source_sections` / `principle_ids`.
3. **Flag the failure mode explicitly**: any statement with `frequency >= 2` AND
   `score <= 4` is a *correlated miss* — a low-rated claim the reading repeated
   across sections, i.e. the prime suspect for a single mis-grounded principle.
   List these under a clear heading; this is the readout the whole harness exists
   to produce.

Keep the score scale and methodology caveat in mind in the output wording: these
are **self-rated truthfulness** (resonance), useful as a tuning signal, not
ground-truth accuracy.

---

## §7 Invariants

1. No statement in `statements.json` contains an astrology term (the prompt
   enforces it; a light post-filter on an astrology-term blocklist is a cheap
   guard — flag, don't silently drop, so misses are visible during tuning).
2. `scoresheet.csv` row count == `statements.json.count` (+ header).
3. `score` / `comment` columns are emitted empty by the distiller.
4. Every `category` value is a member of the §4 enum.
5. `frequency >= 1` for every statement; `source_sections` non-empty.
6. The distiller never writes Turkish output (English-only, locked).

---

## §8 Integration & standalone use

- **Primary path — pipeline stage L5.** `run.py` calls `distill(output, run_dir)`
  as a mandatory stage immediately after a clean L4 run (ORCHESTRATOR_SPEC.md §4
  step 7). Every run folder therefore ships with `statements.*` and an empty
  `scoresheet.csv`. A distiller failure is a run failure, handled like any other
  stage error — not swallowed.
- **Secondary — standalone re-distill.** `python distill.py --l4
  runs/<id>/l4_output.json --out runs/<id>/` re-runs L5 on an existing run (e.g.
  after a prompt tweak) without recomputing the chart/grounding/reading. Same
  function, same outputs; a convenience, not the main path.
- **Readback (necessarily deferred).** `python score_report.py
  runs/<id>/scoresheet.csv` — run by hand once you've filled in the scores. This
  cannot be a stage of `run.py` because the scores don't exist at run time; the
  orchestrator's final line prints this exact command so the loop is obvious.
