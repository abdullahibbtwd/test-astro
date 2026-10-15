# FE 07: Astro map (Map tab)

*Brief §10. API: FE_02 §7.7. Backend: ACG layer (ACG_00–ACG_11). Principles that bind the UI: the reading is
reflective, never directive (ACG D10); suitability is a 5-band grade, never yes/no (ACG_07 D10); distances appear
only as rounded UI data with "≈" (ACG_07 §4); the model's prose never contains numbers; the fixed footer is shown
with every place text.*

## 1. Screen layout

```
┌ ProfileSwitcher ┐ ┌ Search cities, countries…           ┐  Ask
[ Lines ] [ Love ] [ Career ] [ Business ] [ Money ] [ Family ] … (goal chips, one selected)
                               MAP
                                                         (layers)  (legend)  (list)
                                         ( ◎ Where should I go? )
```

- Goal chips: **Lines** (no heat) + the 11 goals in the catalogue order with their labels. One at a time.
- Layers button: planet filter (10 toggles, all on), **Latitude crossings** (parans, default off), **Nodes**
  (default off; their lines are drawn but not read, ACG D3).
- Legend button: planet colours + angle styles; with a goal selected, the 4 heat levels with their band labels.
- List button: the accessible lines list (§8).
- The "Where should I go?" button opens §6.

## 2. Base map

- `@maplibre/maplibre-react-native`, style from `config.map_style_url.{light,dark}`: muted, low-saturation vector
  style (hairline borders, pale land, no POIs, place labels only), labels in the app language (`name:tr` /
  `name:en` fallback `name`).
