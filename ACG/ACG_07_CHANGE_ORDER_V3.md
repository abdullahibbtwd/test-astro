# ACG 07: change order v3 (client requirements, section 10 "Astrocartography")

*2026-09-25. This is applied **on top of** the implemented specs 00–06. It lists only what changes
or is added. Two new specs come with it: **ACG_08** (goal scoring) and **ACG_09**
("Where Should I Go?"). Where this document conflicts with specs 00–06, this document wins.*

**Assumptions from Radul:** every user has an exact birth time and place. The free/premium
split is ignored for now: all features are built and available. The absence contracts for
non-exact time stay in the code untouched. Don't remove them and don't build UI flows for them.

## 0. Requirement → implementation map

| Client requirement | Where |
|---|---|
| Interactive world map with personal lines | existing `acg.geojson` + **goal heat layer** (08 §6) |
| Pick a **city** | existing locate flow, gazetteer expanded (§2) |
| Pick a **country** (and regions) | **new** country/region view (§3) |
| 11 goals | **new** goal taxonomy (08 §1), replaces the profile lens (§5) |
| City: general analysis | `place_overview` (kept) |
| City: nearby lines + **distance** | **new** `lines_near` data block, **distances shown as data** (§4) |
| City: positive influences / potential challenges | **new** sections `positives` / `challenges` (§6) |
| City: suitable for travel / permanent living / work / business / love / family | **new** 6 suitability cards, graded (08 §4–5, §6 here) |
| "Where Should I Go?" | **new** recommender (ACG_09) |

## 1. Decisions superseded in `ACG_00_INDEX.md`

| # | Old | New |
|---|---|---|
| D6 | Wide lines (400–1,000 km) are only read when there is no stronger line | **Unchanged for the prose reading.** But **every** line within 1,000 km (the 10 planets) is now listed **as data** with its distance (§4) and contributes to goal scores with a distance weight (08 §3). |
| D10 | Never directive | **Kept, and made concrete:** suitability is a **5-band grade**, never yes/no (08 §4). The fixed footer stays. |
| D11 | Profile lens `general/personal/professional` | **Removed.** Replaced by the goal taxonomy (08 §1). An optional `focus_goal` changes emphasis and ordering only. |
| Tradition mask | "The user never sees kilometres" | **Relaxed for data only:** distances appear in structured UI data, rounded to 10 km with an "approx." label. The ban on numbers in model-written prose (AV1) is unchanged. |
| D15 (new) | — | **Scores are deterministic.** The model never decides a grade or a ranking; it only explains results that were already computed, grounded in the records that produced them. |
| D16 (new) | — | **Geography data is open and committed:** GeoNames cities (CC BY 4.0, attribution required in the app credits) and Natural Earth countries/admin-1 regions/land (public domain). No runtime geocoding for scoring. |

## 2. Gazetteer v2 (replaces spec 02 §6)

`Astrocartography/build_gazetteer.py` rebuilds `gazetteer.json` from **GeoNames**, with no
geocoder calls:

- `cities15000` filtered to **population ≥ 300,000**, **plus** every national capital, **plus** all
  **81 Turkish province centres**, **plus** Turkish district centres with population ≥ 100,000, **plus** the
  v1 diaspora list (any missing items). Expected size: ~1,300–1,700 cities.
- Fields: `{id: "gn-<geonameid>", name, name_tr, aliases[], country_code, admin1_code,
  admin1_id, lat, lon, population}`.
- `name_tr` comes from GeoNames `alternateNamesV2` (language `tr`, preferred first); if there's none,
  use `name`. Report the TR coverage per country in the build log.
- `admin1_id` links to the Natural Earth admin-1 region (§3) by point-in-polygon, not by GeoNames code.
- Keep the v1 ids as aliases so existing tests still resolve (e.g. `tr-35` → İzmir).

Update the G1 acceptance: ≥ 1,200 cities; all 81 provinces; every country in Natural Earth admin-0 has ≥ 1
city or is listed in the build log as "no city ≥ threshold" (small states); unique ids; `name_tr` non-empty.

## 3. Countries and regions (new)

`Astrocartography/build_geo_index.py` (a one-off, committed outputs):

| Output | Content |
|---|---|
| `countries.json` | Natural Earth admin-0 (1:50m): `{iso_a2, iso_a3, name, name_tr, bbox}`. Simplified polygons go in `countries.geojson` for the UI. |
| `regions.json` | Natural Earth admin-1 (1:10m): `{admin1_id, iso_a2, name, name_tr, bbox}` + `regions.geojson` (simplified). |
| `geo_grid.npz` | **Land sample points** on a 0.5° grid (land mask = Natural Earth land 1:50m, lat −60…+75), each with `lat, lon, iso_a2, admin1_id`. Expect ~50–60k points. |

- `name_tr`: use Natural Earth `NAME_TR` where present, else GeoNames `tr`, else English. Log coverage.
- **Borders / point of view:** use Natural Earth's **Turkey point-of-view** variant if the release
  provides one; otherwise the default. Record the choice in `build_geo_index.log`. (This matters for
  Cyprus and for disputed areas in the Turkish market. Radul makes the final call.)
