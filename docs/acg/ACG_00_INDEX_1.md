# Astrocartography (ACG) layer: spec index

*Spec set v3, 2026-09-25 (v3 = specs 07–09, applied on top of 00–06). Written against `PROJECT_OVERVIEW.md` (state 2026-09-24).
v2 change: the ACG source text (`TXT/ACG/`, Lewis & Guttman 1989) becomes a corpus delta (spec 06)
and the primary grounding source. It affects D3, D4, D6, D9 and specs 02–05.
Read this file first, then the specs in order.*

## 1. What the layer does

It projects the natal chart onto the globe. For every planet it finds the places
where, at the birth instant, the planet was **rising (ASC)**, **setting (DSC)**,
**culminating (MC)** or **anti-culminating (IC)**, and draws them as lines on a map.
Given a place, it reports which lines pass nearby and builds the **relocated chart**
(same instant, new location → new angles, new Placidus houses). It then produces a
grounded Turkish-first reading of "what this place emphasises for you".

The user sees a map, planet names and plain-language meaning. They never see
coordinates, kilometres, degrees or hour angles (the tradition mask applies).

## 2. Files in this set

| # | File | Scope | Status |
|---|---|---|---|
| 0 | `ACG_00_INDEX.md` | Decisions, layout, phases, exploration report | this file |
| 1 | `ACG_01_COMPUTE_SPEC.md` | `compute_acg`: lines, GeoJSON, precision gating | complete |
| 2 | `ACG_02_LOCATE_RELOCATE_SPEC.md` | City → lines within orb, relocated chart, city scan | complete; relocation call wired after Phase 0 |
| 3 | `ACG_03_GROUNDING_SPEC.md` | `ground_acg`: ACG-corpus line evidence (planet-in-house fallback) + relocated-house evidence | complete; field names confirmed after Phase 0 |
| 4 | `ACG_04_READING_SPEC.md` | Sections, prompts, lengths, validator additions | complete |
| 5 | `ACG_05_ORCHESTRATOR_SPEC.md` | `run_acg.py` stages, flags, run folder, manifest | **partial**: wired to real signatures after Phase 0 |
| 6 | `ACG_06_CORPUS_DELTA_SPEC.md` | Extract, consolidate and guard principles from the ACG source text | complete; `backfill.py` branch confirmed after Phase 0 |
| 7 | `ACG_07_CHANGE_ORDER_V3.md` | **v3 change order** (client requirements §10): gazetteer v2, countries/regions, distances as data, goal tags, new city sections, suitability cards, modes. **Overrides 00–06 where they conflict** | complete |
| 8 | `ACG_08_GOAL_SCORING_SPEC.md` | 11-goal taxonomy, affinity table, place score, bands, aggregates, heat layer | complete; thresholds calibrated at its gate |
| 9 | `ACG_09_WHERE_SHOULD_I_GO_SPEC.md` | Goal → ranked cities, regions, countries (+ Turkey block) with grounded explanations | complete |

## 3. Locked decisions (domain)

| # | Decision | Why |
|---|---|---|
| D1 | **In mundo lines**: use each body's true apparent RA/declination (equator of date), not its ecliptic longitude projected at zero latitude. | This is standard Lewis ACG. It matters for the Moon and Pluto, which can sit far off the ecliptic. |
| D2 | **Geometric horizon**: altitude 0, no refraction, geocentric (no topocentric parallax, the Moon included). | Standard practice, and the lines stay deterministic and location-independent. |
| D3 | **Bodies read in v1**: the 10 planets. **The lunar nodes are computed and drawn but not read** (`out_of_scope: "acg_nodes_v1"`). | The source text covers the 10 planets only. |
| D4 | **Parans/crossings, zeniths and CCG (transits to lines) are fast-follow**, not v1. Their records are extracted now and preserved (`acg_scope: paran / zenith / ccg`), excluded from v1 retrieval. Local space is cut (no source). | The source now covers them, so the blocker is compute and product scope, not corpus. It's the same pattern as `time_lord`. |
| D5 | **Birth time must be at the exact-time precision tier.** Anything less produces an absence contract, with no lines and no relocation. | A 1-minute error shifts every line by ~0.25° of longitude (~28 km at the equator), and 4 minutes shifts it by ~1.0°. |
| D6 | **Orb tiers by perpendicular ground distance**: tight ≤ 150 km, strong ≤ 400 km, wide ≤ 1,000 km. Read: up to the 4 closest tight/strong lines; **if there are none, the single nearest wide line** (worded as faint). | This is the source's rule (`acg-method-orb-distance`): strongest near the line, felt up to ~1,000 km especially when it's the only line, and the nearest line is the most potent. The constants live in `acg_constants.py`. |
| D7 | **Relocation keeps the natal UTC instant.** It never re-resolves the timezone from the new place. | The relocated chart is the same moment seen from elsewhere. |
| D8 | **Relocation is unavailable above \|lat\| 66.0°** (Placidus is undefined near the polar circle). This is an absence contract; lines are still drawn. | It mirrors the known circumpolar failure in `d_layer/test_chart_schema.py`. |
| D9 | **Grounding source = the ACG corpus** (spec 06): planet × angle records, planet synopses, angle frames and method principles. The **fallback** is the main corpus's `planet_in_house` records for the angular house (ASC→1, IC→4, DSC→7, MC→10), used only when a planet × angle bucket has < 3 kept ACG records. That fallback is the one sanctioned exception to the Placidus-only policy. **No authored records.** | A dedicated source beats reframing, and the no-hallucination contract prefers sourced over authored text. The reuse stays as a safety net for thin buckets. |
| D10 | **Reading is reflective, never directive.** No "move here", "avoid this city", guarantees or fatalism. | ACG is symbolic. Users make real relocation decisions. |
| D11 | **Profile lens** (`general / personal / professional`), as in predictive, shifts emphasis and ordering only and never filters. | Mirrors the existing contract. |
| D12 | **v1 is modern-only.** There is no classical ACG material (it is a 20th-century technique). | Same pattern as predictive v1. |
| D13 | **The ACG corpus is a separate file** (`acg_principles.grounded.json`), never merged into the main corpus. | Natal, synastry and predictive grounding must stay byte-identical (GA10). |
| D14 | **Sensitive source material** (death, violence, accident, illness, crime) is flagged at extraction (`sensitivity: high`) and rendered only as psychological or experiential themes, never as predicted events (spec 04 AV8). | The source is candid about the dark side of Mars, Saturn, Neptune and Pluto lines. The product is a self-reflection tool. |

