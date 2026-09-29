# ACG build notes: Phases 3–6 (spec set v3)

*2026-09-25. Covers grounding (spec 03 + 07 §7), the place reading (spec 04 + 07 §6), the
orchestrator (spec 05 + 07 §8), the v3 data (07 §2–5), goal scoring (08) and "Where Should I
Go?" (09). Phases 0–2b are in `ACG_EXPLORATION_REPORT.md`. Nothing is committed.*

## 1. What exists now

| Layer | Files | Tests |
|---|---|---|
| Lines + locate (01, 02, 07 §4) | `compute_acg.py`, `acg_geo.py`, `acg_locate.py`, `acg_schema.json` | `test_acg.py` (32) |
| Geography v2 (07 §2–3) | `build_gazetteer.py` → `gazetteer.json` (2,126 cities); `build_geo_index.py` → `countries.json/.geojson` (239), `regions.json/.geojson` (4,592), `geo_grid.npz` (60,657 points); `acg_geodata.py`; `DATA_CREDITS.md` | in `test_acg.py` |
| Corpus (06) + goal tags (07 §5) | `principles_grounding/extract_acg.py`, `consolidate_acg.py`, `finish_acg.py`, `tag_goals_acg.py` → `acg_principles.grounded.json` (435 records) | `test_acg_corpus.py` (C-1…C-9) |
| Affinity (08 §2) | `build_affinity.py` → `principles_grounding/acg_goal_affinity.json` + `acg_goal_affinity_review.md` | `test_acg_affinity.py` |
| Goal scoring (08 §3–6) | `acg_goals.py`, `calibrate_bands.py` → `calibration_report.md` | `test_acg_goals.py` (S2–S8) |
| Grounding (03, 07 §7) | `principles_grounding/ground_acg.py` | `test_ground_acg.py` (GA1–GA12 + goal block) |
| Reading (04, 07 §6) | `acg_reading/ar_sections.py`, `ar_routing.py`, `ar_prompts.py`, `ar_generate.py`, `ar_validate.py`, `ar_render.py` | `acg_reading/test_acg_reading.py` (AR1–AR5, AV1–AV12, V3-1…V3-5, O1–O5) |
| Area views + recommender (07 §6.3, 09) | `acg_recommend.py` (deterministic), `acg_reading/acg_views.py` (model text) | `test_acg_recommend.py` (W1–W8; W6 live, opt-in) |
| Orchestrator (05, 07 §8) | `run_acg.py` (repo root); `acg_run/` gitignored | in `test_acg_reading.py` |

**Test command** (247 pass, 1 live test skipped; the existing 115 are included and unchanged):

```bash
python -m pytest -q Astrocartography/ principles_grounding/test_acg_corpus.py principles_grounding/test_ground_acg.py acg_reading/ Interpretation_layer/test_l4.py synastry_reading/test_s3.py prediction_reading/test_forecast_reading.py principles_grounding/test_ground_house_policy.py test_llm_client.py
```

The live W6 test (free text → goal): `ACG_LIVE=1 python -m pytest -q Astrocartography/test_acg_recommend.py -k w6`. It passes 27/27.

**Running it:**

```bash
python run_acg.py --date 1985-03-14 --time 11:30 --location Istanbul --city İzmir [--focus-goal love]
python run_acg.py ... --country TR | --region TUR-3045 | --recommend career [--scope TR]
python run_acg.py ... --query-text "Kariyer için en iyi yer neresi?"
python run_acg.py ... (no place) → map mode: lines, city scan, goal scan, 11 heat layers
```

`--dry-run` makes zero model calls. The per-chart cache lives in `acg_run/_cache/<key>/`.

## 2. Design decisions made while building (for review)

1. **Sentence-level traces.** Every model call returns `{units: [{unit_id, sentences: [{text, ids}]}]}`.
   The validator checks each sentence's ids against that unit's routed pool. In
   positives/challenges, each sentence must cite exactly one record of the right polarity (AV11).
   Translation is sentence-aligned, so the EN text inherits the TR trace. This is stricter
   than L4's slot-level trace (report C9).
2. **Band labels are prepended in code**, never written by the model. Cards and recommendation
   items can't assert a different band (AV9/RV3 by construction).
3. **Record text shown to the model has the angle abbreviations swapped for plain words**
   (e.g. "Moon on the DSC" → "Moon on the setting point"), so there's nothing for AV1 to catch.
   Meaning is unchanged; the corpus itself is untouched.
4. **Synthesis pass.** There is no separate TR synthesis rewrite per section; only the overview
   is written last with the other drafts as context (spec 04 §2). A rewrite of the sentence
   units would break the sentence traces. There is one length re-ask per out-of-range unit,
   then the validator refuses.
