# ACG Phase 0: exploration report

*2026-09-25. Answers `ACG_00_INDEX.md` §6 items 1–13 against the working tree at `f9879f2`
plus the uncommitted changes. Line numbers refer to the current working tree.*

**Environment note.** This machine's Python 3.11 had none of the project's runtime deps.
Installed: `pyswisseph 2.10.3 (20230604)`, `timezonefinder`, `geopy`, `tzdata`, `jsonschema`,
`google-genai`, `openai`. The existing suite then passes: **115 tests** (not the 107
`PROJECT_OVERVIEW` §6 states; the count has grown).

---

## 1. `compute_chart` signature, and how time is resolved

`d_layer/compute_chart.py:699`: `def compute_chart(bd: BirthData) -> Chart`. `BirthData`
(`:168`) carries local civil time plus lat/lon. The timezone is always resolved from the
birth coordinates, then local time is converted to UTC:

```python
# compute_chart.py:707
tzname = resolve_timezone(bd.latitude, bd.longitude)
...
# :721-724
if bd.time_precision == "exact":
    dt_utc = local_to_utc(bd.year, bd.month, bd.day, bd.hour, bd.minute, tzname)
    meta["utc"] = dt_utc.isoformat()
    pieces = _compute_at(dt_utc, bd.latitude, bd.longitude, has_time=True)
```

`_compute_at(dt_utc, lat, lon, has_time)` (`:584`) already takes a fixed UTC instant, and
`julian_day_ut(dt_utc)` (`:251`) derives `jd`.

**It can't be called with a fixed UTC instant today.** Passing new lat/lon re-resolves the
timezone and reinterprets the local wall-clock time.

**Proposed minimal change (implemented in Phase 2):** add the keyword
`compute_chart(bd, *, utc_override: datetime | None = None)`. When it is set (and the
precision is `exact`), `dt_utc = utc_override` and `local_to_utc` is skipped. The rest is
unchanged: `meta.timezone` is still resolved from the new coordinates (it is metadata
only), and `meta.utc` is the override. The default path stays byte-identical.

## 2. Precision tier enum

`d_layer/chart_types.py:45`: `Precision = Literal["exact", "approximate", "unknown"]`.
It is emitted in `meta.time_precision` and `confidence`. **The exact tier is `"exact"`.**
`run.py` hard-codes `"exact"` (`run.py:348`). `run_predictive.py` accepts all three.

## 3. Ephemeris flags and node

```python
# compute_chart.py:55-56
EPHE_FLAG = swe.FLG_MOSEPH | swe.FLG_SPEED
EPHEMERIS_NAME = "moshier"
# :84
("North Node", swe.MEAN_NODE, True),  # South Node is derived (+180)
```

This is **Moshier, not SWIEPH**, and no ephemeris path is set. The node is the **mean**
node (`meta.node_type: "mean"`). ⚠ This contradicts spec 01 §7.1 (`"flags": ["SWIEPH", ...]`);
see §13, C1.

## 4. Geocoding

There are two geocoders, both Nominatim via geopy:

- `run.py:137` `geocode(place_query) -> dict`: **interactive** (asks the user to confirm and
  re-prompts on failure). Uncached.
- `run_predictive.py:128` `geocode(location: str) -> dict`: **non-interactive**. It is cached
  by lowercased string in `.cache/geocode.json` (`:68`, gitignored), returns
  `{latitude, longitude, display_name}` rounded to 4 dp, and on failure raises
  `StageError("resolve", ...)`.

ACG reuses **`run_predictive.geocode`** (the non-interactive one) and maps `StageError` to
the absence `place_not_found`. It doesn't add a second geocoder.

## 5. `chart.json` excerpts (1985-03-14 11:30 local, Istanbul)

```json
"meta": {"time_precision": "exact", "zodiac": "tropical", "ephemeris": "moshier",
         "pyswisseph_version": 20230604, "house_systems": ["placidus", "whole_sign"],
         "node_type": "mean", "timezone": "Europe/Istanbul", "utc": "1985-03-14T09:30:00+00:00"}
```
```json
{"name": "Venus", "traditional": true, "longitude": 22.288, "sign": "Aries", "sign_index": 0,
 "degree_in_sign": 22.288, "speed": -0.0256717654, "retrograde": true,
 "sector": {"placidus": 11, "whole_sign": 10},
 "classifications": {"sign_ruler": "Mars", "in_domicile": false, "in_detriment": true,
   "in_exaltation": false, "in_fall": false, "triplicity_ruler": "Sun",
   "triplicity_rulers_all": {"day": "Sun", "night": "Jupiter", "participating": "Saturn"},
   "in_triplicity": false, "bound_ruler": "Mars", "in_own_bound": false,
   "face_ruler": "Venus", "in_own_face": true}}
```
```json
"axes": {"ascendant": {"longitude": 95.0198, "sign": "Cancer", "sign_index": 3, "degree_in_sign": 5.0198},
         "mc": {"longitude": 342.0244, "sign": "Pisces", "sign_index": 11, "degree_in_sign": 12.0244}}
```

