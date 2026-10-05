# FX 02: App shell, navigation and screen structure (Phase 2)

*Goal: screens follow standard mobile patterns: a fixed header with the back button and title, one compact person
switcher, one row of controls before content, a full-screen map, sheets for choices, and progress and
notifications that set expectations. Ground rules: FX_00 §2. Depends on FX1.3 (`describeError`) and FX1.1
(`jobPhase`).*

| Item | Title | Size |
|---|---|---|
| FX2.1 | Shared components first | M |
| FX2.2 | Headers, safe area and transitions | M |
| FX2.3 | One profile switcher | M |
| FX2.4 | Ahead: one row of controls | S–M |
| FX2.5 | Today: life areas as a grid | S |
| FX2.6 | Chart tab layout and wheel gestures | M |
| FX2.7 | Job progress and "ready" notifications | M |
| FX2.8 | Sheets and snackbars instead of system alerts | S–M |
| FX2.9 | Full-screen map with sheets | L |
| FX2.10 | Saved reports list | S |

---

## FX2.1 Shared components first

Build these in `src/design/components/` with stories in `app/gallery.tsx`, light and dark, before touching
screens. All use theme tokens, 44 × 44 pt minimum touch targets, and localised accessibility labels.

| Component | Spec |
|---|---|
| `IconButton` | Icon only, 44 pt target, required `accessibilityLabel`, optional badge. |
| `Segmented` | One row, equal-width segments, 36 pt visual height / 44 pt target, `accessibilityRole="tablist"` with `tab` children and `selected` state; never wraps. Text shrinks to `caption` before truncating. |
| `Sheet` | Wrapper over `@gorhom/bottom-sheet` (already installed): snap points prop, backdrop, handle, header row with title + close `IconButton` (+ optional expand `IconButton`), Android back closes the sheet first, respects reduce motion. |
| `ActionSheet` | `Sheet` with a list of actions (`label`, optional icon, `destructive`), used instead of `Alert.alert` with options (FX2.8). |
| `Snackbar` | Bottom message with one optional action ("Undo", "Open"), auto-dismiss 5 s (paused while TalkBack/VoiceOver is on), swipe to dismiss, positioned above the tab bar when tabs are visible and above the bottom safe-area inset otherwise. One at a time; a new one replaces the old. Announced politely to screen readers. |
| `ProfileSwitcher` | FX2.3. |
| `BandChip` | Pill: band colour tint + ink text + a small shape icon per level so it reads without colour (FE_01 §9): strongly supportive ▲▲, supportive ▲, mixed ◆, challenging ▼, quiet / no emphasis ○. Input: the band key + the API label. Unknown key → neutral (FX1.4). |
| `Skeleton` | Variants `lines` (n lines of text height, last line 60 % width) and `block` (card). Localised `accessibilityLabel` (new key `loading` in en and tr; the current one is hard-coded "Loading"). Shimmer off under reduce motion. |
| `DatePager` | ‹ `IconButton` · formatted label (tap → picker) · › `IconButton`; a "Today" text button only when the shown date is not today. Labels via FX3.1 formatters. |

**Acceptance:** each component renders in the gallery in both themes; unit tests for `Segmented` (selection,
no wrap at 200 % font scale with four Turkish labels) and `Snackbar` (replace, auto-dismiss, undo callback).

---

## FX2.2 Headers, safe area and transitions

**Problem**
- `Screen` (`src/design/components/index.tsx`) renders the back arrow and the title **inside** the `ScrollView`,
  so both scroll away. The root `Stack` in `app/_layout.tsx` has `headerShown: false`, so pushed screens have no
  fixed header.
- `AheadScreen` (`src/features/forecast/AheadScreen.tsx`) and `ChartScreen` render a bare `ScrollView` without a
  safe area. The same `AheadScreen` is also mounted as the stack route `app/ahead/today.tsx` (opened by the
  "report ready" toast for `/home`), and `CalendarScreen` as `app/ahead/calendar.tsx`: there the content starts
  under the status bar and there is no back button (acceptance screenshots of the Month/Year views).
- All stack screens use `animation: "fade"` (`app/_layout.tsx`), so pushes and pops look the same.

**Change**
1. Root `Stack`: `headerShown: true` for pushed routes with themed options (`headerStyle` background `bg`,
   `headerShadowVisible: false`, title font from tokens, `headerBackButtonDisplayMode: "minimal"`). Keep
   `headerShown: false` only for `(tabs)`, `(auth)`, `(onboarding)`, the map report `transparentModal` routes
   (they get the `Sheet` header, FX2.9) and full-screen media/export routes.
