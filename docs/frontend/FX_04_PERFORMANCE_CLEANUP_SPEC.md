# FX 04: Performance and cleanup (Phase 4)

*Goal: the map and long lists stay smooth on a mid-range Android, background work is bounded, and the codebase
loses dead code and unsafe casts. Ground rules: FX_00 §2. Measure before and after every item and put the numbers
in the phase report.*

| Item | Title | Size |
|---|---|---|
| FX4.1 | Country geometry: load once, lighter, never per tap | M |
| FX4.2 | Virtualised lists | M |
| FX4.3 | One job watcher | M |
| FX4.4 | Heat layer: fewer features, no seams | S |
| FX4.5 | Bundle audit and dependency hygiene | S–M |
| FX4.6 | Dead code, typed routes, route builders | S |
| FX4.7 | Performance budget check | S |

---

## FX4.1 Country geometry: load once, lighter, never per tap

**Problem**
- `/geo/countries.geojson` is served from `mock-api/fixtures/geo-countries.json` (9.9 MB file, 239 countries,
  ≈ 2.2 MB of coordinates as compact JSON).
- `MapCanvas.tsx` loads it through `useApi` (full zod parse, FX1.4; persisted into MMKV, FX1.5) to draw the
  preview base map.
- `MapScreen.tsx` (`point`, zoom < 3.5) calls `request("GET", "/geo/countries.geojson")` **on every tap**: a full
  download and parse each time, then a linear point-in-polygon scan (`countryAt`).
- `AreaScreen.tsx` loads it again for the country outline.

**Change**
1. One loader `src/features/map/countries.ts`: fetch once per session through `queryClient.fetchQuery` with a
   fixed key and `staleTime: Infinity`, envelope-only validation (FX1.4), not persisted (FX1.5). Optionally cache
   the raw file on disk with `expo-file-system` keyed by the contract version so cold starts don't download it.
2. Hit-testing: build a bounding-box index once (memo) and test polygons only for boxes containing the point.
   `MapScreen` and `AreaScreen` use the loader; no direct `request` for this path remains.
3. Lighter geometry: add a fixture build step that writes a simplified countries file for the base map and
   hit-testing (target ≤ 400 KB compact JSON, e.g. Douglas–Peucker / Visvalingam at a tolerance that keeps
   borders correct at zoom ≤ 5). Keep the detailed file only where an outline needs it (area report), or drop it
   if the simplified one looks right at those zooms. The Turkey point-of-view worldview (FE_07 O6) must be
   preserved by the simplification.

**Acceptance**
- Network log: one countries request per session (zero after the first launch if cached on disk).
- Tap at zoom < 3.5 → country report opens in < 150 ms (dev timing log), measured on the emulator.
- Map time-to-first-render from tab tap: before / after numbers in the report.
- Screenshots of the base map at zoom 2 and 5 before / after simplification.

---

## FX4.2 Virtualised lists

**Problem**
There is no `FlatList`, `SectionList` or FlashList anywhere. Lists are rendered with `.map` inside scroll views:
Saved reports (paginated with a "Load more" button), recommendation results, places on a line, area best cities and
regions, the Calendar "This month" list, map search results, My Charts, compatibility history, Year overview, and
the Ask chat (which calls `scrollToEnd` on every streamed chunk).

**Change**
1. Rule: any list that can exceed 20 items, or grows with use, is a `FlatList` / `SectionList` (built in; no new
   dependency) with stable `keyExtractor`, memoised row components, and `getItemLayout` where rows have a fixed
   height.
2. Saved reports: infinite scroll (`onEndReached` → `fetchNextPage`), pull-to-refresh, empty state as
   `ListEmptyComponent`; remove "Load more".
3. Recommendation results and Year overview: `SectionList` (sections = line groups / month groups).
4. Ask chat (when enabled): inverted `FlatList`; the streaming message is the first item and grows in place; no
   `scrollToEnd` per chunk; "jump to latest" button when the user has scrolled up.
5. `Screen` gets a list variant (header and safe area from FX2.2, no outer `ScrollView`) so lists are never nested
   inside a vertical `ScrollView`.

**Acceptance**
- No vertical `ScrollView` contains a `.map` over API arrays in the screens listed.
- With a fixture of 200 saved reports, scrolling shows no blank rows on the emulator (screen recording in the
  report) and JS frame rate stays above 50 fps in the performance monitor.

---

## FX4.3 One job watcher

**Problem**
The same job id is polled by up to three observers with different schedules on the shared key
`["job", lang, job_id]`: `useGenerated` (`src/api/jobs.ts`, 1–4 s), `useApi` (`src/api/resource.ts`, 1–4 s, per
pending part), and `JobLifecycle` (`src/lib/JobLifecycle.tsx`, every 4 s for every pending job in the cache,
whether or not a screen shows it). `JobLifecycle` also rescans the whole query cache on every successful query
update.

**Change**
1. A single module `src/api/job-watcher.ts` owns polling: a registry of pending job ids (with the query keys that
   embed them and the route to open), one timer, requests sent one at a time, schedule from FX1.1 per job, paused
   while the app is in the background, resumed with an immediate check on foreground.
2. On each status, it writes `["job", lang, id]` with `setQueryData`; on `succeeded` / `failed` it invalidates the
   owning keys and emits the event used by FX2.7 notifications.
3. `useGenerated`, `useApi` and `Generated` only read job status (no own `refetchInterval`); screens register their
   jobs when they render a pending part. `JobLifecycle` becomes the subscriber that shows the snackbar.
