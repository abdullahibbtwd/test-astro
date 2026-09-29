# ACG 03: `ground_acg` (grounding)

*v2, 2026-09-25: the primary source is now the ACG corpus from spec 06. The
planet-in-house reuse is demoted to a fallback, and the authored slice is retired.*

*Deterministic. No LLM. Extends `principles_grounding/ground.py`: reuse its gate
functions, record loader, `requires` evaluator and drop-report format. **Do not fork them.***

## 1. Purpose

Select the principles that are **true of this person in this place** and bundle them by
factor, under the no-hallucination contract: every claim in the reading must trace to a
record id kept here.

## 2. Inputs

`chart.json` (natal), `chart_relocated.json` (may be absent), `locate.json`,
**`acg_principles.grounded.json`** (spec 06; the primary source), and the main corpus
`all_principles.grounded.json` (fallback and stream B only).

Only the ACG records with `acg_scope ∈ {line, angle_frame, planet_general, method}` are eligible.
Records in `paran`, `zenith`, `ccg` or `mundane` are never loaded in v1.

## 3. Line selection

From `locate.lines_near` (with `read_in_v1: true` only):
1. Take every `tight` and `strong` line, up to the **4 closest** (`ACG_MAX_LINES_READ = 4`).
2. **If that yields none**, take the **single nearest `wide` line** (≤ 1,000 km), if any. This
   applies the source's rule that the nearest line is the most potent, and that a line can be felt
   up to ~1,000 km when it's the only one in the vicinity (`acg-method-orb-distance`).
3. Otherwise there are 0 lines, and `acg-method-no-influence` applies.

## 4. Three evidence streams

### A. Line evidence (primary)

For each selected line (body, angle):

| Source | Candidates | Gate 2 (subject) | Cap |
|---|---|---|---|
| **A1** ACG line records | `about.type == planet_on_angle`, planet = body, angle = angle | the line exists at the selected tier (from `locate.json`) | all that pass gate 3 |
| **A2** planet synopsis | `acg_planet_general` for the body | the body has a selected line | all that pass (1–4) |
| **A3** angle frame | `acg-angle-<angle>` | the angle has a selected line | 1 |
| **A4** fallback | the main corpus's `planet_in_house` records for `ANGLE_HOUSE[angle]` (`ASC→1, IC→4, DSC→7, MC→10`), modern | the line claim replaces the house claim | **used only if A1 kept < 3 records**; fill up to 3 A1+A4 records in total |

**Gate 3 (dependencies)** applies to A1, A2 and A4: evaluate `requires` (excluding A4's house
condition) as follows. Sign, aspect, dignity, speed or retrograde conditions go against the
**natal** chart. Angle, cusp or other-house conditions go against the **relocated** chart. If
the relocated chart is absent, conditions that need it cause a drop with
`requires_needs_relocated_chart`. Unsupported condition kinds cause a drop with
`requires_unsupported_kind` (never guess).

A4 is the only sanctioned exception to the Placidus-only house policy. Document it in the
module docstring.

Every kept record gets `acg_evidence: {"kind": "line", "source": "A1|A2|A3|A4", "body",
"angle", "tier", "distance_km"}`. Bundle order within a line: A3, A1 (by `citation_count`
descending), A2, then A4.

### B. Relocated-house evidence (secondary)

Only when the relocated chart is present. From `locate.house_diff`:
1. Drop the bodies already covered by stream A (reason `covered_by_line`).
2. Order: `angular_after == true` first; then the personal planets (Sun, Moon, Mercury, Venus,
   Mars); then the rest. Break ties by body order, Sun → Pluto.
