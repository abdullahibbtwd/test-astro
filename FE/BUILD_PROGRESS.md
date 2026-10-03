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

# Frontend preview — 1 October 2026

Working copy: `D:\Dev\astrology-app\FE`. Open `D:\Dev\astrology-app\Open Android Preview.cmd`.
Sign in with **demo@example.com**, code **000000**. The launcher opens the Android emulator, API and Metro.

## Implemented

- Turkish/English app shell, themes, onboarding, saved birth profiles, account/preferences, secure local storage and report history.
- Home, daily/monthly/yearly forecast views, lenses, profile/date navigation, optional Solar Return screen and capability flags.
- Interactive canonical chart wheel with zoom/pan, body/sign/house/axis/aspect selection, detail sheets, reading links, accessible tables and contents sheet.
- Chart PNG/JPG, vector PDF, full reading PDF, and feed/story share cards with birth details hidden by default.
- Compatibility creation, relationship type selection, report, chart links, sharing/PDF, history and deletion.
- Calendar month/day/item/period/year screens, goal filters, semantic bands, timeline, Best Days and reminders.
- Notification permissions/preferences, quiet hours, rolling caps, deduplication, background/foreground refresh and notification deep links.
- Native map, planet/angle layers, glyph sprites, heat layers, city/area search, line lists, place/area/point report screens, filterable recommendation requests and list/map results.
- Ask threads, six starters, context chips, streaming, Stop/retry recovery, offline/quota states, structured cards, copy/share and feedback.
- Composite job polling, ready notifications, retry handling and completed-report history.

## Useful preview paths

| Flow | Available sample |
|---|---|
| Home / forecasts / calendar | **Person A**. Preview today is 2026-09-29. Daily calendar facts cover the supplied year. |
| Natal reading and exports | **Person B or Person C** → Chart → Read your chart / Export. |
| Compatibility | Person A + Person B → **Love**. Text is from the matching existing synastry run. |
| Map city reports | Person A → search Istanbul, Sofia, İzmir, Berlin, London, Barcelona or Hong Kong. |
| Map area reports | Person A → Turkey, Bulgaria, Germany, United Kingdom or Spain; selected region links. Bands and city rankings are deterministic backend results. |
| Recommendations | Person A → default Overall, or Love, Career, Travel, Permanent Relocation, with the stored world/default filters. |
| Ask | Person A → starters replay clearly labelled saved-data samples/cards. This is not a live AI service. |
| Notifications | Your space → Notifications → enable → Send a test notification. Uses real device time, not the fixed preview date. |

The local basemap uses the project's Natural Earth Turkey-POV geometry. It is a development fallback; release still needs its provider/style configuration and final worldview review.

## Data boundaries (do not confuse these with live calculations)

The contract server is a local preview, built from existing outputs and deterministic scans. New birth inputs reuse sample chart positions. Arbitrary profile/date/lens combinations, unrepresented city/point reports and recommendation filters can return an explicit unavailable state.

The saved monthly prose is a **rolling September 29–October 29** reading, not a calendar-month reading. Monthly screens therefore show exact calendar facts and an absent-reading notice rather than falsely relabelling that prose. The saved yearly reading displays its actual September 29, 2026–September 28, 2027 range. Person A has no matching natal prose fixture. Area summaries have calculated facts but no generated overview prose. Work/family compatibility, Solar Return and element-note success data are not supplied for the preview profiles; optional capabilities stay disabled where appropriate.

Mock account/thread/report state resets with the API process. Sign in again after a server restart. No emails or paid model requests are made.

## Validation and remaining release work

- `npm run check`: 5,302 fixtures validate; 47 Node tests and 9 native component tests pass. Strict TypeScript, ESLint, contract validation, Node and native component tests cover formatting, numeric parity, W1/W3 byte parity, W4 native SVG chord props, exports, notification policy, SSE, idempotency, history and job completion.
- Android and iOS Hermes bundles build; the Android x86_64 development APK builds and is installed. This does **not** establish an iOS native/device pass.
- Android smoke checks include auth, home/chart facts, real streamed preview answer, compatibility creation/read, calendar, native map, place bottom sheet/full screen, PDF/PNG sharing and local notification delivery.
- Generated export checks: 2048×2400 PNG; chart PDF with vector wheel; full 17-page reading PDF with no raster images. Local evidence is in `artifacts/exports` and `artifacts/screenshots` (Git-ignored).
- Native test coverage does not replace a full TalkBack/VoiceOver, physical-device performance, iOS background delivery or store-release audit.

Still required for fully live functionality: production HTTP API/job/SSE adapter over the Python services; live generation and complete forecast data; authentication/email transport and account-export service; Google/Apple app credentials; final legal text and app identifiers; production map styles. No production deployment or store submission has been performed.

The frontend is available for preview testing; the complete live product is **not** represented as finished.