5. **Goal contributors are filtered by `requires`.** The score comes from the affinity table
   (conditions ignored, as specified), but a contributor record whose natal condition is false
   for this chart is not handed to the card writer (`contributors_dropped_by_requires`).
6. **A card whose band isn't `no_emphasis` but has no usable record** gets a fixed method sentence
   traced to `acg-method-orb-distance` instead of model text.
7. **Cache key** = spec 07 §8 fields plus the gazetteer and grid hashes (the scans depend on them).
   Readings are cached by (chart key, place, focus goal, models, plan hash).
8. **The city scan** reuses the vectorised distance kernel to preselect city–line pairs: 13 s → 0.4 s
   for 2,126 cities, with output identical to the scalar path.
9. **The goal-scan kernel** reproduces `acg_geo` exactly within the 1,000 km orb (max difference
   6e-13 km), using a bounding-cone prefilter. The full scan takes ~2.5–3.5 s for 62,783 points.
10. **Country view.** "Crosses" means a line within 40 km of an area point (about half a grid
    cell). The "best region" named in the overview is taken only from goals whose best region is
    supportive.
11. **Orchestrator.** The profile flag is removed. `--focus-goal`, `--country`, `--region`,
    `--recommend`, `--scope` and `--query-text` were added. The manifest records `mode`, `goal`,
    `scope`, `cache_hit` per stage, `affinity_sha256` and `chart_cache_key`.

## 3. Gates still open (Radul)

| Gate | State |
|---|---|
| 01 §9 golden check vs astro.com | open: needs one of your real charts |
| 06 §9 corpus review | open: `acg_consolidation_report.json` + Saturn\|MC, Venus\|DSC and the 16 fixed ids |
| 07 §3 border point of view | Natural Earth's **Turkey point-of-view** admin-0 (only at 1:10m). Northern Cyprus is kept as **`XN`** (provisional code). Nicosia stays in CY by its GeoNames code. See `build_geo_index.log` |
| 07 §5 / 08 §2 affinity review | **3 of 19 sanity checks fail** (Neptune money at DSC/MC/IC: no corpus evidence). **291/440 cells are low-evidence**. Travel has only 7 tagged records (C-9 warns). Read `acg_goal_affinity_review.md` |
| 08 §4 calibration | **open, and the thresholds can't fix it alone.** On 20 synthetic charts only career, creativity and relocation hit the targets. money/travel/education/love/family are 84–96% `no_emphasis` because their affinity cells are sparse. Per the spec, the fix is corpus/tagging, not A overrides. Run `calibrate_bands.py --charts <your 20 charts>` for the real gate. Constants are unchanged |
| 09 §6 review | open: 1 real chart × career/love/family/relocation × world |
| 04 §8 reading gate | see §4 |

## 4. Live runs (fixture chart 1985-03-14 11:30 Istanbul, not a real person)

| Run | Result |
|---|---|
| City İzmir, focus love (first run) | passed the validator: 8 calls, 12k in / 2.7k out tokens. It exposed repetitive wording ("hissedilir biçimde" in every sentence), and the prompt was tightened. All six cards were `no_emphasis`, which is the sparse-affinity issue above |
| Country TR | passed: 2 calls. The overview names the regional variation and Tunceli as the best region for career |
| Recommend career, world | passed: 2 calls, 50k in / 9k out. Ten cities (RU/KZ/UZ/GL/NZ/FK), five regions, five countries and a Turkey block (Diyarbakır, Erzurum); tradeoffs are named where N ≥ 0.25 |
| Reading gate: Lahore (2 tight lines) / Caracas (no lines, house shifts only) / İzmir × focus none/love/career | see §5 |

## 5. Reading gate (04 §8, profiles replaced by focus goals)

1 chart × {Lahore (2 tight lines), Caracas (no lines; house shifts only), İzmir (2 strong lines)}
× {no focus, love, career}.

- **First pass: 7/9 passed; 2 were refused by the validator.** In one, the model's Turkish came
  back with corrupted characters ("iliřkiler", "bi%cimde"). In the other, the overview didn't
  name the place.
- **Fixes:**
  - an explicit `ENC` encoding-corruption check;
  - one targeted repair round, which redrafts only the failing sections with the validator's
    messages as feedback, then revalidates and refuses anything that remains;
  - the reading cache key now includes a hash of the reading code.
- **Second pass: 9/9 passed.** Calls per reading: 4–14, depending on the number of sections and
  non-template cards. Tokens: 9–24k in, 2–5k out.
- A city with neither lines nor house shifts doesn't occur for this chart. The zero-line
  routing is covered by AR3 instead.
- **Radul reads the TR output.** Run folders are `acg_run/20260925-1038*` to `-1040*`.

