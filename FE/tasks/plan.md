# Complete frontend implementation plan

User instruction: continue until all specified functionality is implemented, then hand over for testing. Existing approved specs FE_01–FE_09 and the locked wheel spec govern the work. No additional approval checkpoint for ordinary implementation.

## Sequence and dependencies
1. Chart facts: tables, two-height detail sheet, drill links. Verify catalogue labels, exact geometry unchanged, native navigation.
2. Chart engine: pure compute model, interactive selection/zoom, parity gates. Depends on 1; verify all fixture geometries and touch targets.
3. Exports: chart/full reading PDFs, raster downloads and private-by-default share cards. Depends on chart renderer; verify outputs.
4. Resource lifecycle: generated subparts, flags, profile/timezone routing, global completion notice. Verify no fabricated text and background behavior.
5. Home/Today: all API blocks, date/lens controls. Verify available real fixture, missing data errors and flags.
6. Month/Year/Solar Return: API-driven screens, navigators, readings and linked events. Verify contract fixtures where supplied; report unavailable upstream endpoints honestly.
7. Compatibility: pair/type creation, history, report and export. Verify distinct people, idempotency, flags, generated sections.
8. Calendar: month/day/item/year/period timeline plus accessible list. Verify complete fixture data and navigation.
9. Best Days: overview/activity/day and one-off reminders. Verify labels, grades, no hidden calculation inputs.
10. Notifications: deterministic timezone/cap selection, OS synchronization, preferences and deep links. Unit-test all scheduler rules.
11. Map: native base map, lines/heat, filters, hit priority and accessible list. Requires provider style configuration for release; preserve attribution.
12. Place/area reports and recommendations: API-driven cards/text, filters, map/list results, missing-data states. Verify real supplied fixtures and routes.
13. Ask: conversations, streaming, cards/context, quota, retry/stop/feedback. Verify scripted SSE and no chart values in requests.
14. Remaining account polish: configured OAuth adapters, location timezone notice, gallery and privacy/export behavior.
15. Full verification: type/lint/test/bundles, Android journeys, exports and accessibility; report external blockers separately.

## Architecture
Keep React Query and centralized response validation. Reuse supplied interpretation text only. Preserve chart geometry and original Drive files. All implementation stays under D:\Dev\astrology-app. Unknown upstream capabilities get explicit errors, never invented readings or successful fake exports.

## Verification checkpoints
After each vertical slice run its focused regressions and relevant native smoke check. Run complete checks at cross-feature checkpoints. Track progress in todo.md and BUILD_PROGRESS.md. User tests only after the completed build, subject to honestly stated external requirements.
