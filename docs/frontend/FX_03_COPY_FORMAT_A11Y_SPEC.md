# FX 03: Copy, formatting and accessibility (Phase 3)

*Goal: no internal formats or jargon on screen, ratings that read without colour, and a complete screen-reader
pass. Ground rules: FX_00 §2. Uses `BandChip`, `Skeleton`, `IconButton` from FX2.1.*

| Item | Title | Size |
|---|---|---|
| FX3.1 | Dates in the user's language | S |
| FX3.2 | Country names and city sizes | S |
| FX3.3 | Report and reading titles | S |
| FX3.4 | Bands everywhere through `BandChip` | S |
| FX3.5 | "No clear emphasis" said once | XS |
| FX3.6 | Calendar and Best Days grids: less noise, a legend | S |
| FX3.7 | Loading placeholders | XS |
| FX3.8 | Accessibility pass | M |
| FX3.9 | Best Day detail | S |
| FX3.10 | Small copy fixes | XS |

---

## FX3.1 Dates in the user's language

**Problem**
Raw ISO strings are shown as titles and labels:
- `CalendarScreen.tsx`: month title `{month}` → "2026-10".
- `BestDaysScreen.tsx`: month headers `{month}` → "2026-10", "2026-11"; the activity list shows the next date as
  "2026-10-21 · 12 good or excellent days" (acceptance screenshot).
- `DayScreen.tsx`: `<Screen back title={date}>` → "2026-10-03".
- `BestDayScreen.tsx`: `<Txt>{date}</Txt>` → "2026-10-21".
- Year view range "2026-10-01 – 2027-09-30"; month forecast screen title "2026-10".
`src/lib/dates.ts` already has `formatDate(date, lang)`; `AheadScreen` formats its month title correctly with
`Intl.DateTimeFormat`.

**Change**
1. `src/lib/dates.ts`: add `formatMonth("2026-10", lang)` → "October 2026" / "Ekim 2026";
   `formatDay(date, lang, { weekday })` → "Saturday, 3 October" / "3 Ekim Cumartesi";
   `formatShort(date, lang)` → "3 Oct" / "3 Eki"; `formatRange(a, b, lang)` with compaction ("9–14 Oct",
   "28 Sep – 3 Oct", "1 Oct 2026 – 30 Sep 2027"). Calendar dates are formatted in UTC from the date string (as
   `formatDate` does) so time zones never shift the day.
2. Use them everywhere a date or month is displayed. Weekday names in grid headers come from the same locale.
3. Test (like FE_07 MP7): render Calendar, Best Days, Best Day, Day, Month, Year and Saved reports with fixtures
   and assert no rendered text matches `/\b\d{4}-\d{2}(-\d{2})?\b/`.

**Acceptance:** the test passes in `en` and `tr`; screenshots of Calendar and Best Days headers.

---

## FX3.2 Country names and city sizes

**Problem**
- `LineScreen.tsx`: `${p.country_code} · ${distance} · ${tier}` → "FO · ≈ 20 km · …".
- `PlaceScreen.tsx`: the country code alone under the city name ("Tórshavn / FO").
- `RecommendResultScreen.tsx`: `${p.country_code} · ${t(p.size)} · …` → "RU · Big · Supportive for 6 goals ·
  challenging for 1".
FE_07 §4.1 and §6.2 specify name + flag and a size chip.

**Change**
1. `countryName(iso2, lang)`: use the API's `country_name` where the response has it; otherwise a generated map
   `src/i18n/countries.json` (`{ "AD": { "en": "Andorra", "tr": "Andorra" }, … }`) built by a new script from the
   `name_en` / `name_tr` properties of `mock-api/fixtures/geo-countries.json` (239 features). Do not rely on
   `Intl.DisplayNames` (not available in Hermes).