## 6. Phase 7 (v4): parans (spec 10) + viable destinations (spec 11), 2026-09-28

**Built**
- `compute_parans.py`: parans (216 on the 1979-03-30 Sofia chart, as in the prototype) with
  `parans_near` / `parans_display`. Cached as `parans.json` + `acg_parans.geojson` per chart.
- Paran scoring in `acg_goals.py` (lines + ≤ 2 parans within ±1°, W_PARAN 0.4); scan and city
  path stay identical.
- Paran evidence stream in `ground_acg.py`, with the paran scope now eligible.
- The `background_influences` reading section, plus AV12 for it and "paran" added to AV1.
- `tag_goals_acg.py` now tags parans. `build_affinity.py` has a `parans` block: 27 of 495
  pair×goal entries come from paran records, the rest from the fallback.
- Destinations data: `build_destinations.py`, `destinations.json` (3,253 rows), `destinations_review.csv`,
  `viability_policy.json`, `regions_map.json`, and the `acg_destinations.py` API.
- `acg_line_first.py`: the line-first ranking, spec 11 §5.
- `acg_reading/ar_recommend.py`: explanations for line groups and destinations, chunked and
  parallel, with 2 repair rounds.
- `run_acg.py` flags: `--regions --city-size --max-distance-km --home-city --climate
  --purpose --include-unreviewed`.
- Tests: `test_acg_parans.py` (PA1–PA8), `test_acg_destinations.py` (DV1–DV3),
  `test_acg_line_first.py` (DV4–DV8). **Full suite: 313 passed, 1 skipped.**

**Fix to spec 01 found by PA2:** near the circumpolar joins, the 0.25° latitude sampling left
rising/setting polylines up to 2.6° of longitude off the true curve. `compute_acg` now inserts
vertices every ≤ 0.5° of hour angle, using the exact inverse φ = atan(−cos H₀ / tan δ). All
216 parans now meet their lines within 0.006°. The chart cache key includes the compute code,
so older caches are rebuilt.

**Calibration re-run (08 §4, with parans):** almost unchanged. Only career, creativity and
relocation are on target; the constants are unchanged (Radul's gate).

**09 gate (1979-03-30 Sofia × career/love/relocation/travel, world):** 4/4 pass the validator.
Career needed a second repair round, now standard. These runs used `--include-unreviewed`,
because only 124 destinations (the TR provinces and the diaspora list) are reviewed, and they
are flagged `include_unreviewed: true`. Run folders: `acg_run/20260928-1022*` / `-102641_wkz`.
The unreviewed candidate set surfaces obscure mid-size cities (Chandrapur, Dindigul, Tangshan);
the review sheet exists to fix exactly that.

**Open for Radul (spec 11 §10 + agent findings)**
1. Review `destinations_review.csv`. Nothing outside TR provinces and the diaspora list is
   recommendable until then (no auto-approval).
2. P6 Central Asia; Bahrain/Kuwait/Oman as Gulf hubs; the Turkey block ignores the size default.
3. Region size: §2 (largest city) vs §10.4 ("small"). Bali and the Canaries are currently `mid`.
4. Afghanistan falls to P7 (allowed); Mauritius/Seychelles/Zanzibar are excluded by P4; conflict
   zones (Ukraine incl. Crimea under TR point of view, Haiti) are not pre-excluded.
5. The Sea of Marmara isn't Mediterranean; Nile Delta cities pass P4 (≤ 100 km).
6. A 422 MB GeoNames `allCountries.zip` sits in `.cache/geodata/` inside Google Drive and will
   sync; delete it or move it outside Drive if that matters (the matches are cached).

## 7. Radul's decisions, 2026-09-28

- **Afghanistan excluded:** added to P1. `viability_policy.json` is now version 2.
- **Islands allowed under the Africa rule (P4):** a new `island` field on every destination
  means the point is not on a landmass of 3 million km² or more (Natural Earth 1:50m land);
  552 destinations are islands. Mauritius, the Seychelles, Zanzibar, Madagascar, Cabo Verde
  and similar now pass. Mainland Africa outside the Mediterranean coast stays excluded.
- **Bali and the Canaries included:** they are allowed under P7 and are `mid`/`big` in size.
- **Recorded as reviewed:** Bali, the Canaries (region, Las Palmas, Santa Cruz), Zanzibar,
  Mauritius (+ Port Louis) and the Seychelles (+ Victoria). The decisions are in
  `destinations_review_decisions.csv`, which every rebuild applies. Reviewed total: 134.
- **New output** `recommend_<goal>_<scope>_<date>.md`: the readable TR + EN version of the
  recommendation JSON.
- Tests: `test_acg_policy_decisions.py`. Full suite: 332 passed, 1 skipped.
