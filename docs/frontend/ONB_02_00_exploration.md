# ONB_02 Phase 0 — shared profile dossier

Date: 2026-10-06. Working checkout: `D:\Dev\astrology-app`.
Source: `G:\My Drive\Tech\Astrology app\FE\ONB_02_PROFILE_DOSSIER_SPEC.md`.
Companion: [ONB_01_00_exploration.md](ONB_01_00_exploration.md).

## Gate

ONB_02 §8 explicitly requires a read-only exploration report followed by **Stop**. This report completes investigation work before implementation approval. Benchmark code lives in ignored `.tooling/`; outputs are in `frontend/artifacts/onb-phase0/`. No production module, store record, Supabase setting or existing reading was changed. Deterministic test calls used isolated calendar/map/wheel output directories. Existing collective-year caches were read. `llm_client.complete` was patched to raise; zero model calls occurred and the budget ledger was unchanged.

## Main findings

1. The requested producers already exist. A shared accessor can reuse them without changing astrological calculations.
2. The PA and app currently use separate map roots, independent natal grounding/routing, and different rolling calendar anchors. They must converge before claiming zero recomputation.
3. The PA scans CLI run folders for reading prose; it does not read the app's SQLite reading records. The new readings index is required, not optional.
4. A warm `run_acg.build_chart_products` still calls `compute_acg` before testing the cache. Merely wrapping that function does not satisfy D6. The dossier must return stored products before entering a producer.
5. Map recommendations in the actual frontend use the newer `acg_line_first.rank_line_first` and destination filters, not only the `acg_recommend.rank` named in the spec. Preserve that behavior; add its inputs/products to the inventory.
6. Anonymous auth is disabled remotely and unsupported by the local owner-bound data model. Keep it off until account isolation and claim tests pass.

## Real producers and call sites

The exact Python signatures and source locations are captured in `artifacts/onb-phase0/signatures.txt`.

| Product | Producer and current consumers |
|---|---|
| Chart | `compute_chart(BirthData, utc_override=...)`; chart_bridge.calculate validates exact local time, rejects DST ambiguity/nonexistence, and sets a deterministic reading_date_utc. PA chart_of separately constructs BirthData. Keep the app's validation semantics in the central birth resolver. |
| Natal grounding | `ground(records, chart, reading='natal', house_policy='placidus')`; reading_bridge calls it for batch reading, PA ground_chart calls it independently. |
| Natal Plan | New producer required: l4_progressive.prepare. Existing route, non_empty, section_houses, section_title and low_salience_ids provide the ingredients. Persist sorted identifiers and a serializable routed carrier view, not Python objects. |
| PA dossier | `pa_dossier.build_dossier(chart_key, chart, personal_principles=..., l4_output=...)`; accepting personal_principles avoids re-grounding but it still calls route internally. Add a supplied-routing input so one shared route serves both consumers. |
| Wheels | `run.render_chart_wheels(chart_path, run_dir, suffix, stem='chart_wheel')`; Node renderer checks both themes. |
| ACG geometry | `compute_acg(chart)`; run_acg bundle, map_bridge and PA acg loader. |
| Parans | `compute_parans(acg)`; same map bundle; recommendations require `set_parans` today (mutable module state). Isolate or lock this state across concurrent charts. |
| City scan | `city_scan(acg, gazetteer=None)`; run_acg bundle. |
| Goal scan / heat | `goal_scan(acg, aff, gazetteer, grid, parans)` plus heat_geojson per goal; NumPy-backed cache, not plain JSON. |
| Rankings | `rank(goal, scope, acg, scan, aff)` requires **goal_scan**, not city_scan. Initial probe exposed `KeyError: city_ids` with city_scan; corrected follow-up uses goal_scan. Actual FE recommendation path also uses line-first rankings and filters; overall recommendations are separate. |
| Places | `build_locate(acg, natal, location, parans=...)` returns locate plus relocated chart; `ground_acg` produces payload/drop report. Used by map_place, map_reading_bridge and PA tools. Current place is user-specific, so store multiple place products under shared chart rather than a single mutable current-place slot. |
| Collective events | `ensure_year(year, base=..., rebuild=False)`; shared year files and load_range. |
| Personal events | `ensure_events(natal,tz,start)` wraps build_personal_events; consumed by ensure_calendar, run_calendar and PA. |
| Scores / periods | `ensure_scores(natal,tz,events,ev_key)` returns public scores, periods and cache status. It builds full scores internally for period production. |
| Best Days | `ensure_best_days(natal,tz,start)` retains internal `_parts`; publish only the existing public projection to app clients. |
| Notifications | `cal_scoring.notifications(periods,events,collective,templates,windows=...)`; run_calendar passes Best Days windows. Supplemental measurement omitted optional windows; final equivalence tests must use exact orchestrator inputs. |
| Forecasts | `compute_forecast(natal,target,horizon,latitude=...,longitude=...,now=...,run_id=...,window_tz=...)`; forecast_bridge currently invokes directly. |
| Forecast grounding | `ground_forecast(forecast,chart,records,cap=6,sim_floor=.35,retriever=None)`; current app passes no retriever, so structural grounding only. Preserve this. |
| Pair grounding | `ground_relationship(records,chart_a,chart_b)` returns RelResult; compatibility_bridge and PA compatibility tool each call it. Pair orientation must be preserved alongside a sorted pair key because person_a/person_b are directional. |

