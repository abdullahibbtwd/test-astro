# ONB_02 — Profile dossier: every deterministic data point and every grounded rule, computed once

**For:** the backend coding agent · **Owner:** Radul · **Domain decisions:** Claude
**Companion:** `ONB_01_PROGRESSIVE_NATAL_READING_SPEC.md`. ONB_01's `prepare()` reads from this dossier (§6).
**Also read:** the Personal Astrologist (`astrologist/`, `PA/PA_00–04`, `ask_bridge.py`). It is now in the repo and connected to the app. The PA already builds part of this dossier for itself; §5.1 says how the two become one.
**Status:** ready for Phase 0.

---

## 0. What Radul asked for

> "Calculate every deterministic data point for the person's personal chart that is used for all the readings after. Also all the grounded rules."

When a person's birth profile is created, the backend computes and stores **everything deterministic** that any later reading uses, plus **every grounded rule set**. The readings covered are natal, forecasts, calendar, Best Days, astrocartography, compatibility and the Personal Astrologist. From then on:

1. LLM layers only **read** the dossier. They never recompute charts, events or grounding.
2. Every screen and every reading uses **the same numbers**: one chart, one event list, one set of grounded principles.
3. The Personal Astrologist gets its "all grounded rules for this person" from one place.

The dossier costs **no LLM tokens**; it is CPU only.

## 1. Principles

- **Deterministic.** Same birth data + same code/corpus versions → byte-identical products.
- **Versioned.** Every product records the versions it depends on. A version change rebuilds only the products that depend on it.
- **Non-blocking.** Only tier A0 (§2) is computed synchronously, in under 1 s, because the onboarding reading needs it. Everything else builds in the background, while the user reads.
- **One key.** The code has **four** chart keys today:

  | Key | Where | Shape |
  | --- | --- | --- |
  | App `chart_key` | `FE/local-api/engine.ts computeBirthChart` | sha256(meta, date, time, lat, lon, points, sectors), 32 hex |
  | Calendar / PA key | `Calendar/personal_events.chart_key(natal)`; used by `run_calendar` caches and the PA (`ask_run/_cache/<key>/`) | sha256(utc, precision, points, cusps), 16 hex |
  | Predictive `natal_ref` | `Forecast_compute/compute_forecast._natal_ref(natal)` | "sha256:" + 16 hex of the full chart JSON |
  | Astrocartography cache key | `run_acg.chart_cache_key(acg_meta, corpus_sha, affinity_sha)` | 24 hex, includes code and data versions |

  The dossier is keyed by the **app `chart_key`**. The manifest stores the other three as `aliases`, so the existing caches and locators keep resolving during migration. After Phase 3, nothing outside the dossier computes a key of its own.
- **Absence, not failure.** A product that can't exist (e.g. astrocartography absent at extreme latitudes) is stored as `absent` with a reason, exactly as the orchestrators do today.

## 2. Inventory — what the dossier holds

Producers are the real functions found in the code (verify in Phase 0). "Consumers" are who must read the product instead of recomputing it.

### Tier A0 — birth-static, synchronous at profile creation (< 1 s)

| Product | Producer | Consumers |
| --- | --- | --- |
| `chart` | `d_layer/compute_chart.compute_chart(BirthData)` | Every endpoint and every reading |
| `natal_grounding` (`kept`, `bundled_by_factor`, `grounding_report`) | `principles_grounding/ground.ground(records, chart, reading='natal', house_policy='placidus')` | L4 / ONB_01, chart element notes, Personal Astrologist |
| `natal_plan` (routing, ownership, titles, low-salience ids) | `l4_progressive.prepare(chart, kept)` (ONB_01 §3.1) | ONB_01 progressive reading, natal section links (FE_05 §3.4) |
| `pa_dossier` (`pa-dossier-1`: facts, records, bundles, `by_topic`, `by_body`, prose) | `astrologist/pa_dossier.build_dossier(chart_key, chart, personal_principles=natal_grounding, l4_output=<ready ONB_01 sections>)` | PA tools `chart_facts`, `natal_topics`, `natal_section` |