- Small countries with no grid point inside get at least one point: their largest polygon's
  representative point.

Country selection (`--country <ISO>`) and region selection (`--region <admin1_id>`) are scored by 08 §5
and rendered per §6.3.

## 4. `lines_near` as UI data (spec 02 §4 addition)

`locate.json.lines_near` stays as it is. Add the display block `lines_display` (this is what the UI shows):

```json
"lines_display": [
  {"body": "venus", "angle": "DSC", "planet_tr": "Venüs", "angle_label_tr": "Alçalan çizgi",
   "angle_label_en": "Setting line", "distance_km_rounded": 90, "tier": "tight",
   "tier_label_tr": "Çok yakın", "tier_label_en": "Very close", "read_in_prose": true}
]
```

- It includes **all** of the 10 planets' lines ≤ 1,000 km, sorted by distance. Nodes are excluded.
- `distance_km_rounded` = round to the nearest 10 km; below 10 km it's shown as `"<10"`.
- Tier labels: tight "Çok yakın / Very close", strong "Yakın / Near", wide "Uzak etki alanı / Distant range".
- Angle labels (fixed): ASC "Yükselen çizgi / Rising line", DSC "Alçalan çizgi / Setting line",
  MC "Zirve çizgisi / Culminating line", IC "Kök çizgisi / Root line".
  These are **UI labels only**; the prose rules (AV1) still forbid angle jargon in model text.
- `read_in_prose` = whether spec 03 selected this line for the prose reading.

## 5. Corpus: goal tags (spec 06 addition, post-pass)

The extraction may already have run, so add a **separate idempotent pass**. Don't re-extract.

`principles_grounding/tag_goals_acg.py`:
- Input: `acg_principles.grounded.json`, scopes `line`, `planet_general`, `angle_frame`.
- For each record, an LLM call (batched, 20 records per call, temperature 0) returns
  `goal_effects: {<goal>: "supportive" | "challenging" | "mixed"}` using the **closed goal enum and the
  definitions in 08 §1**. Rules:
  - Tag a goal **only** if the record's meaning directly concerns it, per the definition. At most **3 goals** per record. An empty object is valid.
  - The polarity is **per goal**. A record can be supportive for career and challenging for rest.
- Deterministic post-validation: enum membership, ≤ 3 keys, polarity enum. Invalid output → retry
  once → leave empty and log it.
- Cache key: `record id + sha256(rule + conditions + judgment)`. A re-run only calls the model for changed records.
- Write it back to the same file (a new `goal_effects` field) and update the `.sha256` sidecar.
- Guard **C-9**: every record in the three scopes has a `goal_effects` field (possibly empty); ≥ 80% of
  `line` records have ≥ 1 goal; each of the 11 goals appears on ≥ 15 records. A failure is reported but not
  blocking; Radul decides.
- **Review gate:** Radul checks the affinity table from 08 §2 before 08 goes live.

## 6. Reading changes (spec 04)

### 6.1 City reading: new section model (replaces spec 04 §2)

| Order | key | TR title | EN title | Source | Length (TR words) | Omit when |
|---|---|---|---|---|---|---|
| 1 | `place_overview` | Bu Yere Genel Bakış | This Place at a Glance | method records + gists of the other sections | 90–140 | never |
| 2 | `lines_here` | Buradaki Gezegen Çizgileri | Planetary Lines Here | A3 + A2 per selected line (what the line *is*) | **40–70 per line** | no selected lines |
| 3 | `positives` | Olumlu Etkiler | Positive Influences | selected lines' A1/A2 records with polarity `supportive` (+ `mixed`) | 80–160 | no such records |
| 4 | `challenges` | Olası Zorluklar | Potential Challenges | selected lines' A1/A2 records with polarity `challenging` (+ `mixed`); AV8 applies | 60–140 | no such records |
| 5 | `life_areas_here` | Burada Öne Çıkan Yaşam Alanları | Life Areas That Shift Here | house-shift bundles (kept from v2) | 80–160 | no house bundles |
| 6 | `suitability` | Bu Yer Ne İçin Uygun? | What Is This Place Suited For? | 6 cards (§6.2) | 25–50 per card | never |

The `lines_near` data block (§4) is attached to the reading JSON as `lines_display`. It is not a prose section.
`mixed` records may feed both `positives` and `challenges`, but each *sentence* traces to one record.

### 6.2 Suitability cards

Six cards, in this order. Each maps to a goal from 08 §1:

| Card | TR title | EN title | Goal |
|---|---|---|---|
| travel | Seyahat için | For travel | `travel` |
| living | Kalıcı yaşam için | For permanent living | `relocation` |
| work | Çalışma için | For work | `career` |
| business | İş kurmak için | For business | `business` |
| love | Aşk için | For love | `love` |
| family | Aile için | For family | `family` |

Each card has the shape `{goal, band, band_label_tr, band_label_en, text_tr, text_en, trace[]}`. The
band comes from 08 §4 (deterministic).

- Band ∈ {strongly_supportive, supportive, mixed, challenging}: the model writes 25–50 words using **only
  the records in that goal's `contributors` list** (08 §3). For `mixed`/`challenging`, it must name the demanding side.
