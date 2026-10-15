# DS_02 — Screen migration and Android verification

2026-10-05. Gate B approved by the user. Working copy: `D:\Dev\astrology-app\FE`.

## Status

The shared design migration is implemented and running on Android. **Full Acceptance 3 is not signed off.** Its exhaustive before/after matrix and exact three-screen Parchment evidence remain incomplete. iOS evidence remains deferred under the Android-first approval.

## Implemented

- Legacy theme and component interfaces now adapt the supplied immutable tokens. Night is the default; explicit Light uses Parchment. Settings exposes Light and Dark; the former stored `system` value resolves to Night, without following OS appearance. No API schema or persisted value migration.
- Poppins UI and reading text; Aboreto display headings; Turkish-aware uppercase; supplied sky background, gold controls and glyphs. Existing charts, map layers and generated export artwork retain their data palettes.
- Buttons preserve callbacks, disabled/loading states and original accessible names. Text fields preserve keyboard types and change handlers. Date/time selectors retain native pickers. Compatibility person selectors use kit fields while retaining the existing profile sheet.
- Welcome uses arch, gradient, emblem and hero title. Birth date/time/place stages use the 180pt chart ornament. Readings use bodyLg and ornament dividers. Sheets use raised surfaces, kit radii/shadow and scrim. Chat bubbles use primary/onPrimary and raised/ink.
- Existing FlatList/SectionList virtualization, sheet/back handling, forms, API hooks, calculations, routes and translation keys retained. Segmented controls retain unrestricted user text scaling; tab labels fit on one line.
- No qualities questionnaire exists in the product, so TraitCard remains available in the gallery rather than introducing unsupported state or API fields.

## Validation

- TypeScript `tsc --noEmit`: pass.
- ESLint over app, design, design-system and feature source: pass.
- Native regression suite: **50 tests / 16 suites passed**.
- Design typography/font/license tests: **6 passed**.
- Android development APK opens with the new bundle, authenticated account and saved readings. Preview server was restarted after hot reload became unstable. Home, Ahead and cached reading were rechecked successfully after restart, without the earlier text-rendering warning recurring in those checks. The warning is not proven resolved across every route.
- No paid generation was requested for visual validation. Unsaved name-form text was used; no test birth profile was saved.

## Evidence

Open `artifacts/design-system/screens.html` for the verified screenshot selection. `before/home.png` is the verified original home baseline; before/after home comparison is included. Its original theme was Light, so it is not a Night-to-Night comparison.

Verified after captures: home, chart, Ahead, compatibility list, map, compatibility form, saved natal reading, settings. Parchment: home, settings and unsaved name form. The compatibility screenshot precedes the final SelectField styling pass.

Other files in before/after are raw capture attempts and **must not be treated as verified evidence based on filename alone**. Some Android deep links left a previous screen active. The gallery evidence from DS_01 remains component evidence, not a substitute for logged-out welcome/onboarding screenshots.

## Residual scan exceptions

`fontWeight|textTransform` outside design-system: **0**. Unicode zodiac/planet symbol scan: **0**.

Color literal scan outside design-system: 50 matches on 25 lines across these six files:

- `src/design/bands.ts`: semantic data visualization bands retained.
- `src/features/map/MapCanvas.tsx`: map geometry/base-map palette, explicitly out of scope.
- `src/features/exports/document.ts` and `native.ts`: exported artwork/paper backgrounds, explicitly out of scope.
- `src/features/exports/ExportScreen.tsx`: scaled export preview reflects exported artwork.
- `src/features/account/ExportAudit.tsx`: development export audit matches export artwork.

Remaining Lucide icons have no exact kit equivalent: home, circle-dot chart, users, share-2 (tab layout); arrow-up-down (compatibility); layers/list (map); maximize-2/rotate-ccw (interactive wheel); maximize-2 (sheet); ellipsis (reports and legacy gallery). Native navigation back arrows remain platform controls, tinted accent; an exact kit back-button replacement is not completed.

Retained provisional patterns: content cards, score/band chips, segmented controls, progress/skeleton, Undo snackbar, icon buttons, list rows and calendar date cells. Their data/accessibility behavior is retained. Map/chart internals and export layout geometry retain their existing spacing/font sizes. Some surrounding layout geometry also remains legacy; this is not a claim that every spacing literal has been eliminated.

## Still required for full spec acceptance

