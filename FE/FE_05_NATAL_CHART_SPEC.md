# FE 05: My Chart (wheel, reading, tables, export and share)

*Brief §3 (natal reading), §4 (graphic wheel + interactivity), §5 (download / export / share), §17 (the wheel is
generated dynamically from structured data, sharp on screen, in PDF and in high-res images). API: FE_02 §7.2.
Wheel source of truth: `Chart_wheel/CHART_WHEEL_SPEC.md` (LOCKED decisions §3, §7, §9) and `Chart_wheel/src/*.js`.*

## 1. Screen layout (Chart tab)

```
Header:   ProfileSwitcher · "…" (export / share menu) · Ask
Big three row:  ☉ Oğlak   ☽ Başak   AC Koç          (tap = select on the wheel)
Wheel (square, full width; pinch-zoom 1×–3×, pan; ⤢ = focus mode full screen)
Legend (one line): aspect families
Tabs:     Reading · Planets · Houses · Aspects
```

Data: `GET /profiles/{id}/chart` (instant) and `GET /profiles/{id}/natal-reading` (may be `202`). The wheel,
big three and the three tables never wait for the reading (F12).

## 2. The wheel engine: `packages/wheel-core`

### 2.1 Port, don't redesign
Port `Chart_wheel/src/` (`constants`, `transform`, `spread`, `glyphs`, `theme`, `render`, `invariants`) to
TypeScript **without changing behaviour**. The spec's locked decisions apply unchanged: Ascendant at screen-left,
equal 30° zodiac ring, Placidus cusps at true longitude, the 6° spreading pass (isotonic version), modern-scheme
aspects only, hub colours by family with the soft-aspect floor, ℞ never on nodes, South Node faint, no Lot of
Fortune, no static degree labels, no applying/separating styling, bundled vector glyphs only (no Unicode, no astro
fonts), the §8 invariants.

### 2.2 Refactor into a model + renderers
```
computeWheel(input, opts) → WheelModel     pure geometry: rings, ticks, cusp lines, house-number positions,
                                           points {body, trueLon, displayLon, glyph centre, pointer line,
                                           retro mark, faint}, chords {a, b, type, family, x1..y2, opacity,
                                           width}, axes lines, axis-label positions
renderChart(input, opts) → string          the canonical SVG (CSS-variable theming) — built on computeWheel,
                                           byte-identical to today's Node output
renderChartResolved(input, opts) → string  same geometry with concrete colours / fonts inlined (no <style>,
                                           no var()) — for Skia rasterisation (§6)
<Wheel model theme interactive … />        React Native component (react-native-svg) drawing WheelModel
```
Why three outputs: `react-native-svg` and Skia do not support `<style>` blocks or CSS custom properties, while the
PDF path (a WebView) does. All three read the same `WheelModel`, so geometry cannot drift.

Add (outside the canonical output) the five **aspect glyphs** (conjunction, sextile, square, trine, opposition) in
the same stroke style as `glyphs.js`, for legends, tables and the interactive layer.

### 2.3 Adapter
`toWheelInput(chart: ChartData)` rebuilds the renderer's input (§1 "Consumed" fields of the wheel spec):
`points[].name` (canonical English: "Sun" … "North Node"), `longitude`, `degree_in_sign`, `sign` (canonical English,
capitalised), `retrograde`, `sector.placidus` (= `house`); `axes.ascendant` / `axes.mc`;
`sectors.placidus_cusps` (= `houses[].cusp_longitude`); `relations[]` with `scheme: "modern"`, `source`, `target`,
`type`, `orb`, in API order. Nothing else.

### 2.4 Themes
Use the wheel's own `light` / `dark` token presets. The app's `bg` tokens equal the wheel's `--bg` by design
(FE_01 §5.2), so the wheel sits directly on the screen background.

### 2.5 Parity tests (Phase 2 gate)

| # | Check |
|---|---|
| W1 | For each fixture chart (FE_02 §11: 1988-12-28, 1984-06-12, 1979-03-30), `renderChart(toWheelInput(mockChartData), {theme})` is **byte-identical** to the backend's `chart_wheel_*.{light,dark}.svg`. (This also proves the API mapping keeps order and precision.) |
| W2 | `renderChart` is implemented on top of `computeWheel` (no second geometry path). |
| W3 | The ported §8 invariant gate passes for all fixtures (determinism, completeness, aspect fidelity, Asc anchor, no overlap, node ℞, mask). |
| W4 | The RN `<Wheel>` positions (glyph centres, cusp endpoints, chord endpoints) equal `WheelModel` values (snapshot of the rendered element props), within 0.001. |

## 3. Interaction (brief §4: tap planet → sign → house → aspect)