`pa_dossier` must be built **from** `natal_grounding` and must reuse the routing already in `natal_plan`, so `ground()` and `route()` run once per chart. Its `prose` is refreshed every time an ONB_01 section becomes ready; that is cheap, since only prose and availability change (PA_01 §2.5).

Measured on Radul's chart: corpus load 0.16 s; `ground` + `route` under 0.01 s; 166 kept principles.

### Tier A1 — birth-static, background (once per chart and version)

| Product | Producer | Consumers |
| --- | --- | --- |
| `wheel_svg` (light, dark) | `Chart_wheel/cli.js --check` (as `run.render_chart_wheels`) | FE parity tests, export / PDF |
| `acg` + `acg.geojson` | `compute_acg.compute_acg(natal)` | `/acg/lines`, map |
| `parans` (+ geojson) | `compute_parans.compute_parans(acg)` | Map, goal scan |
| `city_scan` | `acg_locate.city_scan(acg)` (~2.5–3.5 s measured) | Place, area, recommendations |
| `goal_scan` + 11 `goal_heat_{goal}.geojson` | `acg_goals.goal_scan(acg, affinity, gazetteer, grid, parans)` | `/acg/heat/{goal}` |
| `acg_rankings` (11 goals × scopes `world`, `TR`, home country) | `acg_recommend.rank(goal, scope, acg, scan, aff)` | "Nereye gitmeli?" lists; the LLM explains only the rows shown |
| `acg_places` (birth place, current place) | the city path of `run_acg`: locate → relocate → `ground_acg.ground_acg(natal, relocated, locate, …)` | Place readings for the two places people ask about first; Personal Astrologist |

Today all of this is `run_acg.build_chart_products(...)` plus the city path, cached under `acg_run/_cache/<key>/`. The PA calls the same function in `TurnContext.acg()`. The dossier calls the same code once, for both. Other places are still grounded on demand and **added** to the dossier when computed.

### Tier B — rolling, anchored to "today − 7 days" in the user's current time zone

**Anchor = today − `DAY_PAST_DAYS` (7).** That is what the PA uses (`TurnContext.cal_start()`, PA Phase 0 X11), so it can answer about the last 7 days. The calendar cache keys include the start date. With different anchors, the calendar screens and the PA would build the same calendar **twice a day** for the same person; one anchor for both prevents that.

