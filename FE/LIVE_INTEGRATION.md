## Email links, Google and ChatGPT — 3 October 2026

The user chose free email links, Google now, and Apple later. Email-link and Google browser sign-in are implemented for the local Android preview: PKCE exchange stays on the loopback server, and the app retrieves its session using a separate random polling secret. Links can open on this computer or in the emulator with ADB reverse enabled. Cancellation, expiry, replay rejection and owner checks are covered by tests. Apple is hidden in real-auth mode.

**Activation remains pending:** Google branding is prepared in the existing Astrology app Cloud project, at its required User Data Policy acceptance. The Supabase redirect dialog is prepared for `http://127.0.0.1:4020/v1/auth/browser/callback/*`. Neither submission is complete. The user has been asked to approve Google's policy and the Google credential/Supabase connection. No OAuth client was created, no email was sent, and `.local-data/auth-config.json` still has `enabled: false`. Real sign-in has not been exercised on Android.

Validation: TypeScript/lint and **83 API/logic tests + 16 native tests** passed; TypeScript and the native sign-in test also passed after the final Google waiting-screen copy correction. Existing profiles and the AI spending ledger are unchanged. The normal preview still disables new paid generations.

The user additionally requested **Continue with ChatGPT** and use of their own ChatGPT allowance. Official OpenAI documentation confirms a local-app OAuth route with optional plan-use permission. This is a new requirement, **not an implemented or activated feature**. See [AUTH_INTEGRATION.md](AUTH_INTEGRATION.md) for the connection plan, prerequisite account linking, and safeguards for the approved reading pipeline. No OpenAI credentials were requested or registered and no AI usage was consumed by this work.

Older status sections below are historical; the free-link decision is resolved.

---

## Authentication update — 3 October 2026

Supabase **Astro app** was selected and its public-key connection verified against `/auth/v1/settings`. Email is enabled; Google and Apple are not configured. The user supplied the owner email, saved only in ignored `.local-data/auth-config.json` in the D: checkout. **`enabled` remains false: real login has not been activated or tested end to end on Android.** The existing demo preview remains available.

Implemented a server-side Supabase Auth adapter for email OTP verification, native provider ID-token exchange, refresh and logout. Every protected request verifies identity with Supabase; only the configured confirmed email is accepted, and the first verified UUID is pinned. Supabase sessions use a separate namespace, so legacy demo tokens cannot access real-auth mode. Once enabled for a database, removing or changing the owner/project configuration fails startup instead of restoring demo access. Tokens are hashed in the local store; no admin/service-role key is used. Existing local profile IDs and data are preserved. Local account deletion still deletes local data only, not the Supabase identity.

**Pending decision:** Supabase's current Free dashboard requires custom SMTP or Pro to edit its default sign-in email, which contains a link rather than the app's six-digit OTP. Recommended: adapt the app to the free email-link flow. Alternative: configure a separate email sender and retain OTP. No service purchase, template change, sign-in email, or birth-data upload occurred. The email-link callback and mobile flow are not implemented yet.

Validation: TypeScript and lint pass; **81 API/logic tests + 15 native tests pass**. New coverage rejects wrong/unconfirmed identities and malformed provider replies, checks old-demo-token rejection, owner UUID binding, refresh replay, logout and downgrade prevention. Live verification checked project connectivity/settings only, not a real user session. AI budget unchanged.

Activation requires completing the selected email flow, then restarting both local API and Metro through `scripts/Start-Android-Preview.ps1 -RealCharts` with real auth enabled. The launcher reads `.local-data/auth-config.json` and supplies `EXPO_PUBLIC_AUTH_MODE`; existing listeners must be restarted for changed settings. Do not enable the current OTP UI against the unmodified link-only default template.

---

## Current status — 3 October 2026: live maps and account tools

The Android preview is updated in `D:\Dev\astrology-app\FE`. This is substantial progress, but the whole product is **not yet complete**. Real sign-in still needs an account-service choice, and several specified features do not yet have live backend implementations.

### Completed in this continuation

- Real map heat layers for all 11 goals; city and selected-point facts; country/region reports; filtered destination recommendations. Calculations use the existing approved backend, with no model calls for facts or ranking.
- Written place, area and destination reports now use the approved reading pipelines. The app shows facts first, polls persistent jobs, handles failure/retry, caches English/Turkish results, and opens finished readings from Saved Reports. Changed birth details or recommendation home locations cannot receive stale results. Generated explanations cannot change the destination ranking.
- Local **Download my data** creates a JSON file and opens Android sharing. Exports omit login credentials and API keys. **Delete account** clears local profiles/readings/session records and derived map caches, refuses deletion while a reading is running, and preserves the cumulative spending ledger. Previously saved/shared files remain outside the app. Deletion was tested on disposable databases, not the user's preview account.
- Fixed empty-goal place links and malformed recommendation links; unavailable Solar Return controls are hidden. The sample-server UI remains available separately.

