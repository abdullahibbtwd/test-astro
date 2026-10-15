# FE 04: Home, Today, Month, Year, Solar Return

*Brief §6 (daily), §7 (monthly), §8 (yearly + Solar Return), §14 (Home). API: FE_02 §7.3–7.5.
The forecasts are personal (transits to the natal chart), never sun-sign horoscopes (brief §6, §20).*

## 1. Shared pieces

### 1.1 Lens control
Segmented control on Today, Month, Year: **General · Love & relationships · Work & career** (API `lens`:
`general` · `personal` · `professional`; labels from `catalogue.lenses`). The last choice persists per horizon.
Switching lens refetches only the `reading` part; deterministic blocks stay on screen.

### 1.2 `ScoreMeter`
A compact 10-segment horizontal bar: filled segments = `score_10`, fill colour = the band level (FE_01 §5.2), the
number in tabular `title2`, the band/tone label under it. With flag `dayScoreNumbers` off, hide the number and the
bar; show only the `BandChip`. Accessibility label: "Aşk: 8 / 10, Destekleyici".

### 1.3 Rows
- `TransitRow`: planet glyph pair + aspect glyph, `label` ("Saturn conjunct your Sun"), `phase_label` chip, the date
  range ("9 Eki – 7 Şub"), chevron if `has_text` → `calendar/item/[id]`.
- `PeriodRow`: goal icon, `label`, kind chip (favourable / demanding, band colours `plus` / `minus`), date range →
  `calendar/item/[id]`.
- `EventRow` (lunation, eclipse, station, ingress, retrograde): kind icon, `label`, date → `calendar/item/[id]`.

### 1.4 Profile switcher
The Ahead tab header shows the `ProfileSwitcher`; forecasts can be read for any saved profile. Dates use that
profile's effective time zone (FE_02 §7.1).

## 2. Home (tab 1)

Always the self profile, today. One request: `GET /home`.

| Order | Block | Content | Binding |
|---|---|---|---|
| 1 | Header | avatar (→ profile menu), Ask button | — |
| 2 | Greeting | TR "Günaydın, {name}" 05:00–11:59 · "İyi günler, {name}" 12:00–17:59 · "İyi akşamlar, {name}" 18:00–04:59; EN "Good morning / afternoon / evening, {name}" (in `me.current_place.tz`) | `greeting_name` |
| 3 | Date line | "Çarşamba, 30 Eylül" + moon chip: phase glyph, `phase_label · sign_label` | `date`, `moon` |
| 4 | **Your Day** card | overall `ScoreMeter` (tone) + 4 tiles: Love, Career, Money, Family (O2; Energy only with flag `homeEnergyTile` when the API sends a tile with `key: 'energy'`) | `tone`, `tone_label`, `score_10`, `tiles[]` |
| 5 | **Today's Astrology** | serif excerpt of the day reading (first paragraph, max 5 lines) + **Read more** → Today | `today` (GeneratedPart) |
| 6 | Coming up | ≤ 3 `UpcomingItem` rows: date chip + `label` → deep link (FE_08 §6.4) | `next_up` |
| 7 | Quick access | 4 buttons (brief §14): **My Chart** · **Today** · **Compatibility** · **Astro Map** | routes |
| 8 | Ask card | a field-shaped button "Ask about your day…" → Ask with context `{ date: today }` | FE_09 |

- A tile tap opens Today scrolled to that life area.
- `today.status = pending` → a two-line skeleton + a one-line `JobProgress`; the rest of Home is interactive.
- Pull to refresh refetches `/home`. At local midnight (current tz) Home refetches when foregrounded.

## 3. Today (Ahead → Today)

`GET /profiles/{id}/forecast/day?date=&lens=`. Date navigator: ‹ previous day · **Today** · next day › and a date
picker (today − 7 … today + 365; the API returns `out_of_range` beyond).

Brief §6 asks for: main energy, love, family, work, money, communication, emotional state, important transits,
advice. Mapping:

| Order | Block | Content | Binding | Brief item |
|---|---|---|---|---|
| 1 | Day at a glance | `ScoreMeter` (tone) + `day_note` in serif if present | `tone*`, `score_10`, `day_note` | — |
| 2 | Main energy of the day | the day reading, serif | `reading.text` | main energy |
| 3 | Life areas today | grid of all 11 areas; first row Love · Family · Career · Money (brief order), then the other 7. Tile: goal label, `BandChip`, `score_10`. Tap → sheet listing `drivers` (transit labels) + "Open in calendar" | `areas` | love, family, work, money |
| 4 | By topic *(NEW, render-if-present)* | cards for love, family, work, money, communication, emotions, each `title` + serif `text` | `domains` | communication, emotional state (+ richer love/family/work/money) |
| 5 | Important transits | `TransitRow` list (major first, then moderate), then the day's `events` as `EventRow`s | `transits`, `events` | important transits |
| 6 | The Moon today | phase glyph + label, sign, void-of-course windows ("05:41–22:54"), retrograde planets as glyph chips | `moon`, `retrograde` | — |
| 7 | Advice *(NEW, render-if-present)* | one highlighted serif paragraph | `advice` | advice |
| 8 | Good for today | activity chips with grade → `best-days/[activity]/[date]` | `best_activities` | links to Best Days |

