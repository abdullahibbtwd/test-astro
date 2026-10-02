# Real calculation preview — 2 October 2026

This is the private integration preview, separate from the saved-example demo.

## Open it

Double-click `D:\Dev\astrology-app\FE\Open Real Charts.cmd`.
Sign in with `demo@example.com`, code `000000`. This remains a **local preview login**, not email delivery or Google/Apple authentication.

A clearly labelled fictional profile, **Example - real calculation** (13 July 1990, 12:30, Sofia), was created for native smoke testing. Its chart was calculated by the existing Python engine. It is not the user's birth data. Add another person or edit the example to test other exact birth details.

The original `Open Android Preview.cmd` still opens the sample-data demo. Switching between services clears the app's cached session and results to prevent mixing their data; their server-side stores remain separate.

## Working now

- Real chart calculations for newly entered birth details, including correct historical time-zone conversion and derived Sun/Moon/Ascendant.
- Rejection of invalid dates and ambiguous/nonexistent times during daylight-saving clock changes.
- Birthplace search over the existing 2,126-city gazetteer, including aliases and Turkish names. This is not yet an unrestricted worldwide geocoder.
- Saved profiles and charts in SQLite; edits recalculate; service/app restart preserves data.
- Existing interactive chart, facts, tables and export interface use the calculated chart.
- Real calendar month/day/year/event/period data, Best Days and notification candidates, generated with model calls explicitly disabled.
- Daily and monthly forecast facts from that real calendar. Fresh forecast prose remains unconnected.
- Reading worker adapter, durable job status, bilingual cache, history, stale-profile protection and explicit retry after interruption. A fresh 17-section natal reading passed existing backend validation and both English/Turkish API schemas; the English reading was verified in Android.
- A shared, durable US$20 AI testing cap with per-call reservations, retry accounting, failed-call reservations and tests for concurrent spending. The ordinary launcher disables paid generation.

## Verification

- Full frontend check: 5,302 fixtures, 53 Node tests, 9 native component tests; type checking and lint.
- 3 Python budget tests, including concurrent reservations and restart persistence.
- Android smoke: computed fictional chart renders, calendar renders, session/profile survives app restart. API tests separately reopen the database and verify stored charts, edits, idempotency and deletion.
- Android/iOS JavaScript bundles built during this integration. No new native dependencies were added. No iOS device test.
- Screenshots: `artifacts/screenshots/real-chart.png`, `real-calendar.png`, `live-reading-en.png`.

## Paid-test status

The user explicitly approved the fictional chart payload and Google Gemini/OpenAI destinations. The fresh test completed successfully: **US$0.305641 recorded by the shared budget guard**, within the US$20 cumulative cap. This is the guard's conservative estimate, not a provider invoice.

The generated English and Turkish readings are saved locally under **Fictional AI test** (13 July 1990, 12:30, Sofia). The test uses coordinates 42.6977, 23.3217; it is separate from the earlier gazetteer-coordinate example. Android displays the fresh English reading. The normal launcher still disables new paid generation, while saved readings remain available.

Preserve `.local-data/ai-budget.sqlite`; the cumulative cap must not reset between runs. The earlier approval block is resolved for this fictional test.

Pricing sources checked on 2 October 2026:
- https://ai.google.dev/gemini-api/docs/pricing — Gemini 3.7 Flash standard text input/output, including thinking.
- https://developers.openai.com/api/docs/models/gpt-6-luna — GPT-6 Luna text rates.

The guard refuses unknown models, unverified endpoint overrides, oversized requests and pricing older than 9 October until reviewed. Unknown outcomes retain their full reservation; the recorded number is a conservative reserved-or-spent estimate, not a provider invoice.

## Still to do

1. Complete native PDF export, Turkish display and saved-report navigation checks using the fresh natal result; generation, bilingual schema validation, job persistence and English Android display have passed.
2. Connect fresh forecast prose and yearly forecasts; resolve rolling-month versus calendar-month semantics explicitly.
3. Connect arbitrary-pair compatibility, real-profile map calculations/recommendations and grounded Ask answers.
4. Replace the local demo login with email delivery and verified Google/Apple sign-in. Android Apple sign-in needs a browser-based flow. External account setup is still unconfirmed.
5. Complete account deletion/export, lifecycle cleanup and cache versioning/invalidation for engine/corpus changes. Calendar cache currently includes profile/chart/current coordinates/start date; old snapshots are retained locally.
6. Broaden native acceptance, accessibility and notification tests with real generated results. Public hosting/store release remains deferred.

## Developer notes

- Start API: `npm run local-api` (port 4020, loopback only). SQLite: `.local-data/app.sqlite`.
- Local Metro: port 8082 with `EXPO_PUBLIC_API_URL=http://127.0.0.1:4020/v1` and `EXPO_PUBLIC_BACKEND_MODE=local`.
- Run checks: `npm run check` and `npm run test:budget`.
- `.local-data/` is Git-ignored and excluded from Metro's watcher. It contains private profiles, charts, calendar outputs and (when enabled) readings; do not commit it.
- Calendar runs reuse the existing Python deterministic pipeline with `dry_run=True` and a model-call blocker. Existing source-cache material may supply validated calendar text; no new prose is fabricated.
- The local API serializes requests for a single private tester. Initial calendar computation can briefly delay another request. It is not a production multi-user service.
- Existing saved-data fixtures remain the demonstration API. Only catalogue/configuration metadata is reused by the local API; personal outputs come from real calculations or explicitly generated readings.

- Approved fictional smoke: `scripts/smoke-live-reading.ts` makes paid provider calls only with `ASTRO_ALLOW_PAID=1`; `scripts/import-live-smoke.ts` imports its exact chart-matched result without further AI calls. Outputs remain in ignored `artifacts/live/`.