### Evidence and how to see it

- `npm run check`: **78 API/logic tests + 15 native tests passed**, with TypeScript, lint, OpenAPI and 5,302 fixture checks. Android/iOS JS bundles built successfully; this is not a claim of native iOS acceptance.
- Fresh, validated bilingual readings generated for the already approved fictional birth (13 July 1990, 12:30, Sofia): Sofia place, Bulgaria country, and Love destination recommendations. The populated result contains **10 destinations across 3 line groups**; a narrow-filter empty result was also checked. An adapter error was corrected and a no-provider regression added for all four writing paths (place, area, goal recommendation, overall).
- Cumulative tracked AI spend/reservation: **US$0.433985 of the US$20 cap**. This includes all supervised calls, including a repeated narrow-filter smoke test. The ordinary preview launcher still disables new paid generation; saved test readings remain viewable. Pricing guard expires after 9 October and requires re-verification before later paid tests.
- On Android, open **Your space → Saved reports** and choose a report for **Fictional AI test**. Sofia and Bulgaria are saved alongside the recommendations and forecasts. Native account sharing and saved place/destination navigation were exercised. Screenshots: `artifacts/screenshots/real-map-heat.png`, `live-place-reading.png`, `account-data-share.png`.

### Still needed, in plain language

1. **Real sign-in:** the app needs a service that stores accounts and verifies email/Google/Apple logins. Pending user question: is there an existing service/project, should one be chosen, or should testing keep the local login? Until configured, use `demo@example.com` / `000000` in the emulator.
2. **Ask Astrology and Solar Return:** their screens exist against the sample API; matching live services are not connected. They remain disabled in the real preview.
3. **Family compatibility:** the approved backend has a general relationship mode, but no family-specific mode. The spec's general fallback has not been enabled in this local integration. Love/work wiring is implemented; a fresh paid compatibility test still awaits the earlier response about the second fictional profile.
4. **Final acceptance and release setup:** broader real-birth/lens/location testing, physical-device accessibility/performance, native iOS, production hosting/account configuration, final legal links/identity and release map provider. These are not claimed as complete by the automated checks.

The older sections below are historical snapshots and may list gaps closed by this update.

## Real map lines — 3 October 2026

- Map lines and crossings now come from the selected profile's actual birth chart through the approved compute_acg / compute_parans backend. Nearby-city lists use its deterministic city scan, with English/Turkish names, rounded distances and proximity tiers. Static country/region boundaries are available to the map.
- Results are cached by chart key and adapter version, survive API restart, and change when birth details change. No model calls are allowed in this bridge. The existing display-geometry simplification is shared with the sample adapter; no astrology calculation rules changed.
- Verified using two distinct fictional births: 44 backend lines (40 planetary plus 4 North Node; backend treats South Node as a derived display counterpart), different geometry, bilingual city results and compressed payload below 150 KB. Full check: 67 Node tests, 10 native tests, 5,302 fixtures, typecheck/lint passed.
- Android displays real lines and the Sun/MC city list (including Asmara and Krasnodar). Screenshot: artifacts/screenshots/real-map.png. AI cost unchanged at $0.370374 of the approved $20 cap.
- Still pending: goal heat layers, city/point and area reports, recommendations, written place readings, grounded Ask, real sign-in and account/data lifecycle. The separate fresh compatibility AI test still awaits the second fictional profile response.

## Saved Reports integration — 3 October 2026

- Saved Reports now includes finished compatibility readings and monthly/yearly forecast readings, with English/Turkish titles and accurate profile, month and focus links. Daily readings remain in Today because the approved report contract has no daily report type.
- Removing a saved entry persists across restart without deleting profiles or cached prose. Edited/deleted profiles and changed forecast locations hide outdated entries. Pending and failed generations are excluded.
- Existing cached forecasts are indexed when opened; the already approved October 2026 monthly and October 2026–September 2027 yearly examples are indexed in the running preview. No model calls or extra budget used (tracked total remains $0.370374).
- Verification: 66 Node tests and 10 native component tests passed; typecheck/lint and Android/iOS bundles passed. Android Saved Reports displays the real saved forecasts, and opening the monthly entry displays the correct October 2026 reading. A native regression verifies the saved focus overrides the remembered focus.
- Fresh compatibility AI generation remains unverified pending the earlier second-fictional-profile question. Family-specific compatibility, maps integration, grounded Ask, real authentication and account/data lifecycle remain to be completed.

## Compatibility integration — 3 October 2026

