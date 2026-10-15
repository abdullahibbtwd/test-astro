# ORCHESTRATOR_SPEC.md — `run.py` (repo root)

A single interactive entry point that runs the whole pipeline end to end and
writes every artifact of one run into its own id'd folder. Replaces the current
manual three-step dance (edit `compute_chart.py` → `ground.py` → `l4_interpret.py`).

The coding agent implements this. It calls the three existing layer functions
**in process** — no shelling out, no editing the layer modules.

---

## §0 Role & boundaries

- `run.py` lives at the **repo root**, above `d_layer/`, `principles_grounding/`,
  and the interpretation folder (`Interpretation_layer/`).
- It owns **all** file writing into the run folder. The layer functions are pure
  computation; their own CLI `main()`s and default output paths are ignored.
- It adds nothing to the astrology. It only: collects input, geocodes, sequences
  the layers, and writes a manifest.
- The pipeline is **five integral stages**, all part of one run: L1 chart → L2/L3
  grounding → L4 interpretation → **L5 distillation + scoresheet** (the eval
  harness, EVAL_HARNESS_SPEC.md). L5 is **not** an optional post-step — a run is
  incomplete without it, exactly as it would be without the reading. The only
  thing that lives outside `run.py` is the score *readback* (`score_report.py`),
  and only because it consumes scores a human fills in **after** the run; see §4
  note and EVAL_HARNESS_SPEC.md §8.

---

## §1 Interactive input

Prompt the user for, in order:

1. **Birth date** — accept `YYYY-MM-DD`. Validate it's a real date.
2. **Birth time** — accept `HH:MM` (24h), **local wall-clock time at the birth
   place**. This is passed straight to `compute_chart`, which converts local→UT
   itself. Do **not** convert here.
3. **Birth place** — free-text city string, e.g. `Istanbul, Turkey`.

`time_precision` is fixed to `"exact"` for now (see §8). No bucket/unknown path.

Re-prompt on invalid input rather than crashing.

---

## §2 Geocoding (the only online step)

City string → `(latitude, longitude, resolved_display_name)`.

- Use `geopy` with the Nominatim provider (free, no API key). Set a descriptive
  `user_agent` string. Respect the ~1 req/sec courtesy limit (single lookup per
  run, so this is a non-issue).
- On **zero results**: print the failure, re-prompt for the place string. Do not
  fall back to a default location and do not proceed without coordinates.