### 3.1 Hit testing (in `WheelModel` coordinates, 1000-unit viewBox)
Convert the touch point to viewBox coordinates (account for zoom/pan), then to radius `r` and ecliptic longitude
with the inverse of the locked transform (`lambda = asc + (theta − 180)`).

| Target | Hit rule |
|---|---|
| Planet / node | nearest glyph centre within 30 units (≈ 44 pt at 3× zoom; see tolerance below) |
| Axis label (AC, DC, MC, IC) | within 24 units of the label |
| Sign | `410 ≤ r ≤ 460` → sign of `lambda` |
| House | `236 < r < 396` and no planet hit → the house whose cusp interval contains `lambda` |
| Aspect | `r ≤ 236` → nearest chord by point-to-segment distance within 12 units |

Touch tolerance scales with zoom so the effective target is ≥ 44 pt on screen. When 2+ planets fall inside the
tolerance (stelliums), show a small popover listing them (glyph + name) instead of guessing.

### 3.2 Selection state (interactive layer only; the static render is untouched)
- **Planet:** accent ring around the glyph; its chords at full strength with the aspect glyph at each chord
  midpoint; every other chord dimmed to 0.15 opacity.
- **Sign:** the sign's 30° sector tinted `accentSoft`; planets in it emphasised.
- **House:** the wedge between its two cusps tinted `accentSoft`; planets in it emphasised.
- **Aspect:** the chord + both planets emphasised, aspect glyph at the midpoint.
- **Axis:** the axis line emphasised.
Tapping empty space or the sheet's close button clears the selection. Selection animates (≤ 200 ms).

### 3.3 Detail sheet (bottom sheet, 2 snap points)
The sheet is the "drill path": every fact is a chip that moves the selection.

| Selection | Facts (from `ChartData` + catalogue; chrome only, no interpretation) | Interpretation block |
|---|---|---|
| Planet | glyph + name; `6°56′` + sign chip; house chip ("9. Ev · Uzak Seyahatler ve Felsefe"); `terms.retrograde` chip if retrograde (never for nodes); list of its aspects (other body + aspect glyph + name + orb `1°46′`), each tappable | §3.4 |
| Sign | sign name; planets in the sign (chips); houses whose cusp is in the sign | §3.4 (element note only; no fallback text for an empty sign) |
| House | ordinal + name; cusp sign chip + degree; rulers (glyph chips); planets in the house (chips) | the **house section of the reading** in full (`sections[house == n]`), or the element note |
| Aspect | body A chip · aspect name · body B chip; orb | §3.4 |
| AC / MC | sign chip + degree ("Yükselen · 29°17′ Koç") | element note, else links to `core_identity` + `identity` (AC) / `status_vocation` (MC) |

### 3.4 Interpretation source
- Flag `elementNotes` **on** and `GET /chart/elements` ready → show the note (`ElementNote.text`, serif) and, if
  `section_key` is set, "Read more in {section title}".
- Otherwise (flag off, `404`, or pending) → **section links**, never client-written text (F8):

