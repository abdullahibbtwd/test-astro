# PA Phase 0: exploration report

*2026-10-05. Answers PA_00 §7 and fills the PA_04 §10 wiring table. No feature code was written; nothing here made a
model call. Paths are relative to the repo root. Measurements use the three fixture charts of PA_04 §9:
1979-03-30 06:30 Sofia (reference), 1988-12-28 (partner), 1984-06-12 (colleague).*

## 0. Summary for review

**Feasible as specified, with the conflicts in §13.** Every deterministic stage the chat needs exists and runs without
a model:
- natal grounding takes under 0.01 s
- calendar: about 6 s cold, instant warm
- ACG place: 8 s cold, about 1 s warm
- synastry grounding is fast and pure

These must be **added** before or during the build:

| # | Gap | Proposal |
|---|---|---|
| G1 | **The L4 "2:1 modern:classical quota" doesn't exist in code.** L4 only tells the model, in its prompt contract, that modern governs (`Interpretation_layer/l4_prompts.py:46-48`). | Implement it in `pa_dossier.select_natal` exactly as PA_01 §2.3 says (it is defined there). |
| G2 | **No fuzzy place search.** `acg_locate.gazetteer_lookup` (`Astrocartography/acg_locate.py:80-106`) is exact after folding case, diacritics and İ/ı. The fallback is Nominatim's first hit. `.cache/geocode.json:32-35` still caches **"instanbul" → Antwerp**, so the bug replays on every run. | `pa_tools` adds a deterministic fuzzy search over the gazetteer + destinations (TR/EN names and aliases, `difflib` ratio on folded text, ranked by population). The chat **never** falls back to the geocoder. Delete the bad cache entry (one line, `.cache/` is gitignored). |
| G3 | **Synastry has no S1–S2-only entry.** `synastry_run.main()` is interactive, requires API keys and always runs S3 (`synastry_run.py:91-372`, :118-123). | Call the pure pieces directly: `compute_chart` ×2 → `ground_relationship(records, chart_a, chart_b)` (`principles_grounding/ground_relationship.py:804`) → `s3_routing.route(payload, profile, houses_valid=…)` (`synastry_reading/s3_routing.py:447`, deterministic). No change to `synastry_run.py`. |
| G4 | **Predictive readings can't be looked up by chart.** They exist only in per-run folders `prediction_run/<run_id>/reading_<h>_<profile>_<target>_<birthdate>.json`; there is no index (`run_predictive.py:352-354`, :582). | v1: a read-only locator that scans `prediction_run/*/run_manifest_*.json` for (`natal_ref`, tz, target, profile). It returns `absent: not_generated` otherwise, which will be the usual case (D4: the chat never generates readings). |
| G5 | **Calendar caches have no public loader.** The keys are computed inside `run_calendar.run_calendar` (`run_calendar.py:178-222`). | Extract the stage logic into `run_calendar.ensure_calendar(natal, tz, start) -> {events, scores, periods, best}` with no behaviour change, so PA and the CLI share one cache path. |
| G6 | **`llm_client` can't do strict Structured Outputs or a per-request key.** The JSON schema is hard-coded `strict: False` (`llm_client.py:444-447`), and the OpenAI client is built from the one platform key (:418-428). | Smallest addition: `complete(..., strict: bool = False, route: dict \| None = None)`. `strict` sets the format flag; `route["openai_api_key"]` selects a per-key cached client. Nothing else changes; existing callers are unaffected. |
| G7 | **No `openapi.yaml`, no `local-api/`, no `budget.py`, no `*_bridge.py`** anywhere on the drive. `FE/scripts/build-contract.ts` would generate `openapi.yaml` from the FE_02/FE_09 `ts` blocks, but it hasn't been run. | T10/E11 validate against JSON Schemas I generate from the FE_09 §4.3 `AskCard` and FE_02 types (`astrologist/fixtures/askcard.schema.json`), and switch to `openapi.yaml` once the FE repo produces it. The bridge follows PA_04 §6 as written; the spending ledger is reported in the audit only (no `budget.py` to call). |

## 1. Natal grounding per chart