4. Registration replaces the full cache scan; jobs also register when the cache is hydrated (pending parents).
5. Cap: at most one job request per second app-wide.

**Acceptance**
- Test with 3 pending jobs and a fake clock: requests are spaced ≥ 1 s, each job follows the FX1.1 schedule, no
  two requests for the same job within 1 s.
- Network log on the emulator with two pending readings: no duplicate `GET /jobs/{id}` bursts.
- FX1.1 and FX2.7 acceptance still pass.

---

## FX4.4 Heat layer: fewer features, no seams

**Problem**
`heatCells` (`src/features/map/geometry.ts`) creates one square polygon per 0.5° point (thousands of features per
goal). Adjacent squares share edges, and anti-aliasing draws visible hairline seams (Love heat screenshot); the
large feature count also costs memory and render time.

**Change**
1. Merge cells: for each latitude row, join consecutive cells of the same level into one rectangle (run-length),
   then emit one `MultiPolygon` feature per level (at most 4 features).
2. Set `fill-antialias: false` on the heat fill layer in `MapCanvas.tsx`.
3. Keep the memo per goal; log build time in dev.

**Acceptance**
- Feature count ≤ 4 per goal; build time < 50 ms on the emulator (log).
- Unit test: merged geometry covers exactly the same cells (area and point-membership checks on a fixture).
- Screenshot at zoom 2–5 shows no seams.

---

## FX4.5 Bundle audit and dependency hygiene

**Problem**
- The Android Hermes bundle is 8.99 MB (iOS 8.75 MB). Nobody has looked at what is in it.
- `lucide-react-native` is imported by name from its package entry in 3 files (10 icons; one of the files is the
  dead `TabScreen.tsx`). Without tree shaking, Metro may include the whole icon set.
- `fastify`, `@fastify/cors` and `yaml` are in the app's `dependencies` but are used only by the local API and
  scripts (not imported by the app).
- `@shopify/react-native-skia` is used in one file (`src/features/exports/native.ts`, offscreen export rendering)
  and adds a large native library to the APK.

**Change**
1. Measure: export without bytecode with source maps (e.g. `npx expo export --platform android --no-bytecode
   --source-maps --output-dir dist-audit`) and analyse with `npx source-map-explorer` (run through `npx`; do not
   add it to `package.json`). Put the top 15 modules by size in the report.
2. Icons: if lucide is significant, import icons from their per-icon paths or replace the 10 icons (plus those
   added in Phase 2) with local SVG components in `src/design/icons/`.
3. Move `fastify`, `@fastify/cors`, `yaml` to `devDependencies` (or a `local-api/package.json`); confirm the local
   API scripts still run.
4. Skia (decision for Radul, do not remove yet): compare an export rendered with `react-native-view-shot` (already
   a dependency) from the SVG wheel at the same output size against the Skia export. Put both images and the APK
   size difference in the report.

**Acceptance:** before / after bundle sizes and the module table in the report; local API, mock API and all tests
still run.

---

## FX4.6 Dead code, typed routes, route builders

**Problem**
- `src/features/home/TabScreen.tsx` is not imported anywhere. `LocalHomeScreen.tsx` becomes dead after FX1.7.
- `typedRoutes` is enabled (`app.json` → `experiments.typedRoutes`), yet 14 `as never` casts remain: 3 in
  `src/api/client.ts` (openapi-fetch typing) and 11 on navigation with hand-built or API-supplied route strings
  (`ReportsScreen.tsx`, `JobLifecycle.tsx`, `NotificationLifecycle.tsx`, `HomeScreen.tsx`, `CalendarScreen.tsx`,
  `AccountScreen.tsx`, `OnboardingScreen.tsx`, `ReadingScreen.tsx`, `AskCards.tsx`, `ChatScreen.tsx`,
  `TabScreen.tsx`). URL strings are also built by hand elsewhere (e.g. `MapScreen.tsx`, `JobLifecycle.routeFor`).

**Change**
1. Delete the dead files.
2. `src/lib/routes.ts`: typed builders, e.g. `routes.place(placeId, { profile, goal })`,
   `routes.area(code, kind, profile)`, `routes.ahead({ view, date, month, profile })`,
   `routes.calendarItem(id, profile)`. All navigation uses them; `JobLifecycle.routeFor` and the notification
   deep-link mapper too.
3. Remove `as never` from navigation calls. Routes that arrive from the API (`ReportRef.route`, notification
   `deep_link`, Ask links) go through one validating mapper that returns a typed `Href` or a safe fallback (the
   tab). Casts that remain for library typing (`openapi-fetch` in `request()`) get a one-line comment.

**Acceptance:** `grep -rn "as never" src app` lists only commented library casts; `tsc --noEmit` passes; deep
links and toasts open the same screens as before (FE_08 CB6).

---

## FX4.7 Performance budget check

Measure on the Android emulator (and a physical mid-range device if available) with a release build, and report:

| Metric | Budget |
|---|---|
| Cold start to Home content (cached) | < 2.5 s |
| Tab switch to first content (cached) | < 300 ms |
| Map pan / zoom with lines + one heat layer | ≥ 55 fps (FE_07 §9) |
| City report deterministic block from cache | p50 < 500 ms (FE_07 §9) |
| Saved reports scroll (200 items) | no blank rows, ≥ 50 fps |
| Persisted cache size after a typical session | < 5 MB |

Anything over budget goes to "Found, not fixed" with the measured value and a suggested fix.