2. Flag: emoji from the ISO code (regional indicator letters); hidden from screen readers.
3. Display: city title "Tórshavn", subtitle "🇫🇴 Faroe Islands"; list rows "🇷🇺 Russia · Large city".
4. City size labels: big → "Large city" / "Büyük şehir", mid → "Mid-size city" / "Orta büyüklükte şehir",
   small → "Small town" / "Küçük şehir"; rendered as a small neutral chip in cards.
5. Recommendation rows: band via `BandChip` and the API `summary_label` as the second line, not concatenated with
   the country.

**Acceptance:** no visible two-letter country code anywhere (manual pass of line, place, recommendation, area
screens + a test on the three row renderers).

---

## FX3.3 Report and reading titles

**Problem**
The compatibility report is titled with the model's own heading in capitals, "RELATIONSHIP READING — PERSONAL":
the local API sets the report title from `r.readings[lang].title` (`local-api/compatibility-jobs.ts`, `reports`),
and `MatchReportScreen.tsx` renders `reading.title` as the screen heading. In Saved reports the delete button
repeats it in capitals.

**Change**
1. Local API `reports()` for compatibility: title from chrome by type ("Love compatibility" / "Aşk uyumu",
   "Work compatibility" / "İş uyumu", "Family compatibility" / "Aile uyumu"); subtitle "A & B".
2. `MatchReportScreen`: heading "A & B" with the type `Segmented` / chip; the model's `title` is not shown as a
   heading (do not change model text; FE_01 C3).
3. Check the other report types use chrome titles ("Yearly forecast · October 2026" is fine); place reports:
   "{City}, {Country}" with subtitle "Place report".

**Acceptance:** Saved reports and the compatibility screen show no all-caps model titles (screenshot).

---

## FX3.4 Bands everywhere through `BandChip`

**Problem**
Bands, tones and grades are plain text under titles ("Mixed", "Supportive", "Strongly supportive", "Good" as a
heading in `BestDayScreen.tsx`, `tone_label` as a title in `DayScreen.tsx`, `${goal} · ${label}` text in
`PlaceScreen.tsx`). Meaning is carried by wording or colour only in places (calendar rings), against FE_01 §9.

**Change**
Render every band / tone / grade label through `BandChip`: `Score` block (`Blocks.tsx`), place cards and
"Other life areas" (`PlaceScreen.tsx`), area bands grid, recommendation rows, Today tiles (FX2.5), Day detail tone,
Best Day grade, Best Days activity rows (next good day), map legend (FX2.9).

**Acceptance:** `grep` for `band_label`, `tone_label`, `grade_label` outside `BandChip` and accessibility labels
returns nothing; screenshots in light and dark.

---

## FX3.5 "No clear emphasis" said once

**Problem**
A place card with band `no_emphasis` shows the label "No clear emphasis" and then the fixed text "No clear
emphasis. For this goal, the place adds no particular emphasis…" (acceptance screenshot).

**Change**
For `no_emphasis` cards render the fixed text only (no chip, no separate label). Do not edit the API text.

**Acceptance:** the For travel card in the Tórshavn fixture shows the phrase once.

---

## FX3.6 Calendar and Best Days grids: less noise, a legend

**Problem**
In `MonthGrid` every day of the month carries a coloured ring (most days are "mixed", so the screen is a wall of
amber circles) and there is no legend for rings or micro-icons. The Best Days activity grid has no legend either.
The month navigator is two outlined buttons around a raw ISO month.

**Change** (amends FE_08 §2.1 and CB1)
1. Calendar rings only for favourable (`plus`) and challenging (`minus`); mixed and quiet days have no ring.
   With a goal filter selected, rings follow the goal's band the same way.
2. Today: bold number + accent dot; the selected day: filled `accentSoft`.
3. Legend row under the grid: ring samples (Favourable, Challenging) and the micro-icons in use (new / full moon,
   eclipse, station). Icons at least 10 pt, ≥ 3:1 contrast.
4. Month navigator: `DatePager` in month mode with the FX3.1 month label.
5. Best Days activity grids: legend (Excellent, Good, Avoid) using the same symbols; avoid days keep the hatched
   outline (FE_08 §5.2).
