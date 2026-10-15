> Historical progress log. For the current 6 October 2026 baseline, team setup and remaining payments/design/iOS work, start with [FRONTEND_TEAM_HANDOFF.md](FRONTEND_TEAM_HANDOFF.md). Ask, guest onboarding and Google login status changed after the entries below.

## Live user testing enabled — 3 October 2026

At the user's explicit request, enabled paid reading generation for the running Android preview under the unchanged shared US$20 total cap. Google owner authentication remains enabled. The launcher now accepts `-RealCharts -EnableReadings -RestartApi`; omit EnableReadings with RestartApi to disable new generation. Existing API processes are verified before stopping; do not restart while a reading is active.

Both configured providers returned text in a small guarded connection test. No personal birth data was used in those probes. Ledger after probes: **US$0.434003 spent/reserved**, about **US$19.565997 remaining**. All four reading bridges still install the shared budget guard, with conservative reservations and the existing 9 October pricing expiry. Current official rates were checked; no cap or deadline increase. Three budget tests pass; PowerShell script syntax validated; the live server confirms paid generation enabled. Emulator remains signed in at Home.

The user can now generate fresh natal, daily/monthly/yearly, love/work compatibility and map/place/area/recommendation readings. Previously cached reports remain usable. [USER_TEST_GUIDE.md](USER_TEST_GUIDE.md) contains navigation, expected results, limits, issue-reporting instructions and enable/disable commands. OpenAI login, Apple, Ask, Solar Return and family compatibility remain outside active testing. Full live feature acceptance now belongs to the user's testing; provider connectivity alone does not establish reading quality.

---

## Google login verified with the selected test account — 3 October 2026

The user chose a separate Google account for private app testing. Added it to the existing Google OAuth test-user list and changed the ignored local owner-email configuration to match. Before migration, verified that no Supabase identity or real session was bound. With the API stopped, updated only the authentication scope marker and config; compared all other database records before/after and confirmed they were unchanged. Both existing profiles are retained. The cloud project administration account was not changed; its original test-user entry remains, but the local API accepts only the newly configured owner email.

Completed live Android Google sign-in, Supabase PKCE callback, app session retrieval and return to Home. Your space displays the selected Google email. Supabase identity is now pinned; future owner changes must not bypass this binding. The first completed attempt expired while returning through browser history; a fresh attempt and direct app return succeeded. Completed tickets remain available for one minute. No passwords or tokens were copied to chat or disk artifacts.

Updated stale preview copy that still said map layers and real sign-in were under construction. Email-link end-to-end verification and live refresh/logout remain untested; automated auth tests cover these session operations. No paid AI calls were made. OpenAI login/plan sharing and Apple remain deferred.

---

## Google activated; OpenAI login deferred — 3 October 2026

The user approved the Google policy/client/Supabase connection and explicitly removed OpenAI/ChatGPT login and plan sharing from the current scope. Apple also remains deferred. Existing server-side OpenAI reading integration is unaffected.

Completed: Google branding in the existing Astrology app Cloud project; a Web OAuth client with Supabase's exact callback; Google provider enabled in Supabase; private loopback callback allowlisted; owner email added as the sole Google test user. No Google client secret was saved to the codebase or chat. Google remains in Testing, not public production.

Live provider settings confirm email and Google enabled, Apple disabled. Local auth is now enabled and both API and Metro have restarted with real-auth settings. Android displays Google/email sign-in without demo login controls; Google launches the emulator browser. **End-to-end user login remains unverified:** Chrome's first-run terms screen requires user input, followed by Google sign-in. The user has been asked to complete that step. No sign-in email or paid AI request was sent.

A regression found that first real login retained the demo email label. The session now stores the verified email while retaining the existing local user/profile IDs. Targeted auth checks cover this migration. Finish live Google callback, app return, refresh/logout and email-link acceptance once the user completes browser setup.

---

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

> **3 October update:** Written daily, monthly and yearly forecasts now use the existing backend. Fresh General readings in English/Turkish passed validation for Fictional AI test and are saved in the Android preview. Cumulative tracked AI cost: US$0.370374. See [LIVE_INTEGRATION.md](LIVE_INTEGRATION.md).

