# Phase 2 — shell and navigation

Status: implemented and ready for review. Branch: `fx/phase-2-shell-navigation`. Phase 1 approval was received. Phase 3 has not started.

## Changes

| Item | Result and main files (under FE/) |
|---|---|
| FX2.1 | Shared IconButton, Segmented, Sheet, ActionSheet, Snackbar, ProfileSwitcher, BandChip, DatePager and localized block/line Skeleton; interactive Gallery stories. `src/design/components/*`, `features/account/Gallery.tsx`. |
| FX2.2 | Fixed native headers, centralized safe areas, platform push transitions, Ask/export modals, large-title settings for lists. Auth/onboarding retain their own fixed header. `app/_layout.tsx`, `components/index.tsx`, nested layouts. Legacy Ahead URLs redirect into the tab rather than mounting duplicate screens. |
| FX2.3 | Header profile picker on Chart/Ahead/Map; self first, recent people next; persisted selection; two compatibility picker rows with swap and excluded opposite selection; Ask header picker. `ProfileSwitcher.tsx`, `state.ts`, tab layout, NewMatchScreen, ChatScreen, useProfile. |
| FX2.4 | Pinned horizon, date pager and short lens controls. Calendar renders inside the same shell. Lens persistence retained. `AheadScreen.tsx`, `CalendarScreen.tsx`. |
| FX2.5 | Eleven two-column life-area tiles, band shapes, optional score meter and driver detail sheet with Calendar link. `ForecastViews.tsx`. |
| FX2.6 | Compact big three, square wheel, overlay controls, one-row tabs and inline saved reading. Normal-size wheel permits page scroll; zoomed wheel pans. New natal reading requires the Prepare action. `ChartScreen.tsx`, `InteractiveWheel.tsx`, `InlineReading.tsx`, `ChartDetailSheet.tsx`. |
| FX2.7 | Kind-specific progress titles, duration estimate, elapsed time while visible, stage labels and leave-screen note. Long-job completion/failure uses named Snackbar only away from its destination; short text jobs stay quiet. `JobProgress.tsx`, `JobLifecycle.tsx`, `job-notification.ts`. |
| FX2.8 | Choice dialogs become sheets; informational/success feedback becomes snackbars. Reversible report/history/thread removal waits for Undo to settle before DELETE. `deferred-delete.ts`, account/export/Ask/compatibility/map/chart screens. |
| FX2.9 | Map fills its tab; floating search/goals/tools, layers/legend/list sheets, heat legend samples; place/area/line report sheets expand into a full-screen route and return correctly. `MapScreen.tsx`, `MapCanvas.tsx`, `MapSearch.tsx`, `ReportSurface.tsx`, `app/map/full.tsx`. |
| FX2.10 | Saved rows have a trailing menu and swipe Delete; horizontal filters; Undo restores without DELETE; confirmed deletion removes stale cached references. `ReportsScreen.tsx`, `api/deleted-cache.ts`. Virtualization remains Phase 4. |

## Verification

- API/logic: **92 passed**. Native: **41 passed across 14 suites**. Typecheck and lint passed. Targeted `git diff --check` passed.
- New regression coverage: Turkish four-segment layout at 200% text, Snackbar replace/timeout/Undo and screen-reader timer pause, zero DELETE on Undo/exactly one on dismissal, deletion failure restoration, cached-list removal, Sheet initial presentation, six-person picker order/exclusion and persisted hydration, explicit natal generation, named job notification filtering.
- Android 1080 × 2400: Chart, Today, Month, Calendar, Best Days, Saved, profile picker, new compatibility, map/heat legend, place sheet/full route/back reviewed. Today first content label starts at y822 (34.3% of screen; card begins above it).
- Chart: 1× drag scrolls the page. At 2× the chart geometry moves while the Reading control remains at y1690; Reset returns to 1×. English and Turkish tabs fit one row.
- Large text: system font scale 2.0 checked in Gallery in English/Turkish and in Today tiles. Long band labels wrap, tile height grows. System text restored to 1.0, language English, light theme.
- Map: search result tap, report at 55%, expansion, Android back to sheet, then back to map verified. Native testing caught and fixed clipped search-result hit bounds and an initially closed Sheet lifecycle bug. Saved filter row growth also fixed.
- Reversible-delete network behavior tested with mocked mutations, preserving the tester's real records. Six-person acceptance uses a six-person test fixture; emulator keeps its two existing people.
- Skeletons are static, including reduced motion. No shimmer is used.

### Verification limits and retained compatibility