- On **multiple candidates**: take the top Nominatim result but **echo the
  resolved display name back to the user for confirmation** (e.g. "Resolved to:
  Istanbul, Türkiye (41.0082, 28.9784) — correct? [Y/n]"). A wrong city silently
  corrupts the entire chart, so this confirmation is mandatory.
- Timezone is **not** resolved here. `compute_chart` derives it from lat/lon
  internally (`timezonefinder`). Do not add a second tz lookup.

---

## §3 Module entry points (call these exactly)

These are the verified signatures. Embed-by-reference; do not re-derive.

### L1 — `d_layer/compute_chart.py`
```python
from compute_chart import compute_chart, BirthData

bd = BirthData(
    year=Y, month=M, day=D,
    hour=h, minute=m,
    latitude=lat, longitude=lon,
    time_precision="exact",
)
chart: dict = compute_chart(bd)          # JSON-serializable; writes nothing
```

### L2/L3 — `principles_grounding/ground.py`
```python
from ground import ground

with open("principles_grounding/all_principles.grounded.json") as fh:
    corpus = json.load(fh)               # the grounded corpus (list[dict])

result = ground(corpus, chart, reading="natal")
kept            = result.kept            # list[dict] — pass straight to L4
personal_payload = result.kept_payload() # dict — write to personal_principles.json
```

### L4 — `Interpretation_layer/l4_interpret.py`
```python
from l4_interpret import interpret
from l4_render import write_readable

output, report, errors = interpret(chart, kept)   # real Anthropic calls
if errors:
    # contract violation — STOP, do not write l4_output.json (see §6)
    ...
# write_readable emits the .en.txt / .tr.txt files INTO the given dir:
paths = write_readable(output, run_dir)
```

`interpret` accepts `model=` / `synthesis_model=` / `max_tokens=` kwargs; thread
through any the user sets via flags (§7-optional), otherwise use defaults.

### Import path handling
Each layer module computes paths relative to its own `__file__` and imports
sibling modules (`ground` imports `grounding_schema`; `l4_interpret` imports
`l4_generate`, `l4_routing`, `l4_render`, …). Before importing each layer, insert
its directory onto `sys.path`:
```python
for d in ("d_layer", "principles_grounding", "Interpretation_layer"):
    p = os.path.join(REPO_ROOT, d)
    if p not in sys.path:
        sys.path.insert(0, p)
```
Use absolute paths derived from `REPO_ROOT = os.path.dirname(os.path.abspath(__file__))`.

---

## §4 Pipeline sequence

```
1. collect input (§1)
2. geocode → lat, lon, display_name (§2)
3. mint run_id, create runs/<run_id>/      (§5)
4. chart  = compute_chart(BirthData(...))   → write chart.json
5. corpus = load all_principles.grounded.json
   result = ground(corpus, chart)           → write personal_principles.json
                                               (result.kept_payload())
6. output, report, errors = interpret(chart, result.kept)
   if errors: write nothing further, abort with the violation list (§6)
   write l4_output.json, l4_routing_report.json
   write_readable(output, run_dir)          → l4_reading.en.txt / .tr.txt
7. STAGE L5 (mandatory): distill(output, run_dir)
                                            → statements.json / .txt / scoresheet.csv
                                               (EVAL_HARNESS_SPEC.md). A clean L4
                                               run that fails to produce these is
                                               an incomplete run — treat a distiller
                                               error like any other stage failure.
8. write run_meta.json (§5); print run_dir + summary AND the next human step:
   "fill scoresheet.csv, then: python score_report.py runs/<id>/scoresheet.csv"
```

Pass `result.kept` to `interpret` **in memory** — do not round-trip through the
written personal_principles.json file. The written file is a record artifact only.

**Why the readback isn't a stage here.** Stages 4–7 are fully automatic. The
score *readback* (`score_report.py`) cannot run in the same pass because it reads
truthfulness scores that don't exist until you fill `scoresheet.csv` by hand. That
human gate is intrinsic, not a design choice — so `run.py` ends by emitting the
empty scoresheet and printing the one command to run once it's filled. The eval
harness is in the orchestration; only the part that needs human input is deferred,
necessarily.

---

## §5 Run directory & manifest

- Run id: `YYYYMMDD-HHMMSS_<3 random lowercase alnum>` (sortable + collision-safe).
- Directory: `runs/<run_id>/` under repo root. Create parents as needed.
- Files written (exact names):
  `run_meta.json, chart.json, personal_principles.json, l4_output.json,
  l4_routing_report.json, l4_reading.en.txt, l4_reading.tr.txt,
  statements.json, statements.txt, scoresheet.csv`
  (the reading filenames are whatever `write_readable` returns; capture them.)

### `run_meta.json` schema
```json
{
  "run_id": "20260626-143002_a4f",
  "created_utc": "2026-06-26T14:30:02Z",
  "input": {
    "birth_date": "1979-03-30",
    "birth_time_local": "06:30",
    "place_query": "Istanbul, Turkey"
  },
  "geocode": {
    "provider": "nominatim",
    "display_name": "İstanbul, Türkiye",
    "latitude": 41.0082,
    "longitude": 28.9784
  },
  "resolved_timezone": "Europe/Istanbul",     // copied from chart.meta.timezone
  "time_precision": "exact",
  "models": { "section": "...", "synthesis": "..." },  // from the L4 report
  "artifacts": [ "chart.json", "...", "scoresheet.csv" ]
}
```
`resolved_timezone` and the UT instant already live in `chart.json.meta`; copy
the tz up into the manifest for convenience, don't recompute it.

---

## §6 Failure modes (fail loud, fail clean)

- **Geocode miss** → re-prompt (§2). Never proceed coordinate-less.
- **L4 contract violation** (`errors` non-empty) → print all errors to stderr,
  **do not** write `l4_output.json` or run the distiller, exit non-zero. The run
  folder may keep `chart.json` / `personal_principles.json` for debugging; mark
  the run failed in `run_meta.json` (`"status": "l4_contract_violation"`).
- **Missing corpus / chart / API key** → clear message naming the missing thing.
- A partial run must never leave a half-written `l4_output.json`; write it only
  after `errors == []`.

---

## §7 Invariants

1. No file under `runs/<id>/` is written before `run_id` is minted and the dir
   exists.
2. `personal_principles.json.kept_count == len(result.kept)` (ground.py already
   guarantees this; assert it on write).
3. `l4_output.json` exists **iff** `errors == []`.
4. `statements.*` / `scoresheet.csv` exist **iff** `l4_output.json` exists.
5. The local wall-clock time entered is never modified before reaching
   `compute_chart` (no tz math in `run.py`).
6. Re-running with identical input produces a new folder (new id) — runs are
   never overwritten.

---

## §8 Out of scope / extension points (do not build now)

- `time_precision` of `"approximate"` / `"unknown"` (compute_chart supports both;
  wire later behind an input branch).
- Batch / multi-chart runs.
- Prompt caching + batch API for L4 cost (tracked separately).
- Re-running the distiller standalone on an old run — supported by the distiller
  module itself (EVAL_HARNESS_SPEC.md §8), not by `run.py`.
