# Astrocartography (ACG) layer: summary

*State as of 2026-09-28. The ACG layer adds relocation astrology to the app: where on Earth
each planet is emphasised for a person, what a place brings out, and where to go for a goal.
Built from the spec set in `ACG/` (specs 00–11). Build history and decisions are in
`ACG_BUILD_NOTES.md`, and the spec-vs-code conflicts are in `ACG_EXPLORATION_REPORT.md`.*

---

## 1. What it does

| Feature | Question it answers |
|---|---|
| **Map** | Where are my planetary lines (rising, setting, culminating, root) and latitude crossings (parans)? |
| **City reading** | What does this city bring out in me? Nearby lines with distances, positive influences, potential challenges, background influences (parans), life areas that shift, and 6 suitability cards (travel, permanent living, work, business, love, family) |
| **Country / region view** | How does a whole country or province look for each goal, and which cities in it are best? |
| **Where Should I Go? (one goal)** | For love, career, etc.: my strongest lines for that goal and the viable places along each |
| **Where Should I Go? (overall)** | Which places help me across **all 11 goals** at once? |

All text is **Turkish first, English second**. The same no-hallucination contract as the rest
of the app applies: every sentence cites the source principles it rests on, and a validator
refuses anything that breaks the rules. The rules forbid numbers or jargon in prose, directive
advice ("move here"), event predictions and yes/no verdicts.

**Scores, grades and rankings are deterministic.** The model only explains results that were
already computed.

---

## 2. How to run

```bash
# map only (no model calls)
python run_acg.py --date 1979-03-30 --time 06:30 --location "Sofia, Bulgaria"

# a city
python run_acg.py --date 1979-03-30 --time 06:30 --location "Sofia, Bulgaria" --city Barcelona [--focus-goal love]

# a country or an admin-1 region
python run_acg.py ... --country TR
python run_acg.py ... --region TUR-3045

# Where Should I Go? for one goal, or overall
python run_acg.py ... --recommend career
python run_acg.py ... --recommend overall
python run_acg.py ... --query-text "Aşk için dünyada en iyi yer neresi?"

# interactive (asks for birth data and a city)
python run_acg.py
```

**Goals:** love, career, business, money, family, education, creativity, spirituality, rest,
travel, relocation (plus `overall` for recommendations).

**Recommendation filters** (all optional):

| Flag | Default |
|---|---|
| `--scope world\|TR\|<ISO-2>` | world |
| `--regions europe,turkey,mediterranean,middle_east_gulf,caucasus,americas,east_asia,south_southeast_asia,oceania,central_asia` | all |
| `--city-size big,mid,small` | **big** |
| `--climate warm,mild,cold` | not applied |
| `--max-distance-km N --home-city X` | none (home defaults to the birthplace) |
| `--purpose living\|travel\|both` | derived from the goal |

**Other flags:**
- `--dry-run`: everything except the model calls; free, and shows the ranking and prompts.
- `--model`, `--synthesis-model`, `--translation-model`: as in the other orchestrators.
- `--include-unreviewed`: development only.

**Requirements:** an exact birth time (local time at the birthplace); `GEMINI_API_KEY` and
`OPENAI_API_KEY`; Python 3.11 with pyswisseph, timezonefinder, geopy, tzdata, numpy, shapely,
pyshp, jsonschema, google-genai and openai.

**Cost and time:** a city reading is 4–14 model calls (~10–25k tokens in). A recommendation is
roughly 60–110k tokens in. Both take about 1–2 minutes. The first run for a new birth chart
computes and caches the map layers; later runs reuse them.

---

## 3. Outputs

Every run writes to its own folder, `acg_run/YYYYMMDD-HHMMSS_xxx/`, which is gitignored
because it holds real birth data. Every file name carries the birth date.

