# DS — Apply the "Astrology App" design system to the React Native frontend

**For:** the coding agent / frontend team · **Owner:** Radul · **Status:** ready for Phase 0
**Kit:** this folder (`astro-design-kit/`). It is self-contained; the design-system artifact on claude.ai is the human-readable brand book behind it.

## 1. Goal

Re-skin the existing Expo / React Native app so every screen follows the design system: a charcoal night ground, one warm gold, Aboreto display type, Poppins UI type, thin gold line-art, tarot-card selection cards. The work is **visual only**.

## 2. Hard constraints (invariants)

1. **No behaviour changes.** Navigation structure, state, API calls, the mock API, data models, validation logic and i18n *keys* stay as they are. If a visual change seems to need a behaviour change, stop and list it in the report.
2. **Tokens only.** After migration, components outside `design-system/` contain no colour literals, no font-family strings, no raw font sizes and no spacing numbers that duplicate a token. Everything comes from `theme/tokens.ts`.
3. **The kit is read-only.** Do not edit `theme/tokens.ts`, `glyphs/glyphs.ts`, fonts or SVGs. If a token is missing, report it — do not invent a hex value.
4. **Approval gates.** Stop after Phase 0 (Gate A) and after Phase 2 (Gate B) and wait for Radul's go-ahead. No screen files are touched before Gate B.
5. **Turkish first.** All uppercase display text must uppercase Turkish correctly (`i → İ`, `ı → I`). Never rely on `textTransform: 'uppercase'` (iOS uppercasing is not locale-aware).
6. **No Unicode astrology symbols or emoji** in UI (`♈…♓`, `☉☽☿♀♂♃♄♅♆♇`). iOS renders some as emoji. Use `Glyph`.

## 3. What is in the kit

| Path | What |
| --- | --- |
| `theme/tokens.ts` | `brand`, `themes.night` / `themes.parchment` (semantic colours), `type` (text styles), `space`, `radius`, `size`, `opacity`, `motion`, `shadow`, `fontFiles` |
| `theme/tokens.json` | same values as plain JSON (for tooling) |
| `fonts/*.ttf` | Aboreto Regular; Poppins Regular / Medium / SemiBold — subset to Latin + Latin Extended (full Turkish). OFL licences beside them; ship them with the app. |
| `glyphs/glyphs.ts` | path data for 16 UI icons, 12 zodiac signs, 10 planets, 7 card motifs; SVG XML for emblem, chart wheel, divider, card corner; screen sky (stars + orbits); TraitCard scatter; Turkish sign/planet names |
| `svg/` | the same artwork as standalone SVG files (gold ink) for marketing / handoff |
| `reference/*.png` | the target look of every component in Night (`_dark`) and Parchment (`_light`). These are the visual acceptance references. |

## 4. Phase 0 — Exploration report (read-only) → **Gate A**

Change nothing. Write `DS_00_exploration.md` answering, with file paths and real signatures:

1. Expo SDK, React Native version, New Architecture on/off, TypeScript strictness, web target yes/no.
2. Routing: expo-router or react-navigation; where headers and the tab bar are configured.
3. Styling approach (StyleSheet, NativeWind, styled-components, Tamagui, other) and any existing theme / colour / font files.
4. Installed or missing: `expo-font`, `expo-splash-screen`, `react-native-svg`, `expo-linear-gradient`, `react-native-safe-area-context`, any date/time picker, any icon library (`@expo/vector-icons`, etc.).
5. i18n: library, where the current language lives, how a component can read it (`tr` / `en`).
6. **Screen inventory:** every screen file with its route, and a one-line description.
7. **Shared UI inventory:** every reusable component (buttons, inputs, pickers, cards, headers, list rows, chat bubbles, sheets, modals) with props.
8. Counts: colour literals (`rg -n "#[0-9A-Fa-f]{3,8}\b|rgba?\(" <src>`), `fontFamily`, `fontWeight`, `textTransform` usages; icon-library usages; Unicode astrology symbols.
9. **Proposed mapping table**: existing component → design-system component (section 6), and existing screen → layout recipe (section 7). Mark anything with no match as "not covered".

## 5. Phase 1 — Foundation

**1.1 Place the kit.** Copy `theme/`, `glyphs/` into the project's source tree as `design-system/theme/` and `design-system/glyphs/` (use the source root found in Phase 0). Copy `fonts/*.ttf` and the OFL files to the project's assets folder.

