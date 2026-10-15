# FORECAST_COMPUTE_NOTES.md

Implementation notes for `compute_forecast.py` (built to `FORECAST_COMPUTE_SPEC.md`).
Records the decisions an engineer would otherwise have to reverse-engineer, and the
two places the implementation deliberately diverges from the letter of the spec.

## Files
- `compute_forecast.py` — the deterministic event engine (`compute_forecast()` is a
  pure function; `write_forecast()` does the §12 persistence I/O).
- `forecast_types.py` — TypedDicts (authoritative Python shape; twin of chart_types.py).
- `forecast_schema.json` — JSON-Schema Draft 2020-12 twin.
- `test_forecast.py` — fixtures + all §13 invariants; emits `forecast_report.json`.

## How to run
```
# from Forecast_compute/, using the repo root venv (has swisseph, timezonefinder,
# jsonschema, pytest):
../.venv/Scripts/python.exe compute_forecast.py      # demo: writes a run folder
../.venv/Scripts/python.exe test_forecast.py         # invariants + writes the report
../.venv/Scripts/python.exe -m pytest test_forecast.py -q
```

## Reuse (SPEC §2)
`compute_chart.py` lives in `../d_layer` and imports its sibling `chart_types` by bare
name, so the engine prepends `../d_layer` to `sys.path` and imports `compute_chart` as a
module. Swiss-Ephemeris access, the position/speed helpers, dignity logic, both house
systems, sect, and the day/hour ruler are all imported from it — nothing is forked.

## Inputs
`compute_forecast(natal, target_date, horizon, *, latitude, longitude, ...)`.
- `natal` is consumed as-is; natal positions/cusps/sect are never recomputed.
- The day-boundary tz comes from `natal.meta.timezone` (§3) — no coordinates needed for
  windowing.
- **`latitude`/`longitude` are an added input** not in the spec's §1 list. The natal
  chart object does not carry birth coordinates, and the day/hour ruler (§6 DAY row,
  invariant 5) needs them for the sunrise anchor. They are optional; omit them and the
  ruler is reported `null`. They are used for nothing else.
- `now`/`run_id` are injectable so tests can pin the only two non-deterministic meta
  fields (invariant 7).

## Deliberate deviations from the spec letter
1. **Aspect names are full, not abbreviated.** §11's `Event.aspect` lists
   `conj|sext|square|trine|opp`, but §11 also mandates reusing chart-object names where
   fields overlap ("confirm against chart_schema.json … don't invent parallel names").
   Aspect type overlaps `chart_schema.json`'s `AspectType`, so we emit the full
   `conjunction|sextile|square|trine|opposition`. This also makes `topic_tags` match the
   corpus's own aspect vocabulary for the embedding path.
2. **No `midheaven` grounding kind.** §9 suggests `{kind: "ascendant"|"midheaven"}` for
   angle contacts, but the grounded corpus has **no** `midheaven` kind (confirmed by
   counting `requires.kind` across the predictive records) — emitting it would never
   match structurally. So only Ascendant contacts ground as `ascendant`; MC / IC /
   Descendant contacts ground as `other` with `angle` + rich `topic_tags` (including
   `"midheaven"`), which is the load-bearing embedding path anyway.

## Other decisions worth knowing
- **Lunations/eclipses are pure-sky events** (`bodies.transiting = null`): a syzygy is not
  a body transiting *to* a natal point. This is also what makes invariant 2 hold literally
  on YEAR — the Moon never sits in the transiting slot; eclipses survive as sky events and
  the luminary is carried in `grounding.point` / `topic_tags`.
- **Detection is grid + bisection.** Each in-scope body is sampled once across the window
  (step 10 min / 60 min / 6 h for day / month / year); crossings (aspect elongations, sign
  and house boundaries, Sun–Moon syzygies) are found by sign-change between samples and
  refined by bisection to sub-second. Retrograde multi-perfection falls out naturally —
  each crossing is a separate bracketed root (invariant 10).
- **Standing aspects** (in-orb at window start, perfecting *outside* the window) use the
  §7 orb table (luminaries 1.5°, else 1.0°) and are suppressed on the DAY horizon
  (invariant 3). An aspect that perfects *inside* the window is emitted as a perfection,
  not also as standing.
- **Day/hour ruler** is a forecast-level `rulers` block (DAY only), not an `events[]`
  entry — the §11 `family` enum has no ruler family, and invariant 5 only requires it be
  "included".
- **Precision fallback (§8):** `degraded = (natal.confidence == "unknown")`. When degraded,
  house ingresses, angle-target aspects, and lunation-in-house tagging are dropped and
  listed in `meta.suppressed_families`; planet–planet aspects and sign ingresses remain.
- **Optional modules ship OFF:** profections (§4d) is a gated stub that raises if switched
  on; lots-as-targets (§4a) is a gated flag. Both states are recorded in `meta.config`.

## Not in this module (downstream)
Grounding of events to predictive principles, profile lensing, and rendering. This module
only emits the deterministic, dated event list + its `grounding` signatures.