2. `Screen` keeps its props, but `title` and `back` are applied to the native header (`<Stack.Screen options={{
   title }} />`); remove the in-scroll back button and title. iOS: `headerLargeTitle` on list-like screens
   (Saved reports, My Charts, Settings, Notifications).
3. Every tab screen and every pushed screen renders through `Screen` (or a list variant, FX4.2), so safe areas are
   handled in one place. `AheadScreen` and `ChartScreen` stop rendering bare `ScrollView`s.
4. Remove the duplicate stack routes `app/ahead/today.tsx` and `app/ahead/calendar.tsx`: deep links and the toast
   navigate to the tab (`/(tabs)/ahead?view=day&date=…`). If a stack route must stay, it gets a header with back.
5. Transitions: platform default for pushes and pops; `fade` only when switching between `(auth)`,
   `(onboarding)` and `(tabs)`, and for the map report `transparentModal` routes (their sheet animates);
   `presentation: "modal"` for Ask and Export.

**Acceptance**
- On every screen the back button and title stay visible while scrolling; no content draws under the status bar
  (screenshots of Today, Month, Calendar, Best Days, a place report, Saved reports).
- Android back and iOS swipe-back work on every pushed screen.
- `grep -rn "<ScrollView" src/features` only finds horizontal scrollers or list internals.

---

## FX2.3 One profile switcher

**Problem**
The full list of saved people is rendered as wrapping `Chip`s at the top of Chart (`ChartScreen.tsx`), Ahead
(`AheadScreen.tsx`), Map (`MapScreen.tsx`), New compatibility (`NewMatchScreen.tsx`, twice) and Ask
(`ChatScreen.tsx`). With three people it takes about 200 pt before any content and grows with every person added.
FE_01 §3.2 and FE_04 §1.4 specify a `ProfileSwitcher` chip in the header.

**Change**
1. `ProfileSwitcher` (header chip): initial avatar + label (ellipsis at 160 pt) + chevron. Tap → `Sheet` listing
   people (self first, then by most recently used), each with relationship caption and a check on the active one,
   plus "Add person" → `profile/charts/new`. Accessibility: "Showing {name}. Change person"; rows are radio items
   with `checked`.
2. Chart, Ahead and Map put it in the tab header (title area); switching sets `activeProfileId` as today.
3. New compatibility: two picker rows "Person A · {name} ▾" and "Person B · {name} ▾" opening the same sheet
   (the other selection disabled) and a swap `IconButton` between them, replacing the chip lists and the
   full-width "Swap people" button.
4. Ask (when enabled): the subject chip in the chat header (FE_09 §2.2).

**Acceptance**
- No screen body renders a list of all profiles as chips (`grep -rn "profiles.data?.map" src/features` only in the
  sheet and My Charts).
- With 6 profiles the first content block of Chart, Ahead and Map is visible without scrolling.
- Switching person updates the tab's data and survives restart (persisted `activeProfileId`).

---

## FX2.4 Ahead: one row of controls

**Problem**
`AheadScreen` stacks profile chips, view chips (Today / Month / Year / Calendar), lens chips that wrap to two rows,
and three outlined buttons (Previous / Today / Next) before any content: four control rows, more than half of
the screen on the acceptance screenshots. FE_01 §3.2 specifies a top segmented control and FE_04 §1.1 a segmented lens
control.

**Change**
1. Header: `ProfileSwitcher` (FX2.3).
2. Row 1, pinned at the top (`stickyHeaderIndices` or outside the scroll view): `Segmented` Today · Month · Year ·
   Calendar.
3. Row 2: `DatePager` for Today and Month (Year: the year range label with ‹ ›); hidden on Calendar (it has its
   own month navigator, FX3.6).
4. Row 3: lens `Segmented` with short labels General · Love · Work (full names as accessibility labels and in the
   reading title).
5. Keep "last lens per horizon" persistence.

**Acceptance**
- On a 1080 × 2400 emulator at default font size, the first content card starts in the top 40 % of the screen.
- Lens and date changes keep the scroll position of the controls and only reload the reading part (FE_04 §1.1).

---

## FX2.5 Today: life areas as a grid

**Problem**
`src/features/forecast/ForecastViews.tsx` renders each of the 11 life areas as a full-width `Card` with a score
and a full-width "Explore {area}" button: about four screens of scrolling. FE_04 §3 specifies a grid of tiles with
a sheet on tap.

**Change**
Two-column grid of compact tiles (first row Love · Family · Career · Money, then the other 7): label, `BandChip`,
and the 10-segment meter only when `dayScoreNumbers` is on. The whole tile is the button. Tap → `Sheet` with the
area's `drivers` (transit labels) and "Open in calendar". Remove the "Explore …" buttons.

