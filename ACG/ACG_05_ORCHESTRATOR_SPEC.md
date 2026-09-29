# ACG 05: `run_acg.py` (orchestrator)

*Status: **partial**. The stage order, flags, folder layout and manifest are fixed. Function
calls are wired to the **real signatures from the Phase 0 report**, not assumed ones.
Sections marked ⏳ are completed after Phase 0.*

## 1. Stages

```
1 input-resolve    birth data (same prompts/flags as run.py) + place (--city | --lat/--lon | none)
2 compute_chart    natal chart.json (existing L1, unchanged)
3 compute_acg      acg.json + acg.geojson                          (spec 01)
4 city_scan        city_scan.json                                   (spec 02 §7) — always
5 locate           locate.json                                      (spec 02 §4)  — if place given
6 relocate         chart_relocated.json                             (spec 02 §5)  — if place given
7 ground_acg       acg_principles.json + acg_drop_report.json       (spec 03)     — if place given
                   (preflight: acg_principles.grounded.json exists and its .sha256 matches, else absent: acg_corpus_missing)
8 reading          reading_tr/en.json, reading.md, validation_report.json (spec 04) — if place given
9 persist+manifest manifest.json
```

- With **no place**, the run stops after stage 4 (map mode: lines + scan, no LLM, no cost).
- `--scan-only` forces map mode even when a place is given.
- An absence at any stage is written, recorded in the manifest, and later stages are skipped or
  degrade exactly as their specs say. It is never an exception exit.
- No eval/scoresheet stage (same decision as predictive).

## 2. CLI

```
python run_acg.py [birth flags as run.py] [--city TEXT | --lat F --lon F]
                  [--profile general|personal|professional]   (default general)
                  [--scan-only] [--dry-run]
                  [--model M] [--synthesis-model M] [--translation-model M]
```

- The model flags behave as in the other orchestrators (`same` binds to the synthesis model).
- `--dry-run`: stages 1–7 run fully; stage 8 builds the section plan and prompts and writes
  them to `dry_run_prompts.json`, with no model calls.
- Interactive mode (no flags) prompts for birth data as `run.py` does, then asks
  "Şehir (boş bırak = yalnızca harita)" / "City (blank = map only)".

## 3. Run folder

`acg_run/YYYYMMDD-HHMMSS_<3char>/`, using the **existing run-folder helper** (⏳ name from Phase 0 item 9).
Add `acg_run/` to `.gitignore` in the same commit (it holds real birth data).

Contents: `chart.json`, `acg.json`, `acg.geojson`, `city_scan.json`, and, if a place was
given, `locate.json`, `chart_relocated.json`, `acg_principles.json`,
`acg_drop_report.json`, `reading_tr.json`, `reading_en.json`, `reading.md`,
`validation_report.json` (or `dry_run_prompts.json`), plus `manifest.json`.

## 4. Manifest

Same writer as the other layers (⏳ Phase 0 item 9). ACG-specific keys:

```json
{
  "layer": "acg",
  "mode": "map | place",
  "profile": "general",
  "place": {"name": "Izmir", "source": "gazetteer"},
  "stage_status": {"compute_acg": "ok", "locate": "ok", "relocate": "absent:placidus_undefined_high_latitude", "...": "..."},
  "counts": {"lines_near_read": 1, "selection_rule": "tight_strong", "a1": 6, "a4": 0, "house_shifts": 1, "records_kept": 0},
  "acg_corpus_sha256": "<from sidecar>",
  "models": {"synthesis": "...", "translation": "..."},
  "gaps": ["rising_sign_records_absent"]
}
```

## 5. ⏳ Wiring table (fill from the Phase 0 report before implementing)

| Stage | Call | Real signature |
|---|---|---|
| 1 | birth-input resolver reused from `run.py` | ⏳ |
| 2 | `compute_chart(...)` | ⏳ |
| 6 | `compute_chart(..., utc override)` | ⏳ (the change proposed in Phase 0 item 1) |
| 7 | `ground.py` gate + `requires` evaluator reuse | ⏳ |
| 8 | `llm_client` call, translation, detox, validator entry points | ⏳ |
| 9 | run-folder + manifest helpers | ⏳ |

The coding agent fills this table in a short follow-up note and sends it to Radul **before**
writing `run_acg.py`.

## 6. Acceptance

| # | Check |
|---|---|
| O1 | Map mode (no place): only the stage 1–4 files + the manifest; zero model calls (patch `llm_client` to raise). |
| O2 | Place mode `--dry-run`: all the files except the reading outputs; `dry_run_prompts.json` is present; zero model calls. |
| O3 | Approximate birth time → `acg.json` absent, every later stage recorded as skipped with the reason, exit code 0. |
| O4 | `--lat 70 --lon 25` → the lines are located, relocation absent, the reading still produced from line evidence only. |
| O5 | The run folder name matches the `YYYYMMDD-HHMMSS_<3char>` pattern; `acg_run/` is gitignored. |
| O6 | The full existing test command from `PROJECT_OVERVIEW` §6 still passes (107), plus the new ACG tests. |
| O7 | One live run (a real chart, İzmir, general profile) completes; Radul reviews `reading.md`. |