- Added local create/list/read/delete compatibility endpoints for the selected saved profiles, using the approved relationship grounding and reading pipeline. Love maps to personal; work maps to professional. Family is disabled in the real preview because the approved backend has no family-specific mode.
- Persistent bilingual jobs, deduplication, explicit retry, interruption recovery, context validation and protection against edited/deleted profiles. Deleting a running report cannot resurrect it. Idempotency replay rechecks that the report is still valid.
- Verified offline with two fictional charts (13 July 1990 and 20 February 1992, both 12:30 Sofia). No provider calls. Fresh paid compatibility generation is not yet tested; authorization for the second fictional profile has been requested. Existing budget total remains $0.370374 of $20.
- Full check passed: 64 Node tests, 9 native component tests, 5,302 fixtures, typecheck and lint. Android Match screen loads against the real API. Compatibility history is available in Match; integration into the separate Saved Reports list remains pending.
- Next: approved live compatibility generation and Android reading verification, then maps, grounded Ask, real authentication and remaining account/data lifecycle work.

# Real calculation and reading preview — 3 October 2026

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
- Daily, monthly and yearly forecast facts from that real calendar. Year shows twelve calendar months, quarters split by the backend day-count rules, up to six significant supportive and challenging periods each, major transits, eclipses, slow-planet ingresses and retrogrades. Fresh daily/monthly/yearly prose now uses the existing predictive calculation, grounding, reading and translation pipeline, with persistent bilingual jobs and caches.
- Reading worker adapter, durable job status, bilingual cache, history, stale-profile protection and explicit retry after interruption. A fresh 17-section natal reading passed existing backend validation and both English/Turkish API schemas; both languages, saved-report navigation and full Turkish PDF export were verified in Android.
- A shared, durable US$20 AI testing cap with per-call reservations, retry accounting, failed-call reservations and tests for concurrent spending. The ordinary launcher disables paid generation.

## Verification

- Full frontend check: 5,302 fixtures, 53 Node tests, 9 native component tests; type checking and lint.
- 3 Python budget tests, including concurrent reservations and restart persistence.
- Android smoke: computed fictional chart renders, calendar renders, session/profile survives app restart. API tests separately reopen the database and verify stored charts, edits, idempotency and deletion.
- Android/iOS JavaScript bundles built during this integration. No new native dependencies were added. No iOS device test.
- Screenshots: `artifacts/screenshots/real-chart.png`, `real-calendar.png`, `live-reading-en.png`, `live-reading-tr.png`, `real-year.png`.

## Paid-test status

The user explicitly approved the fictional chart payload and Google Gemini/OpenAI destinations. The fresh test completed successfully: **US$0.370374 recorded by the shared budget guard**, within the US$20 cumulative cap. This is the guard's conservative estimate, not a provider invoice.

The generated English and Turkish natal and forecast readings are saved locally under **Fictional AI test** (13 July 1990, 12:30, Sofia). The test uses coordinates 42.6977, 23.3217; it is separate from the earlier gazetteer-coordinate example. Android displays the natal reading and fresh General forecasts: 3 October 2026 (day), October 2026 (month), and October 2026–September 2027 (year). The normal launcher still disables new paid generation, while saved readings remain available.

Preserve `.local-data/ai-budget.sqlite`; the cumulative cap must not reset between runs. The earlier approval block is resolved for this fictional test.

Pricing sources checked on 2 October 2026:
- https://ai.google.dev/gemini-api/docs/pricing — Gemini 3.7 Flash standard text input/output, including thinking.
- https://developers.openai.com/api/docs/models/gpt-6-luna — GPT-6 Luna text rates.

The guard refuses unknown models, unverified endpoint overrides, oversized requests and pricing older than 9 October until reviewed. Unknown outcomes retain their full reservation; the recorded number is a conservative reserved-or-spent estimate, not a provider invoice.

## Still to do

1. Extend forecast acceptance to Love/Work lenses and other locations/profiles; add forecast entries to Saved reports. General day/month/year readings are verified end to end for the approved fictional chart. The ordinary preview still disables new paid generation; it serves saved results.
2. Connect arbitrary-pair compatibility, real-profile map calculations/recommendations and grounded Ask answers.
3. Replace the local demo login with email delivery and verified Google/Apple sign-in. Android Apple sign-in needs a browser-based flow. External account setup is still unconfirmed.
4. Complete account deletion/export, lifecycle cleanup and cache versioning/invalidation for engine/corpus changes. Calendar cache currently includes profile/chart/current coordinates/start date; old snapshots are retained locally.
5. Broaden native acceptance, accessibility and notification tests with real generated results. Public hosting/store release remains deferred.

## Developer notes