## 4. Target layout (mirrors `Forecast_compute/` + `prediction_reading/`)

```
Astrocartography/
    acg_constants.py        # orbs, sampling steps, latitude limits, body list
    acg_types.py            # dataclasses / TypedDicts
    acg_schema.json         # JSON schema for acg.json
    compute_acg.py          # spec 01
    acg_geo.py              # spherical geometry helpers (spec 01 §6, spec 02 §3)
    acg_locate.py           # spec 02
    gazetteer.json          # spec 02 §6 (committed, cached coordinates)
    build_gazetteer.py      # one-off builder for gazetteer.json
    test_acg.py             # specs 01 + 02 invariants
principles_grounding/
    extract_acg.py consolidate_acg.py finish_acg.py   # spec 06
    acg_principles.grounded.json (+ .sha256)          # spec 06 output, separate corpus file
    test_acg_corpus.py      # spec 06 guards
    ground_acg.py           # spec 03
    test_ground_acg.py
acg_reading/
    ar_sections.py ar_prompts.py ar_routing.py ar_render.py ar_validate.py   # spec 04
    test_acg_reading.py
run_acg.py                  # spec 05 (repo root)
acg_run/                    # run folders, gitignored (real birth data)
```

If Phase 0 shows that the predictive layer uses a different naming convention
(`pr_*`), mirror it (`ar_*`) and report any deviation.

## 5. Phases

| Phase | Deliverable | Gate |
|---|---|---|
| **0: Exploration** | `Astrocartography/ACG_EXPLORATION_REPORT.md` (see §6). **No implementation code.** | Radul reviews it; specs 03 and 05 get their final signatures. |
| **1: Compute** | `compute_acg.py`, `acg_geo.py`, schema, tests | Every spec 01 invariant passes. Golden-chart comparison within tolerance (spec 01 §9). |
| **2: Locate + relocate** | `acg_locate.py`, relocation call, gazetteer, city scan | Spec 02 invariants pass. |
| **2b: Corpus** (parallel with 1–2) | spec 06 scripts + `acg_principles.grounded.json` | Guards C-1…C-8 pass; Radul's review gate (spec 06 §9). |
| **3: Grounding** | `ground_acg.py` | Spec 03 invariants pass. The drop report has been reviewed on 2 real charts. |
| **4: Reading** | `acg_reading/` | Spec 04 validator passes on 3 cities × 3 profiles for 1 real chart. |
| **5: Orchestrator** | `run_acg.py` | End-to-end `--dry-run` and one live run. The existing 107 tests still pass. |
| **6: v3** | spec 07 §2–5 (data + tagging) → spec 08 (scoring, affinity review, calibration) → spec 07 §6–8 (reading + modes) → spec 09 (recommender) | The gates in 07 §9, 08 §2/§4/§7, 09 §6 |

## 6. Phase 0: exploration report (required before Phases 3–5)

Answer each item with **file:line references and pasted excerpts**, not paraphrase.

1. `compute_chart` public signature. How local time, timezone and UTC are resolved. **Can
   it be called with a fixed UTC instant plus arbitrary lat/lon, without re-resolving the
   timezone?** If not, propose the smallest change (e.g. an optional `utc_override` /
   `tz_override` kwarg). Do not change default behaviour.
2. The birth-time precision tier enum and where it lives (`chart_types.py`?). Which
   value means "exact time".
3. Mean vs true node in L1. Which Swiss Ephemeris flags L1 uses (`FLG_SWIEPH` vs
   `FLG_MOSEPH`, `FLG_SPEED`, ephemeris path).
4. The geocoding function (name, signature, caching, failure behaviour).
5. `chart.json` excerpt: one planet block, the angles block, the `precision`/metadata block.
6. `ground.py`: public entry function(s), gate function names, the drop-report format.
   Paste **3 full records** from the planets-in-houses delta (one each for houses 1, 7
   and 10), including `about` and `requires`.
7. How `requires` conditions are evaluated against chart facts (the function, and the
   supported condition kinds).
8. `prediction_reading/pr_*.py` structure: section model, routing, the prompt builder, how
   `llm_client` is called, translation, detox, the validator entry point, and where the
   forbidden-word list lives.
9. The run-folder helper (`YYYYMMDD-HHMMSS_<3char>`) and manifest writer: the function names.
10. `.gitignore` entries for run folders.
11. `CORPUS_DELTA_HOWTO.md` + `extract_houses.py` / `merge_houses_delta.py` / `finish_delta.py`:
    the extractor's 9-field record shape, the prompt structure, and how ids/conditions/tags are forced.
12. `backfill.py`: how records are classified deterministically from id/conditions/tags, and where an
    `acg-*` branch would go.
13. Anything in these specs that contradicts the code. **Flag it; don't silently adapt.**