**1.2 Dependencies.** Install only what Phase 0 found missing, with `npx expo install` (keeps versions SDK-compatible): `expo-font expo-splash-screen react-native-svg expo-linear-gradient react-native-safe-area-context`.

**1.3 Fonts.** Load with `useFonts`, using **exactly** the keys in `fontFiles` (`"Aboreto-Regular"`, `"Poppins-Regular"`, `"Poppins-Medium"`, `"Poppins-SemiBold"`). Keep the splash screen up until fonts load. Never set `fontWeight` together with these families — the weight is the family.

**1.4 Theme provider.** `ThemeProvider` + `useTheme()` returning `{ name: ThemeName, colors: ThemeColors, setTheme }`. Default `night`. v1 ships Night as the active theme and does **not** follow the OS light/dark setting; Parchment must still work when the default is switched (Gate B checks this).

**1.5 System chrome.** Status bar `light-content` on Night, `dark-content` on Parchment. Android navigation bar and root background = `colors.surface` (no white flash between screens).

**1.6 `upper()` helper** (design-system/text/upper.ts):

```ts
export function upper(s: string, lang: 'tr' | 'en'): string {
  return lang === 'tr' ? s.replace(/i/g, 'İ').replace(/ı/g, 'I').toUpperCase() : s.toUpperCase();
}
```

**1.7 `AppText`** — the only text primitive. Props: `variant: TypeStyleName` (default `body`), `color?: keyof ThemeColors` (default `ink`), `lang?` (default = current i18n language), `align?`, plus Text props. Applies `type[variant]` (minus the `uppercase` flag), `includeFontPadding: false` on Android, and, when `type[variant].uppercase` is true, renders `upper(children, lang)` (children must be a string; warn in dev otherwise). `maxFontSizeMultiplier`: 1.2 for `display*`, 1.5 otherwise.

**Acceptance 1:** a dev-only screen shows "Haritamı oluştur / Generate my chart" in every variant. `displayTitle` reads `HARİTAMI OLUŞTUR` in `tr` and `GENERATE MY CHART` (no dotted İ) in `en`; Aboreto and the three Poppins weights are visibly distinct on **both** iOS and Android; no system-font fallback.

## 6. Phase 2 — Components (in `design-system/components/`)

Build each with TypeScript props exactly as below. All colours via `useTheme().colors`; all sizes via `space`, `radius`, `size`, `type`. Compare each against its `reference/<Name>_dark.png` and `_light.png`.

**Glyph** — `{ name; set?: 'icons'|'zodiac'|'planets'|'motifs'; size?; color?: keyof ThemeColors (default 'accent'); strokeWidth?; accessibilityLabel? }`. Look up `set` first if given, else icons → zodiac → planets → motifs (`sun` exists in both planets and motifs — pass `set`). Render `<Svg viewBox="0 0 N N">` with N and default stroke from `glyphGrid[set]`, `fill="none"`, round caps and joins; elements with `fill: true` get `fill={color}` and no stroke. Default size 24 (motifs 40). Decorative unless `accessibilityLabel` is given.

**Ornament** — `{ name: 'emblem'|'chartWheel'|'divider'|'cardCorner'; width; color?: keyof ThemeColors (default 'accent') }`. `<SvgXml xml={…} color={ink} width height />`, with `__SURFACE__` replaced by `colors.surface` (memoise per theme). Aspect ratios: emblem 360:420, chartWheel 1:1, divider 10:1, cardCorner 1:1. `Emblem`, `ChartWheel`, `Divider` are thin wrappers. `ChartWheel` may rotate one turn per `motion.wheelTurn` on hero screens only, and never when reduce-motion is on.

**Screen** — `{ arch?: boolean; grain?: boolean; backdrop?: 'orbits'|'plain'; scroll?: boolean; children }`.
- Background `surface`; behind content, full-bleed `SvgXml` of `sky.withOrbits` (or `sky.plain`) with `__HAIRLINE__` → `hairline`, `__STAR__` → `star`, `preserveAspectRatio` slice.
- `grain`: `LinearGradient` over the lower 55% from transparent to `surfaceDeep`.
- `arch`: absolutely positioned frame inset `size.archInset` from the safe area, 1pt border `accent`, top-left/top-right radius = half its measured width (onLayout), bottom radii `radius.card`; a second line inset 7pt, 1pt `hairline`.
- Content padding: top = safe-area top + `size.screenPaddingTop`; sides `size.screenPaddingX` (+ `size.archInset` with `arch`); bottom = safe-area bottom + `space[8]`.
- Use `arch` + `grain` only on welcome, splash and result-reveal screens.