- Empty `transits` and `events` → the block shows one quiet line ("No major transits today.").
- Changing the date keeps the lens and scroll position of the header.
- Premium/free differences from the brief are ignored (F4): everyone sees the full day, including the transit list.

## 4. Month (Ahead → Month)

`GET /profiles/{id}/forecast/month?month=YYYY-MM&lens=`. Month navigator ‹ Ekim 2026 › from the current month to
+11 months (calendar horizon).

| Order | Block | Content | Binding | Brief §7 item |
|---|---|---|---|---|
| 1 | Main theme | serif `overview` | `reading.overview` | main theme |
| 2 | Focus | heading `focus_title` (depends on lens) + serif `focus` | `reading.focus*` | love / work / career via lens |
| 3 | The month in three parts | vertical 3-step timeline: "1–10 Ekim" `early` · "11–20 Ekim" `mid` · "21–31 Ekim" `late` | `segments`, `reading.early/mid/late` | important periods |
| 4 | By topic *(NEW, render-if-present)* | love, family, work, career, money, social, travel | `domains` | love, family, work, career, money, social, travel |
| 5 | Most favourable days | date chips (`plus` colour), tap → calendar day | `highlights.favorable_days` | most favourable days |
| 6 | More demanding days | date chips (`minus` colour) | `highlights.challenging_days` | tense days |
| 7 | Important periods | `PeriodRow` list | `highlights.periods` | important periods |
| 8 | Important transits | `TransitRow` list | `highlights.major_transits` | important transits |
| 9 | Sky events | new / full moons, eclipses, retrogrades as `EventRow`s, by date | `highlights.lunations/eclipses/retrogrades` | — |
| 10 | Link | "Open October in the calendar" → Calendar at that month | — | — |

The reading is a `GeneratedPart`: blocks 5–9 render immediately; blocks 1–3 show skeletons with `JobProgress`
until ready. Empty day lists are hidden (C1), not shown as "none".

## 5. Year (Ahead → Year)

`GET /profiles/{id}/forecast/year?from=YYYY-MM&lens=`. Header: "Next 12 months · Ekim 2026 – Eylül 2027".

| Order | Block | Content | Binding | Brief §8 item |
|---|---|---|---|---|
| 1 | Theme of the year | serif `overview` | `reading.overview` | main theme |
| 2 | Focus | `focus_title` + `focus` | `reading.focus*` | via lens |
| 3 | Four seasons of your year | 4-step timeline with date ranges → `q1`…`q4` | `quarters`, `reading.q1..q4` | — |
| 4 | By topic *(NEW, render-if-present)* | personal growth, love, family, career, business, money, home & property, travel, social | `domains` | those items |
| 5 | Strongest periods | `PeriodRow`s | `highlights.strongest_periods` | strongest periods |
| 6 | More challenging periods | `PeriodRow`s | `highlights.challenging_periods` | challenging periods |
| 7 | Key astrological events | `EventRow` / `TransitRow` list | `highlights.key_events`, `retrogrades` | important events |
| 8 | Month by month | 12 rows (month label) → `forecast/month/[month]` (generated on first open) | `months` | month by month, 12 months |
| 9 | Solar Return | a card "Your solar return {year}" → §6 (flag `solarReturn`) | — | Solar Return |

`forecast/month/[month]` is the Month screen (§4) with a fixed month and a back button.

## 6. Solar Return (`solar-return/[year]`, flag `solarReturn`, API NEW)

- Header: `terms.solar_return` + year; the return moment formatted in the viewer's tz ("28 Aralık 2026, 14:12")
  and the place.
- Place selector: "Where will you be on your birthday?" (`PlaceSearchField kind=city`, default the effective
  current place). Changing it refetches (`place_id`).
- The return chart drawn with the same wheel component as FE_05 (static and tappable for facts; no element notes).
- `reading.sections` as `ReadingSection`s (API order and titles).
- Year switch: this year's return and next year's.
- `404` (endpoint not live) → the Year screen hides the card (flag behaviour).

## 7. Acceptance

| # | Check |
|---|---|
| HF1 | Home renders from one `/home` call; greeting changes at 12:00 and 18:00 in `me.current_place.tz`, not device tz (test with device tz ≠ current place tz). |
| HF2 | Home shows Love, Career, Money, Family tiles by default; with flag `homeEnergyTile` and an `energy` tile in the fixture it shows Energy instead of Family. |
| HF3 | With `dayScoreNumbers` off, no x/10 number appears anywhere; band chips remain. |
| HF4 | Today: all 11 areas render with the brief's four first; `domains` / `advice` blocks appear only with the NEW fixture and leave no gap without it. |
| HF5 | Lens switch on Today / Month / Year refetches only the reading; deterministic blocks do not flash. |
| HF6 | Month: favourable / demanding day chips open the calendar day; beats show the correct date ranges for 30- and 31-day months and February. |
| HF7 | Year: month-by-month rows open month forecasts that show `JobProgress` on first open and cache afterwards. |
| HF8 | Solar Return: hidden under the `new_off` scenario; with the fixture, the place change refetches and the wheel renders. |
| HF9 | Reading pending on any screen never blocks scrolling, navigation or the date/month navigators. |