| Body | Section links (title + the section's first 2 lines as a teaser) |
|---|---|
| sun | `sun_house`, `core_identity` |
| moon | `moon_house`, `core_identity` |
| mercury, venus, mars | the house section of the body's house, `inner_drives` |
| jupiter, saturn, uranus, neptune, pluto, north_node, south_node | the house section of the body's house, `chart_shape` |
| aspect | the sections of both bodies (by the rows above), de-duplicated |
| sign | the sections of the bodies in the sign |

A link opens `chart/section/[key]` (the section screen) or scrolls the Reading tab to it.

### 3.5 Focus mode
⤢ opens the wheel full screen (landscape allowed), zoom 1×–4×, the same hit testing and sheet. The static render
stays crisp at any zoom (vector).

## 4. Reading tab (brief §3)

- Document title (`NatalReading.title`) as a quiet overline; parts as headers ("BİRİNCİ BÖLÜM — Kim Olduğun" /
  "PART ONE — Who You Are"), then `ReadingSection`s in API order with API titles.
- The first section expanded, the rest collapsed with a two-line serif teaser; **Expand all**.
- A contents button opens a sheet listing section titles → jump.
- Each section: Copy, Share (FE_01 C10); `chart/section/[key]` is deep-linkable (used by §3.4 and Ask).
- Pending (the self profile's reading right after onboarding, or a new profile): a `JobProgress` card in place of
  the sections, with the tables still usable.
- Brief §3 topic coverage comes from the backend's 17 sections (core identity, luminaries, drives, chart shape,
  12 life-area sections). The app shows everything to everyone (F4); it adds no topic headings of its own.

## 5. Tables (accessible alternative to the wheel; brief §3 premium list)

| Tab | Rows | Columns |
|---|---|---|
| Planets | 12 bodies in wheel order | glyph · name · sign glyph + sign · `6°56′` · house ordinal · ℞ (planets only) |
| Houses | 1–12 | ordinal + name · cusp sign + degree · rulers (glyphs) · planets (glyphs) |
| Aspects | grouped by type: conjunction, opposition, square, trine, sextile | body A · aspect glyph · body B · orb |

Row tap → select on the wheel (scroll up) and open the sheet. The aspect set is what the backend computes (the five
major aspects, modern scheme); the app adds none.

Legend line under the wheel (chrome): swatch + aspect glyphs per family — TR "Gerilimli (kare, karşıt)",
"Akıcı (üçgen, altmışlık)", "Kavuşum"; EN "Tense (square, opposition)", "Flowing (trine, sextile)", "Conjunction".

## 6. Export and share (brief §5, F16)

Menu "…" in the header:

| Action | Output | How |
|---|---|---|
| **Download chart** | PNG or JPG (user picks; default PNG), 2048 × 2400 px: the wheel (2048 px square) + a caption band (name, birth date, time, place; small `{{APP_NAME}}` wordmark) | `renderChartResolved` + caption drawn in Skia; save to Photos (`expo-media-library`) or share |
| **Download PDF** | A4 portrait: title, name, birth data, the wheel as **vector SVG**, big three, Planets / Houses / Aspects tables, disclaimer, wordmark | HTML template + canonical `renderChart` SVG inline → `expo-print` |
| **Download full report** | A4 PDF: cover (name, birth data, wheel), contents, both parts with every section (serif), the three tables as an appendix, disclaimer | same pipeline; needs the reading ready (button shows progress if pending) |
| **Share chart** | branded share card, 1080 × 1350 (feed) or 1080 × 1920 (story): wheel, name, big three with glyphs, wordmark + short URL | an off-screen React view captured with `react-native-view-shot` → `expo-sharing` |

- Theme: exports default to the **light** wheel; a toggle offers dark for PNG and the share card.
- Language: the current app language.
- Fonts: the PDF HTML embeds Inter and Source Serif 4 via `@font-face` (base64 from the bundled assets) so Turkish
  characters render identically on iOS and Android.
- File names: `{label}-dogum-haritasi.pdf` (TR) / `{label}-birth-chart.pdf` (EN), label ASCII-folded
  (ç→c, ğ→g, ı→i, İ→I, ö→o, ş→s, ü→u) and slugified.
- **Share privacy:** the share card shows the name and big three only. Birth date, time and place are **off by
  default** (toggle "Include birth details").
- Sharing targets (WhatsApp, Instagram, Messenger, email, other apps; brief §5) are reached through the native
  share sheet. No per-app SDKs in v1.
- Performance: PNG < 1.5 s, chart PDF < 3 s, full report PDF < 6 s on a mid-range Android.

## 7. States
- Chart loading: wheel skeleton (hairline rings only). Chart error: ErrorState; tables hidden.
- Reading pending / failed: §4; export "full report" disabled with the reason.
- Offline: cached chart and reading render with `StaleBadge`; exports still work (on-device).

## 8. Accessibility
- The wheel: `accessibilityLabel` "Doğum haritası çarkı" / "Birth chart wheel", hint "Use the Planets, Houses and
  Aspects tabs for details". With a screen reader active, planet glyphs are focusable elements labelled
  "Güneş, 6°56′ Oğlak, 9. Ev" (comma-separated facts; no composed Turkish suffixes).
- The tables are the complete non-visual equivalent of the wheel.

## 9. Acceptance

| # | Check |
|---|---|
| NC1 | W1–W4 pass (§2.5). |
| NC2 | Tapping each of the 12 bodies, 12 signs, 12 houses, the four axis labels and every chord on the 1988-12-28 fixture selects the right element at 1× and 3× zoom on a 375-pt-wide screen; the Capricorn stellium (Sun, Saturn, Uranus, Neptune) triggers the disambiguation popover at 1×. |
| NC3 | The drill path works: planet sheet → sign chip → house chip → aspect row, each updating the wheel selection. |
| NC4 | With `elementNotes` off, no interpretive text appears in any sheet except reading sections (house sheet) and section teasers. |
| NC5 | The reading renders 17 sections in API order with API titles in TR and EN; empty sections from the fixture are absent. |
| NC6 | PNG export is 2048 px wide and pixel-sharp; the PDF contains a vector wheel (zooming the PDF shows no pixels) and correct Turkish glyphs; the full report contains every section. |
| NC7 | The share card has no birth details unless the toggle is on. |
| NC8 | C5 scan over every string rendered on this screen, the exports' HTML and accessibility labels finds no mask term. |