**`jd_ut` is not stored.** Only `meta.utc` (ISO, second precision) is. ACG recomputes
`jd_ut = julian_day_ut(datetime.fromisoformat(meta.utc))` with **L1's own function**, which is
bit-identical to what L1 used. L1 has no absence-contract block. Its degradation style is
structural omission (`NotRequired`) and null (`X | None`), so ACG's `status`/`absence`
shape follows the predictive `absent` convention in the ACG specs themselves. The meta
schema is `additionalProperties: false` (`chart_schema.json` Meta def), so
**`relocated_from` can't go into the relocated chart's meta**. It is recorded in
`locate.json.relocation` (the fallback spec 02 §5 allows).

## 6. `ground.py`

- Public entry: `principles_grounding/ground.py:457`
  `ground(records, chart, reading="natal", strict_invariants=False, house_policy="placidus") -> GroundingResult`.
- Gates: `_gate_a(record, allowed)` (`:153`, domain), `_gate_b(record, chart, pts, strict_invariants, house_policy)`
  (`:214`, subject reconciliation, returning `(ok, reason, fact)`), and `_gate_c(record, chart, pts)` (`:410`,
  dependencies). Helper: `_point_index(chart)`.
- Drop report: `DropLog(principle_id, gate, reason, about, relevant_chart_fact)` (`:90`);
  `GroundingResult.report()` (`:117`) →
  `{reading, house_policy, kept, dropped, drops_by_gate, bundles, drop_log: [DropLog.as_dict()]}`.

Three planets-in-houses delta records. Note that the record id key is **`principle_id`**, and
`about` uses **`factor_type`**, not `type`:

```json
{"principle_id": "venus-1st-congenial-persona-presentation", "domain": "natal",
 "topic_tags": ["Venus", "1st house", "identity", "charm", "social-interaction", "approval-seeking"],
 "rule": "Venus in the 1st house integrates relational harmony and affability directly into the native's immediate self-expression. ...",
 "conditions": {"planet": "Venus", "house": 1},
 "judgment": "The native approaches the external world through an agreeable and aesthetically pleasing persona ...",
 "attribution_in_text": null, "notes": "An overemphasis on cultivating an agreeable exterior ...", "tradition": "modern",
 "about": {"factor_type": "planet_in_house", "point": "Venus", "house": 1, "house_system": "placidus",
           "extraction_confidence": "high", "extraction_source": "deterministic"},
 "requires": [{"kind": "point_house", "point": "Venus"}]}
```
The house-7 and house-10 records from the same delta have the identical shape, for example
`venus-7th-...` / `saturn-10th-...` with `conditions {"planet": P, "house": 7|10}`,
`about.factor_type planet_in_house`, `house_system placidus`, and
`requires [{"kind": "point_house", "point": P}]`.

⚠ **The `planet_in_house` pool is not only natal.** The same factor type is carried by
785 predictive (transit) records, e.g. `saturn-10th-house-transit` (`domain: predictive`),
and by traditional whole-sign records such as `venus-7th-marriage-success`. The A4 fallback
and stream B must filter to **`domain == "natal"` and `tradition == "modern"`**, or they
would read transit text as natal/relocation meaning.

## 7. How `requires` is evaluated

`ground.py:379` `_requirement_satisfiable(req, chart, pts) -> (ok, reason)`. Supported
kinds: `native_gender` (always unsatisfiable), `birth_time`, `ascendant`, `house_ruler`,
`point_sign`, `point_aspects`, `point_house`, `point_dignity`, `sign_element`, and `other`
(anything unknown passes).