- Band `no_emphasis`: **no model call.** A fixed template traces `acg-method-no-influence`:
  TR "Bu hedef açısından bu yer doğum haritanızdaki mevcut eğilimlere belirgin bir vurgu eklemiyor."
  EN "For this goal, the place adds no particular emphasis to what your birth chart already shows."
- The card text must **begin with the band label** (§6.4, AV9).

The **other 5 goals** (money, education, creativity, spirituality, rest) appear only as data: `goal_scores`
for all 11 goals is attached to the reading JSON (bands + scores, no text). The UI can show them as chips.

### 6.3 Country and region view

Deterministic data + one short overview:
- Data: `{bands: {goal: band} × 11 (08 §5 aggregate), lines_crossing: [{body, angle, crosses: true}],
  best_cities: {goal: [top 3 gazetteer cities in this country/region]}, varies_by_region: bool}`.
- One section `place_overview` (90–140 words), grounded on the method records + the A3/A2 records of the
  **3 lines covering the largest share of the country's grid points** (a line "covers" a point if it is
  ≤ 400 km away). When `varies_by_region` is true (the best vs worst region band differs by ≥ 2 bands on any
  of the 6 card goals), the overview must say that it varies by region and name the best region for 2 goals.
- Region view = the same as the country view, restricted to the admin-1 polygon.

### 6.4 Validator additions

| # | Rule |
|---|---|
| AV9 | Each card's `text_tr` / `text_en` starts with its band label (exact string). The trace ⊆ that goal's `contributors`. |
| AV10 | No yes/no verdicts: reject TR `evet`, `hayır`, `kesinlikle uygun`, `uygun değil`, `taşınmalı`; EN `yes,`, `no,`, `definitely suitable`, `not suitable`, `you should`. |
| AV11 | `positives` traces only records with polarity supportive/mixed; `challenges` traces only challenging/mixed. |
| AV12 | The planets named in `positives`/`challenges` ⊆ the selected lines' bodies. |

AV1 (no numbers or distances in prose) is **unchanged**: distances live only in `lines_display`.

### 6.5 `focus_goal` (replaces the profile lens)

The optional `--focus-goal <goal>` does three things: (a) orders `lines_here` by that goal's contribution,
then by distance; (b) moves that goal's card first if it is one of the 6, and otherwise adds it as a 7th card;
(c) adds one emphasis sentence instruction to the overview prompt. It never filters records.

## 7. Grounding changes (spec 03)

- Carry `goal_effects` and `polarity` on every kept record (they're already in the record; just don't strip them).
- New output block `goal_contributors` in `acg_principles.json`, taken from 08 §3 for this place:
  `{goal: {score, band, contributors: [record ids]}}` × 11.
- Records that contribute to a goal score but come from a **wide** line not selected for prose are still
  loaded into `goal_contributors` (the cards may use them). They are marked `acg_evidence.tier: "wide"`.
- The drop-reason enum is unchanged.

## 8. Orchestrator changes (spec 05)

Modes replace the old place/map split:

| Mode | CLI | Stages | Outputs (new ones in bold) |
|---|---|---|---|
| map | (no place) | 1–4 + **goal scan** | `acg.json`, `acg.geojson`, `city_scan.json`, **`goal_scan.npz`**, **`goal_heat_<goal>.geojson`** × 11 |
| city | `--city` / `--lat --lon` | all | as v2 + **`lines_display`**, **`goal_scores`** in the reading JSON |
| country | `--country ISO` | 1–4, goal scan, country aggregate, overview | **`country_<ISO>.json`**, reading |
| region | `--region ID` | same | **`region_<ID>.json`**, reading |
| recommend | `--recommend GOAL [--scope world\|TR\|<ISO>]` | 1–4, goal scan, ACG_09 | **`recommend_<goal>_<scope>.json`**, explanations |

- `--profile` is removed. `--focus-goal` is added.
- **Caching:** `acg.json`, `city_scan.json` and `goal_scan.npz` depend only on the birth data. Store them in
  a per-chart cache folder keyed by `sha256(jd_ut, flags, corpus sha256, affinity-table sha256)` and
  reuse them across runs. Readings are cached by `(chart key, place id, language, focus_goal)`.
- Manifest: add `mode`, `goal`, `scope`, `cache_hit` per stage, and the `affinity_sha256`.

## 9. Acceptance (additions)

| # | Check |
|---|---|
| V3-1 | City run output has 6 cards in the fixed order, `goal_scores` for 11 goals, and `lines_display` sorted with rounded distances and no nodes. |
| V3-2 | `no_emphasis` cards make zero model calls (patch `llm_client` to count calls). |
| V3-3 | `--country TR` and `--country DE` produce `best_cities` drawn only from cities inside that country. |
| V3-4 | Changing `--focus-goal` changes the order, never the set of traced records (except the added 7th card). |
| V3-5 | The second run for the same chart hits the cache for `acg.json`, `city_scan.json` and `goal_scan.npz`. |
| V3-6 | Every existing test still passes. |