**Title** — `AppText` with `variant` `displayHero | displayTitle | displaySection | displayCard`, colour `accent`, centred, `accessibilityRole="header"`. A screen title is followed by an optional subtitle (`body`, `inkSoft`, centred) `space[3]` below.

**Button** — `{ variant?: 'primary'|'outline'|'ghost'; size?: 'lg'|'md'; onPress; disabled?; children: string; lang? }`.
- Height `size.buttonLg` (56) / `size.buttonMd` (44); radius `radius.md`; full width by default; horizontal padding `space[6]` / `space[4]`.
- primary: bg `primary`, label `onPrimary`. outline: 1pt `borderControl`, label `accent`. ghost: label `accent`.
- Label `AppText variant="button"` (uppercased via `upper`).
- Pressed: primary opacity 0.88; outline border → `accent`. Disabled: `opacity.disabled`.
- One primary per screen. `accessibilityRole="button"`, `accessibilityState={{ disabled }}`.

**Field** — `{ label; hint?; error?; children }`. Column, gap `space[2]`: label (`label`, `inkSoft`); a row of controls with gap `space[2]`; then either error (alert Glyph 16 + `caption`, both `danger`) or hint (`caption`, `inkFaint`). Error replaces hint. Field groups stack `space[6]` apart.

**SelectField** — the trigger for every existing picker (date, time, place, lists). It **only restyles the trigger**; keep the app's existing picker/sheet logic. Props: `{ valueLabel?; placeholder?; onPress; invalid?; disabled?; flex?; accessibilityLabel }`. Height `size.control` (48), 1pt border `borderControl` (pressed → `accent`, invalid → `danger`), radius `radius.md`, padding left `space[3]`, right 36; value `AppText variant="input" color="inkSoft"` single line; placeholder `body`/`inkFaint`; `chevron-down` Glyph 20 `accent` pinned `space[2]` from the right. Date row ratio day : month : year = 1 : 1.5 : 1.

**TextInputField** — `{ value; onChangeText; placeholder?; icon?: 'map-pin'|'search'; invalid? } & TextInputProps`. Same box as SelectField; padding `space[4]` (left 44 with icon, icon Glyph 20 `accent` at `space[3]`); text `Poppins-SemiBold` 16 `inkSoft`; `placeholderTextColor` `inkFaint`; `selectionColor` / `cursorColor` `accent`; focused border `accent`.

**TraitCard** — `{ label: string; motif: MotifName; selected: boolean; onToggle(next: boolean); lang? }`.
- `aspectRatio` 5/8, 1pt border `borderControl`, radius `radius.card`. Ink = `onPrimary` when selected, else `accent`. Selected bg `primary`, border `primary`.
- Inner frame: inset 5pt, 1pt border in ink at `opacity.traitFrame`, radius 2.
- Corners: `Ornament cardCorner` 18pt at 2pt from each corner; mirror with `scaleX: -1` / `scaleY: -1`.
- Scatter: `<Svg viewBox="0 0 100 160">` full size at `opacity.traitScatter`: circles from `traitScatter.dots`, sparkles from `traitScatter.sparkles` via `sparklePath`, fill ink.
- Motif: `Glyph set="motifs" size={40}` centred at top 11%, and again at bottom 11% rotated 180°.
- Label `AppText variant="displayCard"` in ink, centred, horizontal padding `space[6]`, max 3 lines.
- Selected badge: 28pt circle centred on the top edge (translateY −14), bg `surface`, 1pt border `primary`, `check` Glyph 14, strokeWidth 2, `accent`.
- Grid: two columns, gap `space[4]`. `accessibilityRole="checkbox"`, `accessibilityState={{ checked: selected }}`. Background change may fade over `motion.base`.