- **Producer:** `principles_grounding/ground.py:457`
  `ground(records, chart, reading="natal", strict_invariants=False, house_policy="placidus") -> GroundingResult`
  (`kept`, `bundles`, `drops`, …; :107-115).
- **Caller:** `run.py:371-382` writes `result.kept_payload()` as
  `runs/<run_id>/personal_principles_<birthdate>.json`, with corpus `principles_grounding/all_principles.grounded.json`
  (run.py:53).
- **Payload** (`kept_payload`, ground.py:130-140): `reading, house_policy, kept_count, principles, bundled_by_factor`.
  - Bundles are plain lists of the unchanged corpus records.
  - Keys come from `_bundle_key` (:422-450): `"Sun in Capricorn"`, `"Sun in placidus house 9"`, `"Saturn in bound"`,
    `"placidus house 4 domain"`, `"lord of placidus house 1 in house 12"`, `"general"`, …
  - Each record is in exactly one bundle.
- **Record fields:** `principle_id, domain, topic_tags, rule, conditions, judgment, attribution_in_text, notes,
  tradition, about, requires` (+ `reclassified_from`, `reclassify_rule`). **Natal records carry no polarity and no
  sensitivity** (only ACG and relationship records do), so the dossier's `polarity`/`sensitivity` are `null` for natal.