**Acceptance**
- The 11 tiles take at most 1.5 screen heights at default font size; at 200 % font scale tiles grow in height and
  never clip text.
- Tile tap opens the sheet; TalkBack reads "Love, Supportive, button".

---

## FX2.6 Chart tab layout and wheel gestures

**Problem**
- `ChartScreen.tsx` order: profile chips, large name, full-width "Export & share", big-three chips (wrapping),
  wheel, "Zoom in" / "Reset zoom" buttons (`InteractiveWheel.tsx`), full-width "Focus mode", aspect legend,
  tab chips that wrap to two rows, a note, then a "Read your chart" button; the reading itself is behind that
  button. The wheel starts below the fold.
- `InteractiveWheel.tsx`: the `Pan` gesture (`minDistance(8)`) activates even at scale 1 (it only ignores the
  movement), so a vertical drag that starts on the wheel can be captured instead of scrolling the page.
- A tap on a stellium opens `Alert.alert` with planet names (`choosePlanet`).

**Change**
1. Header: `ProfileSwitcher`; Export & share as a share `IconButton` (header right, before Ask).
2. Body order: big three as one compact row of three equal cells (glyph + "Sun · Capricorn") → wheel (square,
   full width) → one-line aspect legend (small) → `Segmented` Reading · Planets · Houses · Aspects (one row) → tab
   content.
3. Wheel controls as overlays on the wheel: expand `IconButton` (top right, → Focus mode) and a "Reset zoom"
   `IconButton` that appears only when zoomed. Double-tap toggles 1× / 2×. Remove the text buttons.
4. Gestures: `Pan` enabled only when zoomed (track `zoomed` on the JS side, updated at pinch end and double-tap);
   at 1× the page scrolls normally. Pinch stays.
5. Stellium tap → `ChartDetailSheet` (or `ActionSheet`) listing the bodies, not an alert.
6. Reading tab shows the reading inline: section list (first section open, others collapsed) with `Generated`
   states. If no reading exists yet, one primary button "Prepare my reading" (explicit user action) with the
   expected duration line (FX2.7). Remove "Read your chart".

**Acceptance**
- The top of the wheel is visible without scrolling on a 6.1" device.
- A vertical drag starting on the wheel at 1× scrolls the page; at 2× it pans the wheel.
- The four tabs fit on one row in English and Turkish at default font size.
- No `Alert.alert` in `src/features/chart`.

---

## FX2.7 Job progress and "ready" notifications

**Problem**
- `JobProgress.tsx` shows "Preparing" and one row per stage, almost always "Preparing"; no expected duration or
  elapsed time (FE_01 §3.4 asks for elapsed time).
- `JobLifecycle.tsx` shows a toast "Your report is ready." for **every** succeeded job, including short text jobs
  (calendar and Best Days texts), and also when the user is already on that screen. It is generic, sits at a
  fixed `bottom: 84` (covers content on screens without a tab bar), has two large buttons, and stays 10 s
  (acceptance screenshots: Map, New compatibility, Year).

**Change**
1. `JobProgress`:
   - Title by `job.kind`: "Preparing your chart reading", "Preparing your monthly forecast", "Preparing the report
     for {place}", etc. (chrome strings per kind).
   - Expectation line from `job.eta_seconds`, else a per-kind default (natal ≈ 2 min; month / year ≈ 1–2 min;
     compatibility ≈ 2 min; place / area / recommendation ≈ 1 min; day ≈ 30 s; text jobs ≈ 10 s): "Usually takes
     about 1 minute".
   - Elapsed time "1:24" (tabular figures), updated every second only while visible.
   - Stage rows only when there is more than one stage, with done / in-progress / waiting icons and the FE_02 §4.3
     labels. No percentages.
   - Footnote: "You can leave this screen. We'll let you know when it's ready."
   - Slow / very slow copy from FX1.1; failed copy and action from FX1.3.
2. "Ready" notification (replaces the custom toast with `Snackbar`):
   - Only for long kinds (`natal_reading`, `month_reading`, `year_reading`, `compatibility`, `place_reading`,
     `area_reading`, `recommendation`, `solar_return`). Never for `day_reading`, `element_notes`,
     `calendar_text`, `best_day_text`.
   - Only when the job's route is not the current route.
   - Named copy: "Your chart reading for {label} is ready", "Your report for {place} is ready", … with "Open".
   - A failed long job while the user is elsewhere → "Your {kind} couldn't be prepared" + "Open".
   - Screen reader announcement once per job.