⚠ **These are existence dependencies, not value conditions.** `{"kind": "point_sign",
"point": "Venus"}` means "this principle needs Venus's sign to be known". It never says
*which* sign, and the gate never compares values. So spec 03 GA3 ("`requires` Venus in
Libra on a chart with Venus in Taurus → dropped") can't be expressed with the existing
kinds. See §13, C6 for the resolution.

## 8. Reading-layer structure

**`prediction_reading/` is not the natal-style pipeline that spec 04 describes.** It has one
generator (`pr_generate.LLMGenerator`), per-horizon beats plus a synthesis call
(`read_forecast.run_reading`), and a validator `pr_validate.validate(reading, ctx) -> list[str]`
with `is_build_blocking`. It has **no per-section translation or detox**: English is produced
by the orchestrator (`run_predictive.translate_reading`, `:289`). The forbidden lists are in
`pr_prompts.py:34-75` (`TIER_A_HARD`, `MODERN_HARD`, `TECH_HARD`, plus contexts).

The pipeline spec 04 §1 describes (draft → per-section TR synthesis → per-section EN
translation → detox → validate) is the **natal L4** machinery in `Interpretation_layer/l4_generate.py`:

| Need | Function |
|---|---|
| model call with retry, truncation growth, and JSON repair | `LLMGenerator._call_json(model, system, user, *, temperature, max_tokens, label, schema)` (`:222`) |
| cheap model with fallback to the synthesis model | `LLMGenerator._call_cheap(system, user, *, max_tokens, label, schema)` (`:311`) |
| the translation pattern | `LLMGenerator.translate(key, text_tr)` (`:333`), prompt `l4_prompts.build_translation_prompt` (`:428`) |
| the detox pattern | `LLMGenerator._detox_text` (`:392`), prompt `l4_prompts.build_detox_prompt` (`:467`) |
| the forbidden-word list | `l4_prompts.FORBIDDEN_READER_TOKENS` (`:28`), shared by `l4_validate._FORBIDDEN_RE` |
| provider routing | `llm_client.complete(model, system, user, *, max_tokens, temperature, schema, timeout_s, label, thinking)` (`llm_client.py:500`) |

**Trace format:** L4 does **not** let the model write traces. The model returns prose
only, and the per-section `principle_id` trace is attached **deterministically from
routing** (`l4_prompts.py:249-250`). ACG does the same, per paragraph (see §13, C9).

**Plan:** `acg_reading/ar_generate.py` subclasses `l4_generate.LLMGenerator`, reusing
`_call_json` and `_call_cheap` (retry, fallback, usage accounting) and adding ACG prompts.
The ACG forbidden list is `FORBIDDEN_READER_TOKENS` plus the AV1/AV2/AV8 lists.

## 9. Run-folder and manifest helpers

- `run.py:188` `mint_run_id(now_utc, birth_date)` → `YYYYMMDD-HHMMSS_<3>_<birthdate>` (natal).
- `run_predictive.py:233` `_mint_run_id(now_utc)` → `YYYYMMDD-HHMMSS_<3>` (**this matches spec 05**).
- `run.py:65` `suffixed(filename, suffix)`: **every artifact carries the birth date**
  (`chart_1990-07-13.json`), per commit `1c628b2`, in all three orchestrators.
- There is **no shared manifest writer.** `run_predictive.run_predictive` builds the manifest
  dict inline, and `finish(status)` (`:382`) writes `suffixed("run_manifest.json", suffix)` via
  `run._write_json` (`run.py:254`).

## 10. `.gitignore`

```
# --- Personal run outputs (real birth data + readings) ---
runs/
synastry_run/
prediction_run/
```
Also: `**/chart.json`, `**/validation_report.json`, `.cache/`, `TXT/`. **`acg_run/` is not
there yet.** It is added with `run_acg.py` (spec 05 §3).

## 11. Corpus delta tooling

- **Nine extractor fields** (`CORPUS_DELTA_HOWTO.md`): `principle_id, domain, topic_tags,
  rule, conditions, judgment, attribution_in_text, notes, tradition`.
- **Prompt structure** (`extract_houses.py`): `SYSTEM` holds the rules (atomic principles;
  never reproduce source phrasing; drop anecdotes; third person; 4–7 per unit). `USER_TMPL`
  holds the placement header plus the source unit. The call is `llm_client.complete(...,
  schema=SCHEMA, temperature=0.2)`, and the model returns only
  `principle_id`-slug/`topic_tags`/`rule`/`judgment`/`notes`.
- **Forcing** (`extract_houses.shape_records`, `:227`): the id is prefixed in code
  (`{planet}-{N}th-{slug}`); `conditions = {"planet": P, "house": N}`; tags are prefixed with
  `[P, "Nth house"]`; `domain`/`tradition` are forced; the model never sets them.
- `merge_houses_delta.py` normalises, dedupes and appends to the clean corpus.
  `finish_delta.py` runs `backfill()` plus a delta gate and appends to the grounded corpus.
  **ACG doesn't append to either** (D13), so `finish_acg.py` is a standalone equivalent that
  writes its own file.

## 12. `backfill.py` classification

`backfill.py:897` `ground_record(record, extractor)` takes the result of
`tier1_deterministic(record)` (`:500`) as locked (the id parse → conditions → structural →
dignity → element tiers), otherwise it calls the LLM tier 3. It then runs
`validate_about(about)`, which uses the main `FACTOR_TYPES` vocab, and
`requires = extract_requires(record)`.

**The `acg-*` branch goes at the top of `ground_record`**, before `tier1_deterministic`. It is
a `tier0_acg(record)` that derives `about` from the id pattern (`acg-<planet>-<angle>-NN`,
`acg-general-<planet>-NN`, `acg-angle-<angle>`, `acg-method-<slug>`,
`acg-paran-<p1>-<p2>-NN`, ...) and validates it against its own ACG vocab, not the main
`validate_about`. The ACG factor types must **not** be added to `grounding_vocab.FACTOR_TYPES`:
that would change the main schema. No main-corpus id starts with `acg-` (verified: 0 of
2,770), so the branch is inert for existing records (GA10).

## 13. Spec ↔ code contradictions (flagged, with the resolution I propose)

| # | Spec says | Code says | Resolution |
|---|---|---|---|
| C1 | 01 §7.1 `flags: ["SWIEPH", ...]` | L1 uses `FLG_MOSEPH` (`compute_chart.py:55`) | Mirror L1: `["MOSEPH", "SPEED", "EQUATORIAL"]`, `ephemeris: "moshier"`. The golden check (§9) tolerance of 0.1° is far above the Moshier/SWIEPH difference (≈ arcseconds). |
| C2 | 01 §2 "read `jd_ut` from `chart.json`" | `jd_ut` isn't stored; `meta.utc` is | Recompute via L1's `julian_day_ut(fromisoformat(meta.utc))`. Bit-identical. `missing_utc_instant` if `meta.utc` is absent. |
| C3 | 02 §5 relocation keeps the UTC instant | `compute_chart` always re-resolves the timezone | Add the `utc_override` keyword (§1). |
| C4 | 02 R3 "dignities ... identical" | `triplicity_ruler`/`in_triplicity` depend on **sect**, which depends on the location (Sun above/below the new horizon); the lots and planetary day/hour are also local | R3 compares positions, signs, speeds, retrograde flags, aspects, and the **sect-independent** dignity fields. The triplicity fields, `is_diurnal`, lots and planetary hour may differ. |
| C5 | 02 §5 `relocated_from` in chart metadata | `Meta` is `additionalProperties: false` | Record it in `locate.json.relocation` (spec's own fallback). |
| C6 | 03 §4 gate 3 evaluates `requires` as conditions ("Venus in Libra") | `requires` kinds are existence tokens only (§7) | Existing kinds still go through `ground._requirement_satisfiable` (reused, not forked). ACG records add **value-bearing kinds** built by `finish_acg.py` from structured extractor conditions: `natal_point_sign {point, sign}`, `natal_point_aspect {point, other, aspect?}`, `natal_point_retrograde {point}`, `natal_point_dignity {point, dignity}`, `relocated_point_house {point, house}`, `relocated_point_angular {point}`. They are evaluated by `ground_acg`. Anything else → `requires_unsupported_kind`. |
| C7 | 06 §5 `"id"`, `about.type` | the project uses `principle_id` and `about.factor_type` | Use `principle_id`/`factor_type` in the ACG corpus. The values are as specced (`planet_on_angle`, `acg_angle_frame`, `acg_planet_general`, `acg_method`, `acg_paran`, `acg_mundane`). |
| C8 | 03 A4 "main corpus `planet_in_house` records, modern" | the pool includes 785 predictive transit records | Filter A4 and stream B to `domain == natal` and `tradition == modern`. |
| C9 | 04 §4 rule 2 "each paragraph ends with its trace" (model-written) | L4 attaches traces deterministically; the model writes prose only | The model returns one paragraph per routed slot (JSON keyed by slot); `ar_render` attaches each slot's ids. AV4 checks that every slot has a non-empty trace whose ids all exist in `acg_principles.json`. |
| C10 | 04 "mirrors `prediction_reading/`" | predictive has no per-section translate/detox; natal L4 does | Reuse L4's `LLMGenerator` machinery (§8). |
| C11 | 05 run-folder files named `chart.json`, `manifest.json` | every orchestrator suffixes artifacts with the birth date; the manifest is `run_manifest.json` | Follow the repo convention: `chart_<date>.json`, `acg_<date>.json`, …, `run_manifest_<date>.json`. The folder name follows spec 05 (`_mint_run_id` pattern). |
| C12 | 05 O6 "107 tests" | 115 now pass | Gate: the full existing command passes (115) plus the ACG tests. |
| C13 | 06 C-4 blocks every Appendix-B surname and gazetteer city/country | many surnames are common words ("King", "Young", "Love", "Hope") and some provinces are too (e.g. "Batman", "Van") | Match **case-sensitively, as capitalised whole words**, and never block planet names. Spec 06's `finish_acg` therefore depends on `gazetteer.json` (Phase 2) existing first. |
| C14 | 01 C7 "Sun ≈ −1.0002" | with RA speed ≈ +0.99°/day the 4-min Sun shift is `Δra − 1.002738 ≈ −1.0000` | The test asserts the formula (`Δra − 1.002738·(4/4)`, using the computed Δra), not the example constant. |

## Wiring table for spec 05 §5 (real signatures)

| Stage | Call |
|---|---|
| 1 birth input | interactive: `run.collect_input()`. Flags: `--date --time --location` like `run_predictive._build_request_from_args`. Geocode: `run_predictive.geocode(location)` |
| 2 natal chart | `compute_chart.compute_chart(BirthData(year, month, day, latitude, longitude, time_precision, hour, minute))` |
| 3 lines | `Astrocartography.compute_acg.compute_acg(chart) -> dict` (reads `meta.utc` and `meta.time_precision`) |
| 6 relocation | `compute_chart(bd_same_birth_with_new_latlon, utc_override=datetime.fromisoformat(natal["meta"]["utc"]))` |
| 7 grounding | `ground._point_index`, `ground._gate_b(rec, chart, pts, house_policy="placidus")`, `ground._gate_c`, `ground._requirement_satisfiable`, `ground.DropLog`, via `principles_grounding.ground_acg.ground_acg(natal, relocated, locate, acg_corpus, main_corpus)` |
| 8 reading | `acg_reading.ar_generate.ACGGenerator(LLMGenerator)` (reuses `_call_json`, `_call_cheap`) and `ar_validate.validate(reading_tr, reading_en, plan, grounded) -> list[str]` |
| 9 folder and manifest | `run_predictive._mint_run_id(now_utc)`, `run.suffixed`, `run._write_json`. The manifest is built inline as in `run_predictive` |

---

## Phase 1–2 results (2026-09-25)

**Built:** `acg_constants.py`, `acg_types.py`, `acg_geo.py`, `compute_acg.py`, `acg_schema.json`,
`acg_locate.py`, `build_gazetteer.py`, `gazetteer.json` (124 cities: 81 provinces + 43 diaspora),
`test_acg.py`. `d_layer/compute_chart.py` gained the keyword-only `utc_override` (C3). Its default path
is unchanged (`test_default_compute_chart_unchanged`), and the existing 115 tests still pass.

**Tests:** `python -m pytest -q Astrocartography/test_acg.py` → **31 passed**. That covers C1–C11,
LO1–LO4, R1–R6, G1 and G2, plus the absence propagation, gazetteer lookup and geocoder-failure
cases. The numerical residuals on the fixture are 3e-14° (C1, ARMC vs RA) and 9e-14° (C3, true
altitude on ASC/DSC vertices).

**Decisions made while building (for review):**
- R3 is tested with the sect-dependent dignity fields (`triplicity_ruler`, `in_triplicity`) and
  the house placements excluded. Everything else in `points[]`, and all of `relations[]`, is
  identical (C4).
- The gazetteer is geocoded with `featuretype="city"`: a bare "Van, Türkiye" returns the
  province-boundary centroid, about 30 km from the city. Coordinates are frozen in the committed
  file; the raw build cache is `.cache/gazetteer_build.json` (gitignored).
- `distance_km` is rounded to 0.1 km in `locate.json` and `city_scan.json`; the tier is decided on the
  unrounded value. `nearest_point` is rounded to 4 dp.
- `locate.json` carries `house_diff` at the top level (spec 02 §5.1 "store this in `locate.json`"),
  and `relocation.relocated_from` when the orchestrator passes the natal coordinates. `chart.json`
  carries no birth coordinates, so they come from the run's geocode.
- The city scan takes ~0.8 s per chart and makes no network calls.

**Golden check (spec 01 §9): still open.** It needs one of Radul's real charts compared against
astro.com AstroClick Travel. The internal consistency checks (C1/C3 against Swiss Ephemeris's own
`houses_ex` and `azalt`) pass at ~1e-13°.
