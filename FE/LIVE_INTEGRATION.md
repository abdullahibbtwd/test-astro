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
- Reading worker adapter, durable job status, bilingual cache, history, stale-profile protection and explicit retry after interruption. This infrastructure is tested with injected saved outputs; a fresh paid reading has **not** been verified.
- A shared, durable US$20 AI testing cap with per-call reservations, retry accounting, failed-call reservations and tests for concurrent spending. The ordinary launcher disables paid generation.

## Verification

- Full frontend check: 5,302 fixtures, 53 Node tests, 9 native component tests; type checking and lint.
- 3 Python budget tests, including concurrent reservations and restart persistence.
- Android smoke: computed fictional chart renders, calendar renders, session/profile survives app restart. API tests separately reopen the database and verify stored charts, edits, idempotency and deletion.
- Android/iOS JavaScript bundles built during this integration. No new native dependencies were added. No iOS device test.
- Screenshots: `artifacts/screenshots/real-chart.png`, `real-calendar.png`.

## Paid-test status

**Spent: US$0. No paid request has executed.** Automatic approval review rejected the proposed fresh-reading smoke test pending explicit approval of the payload and destination. A question is pending for sending the fictional chart and derived astrology facts to Google Gemini and OpenAI, within the already approved US$20 total.

Do not start external calls or enable the paid worker until that answer arrives. No workaround should bypass the rejection. The budget limit is cumulative across the integration effort and is not reset per run. Preserve `.local-data/ai-budget.sqlite` once initialized.

Pricing sources checked on 2 October 2026:
- https://ai.google.dev/gemini-api/docs/pricing — Gemini 3.7 Flash standard text input/output, including thinking.
- https://developers.openai.com/api/docs/models/gpt-6-luna — GPT-6 Luna text rates.

The guard refuses unknown models, unverified endpoint overrides, oversized requests and pricing older than 9 October until reviewed. Unknown outcomes retain their full reservation; the recorded number is a conservative reserved-or-spent estimate, not a provider invoice.

## Still to do

1. With the pending payload approval, run a fresh natal reading, inspect its grounding/validation and verify Android reading/export/history end to end. Record actual/reserved test cost.
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