| File | Content |
|---|---|
| `chart_*.json` | The natal chart |
| `acg_*.json` / `acg_*.geojson` | The 44 lines (10 planets + node × 4 angles), as data and as a map layer |
| `parans_*.json` / `acg_parans_*.geojson` | Parans: one dashed latitude line each, plus a marker where the two planet lines cross |
| `city_scan_*.json` | Which lines pass within 400 km of each of 2,126 cities |
| `goal_scan_*.npz` | Scores for all 11 goals at every city and ~60k land grid points |
| `goal_heat_<goal>_*.geojson` × 11 | Map points where a goal is emphasised, by band, for heat/colour layers |
| `locate_*.json` | For a city: the lines within 1,000 km with distances, nearby parans, relocation status and house shifts |
| `chart_relocated_*.json` | The same birth moment seen from the chosen place |
| `acg_principles_*.json` / `acg_drop_report_*.json` | Grounded principles for the place, and what was left out and why |
| `reading_tr_*.json`, `reading_en_*.json`, `reading_*.md` | The city reading, including `goal_scores`, `lines_display` and `parans_display` |
| `country_<ISO>_*.json` / `region_<ID>_*.json` | Country/region bands per goal, crossing lines, best cities, overview text |
| `recommend_<goal>_<scope>_*.json` + `.md` / `.en.md` / `.tr.md` | Recommendations: structured, bilingual, English-only, Turkish-only |
| `run_manifest_*.json` | Stages, cache hits, models, corpus and affinity hashes, gaps |

---

## 4. How it works

```
birth data → natal chart (L1) → lines + parans → goal scores (all cities, grid)
                                     │
      city ───────→ locate → relocate → grounding → reading (TR → EN, validated)
      country ────→ aggregate over the area → overview
      recommend ──→ viable destinations (policy + filters) → ranking → explanations
```

**Lines** (`compute_acg.py`) are in-mundo lines from each body's true right ascension and
declination against Greenwich apparent sidereal time, using the geometric horizon. Rising and
setting curves are densified near the polar joins. Accuracy against Swiss Ephemeris is about
1e-13°.

**Parans** (`compute_parans.py`) are latitudes where two planets are angular at once. There
are 12 angle combinations per planet pair (meridian × meridian excluded); the 1979-03-30 chart
has 216.

**Goal scores** (`acg_goals.py`). An **affinity table** (`principles_grounding/acg_goal_affinity.json`)
says how strongly each planet × angle (and each planet pair, for parans) supports or challenges
each goal. It is built from the goal-tagged ACG principles. A place's score for a goal sums:
- every line within 1,000 km, weighted by distance (1.0 up to 150 km, 0.5 at 400 km, 0 at 1,000 km);
- up to 2 parans within ±1° of latitude, at a weight of up to 0.4.

The result is a positive part P, a negative part N and S = P − N. Those give one of five
**bands**: strongly supportive, supportive, mixed, challenging, no clear emphasis.

**Grounding** (`ground_acg.py`) selects the principles that are true for the person in that
place:
- line evidence for up to 4 closest lines;
- paran evidence;
- relocated-house evidence;
- method framing.

A record whose natal condition (e.g. "Sun square Saturn") doesn't hold is dropped.

**Recommendations:**
- **One goal** (`acg_line_first.py`): the user's strongest lines for the goal (affinity ≥ 0.30),
  then up to 5 viable places within 400 km of each line. There are up to 4 line groups, and a
  paran can fill the 4th. Diversity rules: ≤ 2 places per country per line, and no two places
  within 150 km of each other. Strong lines that cross no viable place are listed honestly.
- **Overall** (`acg_overall.py`): the average of the 11 goal scores. A place needs a positive
  average and at least 2 goals supported. Each place shows how many goals it supports and
  challenges, e.g. "Supportive for 7 goals · challenging for 1". Diversity: ≤ 3 per country,
  ≥ 150 km apart, ≤ 2 per dominant line.
- Both include a **Turkey** section. It ignores the size default, so resorts can appear there.

---

## 5. Where recommendations can point (viability)

The candidates are **3,253 destinations** (`destinations.json`): capitals, cities of 200k+,
the 81 Turkish provinces, Turkish coastal and heritage places, the diaspora cities and
well-known resorts and regions. The policy `viable_world_v1` (`viability_policy.json`, v2)
decides which may appear; the first matching rule wins.

| Rule | Decision |
|---|---|
| P1 | North Korea, Mongolia, **Afghanistan**: excluded |
| P2 | Russia: European Russia only (not the Ural, Siberian or Far Eastern federal districts) |
| P3 | Mainland China: big coastal cities only (Hong Kong, Macau and Taiwan follow normal rules) |
| P4 | Africa: excluded, except Mediterranean-coast places in Morocco, Algeria, Tunisia, Libya and Egypt, and **all islands** (Mauritius, Seychelles, Zanzibar, Madagascar, Cabo Verde…) |
| P5 | Middle East: Turkey, Israel, Saudi Arabia, UAE, Qatar, Azerbaijan, Bahrain, Kuwait, Oman allowed; others excluded |
| P6 | Central Asia: capitals + Almaty, Samarkand, Bukhara |
| P7 | Everywhere else: allowed (Bali and the Canaries included) |