3. Keep at most `ACG_MAX_HOUSE_SHIFTS = 5` bodies (reason `house_budget_exceeded` for the rest).
4. Per body: candidates = the main corpus's `planet_in_house` records for `(body,
   relocated_house)`, run through the **normal `ground.py` gates against
   `chart_relocated.json`** (Placidus as usual).
5. Tag them `acg_evidence: {"kind": "house_shift", "body", "natal_house", "relocated_house"}`.

**Known gap:** the relocated rising sign has no grounding (the main corpus has no rising-sign
records). Record `gaps: ["rising_sign_records_absent"]`. Don't compensate.

### C. Method records (framing, all from the spec 06 fixed ids)

| Record | Included when |
|---|---|
| `acg-method-ambivalence` | always (status ok) |
| `acg-method-natal-modifies-response` | always |
| `acg-method-degree-of-expression` | always |
| `acg-method-orb-distance` | ≥ 1 line selected |
| `acg-method-no-influence` | 0 lines selected |
| `acg-method-relocated-chart` | stream B kept ≥ 1 body |

`acg-method-lines-permanent`, `-remote-activation` and `-polar-convergence` are not used by the
v1 place reading. They are kept for map mode and for later.

## 5. Output

### 5.1 `acg_principles.json`

```json
{
  "schema_version": "acg-ground-2",
  "status": "ok | absent",
  "absence": null,
  "place": {"name": "Izmir", "name_tr": "İzmir"},
  "selection": {"rule": "tight_strong | nearest_wide | none", "lines": ["venus|DSC"]},
  "bundles": [
    {"factor": "line:venus|DSC", "tier": "tight", "records": ["<record + acg_evidence>"]},
    {"factor": "house:saturn|10", "natal_house": 3, "records": ["..."]},
    {"factor": "method", "records": ["..."]}
  ],
  "gaps": ["rising_sign_records_absent"],
  "counts": {"lines_kept": 1, "a1": 6, "a4": 0, "house_shifts_kept": 1, "records_kept": 0},
  "sensitivity_high_ids": ["acg-mars-asc-04"]
}
```

Bundle order: line bundles by distance ascending, then house bundles in stream B order, then
`method`. The profile lens acts in the reading (spec 04), not here. `sensitivity_high_ids` lists
the kept records flagged `sensitivity: high`, for spec 04 AV8.

### 5.2 `acg_drop_report.json`

The same format as the `ground.py` drop report. The reason enum is closed:
`tier_wide_not_selected`, `body_out_of_scope`, `line_budget_exceeded`, `scope_not_v1`,
`fallback_not_needed`, `covered_by_line`, `house_budget_exceeded`,
`requires_unsatisfied_natal`, `requires_unsatisfied_relocated`,
`requires_needs_relocated_chart`, `requires_unsupported_kind`.

### 5.3 Absence

If `locate.json` is absent, this output is absent with the same reason. If the lines are fine but
the relocation is absent, the status is **ok**: stream A runs with natal-only dependencies, and
stream B is skipped with a `gaps` entry `relocation_absent:<reason>`. If
`acg_principles.grounded.json` is missing, the output is absent with reason `acg_corpus_missing`.
**Never** fall back to A4-only silently.

## 6. Authored slice: retired

The v1 authored records are replaced by the spec 06 fixed ids. Don't create `acg_slice.json`.
If the spec 06 review gate rejects one of the fixed ids, Radul decides between re-extracting and
an authored stand-in. This spec doesn't pre-authorise authored text.

## 7. Acceptance invariants (`test_ground_acg.py`)

| # | Invariant |
|---|---|
| GA1 | Each stream-A record's source is consistent with its `about`: A1 is `planet_on_angle` with a matching body and angle; A2 is `acg_planet_general` with a matching body; A3 is `acg-angle-<angle>`; A4 is `planet_in_house` with `house == ANGLE_HOUSE[angle]`. |
| GA2 | Selection: fixture with 5 tight/strong lines → exactly the 4 closest are kept, and the 5th is `line_budget_exceeded`. Fixture with only wide lines → exactly the nearest one is kept, with `selection.rule == nearest_wide`. Fixture with nothing within 1,000 km → `no-influence` present, no line bundles. |
| GA3 | A synthetic A1 record with `requires` "Venus in Libra" on a chart with Venus in Taurus → dropped as `requires_unsatisfied_natal`, even though the Venus DSC line is tight. |
| GA4 | A4 appears only when A1 kept < 3 records for that line; A1 + A4 ≤ 3 in that case. When A1 ≥ 3, the A4 candidates are `fallback_not_needed`. |
| GA5 | Stream-B records all pass the standard Placidus check against `chart_relocated.json`. |
| GA6 | No body appears in both stream A and stream B. |
| GA7 | The method inclusion table (§4 C) holds exactly for the three GA2 fixtures. |
| GA8 | No kept record has `acg_scope` ∉ {line, angle_frame, planet_general, method}. |
| GA9 | Every kept record id exists in `acg_principles.grounded.json` or the main corpus. |
| GA10 | The natal `ground.py`, synastry and predictive grounding outputs for the fixture chart are byte-identical before and after this layer is added (the ACG corpus never leaks). |
| GA11 | Determinism and idempotence: two runs give byte-identical output. |
| GA12 | Relocation absent + one tight line → status ok, stream A present, stream B empty, and the `gaps` entry is present. |