- **No model call:** ground.py's import graph is `argparse, json, os, dataclasses, typing, grounding_schema,
  grounding_vocab` (:36-43); none of them reaches `llm_client`.
- **Measured** (`compute_chart` + `ground`, warm):

| Chart | Kept | Bundles | Modern / classical | By factor type | Ground time | Full kept set rendered as L4 does |
|---|---|---|---|---|---|---|
| 1979-03-30 Sofia | 169 | 57 | 139 / 30 | planet_in_house 57, general 51, house_domain 36, dignity 14, planet_in_sign 8, node 2, house_lord_relative 1 | < 0.01 s | **32.3k tokens** |
| 1988-12-28 | 166 | 55 | 140 / 26 | 57 / 51 / 36 / 13 / 7 / 1 / 1 | < 0.01 s | 31.5k |
| 1984-06-12 | 169 | 57 | 140 / 29 | 58 / 51 / 36 / 14 / 7 / 2 / 1 | < 0.01 s | 31.9k |

  Token counts use `tiktoken o200k_base` over the unique routed records' `as_prompt_dict()` JSON.
- **O3: the default holds.** About 32k tokens is above the ~25k threshold, so **retrieval** (PA_01 §2.3).

## 2. L4 routing

- **The 17 keys, in order:** `Interpretation_layer/l4_sections.py:51-58`, `SECTION_ORDER`. They equal FE_02
  `NatalSection.key` (`core_identity, sun_house, moon_house, inner_drives, chart_shape, identity, values_money,
  communication_learning, family_home, joy_creativity_children, health_routine_pets, partnerships,
  transformation_intimacy, travel_philosophy, status_vocation, friendships_future, subconscious_solitude`).
- **Router:** `l4_routing.py:488` `route(kept, chart) -> RoutingResult` (`.sections: {key: [RoutedPrinciple]}`).
  - **It routes per record, not per bundle** (l4_interpret.py:17-18: `bundled_by_factor` "is NOT routed off").
  - A record can land in several sections (occupancy and rulership, :454-463).
  - Therefore `by_topic` (PA_01 §2.2) = for each section, the bundles of the records routed there, in routing order.
    That is deterministic.
- **Renderer:** `RoutedPrinciple.as_prompt_dict()` (`l4_sections.py:218-235`), serialised by `_principles_block`
  (`l4_prompts.py:236-241`). It emits `principle_id, tradition, rule, topic_tags, about (+ texture, salience)`. **`rule`
  is the only prose field** (judgment, conditions and notes are not rendered).
- **Quota:** none in code (G1).
- **Version constant:** none for routing. The closest is `SCHEMA_VERSION = "l4.v1"` (`l4_validate.py:21`). Proposal:
  `routing_version` = sha256 of `l4_routing.py` + `l4_sections.py` (the same pattern ACG uses for its cache key).

## 3. `l4_output.json`

Written by `_assemble` (`l4_interpret.py:89-118`) as `runs/<run_id>/l4_output_<birthdate>.json`.
- `sections[].key`, `text_tr`, `text_en`, `principle_ids`: **confirmed**.
- Additional fields: `movement` (1|2), and `house` on the house sections and on sun_house / moon_house.
- `principle_ids` is the set routed to the section, not a per-sentence citation.
- Top level: `schema_version: "l4.v1"`, `precision_tier`.
- **There is no cache by chart**, only run folders (same issue as G4). The dossier's `prose` therefore needs the same
  locator: scan `runs/*/run_meta_*.json` for the chart (`input` + `resolved_timezone`). Absent → `{}`.

## 4. Calendar

| Need | Where |
|---|---|
| Per-chart caches | `cal_run/_cache/<chart_key>/<tz_slug>/`: `personal_events_<k>.json`, `scores_<k>.json` (day scores + periods), `best_days_<k>.json`; keys are built in `run_calendar.py:178-222` (G5) |
| Collective | `cal_run/_collective/<year>.json`; `collective_events.ensure_year(year)` / `load_range(jd0, jd1)` (`Calendar/collective_events.py`) |
| Texts | `calendar_reading/cr_generate.TextStore(collective_path, personal_path)` + `cache_key(unit, corpus_sha, chart_key)`; `texts_for(units, store, …, lang)` |
| **CAL_03 unit record sets, without generating** | `calendar_reading/cr_sections.plan_units(events_doc, periods_doc, collective_refs, collective_by_id, index, modern, tags)` returns units with `pool` (the allowed records), `label_tr/en`, `span`, `text`, `gap`. Also `day_note_unit(...)` and `best_day_units(...)`. **Pure; no model.** |
| Labels | `cr_sections.event_label / transit_label / lunation_label / collective_label / period_label / station_label` |
| Goal tags on transit records | `principles_grounding/transit_goal_tags.json` (`{principle_id: {goal: polarity}}`) + `cal_transit_affinity.json`; corpus index `Calendar/cal_corpus.load()` |
| Best Days factor grounding | `principles_grounding/best_days_factors.json` (P1–P4 enabled with `grounding` id lists; C1–C8 disabled); `Calendar/best_days.part_records(part, index)` gives the records behind a day's reason |
| chart_key | `Calendar/personal_events.chart_key(natal)`: sha256 of utc, precision, points and cusps, first 16 hex chars |

All modern-only by construction (`cal_corpus` filters `tradition == "modern"`).

## 5. Predictive

- Lookup by (chart, tz, date, lens): **not possible today** (G4).
- `ground_forecast(forecast, chart, records, *, cap=6, …)` (`principles_grounding/ground_forecast.py:231`) sets
  `event["matched_principles"] = [{principle_id, judgment, topic_tags, tradition: "modern", source_stage, similarity}]`
  on each forecast event (`event_id, family, bodies{transiting, natal}, aspect, phase, …`).
- For PA's `day`/`span` the **calendar** is the primary source anyway (PA_01 §4.4–4.5); predictive prose is optional.

## 6. ACG

| Need | Entry point |
|---|---|
| Place text search | `acg_locate.gazetteer_lookup(query, gazetteer)` (exact only) and `resolve_place(city, lat, lon, gazetteer=, geocoder=)` (:115-139, gazetteer → Nominatim). The gazetteer has `gn-745044 Istanbul / İstanbul`; "Instanbul" misses it only because matching is exact (G2). |
| Per-chart products | `run_acg.build_chart_products(natal, cache_root, stages=, with_goal_scan=True)` (`run_acg.py:119-192`), cached in `acg_run/_cache/<key>/` (key: `chart_cache_key`, :105-116) |
| Locate (no reading) | `acg_locate.build_locate(acg, natal_chart, place, natal_latlon=, parans=)` (:253-283) → `(locate, relocated)` |
| Goal scores + contributors | `acg_goals.score_point(acg, lat, lon, aff, parans)` (`acg_goals.py:281-326`) → `{goal: {S, P, N, band, contributions, contributors}}` |
| Grounding | `ground_acg.ground_acg(natal, relocated, locate, acg_corpus, main_corpus, acg=, affinity=, parans=)` (`principles_grounding/ground_acg.py:299`) → payload with `bundles, goal_contributors, goal_records, sensitivity_high_ids, …` |
| Recommender, zero model | `acg_destinations.resolve_filters(...)` → `acg_recommend.set_parans(...)` → `acg_line_first.rank_line_first(goal, scope, acg, scan, aff, filters)` (`acg_line_first.py:168-207`) → `by_line, cities, regions, countries, thin_result, turkey{…}`; honesty fields from `acg_recommend._honesty_from` (band, dominant_line, has_tradeoff) |
| Tier wording | `acg_reading/ar_sections.py:58-63` `TIER_WORDING` (TR/EN); band labels `acg_constants.BANDS` (:132-138) |

**Runtimes** (`run_acg.py --city İzmir --dry-run`, which runs every stage up to ground_acg, writes the prompts and
makes zero model calls):
- cold, new chart: **8 s**
- warm: **~1 s**

The PA place tool will call the functions directly, not the CLI.

## 7. Synastry

- **S1:** `compute_chart` per person (no separate synastry compute; cross aspects and overlays are computed inside
  grounding).
- **S2:** `ground_relationship(records, chart_a, chart_b) -> RelResult`; `.payload()` gives
  `{reading, counts, person_a, person_b, synastry, framing}`. The corpus is
  `principles_grounding/combined_relationship_principles_tagged.json`; callers check context tags themselves
  (`synastry_run.py:242-250`).
- **The lens is applied in S3 routing, which is pure:** `s3_routing.route(payload, profile, houses_valid=)`.
  1. It filters by context (`s3_profiles._ADMITS`: personal = universal + personal; professional = universal +
     professional; general = all).
  2. It weights by emphasis.
  3. It caps each section at 8 records.

  **The context filter conflicts with PA_01 §4.10**: "Universal records stay in; … reframed, not filtered" (§13 X6).
- **Family relation:** not in code (only love/work/general). The spec's family → general mapping is new.
- **Runtime:** grounding is pure Python over about 1.2 MB of records; well under a second warm (to be measured in Phase 2).

## 8. `llm_client`

- **Routing:** `split_model`: `gpt-*` → OpenAI **Responses API** (`_openai_complete`, :433-483).
- **`reasoning_effort`:** supported through `complete(..., thinking=…)` → `reasoning: {effort}`; `"none"` passes
  straight through.
- **Structured Outputs:** `text.format = {type: json_schema, schema, strict: False}`, hard-coded (G6).
- **Usage:** `input_tokens` (excluding cached), `output_tokens`, `cache_read_input_tokens` = cached. ✓
- **Key:** `OPENAI_API_KEY` or `~/.openai_key` only; there is no per-user key (G6).
- **Retries:** none inside (`max_retries=0`); callers loop with `transient_errors(model)`. `ProviderQuotaError` covers
  "no credits".
- **Faking it in tests:** monkeypatch the openai module (`test_llm_client.py:193-230`). For PA, the engine takes an
  injectable `complete` callable, and tests pass a scripted fake (PA_02 PL6).

## 9. Validator framework

| List / function | Location |
|---|---|
| AV1, AV2, AV8, AV10, encoding, `text_problems(text, lang)`, `tr_fold` | `acg_reading/ar_validate.py:47-132` |
| RV4 (certainty) | `acg_reading/acg_views.py:41-42` (`RV4_TR`, `RV4_EN`) |
| CV2 (numbers, months, house ordinals, jargon) + CV3 (body/medical, TR planet names, register) | `calendar_reading/cr_validate.py` |
| Mask tokens | `Interpretation_layer/l4_prompts.py:28-32` `FORBIDDEN_READER_TOKENS`; `prediction_reading/pr_prompts.py:34-70` `TIER_A_HARD`, `MODERN_HARD`, `TECH_HARD` |
| Detox rewrite | `ar_generate.detox_unit` + `ar_prompts.build_detox_prompt`; `cr_generate.CalendarGenerator.detox` + `cr_prompts.build_detox_prompt`; `l4_generate._detox_text` |

**PA doesn't need a detox model call:** PA_03 §6 replaces detox with one repair call, and PA uses the lists only.
FE_02 AC3 (`FE/FE_02_API_CONTRACT_SPEC.md:965`) and FE_00 F7 (`FE/FE_00_INDEX.md:57`) are not in backend code yet.
`pa_validate` merges them with the lists above (PV8).

## 10. Catalogue

**There is no single TR/EN catalogue module.** FE_02 §8.1 (`/meta/catalogue`) expects one "derived from the backend's
catalogues". Today the labels live in:

| Labels | Source |
|---|---|
| bodies, signs, aspects, natal points (with TR suffix forms), eclipse kinds, transit / lunation / station / period labels | `calendar_reading/cr_sections.py` |
| life areas (12 houses) | `calendar_reading/notification_templates.json` `slot_forms.area` (= PROJECT_OVERVIEW §3) |
| goals | `Astrocartography/acg_constants.GOALS` |
| activities | `Calendar/best_days.ACTIVITIES` |
| ACG bands, tiers | `acg_constants.BANDS`, `TIER_LABELS`; `ar_sections.TIER_WORDING` |
| grades, day bands, tones, transit phases | **TR/EN labels missing** (enums only) |

**Proposal:** `astrologist/pa_catalogue.py` imports from these sources and adds the four missing label tables (grades,
day bands, tones, phases: FE_02 §6.3 building/peak/easing) in one place. `pa_lexicon` is built from it. The missing TR
strings go to native review with the templates.

## 11. API integration

**Nothing to read:** there is no `local-api/`, `budget.py`, `*_bridge.py` or `openapi.yaml` (G7). The contract
facts PA must match come from FE_09 / FE_02:
- **Events:** `status`, `delta`, `card`, `link`, `done`, `error`.
- **`AskSourceKind`:** `chart, natal_reading, forecast, calendar, best_days, acg, compatibility`.
- **Cards:** the 7 `AskCard` shapes match PA_01 §6 field for field.
- **`done`** carries `{message_id, quota}`, built by the API.
- **`AskSourceKind` and the SSE payloads are prose in FE_09**, not `ts` blocks, so `openapi.yaml` won't contain them
  either.

## 12. Run folders, manifests, caches

- **Run folders:** `run.mint_run_id(now_utc, birth_date)` and `run.suffixed(filename, suffix)` (`run.py:65-78`,
  :188-194); `run._write_json`.
- **No shared per-chart cache root.** Each layer keeps its own:
  - ACG: `acg_run/_cache/<sha24 of jd_ut + …>`
  - calendar: `cal_run/_cache/<chart_key16>/<tz>`
  - predictive, natal and synastry: none

  **Proposal:** use `ask_run/_cache/<chart_key>/` (gitignored with `ask_run/`), with `chart_key` =
  `Calendar/personal_events.chart_key` (already used by the calendar, and matching FE_02 `BirthProfile.chart_key` in
  spirit). FE_02 doesn't define how `chart_key` is computed (§13 X9).

## 13. Contradictions between the specs and the code (flagged, not adapted)

| # | Spec says | Reality | Proposal |
|---|---|---|---|
| X1 | PA_00 O2: "Readings and calendar texts use **siz**"; answers in siz | **Both use "sen".** The natal L4 TR text: "Hayata yaklaşımında…, enerjini…" (41 informal vs 1 formal ending in `runs/…_1988-12-28/l4_output`). The calendar validator **rejects** siz (`cr_validate` CV3). FE_01:220-221 sets the app register to **"sen"**, and so does the FE_09 disclaimer. Only the calendar *labels* use plural possessives ("Güneş'inize"). | **Use "sen"** for answers, templates and source labels (rewrite the PA_03 §7 and PA_04 §3 TR strings), matching FE_01 and the existing texts. Optionally align the calendar labels too. **Needs Radul's OK.** |
| X2 | PA_01 §2.2: `render` from "the L4 prompt renderer"; PA_01 §3.1: internal fields never enter the pack | `as_prompt_dict()` includes `principle_id, tradition, about, topic_tags` (all internal) | `render` = the record's `rule` text, the only prose L4 renders. |
| X3 | PA_00 D5 / PA_01 §2.3: "the L4 2:1 quota" | not implemented (G1) | Implement in PA as specified. |
| X4 | PA_01 T3: exclude `predictive_scope: time_lord` | no record has `predictive_scope`; the 23 `out_of_scope` records are all `unclassified` and dropped by grounding | Exclude `out_of_scope == true` explicitly; time-lord records are classical, so modern-only already removes them. |
| X5 | PA_01 §2.2: facts omit `sect` | chart.json has `is_diurnal`, no `sect` | Mask `is_diurnal` (FE_02 §6.4 names both). |
| X6 | PA_01 §4.10: synastry universal records "reframed, not filtered" | `s3_routing` **filters** by context per lens | Reuse S3's filter (it is the layer's own rule, D5 "S2's kept records under the lens"). Or Radul confirms the PA wording wins. |
| X7 | PA_01 §6 link routes `/chart?section=`, `/ahead?view=today&…`, `/ahead?view=calendar&item=`, `/ahead?view=best_days&activity=`, `/profiles/new`, `/match/new?b=&type=` | The FE routes are `chart/section/[key]` (FE_05:131), `/(tabs)/ahead?view=day&date=` (FX2.2), `calendar/item/[id]`, `best-days/[activity]?date=` (FE_08:122-124), `profile/charts/new` (FE_01:109). The `match/new` params are undefined. Only `/map?place=` matches. | Use the FE route forms (they win per FX4.6, whose mapper sends unknown routes to the tab). Keep the table in `pa_cards.py` as data. |
| X8 | PA_01 §4.8: the place card carries "the six suitability goals" | AskCard `place.cards[]` is `{goal, band, band_label}` only; suitability `card` ids (travel/living/…) don't fit | Emit the ACG_07 §6.2 goals as `Goal` values: `living` → `relocation`, `focus` → the asked goal. |
| X9 | FE_02 `BirthProfile.chart_key` | the calendar and ACG compute different keys | One canonical `chart_key` for the API. Proposal: the calendar's. API team to confirm. |
| X10 | PA_04 §3 `final.message` with `answer_kind`, `lang` | FE `Message` has neither; `done` = `{message_id, quota}` | Keep them on the internal `final`; the API stores them additively or drops them. No FE change. |
| X11 | PA_01 §4.4: past days → `out_of_range: past_not_cached` | FE_02 allows today − 7 … today + 365 | The calendar cache starts at its `from` date. Proposal: PA builds the calendar from today − 7 so past days are always cached (6 s cold, once per chart and day). |
| X12 | PA_01 T10 / PA_04 E11: validate against `openapi.yaml` | it doesn't exist; `AskSourceKind` and the SSE payloads won't be in it either | G7: local JSON Schemas generated from the FE ts blocks; switch over when the FE repo ships `openapi.yaml`. |
| X13 | PA_04 §8: report spend to the platform ledger (`budget.py`) | doesn't exist | Usage and cost go in the audit; the ledger hook is a no-op interface until the API exists. |
| X14 | Calendar phase words | the calendar's internal phases are approaching / exact_window / separating; FE_02 §6.3 is building / peak / easing (d < min exact → building; d > max → easing) | PA uses the FE_02 rule and labels. |

## 14. Wiring table (PA_04 §10)

| Need | Existing call | Real signature |
|---|---|---|
| chart | `d_layer/compute_chart.py` | `compute_chart(bd: BirthData, *, utc_override=None) -> Chart`; `BirthData(year, month, day, latitude, longitude, time_precision="exact", hour=12, minute=0, approx_bucket=None, reading_date_utc=None)` |
| natal grounding per chart | `principles_grounding/ground.py` | `ground(records, chart, reading="natal", strict_invariants=False, house_policy="placidus") -> GroundingResult` (`.kept`, `.bundles`, `.kept_payload()`) |
| L4 routing + renderer + 2:1 quota | `Interpretation_layer/l4_routing.py`, `l4_sections.py` | `route(kept, chart) -> RoutingResult(.sections)`; `RoutedPrinciple.as_prompt_dict()` (render = `rule`, X2); quota: **new in PA** (G1) |
| natal reading lookup | `runs/<run_id>/l4_output_<birthdate>.json` | **new** locator over `run_meta_*.json` (§3) |
| calendar caches + views | `run_calendar.py` | **extract** `ensure_calendar(natal, tz, start) -> {events, scores, periods, best}` (G5); views `month_view(...)`, `day_view(...)` |
| CAL_03 unit record sets | `calendar_reading/cr_sections.py` | `plan_units(events_doc, periods_doc, collective_refs, collective_by_id, index, modern, tags) -> {unit_id: unit}`; `day_note_unit(day, events_doc, units, index, modern)`; `best_day_units(bd_doc, index, modern)` |
| Best Days + factor grounding | `Calendar/best_days.py` | `build_best_days(natal, tz, from_local, n_days=90, activities=None, cat=None, collective_dir=…)`; `load_catalogue()`; `part_records(part, index)` |
| predictive reading lookup | `prediction_run/` | **new** locator over `run_manifest_*.json` by `natal_ref` (G4) |
| ACG gazetteer search | `Astrocartography/acg_locate.py` | `gazetteer_lookup(query, gazetteer)` (exact) → **new** fuzzy search in `pa_tools` (G2) |
| ACG locate + goal scores + ground_acg | `run_acg.py`, `acg_locate.py`, `acg_goals.py`, `ground_acg.py` | `build_chart_products(natal, cache_root=CACHE_DIR, *, stages, with_goal_scan=True)`; `build_locate(acg, natal_chart, place, *, natal_latlon=None, chart_filename=…, parans=None)`; `score_point(acg, lat, lon, aff, parans=None)`; `ground_acg(natal, relocated, locate, acg_corpus, main_corpus, *, acg=None, affinity=None, parans=None)` |
| ACG recommender ranking | `acg_line_first.py`, `acg_destinations.py`, `acg_recommend.py` | `resolve_filters(goal, *, regions, city_size, max_distance_km, home_latlon, climate, purpose)`; `set_parans(parans)`; `rank_line_first(goal, scope, acg, scan, aff, filters, *, include_unreviewed=False)` |
| synastry S1–S2 | `ground_relationship.py`, `s3_routing.py` | `ground_relationship(records, chart_a, chart_b) -> RelResult(.payload())`; `route(payload, profile, *, houses_valid)` (G3) |
| model calls | `llm_client.py` | `complete(model, system, user, *, max_tokens, temperature=None, schema=None, timeout_s=120.0, label="", thinking=None) -> LLMResponse`; **add** `strict`, `route` (G6); `transient_errors(model)` |
| forbidden lists, detox, mask list | `ar_validate.py`, `acg_views.py`, `cr_validate.py`, `l4_prompts.py`, `pr_prompts.py` | `text_problems(text, lang)`, `tr_fold(text)`, `cv2_problems`, `cv3_problems`, `AV2_*`, `AV8_*`, `RV4_*`, `FORBIDDEN_READER_TOKENS`, `TIER_A_HARD`, `MODERN_HARD`, `TECH_HARD` |
| labels | (§10) | **new** `pa_catalogue.py` aggregating the existing sources + 4 missing tables |
| run folder + manifest | `run.py` | `mint_run_id(now_utc, birth_date)`, `suffixed(filename, suffix)`, `_write_json(path, obj)` |
| spending ledger | (none) | audit only; no-op hook (X13) |
| bridge conventions | (none) | PA_04 §6 as written |

## 15. Decisions (Radul, 2026-10-05: "yes, go")

Radul approved all six recommendations below:
1. Register "sen".
2. S3 context filter reused.
3. FE route forms.
4. The `llm_client` `strict` / `route` additions.
5. `ensure_calendar` extraction.
6. Delete the "instanbul" geocode entry.

The other proposals are adopted as written. Original list follows.

## 15a. Decisions needed before Phase 1 (as asked)

1. **X1 register:** "sen" (recommended, matches the app and every existing text) instead of the spec's "siz".
2. **X6 synastry lens:** reuse S3's context filter (recommended) or keep universal records in.
3. **X7 link routes:** use the FE route forms (recommended).
4. **G6 `llm_client` additions** (`strict`, `route`): a small change to a shared module.
5. **G5 extraction** of `ensure_calendar` from `run_calendar.py`: no behaviour change.
6. **G2:** delete the cached "instanbul" → Antwerp geocode entry.

The other proposals (G1, G3, G4, G7, X2–X5, X8–X14) follow the spec's intent and need no decision unless you disagree.