| Product | Producer | Window (existing constants) | Consumers |
| --- | --- | --- | --- |
| `collective_events` (shared, not personal) | `collective_events.ensure_year(y)` | the years covered | Calendar, Best Days |
| `personal_events` + `day_scores` + `periods` | `run_calendar.ensure_calendar(natal, tz, start, best_days=False)`, which wraps `ensure_events` / `ensure_scores` (`personal_events.build_personal_events`, `cal_scoring.day_scores`, `cal_scoring.periods`). This is the same function the PA calls. | `CALENDAR_MONTHS` (12) | Calendar month/day/year/periods, Home band → `score_10`, Personal Astrologist (`day`, `span`, `calendar_item`) |
| `best_days` (all activities, with the internal `_parts`) | `run_calendar.ensure_best_days(natal, tz, today)` (PA calls the same) | `BEST_DAYS_DAYS` (90) | Best Days, notifications, PA `best_days` |
| `notification_candidates` | `run_calendar` stage 6 | same | Notifications |
| `forecast_day` (today), `forecast_month` (this month), `forecast_year` (from this month) | `compute_forecast.compute_forecast(natal, target_date, horizon, window_tz=tz, latitude, longitude)` | day / month / year | Home, Today, month and year forecasts, Personal Astrologist |
| `forecast_grounding` (per horizon above) | `ground_forecast.ground_forecast(forecast, chart, records)` (structural; today's code passes no retriever) | same | Forecast readings, Personal Astrologist |

Today the calendar rebuilds in full in about 6 s per chart (CAL_BUILD_NOTES), cached by horizon start date. The dossier keeps that cache rule.

### Tier C — pair products, built when a second person is added

| Product | Producer | Consumers |
| --- | --- | --- |
| The other person's A0 (and A1/B only if they are themselves a user) | as above | Compatibility |
| `relationship_grounding` per pair | `ground_relationship.ground_relationship(records, chart_a, chart_b)` (tagged corpus; all three reading types read from the same result) | Compatibility readings, Personal Astrologist |

### Not in the dossier

- **Anything an LLM writes:** readings, element notes, calendar and Best Days texts, astrocartography explanations, Personal Astrologist answers. These are cached as **readings**, keyed to the dossier versions they used.
- **Solar Return:** FE_02 §7.5 lists it as NEW and no backend producer exists yet. Add it to tier B (`solar_return_{year}`) when it is built.
- **Points L1 does not compute yet** (profections, antiscia, fixed stars, harmonics, midpoints, declinations). No reading consumes them. Each one joins the dossier the day a reading starts using it. That's the rule: the dossier holds **exactly what readings consume**, no more and no less.

## 3. Storage

```text
dossier/{chart_key}/
  manifest.json
  a0/chart.json  a0/natal_grounding.json  a0/natal_plan.json
  a1/wheel.light.svg  a1/wheel.dark.svg  a1/acg.json  a1/acg.geojson  a1/parans.json  a1/city_scan.json
  a1/goal_scan.npz  a1/goal_heat_{goal}.geojson  a1/acg_rankings.json  a1/places/{place_id}.json
  b/{tz_slug}/{anchor}/personal_events.json  day_scores.json  periods.json  best_days.json
  b/{tz_slug}/{anchor}/notifications.json  forecast_{horizon}_{period}.json  forecast_grounding_{horizon}_{period}.json
pairs/{pair_key}/relationship_grounding.json            # pair_key = sorted(chart_key_a, chart_key_b)
```

`manifest.json`:

```json
{
  "chart_key": "…",
  "birth": { "utc": "…", "lat": 0, "lon": 0, "time_precision": "exact" },
  "versions": {
    "code": "<git sha>", "ephemeris": "<swisseph version>",
    "natal_corpus_sha": "…", "forecast_corpus_sha": "…", "acg_corpus_sha": "…",
    "acg_affinity_sha": "…", "cal_corpus_sha": "…", "cal_affinity_sha": "…",
    "best_days_catalogue_sha": "…"
  },
  "products": [
    {
      "name": "city_scan", "tier": "A1", "anchor": null, "path": "a1/city_scan.json",
      "sha256": "…", "depends_on": ["code", "ephemeris"],
      "status": "ok | absent | failed", "absence": null,
      "computed_at": "…", "duration_ms": 0
    }
  ]
}
```

- **Profile → dossier:** each profile references its `chart_key` and the user's current tz.
- **Shared dossiers:** two profiles with the same birth data share one dossier. It is deleted when the last referencing profile is deleted (`DELETE /profiles/{id}`, `DELETE /me`).
- **Private data:** the dossier contains birth data and personal events. Store it with the same protection as the reading records, never in logs.
- **Existing caches:** `cal_run/_cache/` and `acg_run/_cache/` are migrated into the dossier, or become a read-through. Phase 0 proposes which. There must never be two copies computed independently.

## 4. Build and refresh

| When | What runs |
| --- | --- |
| `POST /profiles` (onboarding or My Charts) | **A0 synchronously** (< 1 s), then ONB_01 starts `core_identity`. Then one background job `kind: 'dossier'` builds A1 + B. |
| First request of a new local day | Rebuild B for the new anchor. Also allowed as a nightly batch for active users. |
| Month or year boundary | Rebuild `forecast_month` / `forecast_year` + their grounding. |
| Current location change | Rebuild B for the new tz; add `acg_places` for the new current place. |
| Second person added | Tier C for that pair; A0 for the new profile. |
| Birth data edited | New `chart_key` → new dossier; the old one is kept only if another profile references it. |
| Corpus / affinity / code version bump | Rebuild only the products whose `depends_on` changed. Example: the natal corpus changes → `natal_grounding` + `natal_plan` rebuild; astrocartography does not. Sections already read in ONB_01 stay immutable. |

- **Worker pool:** dossier jobs run separately from LLM jobs and at lower priority, so they never delay the first reading section.
- **Readiness:** a consumer that needs a product not yet built waits on the dossier job, using the existing FE_02 §4 `202 { job }` pattern with stage names `compute_chart`, `natal`, `compute_acg`, `city_scan`, `goal_scan`, `events`, `scores`, `best_days`, `compute_forecast`, `ground_forecast`. FE labels for these already exist (FE_02 §4.3).

## 5. Consumers read only from the dossier

- Add one accessor: `dossier.get(chart_key, product, anchor=None)`. It returns the stored product, or builds it on a miss, stores it, and returns it.
- **Every bridge reads through the accessor:** `chart_bridge.py`, `reading_bridge.py` / ONB_01, `forecast_bridge.py`, `calendar_bridge.py`, `map_bridge.py`, `map_reading_bridge.py`, `compatibility_bridge.py` and the Personal Astrologist bridge. No bridge calls `compute_chart`, `ground*`, `compute_forecast`, `build_personal_events`, `build_best_days` or the astrocartography compute functions directly.
- **Personal Astrologist:** the dossier is its source for "all grounded rules for this person" (§5.1).

### 5.1 Personal Astrologist integration (code read on 2026-10-06)

**What the PA does today:**
- **`astrologist/pa_context.TurnContext` computes everything itself, lazily, on each turn:**
  - `natal()` → `compute_chart`
  - `dossier()` → `pa_dossier.load_or_build` → `ask_run/_cache/<calendar key>/dossier.json`
  - `calendar()` → `run_calendar.ensure_calendar`
  - `best()` → `ensure_best_days`
  - `acg()` → `run_acg.build_chart_products`
- **`prewarm(subject)` exists** (`pa_engine.py`), building dossier, calendar, Best Days and astrocartography. `PA_FRONTEND_INTEGRATION.md` says it is **not wired** in the app, so the first question after onboarding can hit the 45 s `not_ready` path (`PA_TOOL_TIMEOUT_S`).
- **Gap — the PA can't see app readings.** It finds natal prose with `find_l4_output(birth)`, which scans `runs/*/run_meta_*.json`. It finds forecast readings with `find_prediction(natal_ref, …)`, which scans `prediction_run/`. Readings generated by the app live in the local-api store, not in those folders, so for app users the PA never sees them: `natal_section` is always `absent`.

**What changes:**
1. **The dossier build job replaces `prewarm`.** It runs at profile creation and covers `chart`, `pa_dossier`, calendar, Best Days and astrocartography. The first Ask turn finds everything ready.
2. **`TurnContext` loaders read through `dossier.get(...)`:** `natal`, `chart_key`, `dossier`, `calendar`, `best`, `acg`, `collective`. They keep their signatures, so the PA code changes are confined to `pa_context.py`.
3. **`find_l4_output` / `find_prediction` are replaced by a dossier `readings` index.** It lists, per chart and language:
   - the ready ONB_01 sections;
   - the cached forecast readings (day, month, year, lens);
   - the cached calendar texts;
   - the place readings.

   The PA reads prose only through it. The run-folder scans remain for the CLI.
4. **The PA keeps its rule D4:** it never starts paid generation. In particular, a PA question about an unread natal section **never** triggers ONB_01 generation. The PA answers from the section's grounded records (`natal_topics`), as PA_01 §4.3 already does when prose is absent.
5. **One natal grounding:** `pa_dossier.build_dossier` receives `natal_grounding` (it already accepts `personal_principles`) instead of calling `ground_chart()` itself.

## 6. Change to ONB_01

ONB_01 §5 "Start" becomes: `POST /profiles` → **dossier A0** (chart, `natal_grounding`, `natal_plan`) → generation of `core_identity` starts.
- `prepare()` is the producer of the `natal_plan` product.
- ONB_01 reads Plan and kept principles from the dossier and never re-grounds.
- ONB_01's `reading-plan:{chart_key}` record is replaced by `dossier/{chart_key}/a0/natal_plan.json`.

## 7. Invariants and acceptance

| # | Check |
|---|---|
| D1 | **Deterministic:** building the full dossier twice for each fixture chart (1988-12-28, 1984-06-12, 1979-03-30, plus Radul's) gives identical `sha256` for every product. Manifest timestamps are excluded. |
| D2 | **Zero LLM:** with `llm_client.complete` patched to raise, a full A0 + A1 + B + C build succeeds, and the budget ledger total is unchanged. |
| D3 | **A0 is fast:** p95 under 1 s, including corpus load. The corpus is loaded once per process and kept in memory. |
| D4 | **Build time:** per-product `duration_ms` reported for the fixture charts; full A1 + B in the background. Target ≤ 60 s CPU per chart; report the real figure. |
| D5 | **Equivalence:** for the same inputs, dossier products are byte-equal to what today's orchestrators write: `run_acg` map mode cache, `run_calendar --mode all` (deterministic stages), `run_predictive --dry-run` forecast + grounding. Nothing changes in behaviour. |
| D6 | **Read-only consumers:** with a warm dossier, serving every WRAP / DERIVED endpoint in FE_02 §9 for one profile makes **zero** calls to the compute and ground functions listed in §5 (instrument them). |
| D7 | **Rolling refresh:** advancing the clock one local day rebuilds only tier B products with a day anchor. Crossing a month boundary also rebuilds `forecast_month`. A1 is untouched. |
| D8 | **Version scope:** changing the natal corpus sha rebuilds `natal_grounding` + `natal_plan` only. Changing the astrocartography affinity sha rebuilds `goal_scan`, heat layers and rankings only. |
| D9 | **Absence:** a chart at a polar latitude (pick one where `compute_acg` returns absent) produces a complete dossier with astrocartography products `absent` + reason, and no exception. |
| D10 | **Deletion and export:** deleting the last profile on a `chart_key` deletes its dossier and pair products. `POST /me/export` includes the manifest, `chart` and the grounded `principle_id` lists; the corpus itself is not exported. |
| D11 | **Shared dossier:** two profiles with identical birth data build A0 / A1 once. |
| D12 | **PA ready after onboarding:** after profile creation and the background build, a first Ask turn (`run_ask.py --fake-llm`) finds dossier, calendar, Best Days and astrocartography ready: no `not_ready`, and zero compute calls during the turn (instrumented as D6). |
| D13 | **PA sees app readings:** once ONB_01 `core_identity` is ready, `natal_section{core_identity}` returns its prose. For a section not yet generated it returns `absent` (`not_generated`) plus `natal_topics` evidence, and **no generation job is created**. |
| D14 | **PA suites still pass:** `astrologist/test_pa_dossier.py`, `test_pa_tools.py`, `test_pa_cards.py`, `test_pa_pipeline.py`, including PA D1 (byte-identical dossier) and T13 (other layers' outputs unchanged by a PA session). |
| D15 | **One calendar build per day:** with the app calendar screen and the PA both used on the same day, `run_calendar` caches hold one events / scores / best-days build per (chart, tz, anchor). |

## 8. Phases and gates

| Phase | Scope | Gate |
|---|---|---|
| 0 | Read-only report `ONB_02_00_exploration.md`. Cover: real signatures and current call sites of every producer in §2, including every `TurnContext` loader and locator in `astrologist/pa_context.py`; every existing cache and the four chart keys (§1); where the app stores generated readings, for the `readings` index; Solar Return status; `ground_forecast` retriever status; measured time per product on the fixture charts (needs `pyswisseph`). Propose migrate vs read-through for `cal_run/_cache`, `acg_run/_cache` and `ask_run/_cache`. | **Stop** |
| 1 | Dossier core (manifest, accessor, versions), A0 + A1, tests D1–D3, D8, D9, D11 | — |
| 2 | Tier B + refresh rules + tier C (D4, D7) | — |
| 3 | Rewire every bridge and the PA `TurnContext` through the accessor; `readings` index; dossier job replaces `prewarm` (D5, D6, D10, D12–D15); ONB_01 reads from the dossier (§6) | **Stop** |

## 9. Decisions for Radul

1. **Horizons:** keep the existing constants (12-month events, 90-day Best Days) for the onboarding build, or shorten them for anonymous users? I recommend keeping them: it's CPU only and they're needed the moment the user opens Calendar.
2. **Anonymous users:** build A1 + B for them too (cost is CPU only) or only after sign-in? I recommend after the first sign-in, or after Part One is read, to avoid computing for bounce-only installs. A0 always.
3. **Storage:** files under a per-chart folder (as now) for the local preview. Production storage (object store vs DB) is decided with the hosting plan.