### Additional consumer rewrites beyond pa_context

The spec says PA changes can be confined to pa_context, but current `pa_tools.compatibility` directly invokes relationship grounding, and `pa_tools.place` performs location grounding. Those paths also need the pair/place accessor or injected context methods. `units()` builds calendar unit plans from stored event/corpus data; this is deterministic projection, not new astrological computation, but should be cached by version if D6 measures it.

## Keys and cache roots

| Identity | Current derivation / location | Proposed migration |
|---|---|---|
| App chart key | engine.ts SHA-256 of JS JSON `[raw.meta,date,time,lat,lon,raw.points,raw.sectors]`, first 32 hex | Canonical dossier key. Preserve existing byte serialization and keys; do not casually replace with Python json.dumps. Use cross-language golden tests before moving key computation. |
| Calendar / PA alias | personal_events.chart_key, first 16 hex | Manifest alias; existing calendar cache is a read-through source. |
| Predictive alias | compute_forecast._natal_ref, `sha256:` plus 16 hex | Manifest alias; connect existing forecast caches/index. |
| ACG alias | run_acg.chart_cache_key, 24 hex, includes code/data versions | Manifest alias. A cache version is not the permanent profile identity. |
| Calendar storage | `cal_run/_cache`, collective year/text files; app run views in `frontend/.local-data/calendar` | Adopt existing matching products through one accessor; no independent rebuild on a cache hit. |
| Map storage | CLI/PA `acg_run/_cache`; app `frontend/.local-data/map-products` | Read-through from both legacy roots, verify matching aliases/dependencies, then select one dossier product as authoritative. |
| PA natal storage | `ask_run/_cache/<calendar-key>/dossier.json` | Import compatible products into dossier A0, refresh prose from app reading index; preserve CLI fallback during migration. |
| App text storage | `reading:`, `forecast-reading:`, `map-reading:`, `compat:` in SQLite; calendar TextStore separately | Index ready content only; never initiate model calls from a deterministic dossier getter or PA request. |

### Rolling inputs

The app currently starts its calendar at local today; PA starts at today minus seven. Standardize event/score/period products to **today minus seven**. Keep Best Days' actual generation start at **today**, although it is stored in the same rolling dossier bucket, so its ninety-day future coverage is not shortened.

A day forecast consumes current latitude and longitude as well as timezone. Moving within the same timezone can change those inputs. Store a location fingerprint in its product dependency key; a timezone-only path is insufficient. Multiple profiles/users sharing a birth chart must not overwrite one another's location-dependent forecasts or current-place products.

## Determinism and version mismatches to resolve

- Forecast outputs contain `meta.generated_at` and `meta.run_id`; deterministic injection arguments already exist. Use fixed product-context values and keep operational timestamps in the manifest. Equivalence compares calculated content separately from operational provenance.
- A blanket git SHA dependency would rebuild unrelated products on every commit. Keep git SHA as audit provenance, plus product-specific source/corpus/affinity hashes for selective invalidation.
- The D9 example assumes a polar birth location makes ACG absent. At latitude 85 the tested chart has no Placidus cusps, but compute_acg returns **ok**. Absence tests should exercise supported reasons (non-exact time, missing UTC or controlled ephemeris failure) and separately test unavailable polar houses; do not manufacture absent geometry.
- The public chart bridge rejects unavailable Placidus houses today. Keep that onboarding behavior unless a separate domain decision changes it.
- The current code can produce the same pair's directional result in different input order. Store canonical orientation plus a reversible consumer view, not one ambiguous sorted-pair payload.
- Solar Return has a declared API route but no implemented deterministic producer was found; it remains outside the dossier inventory until implemented.

## Measured timings

See the appended measured table and JSON artifacts. These are Phase 0 probes, not completed D1–D15 acceptance tests. Three supplied fixture charts were used; no unverified identification of a fixture as Radul's personal chart is made. The spec's reference counts differ by fixture as documented in ONB_01.

Fresh-process A0 probe (imports, chart, corpus load, grounding, route and existing PA dossier): **289.87, 305.10 and 306.13 ms wall time**. This supports feasibility of the one-second target, but is not a p95 production claim. Existing PA dossier does a second route; the implementation will remove that duplication.