6. Day cell accessibility label: "3 October, favourable, full moon".

**Acceptance:** CB1 (amended) passes; screenshot of October 2026 with the legend; TalkBack reads a day cell with
its tone and icons.

---

## FX3.7 Loading placeholders

**Problem**
`Skeleton` is three 64 pt grey blocks with a hard-coded English label "Loading". Place cards waiting for text show
three such blocks each (acceptance screenshot), which looks heavier than the content.

**Change**
Use `Skeleton` `lines` for pending text (two lines for a card text, FE_07 §5.1 MP4; three for a reading
paragraph) and `block` only for whole cards. Label from the new `loading` key (FX2.1).

**Acceptance:** no hard-coded "Loading" string; place report screenshot while pending.

---

## FX3.8 Accessibility pass

**Problem**
About 20 `accessibilityLabel`s exist in the whole app. Icon-only controls added in Phase 2 need labels. `Chip`
uses `accessibilityRole="radio"` with `accessibilityState={{ selected }}`; radios expose `checked`.

**Change**
1. Every icon-only control has a localised label and role (`IconButton` enforces it).
2. `Chip`: single-choice groups use role `radio` + `checked`, inside a container with role `radiogroup`;
   multi-select chips (map layers, filters) use role `checkbox` + `checked`.
3. Lists and grids expose meaningful labels (day cells FX3.6, tiles FX2.5, report rows "Tórshavn, place report,
   3 October").
4. Font scaling: check every screen at the largest Android font size; nothing clips or overlaps. Limit
   `maxFontSizeMultiplier` (1.3) only on tab bar labels and wheel glyph labels.
5. Reduce motion: no shimmer, no animated sheet springs, instant toasts.
6. Streaming chat (when Ask is enabled): announce the answer when complete, not per token (FE_09 AK7).

**Acceptance**
- A render test walks Home, Chart, Ahead (all four views), Map, place report and Saved reports and fails on any
  pressable without an accessible name.
- Manual TalkBack pass of the same screens; findings listed in the phase report.
- Screenshots at the largest font size for Today and the place report.

---

## FX3.9 Best Day detail

**Problem**
`BestDayScreen.tsx` renders What helps / What makes it harder only when `reasons` are present; in local mode they
are empty, so the screen shows only the activity, a raw date, the grade as a heading and "Remind me" (acceptance
screenshot).

**Change**
1. Check whether the local API's Best Days details (`calendarFor(...).bestDetails`) pass the positive and negative
   reason labels from the Best Days engine output (CAL_04). If the engine provides them, map them; if not, record
   it as a backend gap in the phase report (do not invent reasons).
2. Layout: header with activity title; formatted date (FX3.1) and `BandChip` grade; reasons when present (C1:
   omit empty sections); the text when present; actions "Remind me" (primary), "See in calendar" (→ Calendar month
   with the day selected), and "Ask about this day" when Ask is enabled.

**Acceptance:** with the mock fixture the reasons render; with empty reasons the screen shows date, grade chip
and actions, with no empty headings.

---

## FX3.10 Small copy fixes

| Where | Now | Change to |
|---|---|---|
| Recommendation filter chip | "Purpose: Both" | "For living and travel" |
| Recommendation filter chip | "City size: Big" | "Large cities" |
| Map search field | label above an empty grey box | placeholder inside the field + search icon (FX2.9) |
| Chart note | "Your reading is saved automatically. You can come back to it from Saved reports." shown above the button | show once, under the reading, as a caption |
| Retrograde chips on Day detail (`DayScreen.tsx`) | one radio-role `Chip` per planet ("Neptune · Retrograde"), each opening the Chart tab | one line "Retrograde: Neptune, Pluto, Saturn, Uranus, Venus"; if a link is wanted, rows to the retrograde period item (`calendar/item/[id]`), not the Chart tab |

**Acceptance:** screenshots of the changed places.
