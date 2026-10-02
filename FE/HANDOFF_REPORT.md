> **2 October integration update:** Real charts, saved profiles, calendar, Best Days and daily/monthly facts now work in the separate local preview. See [LIVE_INTEGRATION.md](LIVE_INTEGRATION.md) for current status. Paid reading verification is pending explicit payload approval; spend remains US$0. The earlier snapshot below describes the sample demo.

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
- Detailed frontend inventory and sample paths: `FE/BUILD_PROGRESS.md`.
- Preserve unrelated changes: the user's change in `FE/PHASE_1_REPORT.md` and untracked root `Claude outputs/`.

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

Evidence folders: `FE/artifacts/exports` and `FE/artifacts/screenshots` (ignored by Git). Automated sample-data tests do not establish live-backend correctness.

## Deferred beyond private emulator testing

Public hosting, store submission, production branding/legal publication, physical-phone/iPhone acceptance and final production map-service configuration. Provider sign-in may still require registered identifiers and an HTTPS callback before public release; determine the smallest necessary setup during implementation.

## What the user needs to do now

Nothing further is needed to clarify the next milestone. The developer can inspect and integrate the existing services. If a Google/Apple/email account action becomes necessary, explain what it is for and give concrete steps. The user should not have to choose infrastructure or supply passwords in chat.