The first 99-call ranking sweep (eleven goals × three scopes × three charts) was stopped after **253.5 seconds** without completing. Its per-chart timing was not persisted, so no per-chart total is claimed. A bounded follow-up measures one world career ranking per fixture. The full <=60-second target remains unproven and needs shared intermediate geometry/scoring work, without changing the approved ranking output.

## Proposed implementation

1. File-backed dossier under the private local data root (logical `dossier/{app_chart_key}`), atomic writes, per-product locks, references and manifest; import matching legacy caches on first use.
2. A0 built synchronously, loading corpus once per persistent worker and sharing one grounding and routing result with progressive reading and PA. Do not introduce a model call here.
3. Separate lower-priority CPU worker for A1/B and pair products; reading jobs retain priority. Ready section generation starts after A0 without waiting for map rankings.
4. Accessor returns stored products before calling producers, with explicit ok/absent/failed semantics. Rolling products use one anchor and dependency fingerprint.
5. Rewire each Python bridge plus PA context/tools; preserve byte-compatible public contracts and existing validated rendering.
6. Publish ready readings from the app's writing path into a versioned read-only index. Never scan CLI runs for app-user prose; retain those locators for CLI-only migration.
7. Profile edit, current-location update, deletion and export update reference counts and product indexes transactionally. Deleting the last reference removes dossier and related pair products; shared references prevent deletion. Export manifest/chart/principle-id lists, not corpora or credentials.
8. Instrument producer calls on warm endpoint/PA requests, and run D1–D15 before declaring migration complete. Stop at ONB_02 Phase 3 as specified.

## Defaults proposed for approval

- Keep twelve-month events and ninety-day Best Days.
- Anonymous users receive A0 immediately. Build A1/B after first sign-in **or** when Part One is read; this follows the recommendation in §9 and avoids work for users who leave immediately. Signed-in self profiles receive the background build at creation. Other saved people receive A0 plus required pair products; expand other tiers on demand.
- Use private local files and existing SQLite references now; production hosting/storage is not selected by this task.
- Preserve the approved app's newer line-first and overall map recommendations, alongside the required deterministic rankings.

The anonymous build timing conflicts with the unconditional build wording in §4; the proposed default resolves that conflict explicitly rather than silently choosing a costly path.

## Measured product table (milliseconds)

| Product | 1988-12-28 | 1984-06-12 | 1979-03-30 |
|---|---:|---:|---:|
| chart | 5.81 | 0.42 | 0.45 |
| natal_grounding | 3.87 | 4.36 | 5.05 |
| routing | 0.86 | 0.88 | 1.06 |
| pa_dossier_existing | 1.46 | 1.47 | 1.83 |
| wheel_both | 95.09 | 93.88 | 92.68 |
| acg_bundle_cold | 5751.83 | 5402.12 | 6697.07 |
| personal_events | 2830.63 | 2825.85 | 2859.27 |
| scores_periods | 56.60 | 57.77 | 58.44 |
| best_days | 571.11 | 555.85 | 585.82 |
| collective_years | 0.67 | 0.76 | 0.82 |
| notifications | 0.47 | 0.46 | 0.44 |
| forecast_day | 34.60 | 33.24 | 34.17 |
| forecast_grounding_day | 1.59 | 1.18 | 1.38 |
| forecast_month | 197.21 | 198.14 | 197.36 |
| forecast_grounding_month | 3.11 | 3.42 | 4.17 |
| forecast_year | 206.74 | 203.45 | 261.83 |
| forecast_grounding_year | 1.57 | 1.83 | 2.19 |

Pair grounding: 4.38 ms, 3.71 ms, 3.51 ms.
Natal corpus load: 11.73 ms. Collective-year measurements are existing-cache reads, not cold builds.

Raw artifacts: `artifacts/onb-phase0/timings.json`, `cold-a0.json`, `auth-settings.json`, `polar.json`, `supplement.json`, `signatures.txt`.

### Completed bounded follow-up

| Product | 1988-12-28 | 1984-06-12 | 1979-03-30 |
|---|---:|---:|---:|
| acg_warm | 36.86 | 35.39 | 31.09 |
| rankings_goal_scan | 8874.57 | 8746.03 | 8775.17 |
| place_locate_relocate | 7.11 | 6.45 | 6.75 |
| place_grounding | 30.50 | 18.96 | 20.25 |

`rankings_goal_scan` here measures **one career/world ranking**, not all eleven goals or all three scopes. About 8.75–8.87 seconds per call makes sharing reusable ranking inputs a material part of the implementation. Place timings use each fixture birth place as a deterministic sample; current places follow the same producer path.
Warm ACG bundle calls still enter compute_acg despite the 31–37 ms total; an accessor must bypass that call to pass D6.

Reproduction scripts: `.tooling/onb-explore.py`, `.tooling/onb-supplement-bounded.py`. The initial failed city-scan ranking attempt remains in the raw evidence; the corrected measurements are separate rather than silently replacing it.