- Start API: `npm run local-api` (port 4020, loopback only). SQLite: `.local-data/app.sqlite`.
- Local Metro: port 8082 with `EXPO_PUBLIC_API_URL=http://127.0.0.1:4020/v1` and `EXPO_PUBLIC_BACKEND_MODE=local`.
- Run checks: `npm run check` and `npm run test:budget`.
- `.local-data/` is Git-ignored and excluded from Metro's watcher. It contains private profiles, charts, calendar outputs and (when enabled) readings; do not commit it.
- Calendar runs reuse the existing Python deterministic pipeline with `dry_run=True` and a model-call blocker. Existing source-cache material may supply validated calendar text; no new prose is fabricated.
- The local API serializes requests for a single private tester. Initial calendar computation can briefly delay another request. It is not a production multi-user service.
- Existing saved-data fixtures remain the demonstration API. Only catalogue/configuration metadata is reused by the local API; personal outputs come from real calculations or explicitly generated readings.

- Approved fictional smoke: `scripts/smoke-live-reading.ts` makes paid provider calls only with `ASTRO_ALLOW_PAID=1`; `scripts/import-live-smoke.ts` imports its exact chart-matched result without further AI calls. Outputs remain in ignored `artifacts/live/`.

## Latest verified increment

- Yearly facts are connected for the selected profile, with localized month links and calendar event detail navigation. Each home profile has an Ahead button.
- Day/month requests now anchor calculation to the requested calendar month instead of silently relying on today's rolling snapshot; invalid dates are rejected before calculation. Preview accepts forecast dates in 2000–2099.
- Calendar item lookup also finds snapshots for the same profile, chart and current coordinates, so future-year events can open without substituting another profile's facts.
- `npm run check` passed: 53 Node tests, 9 native tests, 5,302 validated fixtures, types and lint. API regression includes a future-year request and its event detail, complete-month/day requests and invalid dates.
- Android: year loaded for Fictional AI test (October 2026–September 2027), period detail opened, monthly navigation passed. Fresh natal reading opened from Turkish history; full Turkish PDF exported (15 pages). All 17 section texts matched the source after Unicode ligature/whitespace normalization; rendered pages inspected.
- No new paid provider requests in this increment; guard total remains US$0.305641.

## 3 October — written forecast integration

- Reused the approved predictive backend without altering its astrology rules: compute_forecast → ground_forecast → existing calendar context → run_reading → existing English translator. Paid calls use the same persistent US$20 guard as natal readings.
- Month and year requests begin on the first of the selected month. Displayed thirds/quarters now match `pr_calendar.segment_dates` exactly (including leap years), rather than fixed 1–10/11–20 splits or three-calendar-month quarters. Dry-run tests compare all three horizons to the real backend with model calls blocked.
- Forecast facts return immediately alongside absent/pending/failed/ready prose. Jobs cache both languages by profile, chart, current coordinates/time zone, target date, horizon, lens and adapter version. Edits during generation reject stale results; restart interruptions require explicit retry. Window/context mismatches and incomplete bilingual output cannot enter the cache.
- Fresh fictional General tests: day, month and year succeeded, each with zero backend validation warnings. Cumulative budget estimate rose from US$0.305641 to US$0.370374 (about 6.47 cents for this increment, including wording-fix retests). All six live API responses passed their schemas; English day/month/year and Turkish month were checked in Android.
- Checks: app checks passed (57 Node + 9 native tests, 5,302 fixtures, types/lint), plus 13 predictive-reading backend tests. The normal launcher remains paid-disabled, while cached forecast prose is available.
- Developer helpers: `scripts/smoke-live-forecast.ts day|month|year` makes supervised paid requests using only the fixed fictional chart; `scripts/import-live-forecast.ts` imports the already generated output with exact context checks and no provider calls; `scripts/verify-live-forecast.ts` validates the six cached responses from the running local service.
- Screenshots: `artifacts/screenshots/live-forecast-day.png`, `live-forecast-month.png`, `live-forecast-year.png`, `live-forecast-month-tr.png`. Generated artifacts remain ignored.

- During native review, the forecast prose incorrectly attached a transit sign to a natal target. Fixed the upstream descriptor to say “transiting Neptune in Aries trine natal Mercury,” and made sign ownership explicit in the reading prompt. All 13 existing predictive-reading offline tests pass, including the updated regression. Calculation/grounding rules are unchanged.
- Forecast cache revision 2 and a client query-cache version change prevent reuse of the earlier text. Regenerated all three fictional horizons after the fix: zero backend validation warnings, six live API schemas passed again, and the corrected English/Turkish monthly overview explicitly attributes Aries to Neptune. Reading quality still needs broader human acceptance; structural checks cannot prove every generated sentence correct.

- Fixed an observed Expo typed-route generation race: the launcher uses an absolute CLI path and stops only the competing preview whose command belongs to this same checkout. Other projects are not stopped. A malformed generated router file was regenerated, then type/lint/test checks passed.