1. Complete screen-by-screen visual pass, including per-screen CTA pinning and title alignment, remaining picker trigger styling, and exact header-back glyph integration where it preserves native navigation.
2. Verified before/after coverage for every mapped route; replace raw captures that display the wrong route. Repeat compatibility capture after the final field changes.
3. Exact Parchment smoke test: real welcome, birth-date controls, and a saved reading. Current verified Parchment captures cover home/settings/name instead.
4. Check calendar and other deeper routes for the earlier text-rendering warning on a clean runtime; the Home/Ahead/reading retest alone does not establish a full fix.
5. iOS device/simulator visual checks, previously deferred. Android remains the working preview.

## Diff scope

No backend, contract, calculation or translation source was changed in this migration. Existing unrelated report changes are excluded.

```text
 frontend/app/(tabs)/_layout.tsx                          |  27 ++--
 frontend/app/_layout.tsx                                 |  18 ++-
 frontend/src/design-system/ThemeProvider.tsx             |   9 +-
 frontend/src/design-system/text/AppText.tsx              |   2 +-
 frontend/src/design/components/ActionSheet.tsx           |   3 +-
 frontend/src/design/components/BandChip.tsx              |  11 +-
 frontend/src/design/components/ContentList.tsx           |   9 +-
 frontend/src/design/components/DatePager.tsx             |   8 +-
 frontend/src/design/components/DateTimeField.tsx         |  11 +-
 frontend/src/design/components/Glyph.tsx                 |   6 +-
 frontend/src/design/components/IconButton.tsx            |   3 +-
 frontend/src/design/components/JobProgress.tsx           |   3 +-
 frontend/src/design/components/ProfileSwitcher.tsx       |  12 +-
 frontend/src/design/components/Segmented.tsx             |  16 +--
 frontend/src/design/components/Sheet.tsx                 |  17 ++-
 frontend/src/design/components/Snackbar.tsx              |  17 +--
 frontend/src/design/components/index.tsx                 | 158 +++++++--------------
 frontend/src/design/theme.tsx                            |  13 +-
 frontend/src/design/tokens.ts                            |  54 ++-----
 frontend/src/features/account/AccountScreen.tsx          |   4 +-
 frontend/src/features/account/AuthScreen.tsx             |  21 +--
 frontend/src/features/account/BrowserSignInScreen.tsx    |   3 +-
 frontend/src/features/account/ListAudit.tsx              |   3 +-
 frontend/src/features/account/NotificationsScreen.tsx    |   3 +-
 frontend/src/features/account/ReportsScreen.tsx          |   7 +-
 frontend/src/features/ask/ChatScreen.tsx                 |  16 ++-
 frontend/src/features/calendar/CalendarScreen.tsx        |   3 +-
 frontend/src/features/calendar/DayScreen.tsx             |   3 +-
 frontend/src/features/calendar/MonthGrid.tsx             |  11 +-
 frontend/src/features/calendar/OverviewScreen.tsx        |   5 +-
 frontend/src/features/chart/ChartDetailSheet.tsx         |   3 +-
 frontend/src/features/chart/ChartScreen.tsx              |  18 +--
 frontend/src/features/chart/ChartTables.tsx              |   3 +-
 frontend/src/features/chart/InteractiveWheel.tsx         |   4 +-
 .../features/compatibility/MatchReportScreen.tsx   |   5 +-
 frontend/src/features/compatibility/NewMatchScreen.tsx   |  18 ++-
 frontend/src/features/forecast/ForecastViews.tsx         |   9 +-
 frontend/src/features/forecast/SolarReturnScreen.tsx     |   4 +-
 frontend/src/features/home/HomeScreen.tsx                |   5 +-
 frontend/src/features/map/AreaScreen.tsx                 |   3 +-
 frontend/src/features/map/MapCanvas.tsx                  |   7 +-
 frontend/src/features/map/MapScreen.tsx                  |  20 +--
 frontend/src/features/map/MapSearch.tsx                  |  28 ++--
 frontend/src/features/onboarding/OnboardingScreen.tsx    |   7 +-
 frontend/src/features/profiles/ProfileEditor.tsx         |   4 +-
 frontend/src/features/profiles/ReadingScreen.tsx         |  20 ++-
 frontend/src/features/profiles/WheelPreview.tsx          |   2 +-
 frontend/src/features/shared/Blocks.tsx                  |   8 +-
 48 files changed, 311 insertions(+), 333 deletions(-)
```