- iOS swipe-back, large native titles and VoiceOver require an iOS device/simulator and were not runtime-tested on this Windows computer. TalkBack semantics/timer behavior have test coverage; this is not a full spoken TalkBack audit (Phase 3).
- Auth/onboarding and disabled Ask flows have code/test coverage; a fresh signed-out onboarding screenshot run was not performed to preserve the working test login. Screenshots are representative, not a before/after recording of every changed feedback state.
- No new paid jobs were run. Progress/completion/error behavior is tested with fake jobs. Existing cached reports were used for Android checks.
- Legacy `/ahead/today` and `/ahead/calendar` files remain as redirects only. The inactive `home/TabScreen.tsx` still contains the old ScrollView/profile chips; deleting dead code is explicitly Phase 4. Active screen ScrollViews are centralized or horizontal/list internals.
- Inline Chart detects saved references and client-cached readings. A server-only cached reading whose Saved reference was removed may require the explicit Prepare button; no new backend cache-probe API was introduced.

## Remaining native alerts

Only irreversible confirmations and OS settings prompts remain (six calls):

- `src/features/profiles/ProfileDetail.tsx`: delete person.
- `src/features/profiles/ChartsScreen.tsx`: delete person.
- `src/features/profiles/ProfileEditor.tsx`: recalculate chart.
- `src/features/calendar/BestDayScreen.tsx`: notification permission/settings.
- `src/features/account/AccountScreen.tsx`: notification settings.
- `src/features/account/NotificationsScreen.tsx`: notification settings.

No `Alert.alert` remains in Chart or Map.

## Spending and scope

Before and after: **302 ledger calls; 1,217,258 microdollars ($1.217258); zero unsettled calls**. Difference: **$0 and zero calls**. Paid generation remains disabled. No Python pipelines, bridges, API contracts or credentials changed. Existing unrelated user documents were left out of commits.

## Screenshots

Open [the screenshot gallery](FE/artifacts/fx-phase-2/index.html). Current-run baselines: Chart, Ahead, Map, Saved. Older October 3 acceptance baselines are explicitly labeled in the gallery. Images stay local under ignored `FE/artifacts/`; they may contain the tester's saved labels and report content and are not committed.

## Turkish review

English/Turkish keys remain in parity. A native Turkish speaker should review all these new or changed strings (especially job-kind phrasing, duration/plural wording, picker labels and shortened lens labels):

`loading`, `choosePerson`, `showingPerson`, `undo`, `removed`, `workShort`, `loveShort`, `generalShort`, `prepareMyReading`, `usuallyMinutes`, `usuallyMinute`, `usuallySeconds`, `leavePreparing`, `openInCalendar`, `tenseShort`, `flowingShort`, `conjunctionShort`, `reportActions`, `deleteFailed`, `clear`, `more`, `supportive`, `preparingPlaceNamed`, `waiting`, `yourReport`, `reportCouldNotPrepare`, `kind_natal_reading`, `preparing_natal_reading`, `ready_natal_reading`, `kind_month_reading`, `preparing_month_reading`, `ready_month_reading`, `kind_year_reading`, `preparing_year_reading`, `ready_year_reading`, `kind_compatibility`, `preparing_compatibility`, `ready_compatibility`, `kind_place_reading`, `preparing_place_reading`, `ready_place_reading`, `kind_area_reading`, `preparing_area_reading`, `ready_area_reading`, `kind_recommendation`, `preparing_recommendation`, `ready_recommendation`, `kind_solar_return`, `preparing_solar_return`, `ready_solar_return`, `kind_day_reading`, `preparing_day_reading`, `ready_day_reading`, `kind_element_notes`, `preparing_element_notes`, `ready_element_notes`, `kind_calendar_text`, `preparing_calendar_text`, `ready_calendar_text`, `kind_best_day_text`, `preparing_best_day_text`, `ready_best_day_text`, `stageCalculating`, `stageGrounding`, `stageWriting`, `stageTranslating`, `stageChecking`

## Found, not fixed

- Raw country codes, dates and report-title casing in older report content: Phase 3 formatting work.
- Full accessibility audit, calendar legend and Best Day detail: Phase 3.
- Preview map geometry/heat edges, list virtualization, shared job polling and dead code: Phase 4.
- At 200% text the date pager visually shortens the date; the full accessibility label remains available. Broader large-text audit belongs to Phase 3.

## Next step

Review this phase before Phase 3. FX_00 §2.1 requires: “After each phase stop, deliver the phase report (§4) and wait for Radul's approval before starting the next phase.” No merge or Phase 3 work has been performed in this phase.