**Acceptance**
- Finishing a `calendar_text` job shows nothing; finishing a natal reading while on Map shows the named snackbar;
  finishing it while on the reading screen shows nothing.
- Snackbar never covers the tab bar or the bottom buttons of a pushed screen (screenshots).
- `JobProgress` shows the expectation line and a running elapsed time.

---

## FX2.8 Sheets and snackbars instead of system alerts

**Problem**
There are 26 `Alert.alert` calls. Several are choices (stellium planet, "No city nearby" with "Explore this exact
spot"), several are success messages ("Saved to Photos", export sent, reminder set), and some are confirmations.

**Change**

| Use | Replace with | Examples |
|---|---|---|
| Choosing between options | `ActionSheet` / `Sheet` | `InteractiveWheel.tsx` (choose planet), `MapScreen.tsx` (no city nearby, two places) |
| Success / info after an action | `Snackbar` | `ExportScreen.tsx` (saved to Photos), `AccountScreen.tsx` (export sent), `BestDayScreen.tsx` (reminder set / limit) |
| Reversible delete | immediate action + `Snackbar` with Undo | Saved reports (FX2.10), compatibility history (`MatchScreen.tsx`), Ask threads |
| Irreversible or destructive confirmation | keep `Alert.alert` | delete account, delete profile, recalculate chart (`ProfileEditor.tsx`) |
| OS settings prompts | keep `Alert.alert` | notification / location permission → Settings |

**Acceptance:** remaining `Alert.alert` calls are only irreversible confirmations and OS-settings prompts; list
them in the phase report.

---

## FX2.9 Full-screen map with sheets

**Problem**
- `MapScreen.tsx` is a `<Screen embedded>` (a `ScrollView`) with profile chips, search, goal chips,
  Layers / Legend / List buttons, inline layer and legend lists, then `MapCanvas` with a fixed `height: 420`
  (`MapCanvas.tsx`). Page scrolling and map panning compete, and the map is a small window.
- The legend is coloured planet names (`MapScreen.tsx`, legend block): no line-style samples and no heat colour
  swatches.
- "No city nearby" is an alert. Line, place, point and area reports are `transparentModal` routes
  (`app/_layout.tsx`) that show a sheet with large "Close" / "Full screen" text buttons (acceptance screenshots).

**Change**
1. Layout: the map fills the tab (no `ScrollView`). Floating over it:
   - top: a search pill (leading search icon, placeholder "Search cities, countries…", clear button) and the
     `ProfileSwitcher` in the header;
   - under the search: one horizontal row of goal chips (Lines + 11 goals);
   - right edge: a column of `IconButton`s: Layers, Legend, List (each opens a `Sheet`);
   - bottom: "Where should I go?" as a floating button above the tab bar.
2. Layers sheet: planet toggles, Nodes, Latitude crossings (as today, in a sheet).
3. Legend sheet: per planet a line sample in its colour, the four angle styles drawn (solid / dashed / solid thin
   / dotted, FE_07 §3.1), and with a goal selected the four heat levels as colour squares with `BandChip` labels.
4. Reports open in a `Sheet` over the map (snap 25 % / 55 % / 92 %, FE_07 §5) with header title, close and expand
   `IconButton`s replacing the text buttons; expand pushes the full-screen route. Keeping the existing
   `transparentModal` routes is fine as long as they use `Sheet`. The map highlights the subject. The List sheet
   and line sheet follow the same pattern.
5. "No city nearby" → a small sheet with "Explore this exact spot".
6. Android back closes the open sheet before leaving the tab.

**Acceptance**
- Panning and pinching the map never scrolls anything else.
- FE_07 MP1–MP3 still pass.
- No `Alert.alert` in `src/features/map`.
- Screenshots: map with Love heat + legend sheet; place report at 55 %; expanded report.

---

## FX2.10 Saved reports list

**Problem**
`src/features/account/ReportsScreen.tsx` renders a full-width red "Delete {title}" button under every row
(plus long-press delete with an alert). The filter chips wrap to three rows. Pagination is a "Load more" button.

**Change**
1. Row: title, subtitle and date, chevron; trailing "…" `IconButton` → `ActionSheet` (Open · Delete). Swipe left
   on a row reveals Delete.
2. Delete removes the row at once and shows a `Snackbar` "Report deleted" with Undo for 5 s; the
   `DELETE /reports/{id}` request is sent only when the snackbar closes without Undo.
3. Filters: one horizontal scroll row.
4. List virtualisation and infinite scroll: FX4.2.

**Acceptance**
- No destructive buttons inside list rows.
- Undo restores the row and no `DELETE` request is sent (network log); without Undo exactly one `DELETE` is sent.