> **2 October integration update:** Real charts, saved profiles, calendar, Best Days and daily/monthly/yearly facts now work in the separate local preview. See [LIVE_INTEGRATION.md](LIVE_INTEGRATION.md) for current status. The approved fresh natal reading passed backend and bilingual schema validation and displays in both languages under Fictional AI test, with saved-report navigation and full Turkish PDF export checked; the budget guard records US$0.305641 of the US$20 cap. The earlier snapshot below describes the sample demo.

# Astrology app — handoff report

Updated: 2 October 2026 (Europe/Sofia)

## Plain-language status

The Android app has its main screens and interactions. It runs in the emulator on this computer. Many results still come from saved examples, so entering a new birthday does not yet reliably produce that person's real results in the app.

The separate Python project already contains calculation and written-reading pipelines. The user confirms both work. The next job is to connect the app to these programs, save real profiles and results, and verify the complete experience. This is integration work, not a request to rebuild the astrology engine.

## Decisions confirmed with the user

- Next milestone: private testing by the user, using real birth details.
- Device: the Android emulator on this computer. A physical phone, public hosting and store release are not required for this milestone.
- Required sign-in options: email, Google and Apple. They remain in scope even if provider configuration takes longer than calculation integration.
- Existing calculation and reading programs: user confirms they work.
- Google/Apple developer and email-service accounts: user is not sure. Inspect configuration before asking them to create anything.
- Paid AI integration-test authorization: **US$20 total**, not per run, per model, per provider or per month. This is a combined ceiling for this integration effort. No paid calls were made while preparing this handoff.
- No further product decisions are needed to begin integration. Ask only when an actual external account/setup action or an unavoidable ambiguity is reached.

## Where the work is

- Active project: `D:\Dev\astrology-app`
- Frontend: `D:\Dev\astrology-app\FE`
- Original specifications: `G:\My Drive\Tech\Astrology app\FE`
- Branch: `codex/frontend-specs`
- Latest implementation commit: `acc196f` — frontend preview flows and Android validation.
- Start demo: `D:\Dev\astrology-app\Open Android Preview.cmd`
- Demo login: `demo@example.com`, code `000000`. This does not send an email.
- Detailed frontend inventory and sample paths: `frontend/BUILD_PROGRESS.md`.
- Preserve unrelated changes: the user's change in `frontend/PHASE_1_REPORT.md` and untracked root `Claude outputs/`.

## What we have so far

| Area | What exists | What still needs connecting or verifying |
|---|---|---|
| Profiles and account screens | Onboarding, profile editor, preferences, English/Turkish, themes | Durable accounts/profiles and actual calculations for new birth details |
| Birth chart | Interactive wheel, facts, tables, selection, zoom and reading screens | Return the new person's computed chart and reading through the app service |
| Exports | Chart PNG/JPG, chart PDF, full-reading PDF, share cards | Verify exports using newly generated results |
| Forecasts | Home, daily/monthly/yearly views, lenses and date navigation | Fresh results for arbitrary profiles/dates; reconcile calendar-month UI with rolling-month engine output |
| Compatibility | Pair selection, relationship type, reading, history and export | Run real comparisons for any chosen pair; verify type mapping |
| Calendar and Best Days | Month/day/year/event screens, periods, goals and reminders | Compute/cache results for each actual profile and current date |
| Notifications | Permissions, preferences, quiet hours, limits, scheduling and links | Verify with live calendar results and app restarts |
| Astro map | Native map, lines, goal layers, search, place/area reports and recommendations | Feed actual profile calculations, location search and generated readings into all routes |
| Ask | Conversation interface, streaming, stop/retry, cards, feedback and history | Implement/connect real grounded answers; current samples are replayed, not a live assistant |
| Background report work | Pending states, job polling, completion notices and history | Durable server-side jobs, retries and restart recovery |
| Sign-in | Email demo and provider client code | Real email delivery and identity verification; Google configuration; Apple browser-based flow for Android |

Optional screens such as Solar Return exist, but successful backend coverage is not established for all optional features. A checked frontend task means its interface was implemented, not that its live service is complete.

## Existing calculation and reading programs

`PROJECT_OVERVIEW.md` describes the shared chart, grounding and interpretation layers. Starting points:

- `run.py`: natal chart and written reading.
- `synastry_run.py`: compatibility.
- `run_predictive.py`: daily/monthly/yearly forecasts.
- `run_calendar.py`: personal calendar and Best Days.
- `run_acg.py`: astrocartography, place/area readings and recommendations.
- `llm_client.py`: shared AI-provider client and usage reporting.

Reuse the existing grounding/validation rules. Do not substitute invented text when a calculation or reading is missing. Confirm actual input/output contracts and runtime dependencies before implementing adapters.

## Configuration inspection — no secrets exposed

On 2 October, the checked process/user/machine environment contained Gemini and OpenAI API-key settings. Their presence does not establish that the credentials are valid or funded. Their values were not displayed or copied.

The frontend Google client-ID settings were not found. Common Apple client/team/key-ID and SMTP/Resend/SendGrid settings were also not found. No `.env*` file was found at the project or frontend root. This limited inspection does not establish that the user has no accounts, or that no configuration exists elsewhere.

Current Apple code uses native Apple authentication intended for iOS. Android Apple sign-in still needs a browser-based implementation and backend verification. Development package identifiers are still placeholders.

## Work remaining, in useful order

1. **Inspect and exercise existing calculations without paid generation.** Establish runnable dependencies and actual input/output shapes. Verify at least two distinct birth inputs produce distinct, correct outputs.
2. **Build the local app service.** Implement the existing frontend API contract over the Python engines. Save profiles, results and jobs locally so restarting does not erase them. Keep the service private to this computer for emulator testing.
3. **Complete one real birth-chart flow.** Enter birth details, calculate the chart, generate its reading, reopen it after restart and export it. Use this as the first complete acceptance test.
4. **Connect the other features.** Compatibility, forecasts, calendar/Best Days, map/recommendations and Ask. Resolve real engine/UI mismatches explicitly. Keep unavailable features clearly labelled until they work.
5. **Connect real sign-in.** Persistent sessions, email code delivery and server-side Google/Apple verification. Guide the user through any missing account registrations when specific requirements are known; never request secrets in chat.
6. **Run Android acceptance checks.** Fresh birth inputs, changed profiles, unknown birth time, dates/time zones, failed/slow generation, retry, restart persistence, exports, notifications and all three requested sign-in options.
7. **Refresh the handoff.** Record exactly what passed, remaining limitations, setup instructions and cumulative AI test spend. Then invite the user to test the live local version.

Independent calculation/service work can proceed while provider account setup is pending. Do not mark sign-in complete merely because the demo login works.

## Paid testing rule

Before the first paid request, verify current provider/model rates and establish a cumulative cost ledger. Include retries, translations and all model stages in the combined US$20 budget. Limit output/concurrency and reserve enough budget for requests already in flight. Reuse cached outputs. If costs cannot be bounded reliably, pause paid calls rather than assuming the ceiling will be respected. Do not silently increase the budget or treat this approval as permission for public deployment, subscriptions or unrelated spending.

## Evidence already available

Reported validation from the frontend implementation, not freshly rerun for this report:

- 5,302 fixtures validated against contracts.
- 47 Node tests and 9 native component tests passed; TypeScript and lint passed.
- Android and iOS JavaScript/Hermes bundles built. This is not an iOS native-device pass.
- Android development APK built and installed; the demo was launched again on 2 October.
- Android smoke checks covered login, chart facts, sample streamed answers, compatibility, calendar, map/place reports, exports and notification delivery.
- Export evidence includes a 2048 x 2400 PNG and a 17-page reading PDF without raster images.

Evidence folders: `frontend/artifacts/exports` and `frontend/artifacts/screenshots` (ignored by Git). Automated sample-data tests do not establish live-backend correctness.

## Deferred beyond private emulator testing

Public hosting, store submission, production branding/legal publication, physical-phone/iPhone acceptance and final production map-service configuration. Provider sign-in may still require registered identifiers and an HTTPS callback before public release; determine the smallest necessary setup during implementation.

## What the user needs to do now

Nothing further is needed to clarify the next milestone. The developer can inspect and integrate the existing services. If a Google/Apple/email account action becomes necessary, explain what it is for and give concrete steps. The user should not have to choose infrastructure or supply passwords in chat.