- **Borders from a Turkey point-of-view worldview** (O6); the provider is Radul's choice.
- Attribution control always visible (tile provider, OpenStreetMap if applicable).
- Projection: globe if the installed MapLibre Native version supports it, else Web Mercator. Lines exist between
  latitudes −80° and +80° (the backend's range).
- Initial camera: fit the user's current place at zoom 2 (world visible).

## 3. Layers

### 3.1 Planetary lines (`GET /acg/lines`, cached per `chart_key`)
- One line layer per angle style, colour by `body` (FE_01 §5.2 planet colours):
  **ASC** solid 2.5 pt · **DSC** dashed `[6, 4]` 2.5 pt · **MC** solid 2 pt · **IC** dotted `[1.5, 3]` 2 pt.
- Symbol layer along each line (every ~280 pt): the planet glyph (sprite images rasterised from `wheel-core`
  glyphs at build time, light + dark) and the angle short label (AC / DC / MC / IC from `catalogue.angles`).
- `read: false` features (nodes) render thin grey dashed, only when **Nodes** is on.
- Lines stay above the heat layer.

### 3.2 Latitude crossings (parans, `parans` of the same response)
Thin neutral dotted horizontal lines with a label chip "♄ × ♅" (two glyphs). Off by default.

### 3.3 Goal heat (`GET /acg/heat/{goal}` when a goal chip is selected)
- Build 0.5° square cells from the points client-side (memoised per goal) → one fill layer; colour by level:
  2 → `strongPlus`, 1 → `plus`, 0 → `mixed`, −1 → `minus` (FE_01 §5.2); opacity 0.35 light / 0.45 dark.
  `no_emphasis` points are absent by design (the map stays quiet there).
- Legend shows the four levels with `catalogue.place_bands` labels.
- The selected goal becomes the `focus_goal` of place reports opened from the map.

## 4. Selecting things on the map

| Gesture | Result |
|---|---|
| Tap within 12 pt of a line | **Line sheet** (§4.1). Lines win over places. |
| Tap elsewhere, zoom ≥ 3.5 | `GET /places/reverse`; a city within 75 km → pin + **City report** (§5.1). None → sheet "No city nearby" with **Explore this exact spot** → point report (`/acg/point`). |
| Tap, zoom < 3.5 | the country under the finger (client-side point-in-polygon on `/geo/countries.geojson`) → **Country report** (§5.2) |
| Long press | point report for that spot (`/acg/point`) |
| Search | `/places/search?kind=city` and `?kind=area` merged in two sections (Cities · Countries & regions) → fly to + open the report |

### 4.1 Line sheet
Header: planet glyph + "Venüs · Yükselen çizgi" (`catalogue.bodies` + `catalogue.angles.*.line`). Body: **Places on
this line** from `GET /acg/lines/{body}/{angle}/places` (name, flag, "≈ 40 km", tier label) → city report. Nodes'
lines show only the header and a note that they are drawn for reference. No interpretive text (F8).

## 5. Place reports

Reports open in a bottom sheet over the map (snap points 25 % / 55 % / 92 %) and can be expanded to a full screen.
The map highlights the subject (city pin, or the country / region polygon outlined and tinted `accentSoft`).

### 5.1 City (or spot) report — `GET /acg/places/{place_id}?focus_goal=` or `/acg/point?lat=&lon=`

Deterministic blocks render at once; the reading arrives later (≈ 70 s observed, F11).

| Order | Block | Binding | Brief §10 item |
|---|---|---|---|
| Peek | name + flag; nearest line "Venüs · Yükselen çizgi · ≈ 40 km"; a mini row of the 6 card band chips | `place`, `lines_display[0]`, `cards` | — |
| 1 | Relocation absent notice (above \|lat\| 66°) | `relocation.absence` | — |
| 2 | **What is this place suited for?** 6 cards in API order (travel, permanent living, work, business, love, family; a 7th `focus` card when the focus goal is another one): title, `BandChip`, text. `text: null` → two skeleton lines until the reading is ready. | `cards` | suitable for travel / living / work / business / love / family |
| 3 | Other life areas: band chips for the remaining 5 goals | `goal_scores` | — |
| 4 | **Planetary lines nearby**: glyph, planet + angle label, tier chip, "≈ 40 km" (`'<10'` → "< 10 km"); lines with `read_in_prose: false` in `ink3` | `lines_display` | nearby lines + distance |
| 5 | Latitude crossings: two glyphs, label, north/south, "≈ 70 km" | `parans_display` | — |
| 6 | Reading sections in API order with API titles (overview, lines here, background influences, positive influences, potential challenges, life areas that shift here) | `reading.sections` | general analysis, positives, challenges |
| 7 | Footer (fixed text) | `footer` | — |

Actions: **Ask about {place}** (Ask with `context.place_id`), **Share** (text of the overview + footer + app link),
**Open country report**. The report is saved automatically (Saved reports).

Chrome copy for the 5-band grade (never yes/no): the band label from the API is the verdict; the app adds no
"Recommended" / "Avoid" badges.

### 5.2 Country and region reports — `/acg/countries/{iso2}`, `/acg/regions/{admin1_id}`

| Order | Block | Binding |
|---|---|---|
| 1 | Name (+ country for a region) | `area` |
| 2 | Bands grid: 11 goals, the 6 card goals first | `bands` |
| 3 | "Varies by region" notice when true | `varies_by_region` |
| 4 | Overview text | `overview` (GeneratedPart) |
| 5 | Lines crossing this country | `lines_crossing` |
| 6 | Best cities: goal chips → top 3 cities with band chips → city report | `best_cities` |
| 7 | Regions (countries only) → region report | `regions` |
| 8 | Footer | `footer` |

## 6. "Where should I go?" (`map/recommend`, brief §10 premium feature, available to all per F4)

### 6.1 Ask
- **Goal:** chips for **Overall** + the 11 goals; or a free-text field "Ask in your own words" (e.g. "Kariyer için
  en iyi yer neresi?") sent as `query_text`.
- **Scope:** World (default) · Türkiye · a country (picker).
- **Refine** (collapsed by default; every filter has a default, ACG_11 §4): regions (10 chips, default all) · city
  size (big / mid / small; default big + mid) · max distance from home (off, 500, 1,000, 2,000, 3,000, 5,000 km;
  default off) · climate (warm / mild / cold; default not applied) · purpose (Auto = derived from the goal, living,
  travel, both).
- **Find places** → `POST /acg/recommendations` → result screen.

### 6.2 Result (`map/recommend/result`)
- `status: needs_goal` → "Which of these did you mean?" with `goal_options` chips → re-submit with the goal.
  Never guess.
- `status: thin_result` → a quiet note "Only a few places stand out for this goal." above the (short) list.
  No padding.
- Header: goal label, scope, and the applied filters as removable chips (`filters_applied`) + **Change filters**.
- Intro text (`explanations.intro`; skeleton while pending).
- **List | Map** toggle. Map: pins coloured by band; the lines of `by_line` emphasised, other lines dimmed.
- **By line** groups (ACG_11): group header with the planet glyph and `title`, the group text
  (`explanations.groups[group_id]`), then destination cards: name, flag, size chip, `BandChip`, "≈ 60 km from the
  line", a "Has a demanding side" chip if `has_tradeoff`, and the text (`explanations.items[place_id]`).
  Tap → city report with `focus_goal = goal`.
- **Lines without destinations:** each as a quiet row with its fixed text (honest, never hidden).
- **In Türkiye:** always shown for world scope: its intro (`explanations.turkey_intro`), places and regions, even
  when nothing qualifies (the intro then says so; ACG_09 §3.4).
- **Countries and regions:** chips with band → area report.
- `goal = overall`: the flat `places` list with `summary_label` ("Supportive for 7 goals") instead of line groups.
- Footer (fixed text).
- The result is cached and listed in Saved reports.

## 7. Copy and data rules (map-specific)
- Never show coordinates, degrees, orbs or scores. Distances only as "≈ N km" / "< 10 km" from the API's rounded
  values. A spot report is titled "Selected spot" + the country name.
- No "move here" / "avoid" wording in chrome; the API band label is the grade.
- Planet and angle names come from the catalogue (Rising / Setting / Culminating / Root line).

## 8. Lines list (accessible alternative)
Full-screen list grouped by planet (10 + nodes when enabled): each line with its angle label and "Places on this
line" (§4.1). Every map feature is reachable from this list and the search, without the map.

## 9. Performance
- Lines + parans ≤ 150 KB gzipped; heat cells built in < 150 ms per goal; pan / zoom at 60 fps on a mid-range
  Android with lines + one heat layer.
- City report deterministic block: p50 < 500 ms from the per-chart cache.

## 10. Acceptance

| # | Check |
|---|---|
| MP1 | Lines render with the right colour per planet and style per angle; nodes appear only with the toggle; attribution is visible. |
| MP2 | Selecting each of the 11 goals shows the heat layer with 4 levels and the legend; "Lines" removes it; the selected goal is sent as `focus_goal`. |
| MP3 | Tap priority: a tap on a line opens the line sheet even over a city; zoom < 3.5 opens countries; long press opens a spot report. |
| MP4 | City report: 6 cards (7 with a non-card focus goal) in order; `no_emphasis` cards show their fixed text at once; other card texts fill in when the reading completes; lines nearby show "≈ N km" and "< 10 km". |
| MP5 | The `absent_polar` scenario shows the relocation notice and still renders lines and the reading. |
| MP6 | Recommender: `needs_goal` shows options and never auto-picks; `thin_result` shows the note without padding; Türkiye block present for world scope; lines without destinations are listed. |
| MP7 | No string on the map screens contains a digit adjacent to "°" or a coordinate pattern; distances always carry "≈" or "<". |
| MP8 | Performance budget §9 met in the preview build on the reference Android device. |