**Review status:** every place the policy allows is approved (Radul, 2026-09-28): 2,349
places, recorded in `destinations_review_policy.json`. Individual places can still be
excluded in `destinations_review_decisions.csv`.

**Size default:** big cities only (≥ 1,000,000), for more recognisable places.

**Filters never change a score**; they only decide which places may appear.

---

## 6. Data and credits

| Data | Source | Licence |
|---|---|---|
| Cities, Turkish names | GeoNames | CC BY 4.0 (attribution required in the app) |
| Countries, regions, land, coastline, seas | Natural Earth (Turkey point-of-view borders at 1:10m) | Public domain |
| Climate classes | WorldClim 2.1 (bio1, annual mean temperature) | CC BY 4.0 |
| ACG principles | Lewis & Guttman, *The Astro\*Carto\*Graphy Book of Maps* (1989), extracted as technique and meaning only, never wording; guarded against verbatim runs and names | Source text in `TXT/` (gitignored) |

Northern Cyprus is kept as a separate area with the provisional code `XN`; Nicosia stays in CY.
Details are in `DATA_CREDITS.md`, `build_geo_index.log` and `build_destinations.log`.

---

## 7. Files

| Area | Files |
|---|---|
| Compute | `compute_acg.py`, `compute_parans.py`, `acg_geo.py`, `acg_constants.py`, `acg_schema.json`, `acg_types.py` |
| Places | `acg_locate.py`, `gazetteer.json`, `acg_geodata.py`, `countries/regions.json/.geojson`, `geo_grid.npz` |
| Scoring | `acg_goals.py`, `build_affinity.py`, `calibrate_bands.py` |
| Recommendations | `acg_recommend.py`, `acg_line_first.py`, `acg_overall.py`, `acg_destinations.py`, `destinations.json`, `viability_policy.json`, `regions_map.json` |
| Builders | `build_gazetteer.py`, `build_geo_index.py`, `build_destinations.py` |
| Corpus | `principles_grounding/extract_acg.py`, `consolidate_acg.py`, `finish_acg.py`, `tag_goals_acg.py` → `acg_principles.grounded.json` (435 records, separate from the main corpus) |
| Grounding | `principles_grounding/ground_acg.py` |
| Reading | `acg_reading/ar_sections.py`, `ar_routing.py`, `ar_prompts.py`, `ar_generate.py`, `ar_validate.py`, `ar_render.py`, `acg_views.py`, `ar_recommend.py`, `ar_overall.py` |
| Orchestrator | `run_acg.py` (repo root) |

**Tests** (338 pass together with the existing suites):

```bash
python -m pytest -q Astrocartography/ principles_grounding/test_acg_corpus.py principles_grounding/test_ground_acg.py acg_reading/
```

---

## 8. Known limitations and open items

1. **Thin goal evidence.** Only career, creativity and relocation hit the calibration targets.
   Money, travel, education, love and family are "no clear emphasis" for most places, because
   the source book says little about them (travel has only 7 tagged records). This should be
   fixed in the corpus/tagging, never by overriding scores. `calibrate_bands.py --charts <real charts>`
   is the calibration gate.
2. **Paran scores are mostly borrowed.** Only 27 of 495 pair × goal scores come from paran-specific
   text; the rest average the two planets' line scores. Parans are weighted at 0.4 (`W_PARAN`).
3. **Recognisability.** Rankings follow the astrology score. Fame only breaks ties, so the
   big-city default is what keeps results familiar. Weighting fame more is possible.
4. **Reviews still open:**
   - the line-accuracy check against astro.com (one real chart);
   - the corpus review (`acg_consolidation_report.json`);
   - the affinity review (`acg_goal_affinity_review.md`: 3 of 19 sanity checks fail, all Neptune/money);
   - the Northern Cyprus code;
   - conflict zones (Ukraine incl. Crimea, Haiti) are not pre-excluded.
5. **Disk space.** About 680 MB of downloaded source data sits in `.cache/geodata/` inside
   Google Drive. It's only needed to rebuild the data files.