**Patterns not in the reference** (provisional — use exactly these, list each use in the report):
- Tappable list row: `body`/`ink` text, trailing `chevron-right` Glyph `accent`, 1pt `hairline` separator, min height 56.
- Chat (Ask Astrology): user bubble `primary` + `onPrimary` text; astrologer bubble `surfaceRaised` + `ink`; both radius `radius.md`, padding `space[3]`/`space[4]`; composer = `TextInputField` + `Button size="md"`.
- Bottom sheet / modal: `surfaceRaised`, top radii `radius.lg`, `shadow.sheet[name]`, backdrop `scrim`.
- Tab bar / header: background `surface`, 1pt `hairline` top border, active tint `accent`, inactive `inkFaint`, labels `caption`; header back button `arrow-left` Glyph `accent`; header title `displaySection`.

**Gallery.** Add a dev-only route `DesignSystemGallery` that renders every component and variant in both themes (toggle at top), using the sample copy from section 8.

**Acceptance 2 → Gate B:** `DS_01_report.md` with gallery screenshots on iOS and Android, Night and Parchment, side by side with the matching `reference/*.png`. They match in colours, fonts, sizes (button 56, field 48, side padding 32, card 5:8) and states (selected card, error field, disabled button). `tsc` passes. No screen files changed yet.

## 7. Phase 3 — Apply to screens (after Gate B)

Follow the approved mapping table. Per screen:

- Wrap the screen in `Screen`; remove its own background colour.
- Screen title → `Title displayTitle` (+ subtitle). Reading sections → `Title displaySection`; paragraphs → `AppText bodyLg` `ink`; `Divider` between sections.
- Main action → one `Button` primary, pinned near the bottom, `space[12]` above it. Secondary → `outline`; skip / tertiary → `ghost`.
- Form inputs → `Field` + `SelectField` / `TextInputField` (logic untouched).
- Multi-choice "qualities" grids → `TraitCard` grid; give each option a different motif.
- Icons → `Glyph`. Zodiac / planet symbols (text, images or icon fonts) → `Glyph set="zodiac"|"planets"` with the Turkish name beside it from `zodiacTR` / `planetTR` when a label is shown.
- Recipes: **Welcome/splash** — `Screen arch grain`, `Emblem` top, `Title displayHero` (shrink font to fit width if the app name is long), `bodyLg` `inkSoft` subtitle, primary `Button`. **Birth data** — `Screen`, `Title`, `ChartWheel` 180pt, date/time/place fields, primary `Button`. **Compatibility qualities** — `Screen`, `Title` + subtitle, `TraitCard` grid, primary `Button`.
- Maps (astrocartography), charts and data visualisations: restyle only the surrounding chrome; their internal colours are out of scope (list them in the report).

**Acceptance 3:** `DS_02_report.md` with a before/after screenshot for every screen in Night, and a Parchment smoke test of three screens (welcome, birth data, a reading). Then all must hold:

- `rg -n "#[0-9A-Fa-f]{3,8}\b|rgba?\(" <src> --glob '!**/design-system/**'` → 0 results, or each remaining hit justified in the report.
- `rg -n "fontWeight|textTransform" <src> --glob '!**/design-system/**'` → 0 results.
- `rg -n "[♈-♓☉☽☿♀♂♃♄♅♆♇]" <src>` → 0 results.
- No icon-library import remains where a `Glyph` exists; any icon kept is listed.
- `tsc` passes; the app runs on iOS and Android; no behaviour, navigation or API diffs (`git diff --stat` in the report touches only styling/presentation files plus `design-system/`, assets, the font loader and dependencies).

## 8. Copy samples (for the gallery)

| Use | Türkçe | English |
| --- | --- | --- |
| Hero subtitle | Doğduğun anın gökyüzünü keşfet — senin için yazılmış yıldızlar. | Discover the sky of the moment you were born. |
| Screen title | Doğum haritan için bilgilerin | Enter your birth details |
| Labels | Doğum tarihi · Doğum saati · Doğum yeri | Date of birth · Time of birth · Place of birth |
| Primary button | Haritamı oluştur | Generate my chart |
| Traits | Tutku ve karizma · Duygusal denge · Mizah anlayışı · Maddi güven | Passion and charisma · Emotional stability · Sense of humour · Financial security |
| Error | Doğum yerini listeden seç. | Choose your birthplace from the list. |
| Hint | Saati bilmiyorsan 12:00 kullanılır. | If you don't know the time, 12:00 is used. |
