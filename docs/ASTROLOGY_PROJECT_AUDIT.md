# Astrology App — Full Project Audit

**Date:** 13 October 2026 · **Branch audited:** `main` at `dea9af9` plus the uncommitted working tree · **Machine:** macOS (Apple Silicon), Node 24.20, Python 3.14.7 (`.venv`), Xcode 27, Android SDK (platform 37, emulator running)

**Method:** Read the handoff, specs (`FE_00`–`FE_09`, `FX_*`, `ONB_*`), contracts, and source. Ran every available test suite. Booted the mock API and the real local API (the real one in an isolated `git worktree` with its own empty database, so the owner's `.local-data` was not touched). Drove a synthetic end-to-end flow over HTTP. Exported production JavaScript bundles. Attempted a native Android build. **No application code was changed.** This file is the only addition.

**Evidence labels used below**

- **Verified (this audit):** I ran it on 13 October and saw the result.
- **Verified (prior):** Recorded in a dated report in the repository from the owner's Windows workstation (mainly `docs/frontend/ANDROID_ACCEPTANCE_REPORT.md`, 3 October, and `docs/handoff/ACCEPTANCE.md`, 6 October). I could not reproduce it here.
- **Code only:** The implementation exists, but nobody has demonstrated that the full flow works.

---

## A. Executive summary

### What exists today
- **A substantial, well-structured mobile app.** It uses Expo SDK 57, React Native 0.86 (new architecture), Expo Router, TanStack Query, Zod-validated contracts, and English/Turkish translations (513 keys each, no missing keys). Around 60 routes cover onboarding, Home, natal chart and readings, Ahead (day, month, year, calendar, Best Days), Match, Map, Ask Astrology, Reports, and Settings.
- **A strong deterministic astrology core in Python.** It includes Swiss Ephemeris charts, transits, a personal calendar, Best Days, astrocartography lines, heat maps and recommendations, and synastry. Grounded LLM reading layers (Gemini and OpenAI) and the Personal Astrologist agent sit on top. This is the project's most valuable and most reusable asset.
- **A private preview API** (`frontend/local-api`, Fastify). It exposes the core through the app's contract by launching Python "bridge" processes.
- **A mock API** (`frontend/mock-api`) for UI demos. It serves fixture data and does no calculation.

### What has been verified
| Verified (this audit) | Verified (prior, owner's workstation) |
|---|---|
| TypeScript and ESLint pass. JavaScript bundles compile for Android and iOS. | Android emulator: guest onboarding, then live reading, then Google sign-in (6 October) |
| Real local API: sign-in (demo), place search, profile creation with real chart calculation, chart, Home, day/month/year forecast facts, calendar, periods, Best Days, notification candidates, map lines, love heat map, destination recommendations, export, 401 on missing token, **data persists across restart** | 3 October Android pass: chart, natal reading, forecasts, calendar, Best Days, love/work Match, map, area/city reports, recommendations, saved reports, Turkish, PDF export, logout and Google re-login |
| Mock API serves fixture endpoints | Ask Astrology returns a validated answer (6 October) |
| Test results: Node/API 117/124, native components 55/57, Python 490 passed with 2 failures, all explained in §10 | |

### What is only mocked, local, or unverified
- **Every backend capability runs only on a developer's machine.** The server is hard-coded to `127.0.0.1:4020` (`frontend/local-api/server.ts:22`), uses one SQLite file, and accepts **one pinned account** (`frontend/local-api/app.ts:70-74`).
- **Written readings could not be exercised in this audit.** No provider keys are on this machine. The spending guard also hard-stops all paid generation after **9 October 2026** (`frontend/local-api/budget.py:58-59`). Today is 13 October, so readings are **currently blocked everywhere** until someone reapproves pricing and updates the guard.
- **Solar Return:** fully built in the app, **no backend at all.** The API returns 503 and the feature flag is forced off.
- **Family compatibility:** UI exists, **the backend explicitly rejects it** (503).
- **Payments:** **nothing exists** apart from an unused `entitlements` field in the contract.
- **iOS:** there's no successful native build. Uncommitted workarounds show native modules aren't linking (details below).
- **Apple Sign-In:** library code exists, but **there's no button** in the UI.

### Biggest production blockers
1. **No hosted, multi-user backend.** The API is loopback-only, single-owner, and has no tenant isolation. A global lock processes **one request at a time** (`app.ts:278-289`). There's no deployment artifact (no Dockerfile or infrastructure code), and server dependencies (`fastify`, `tsx`) are listed as dev-only.
2. **Authentication isn't built for the public.** Browser sign-in calls back to `127.0.0.1`, any second user gets a 403, release builds have no working sign-in against the mock, and Apple Sign-In is missing.
3. **The data lifecycle is incomplete.** `DELETE /me` leaves calendar caches (folders named with the birth date), reading dossiers, and the Supabase identity behind. Consent text is still marked DRAFT. Legal links are blank.
4. **No payments or entitlement system.**
5. **No production map tiles.** Map style URLs are blank, so release builds show "map style missing" instead of a map (`frontend/src/features/map/MapCanvasNative.tsx:67-68, 163-169`).
6. **LLM spend control is a local $20 ledger that has expired.** There are no per-user quotas or global cost monitoring beyond Ask's daily cap.

### Overall readiness
The **mobile frontend and the calculation/reading engines are advanced and reusable.** The **service layer around them is a single-user prototype.** Backend assessment: **Significant backend work required** (§C). The engines can be kept, but the API, persistence, auth, jobs, hosting, and privacy layers need to be re-engineered before any public release.

### Repository state warnings (act before anything else)
- **`main` is missing two commits** from `origin/codex/frontend-team-handoff-2026-10-06`: `7f35bca` (fixture packaging/docs) and `ba0f5da` (typecheck fix for `app/_layout.tsx`).
- **Uncommitted iOS workarounds that must not ship as-is:**
  - `frontend/src/lib/storage.ts` replaces encrypted MMKV storage with an in-memory `Map`. On Android this would silently lose the offline cache, drafts, lenses, and reminders on every app restart.
  - `frontend/src/features/map/MapCanvas.tsx` was rewritten to load MapLibre lazily (new `MapCanvasNative.tsx`, `mapColors.ts`), with a hard-coded English error.
  - `frontend/src/lib/oauth.ts` loads Google Sign-In lazily.
  - `frontend/app.json` adds new-architecture flags and static linking.
- **The demo fixture ZIP is staged in the Git index** (`fixtures/frontend-demo-fixtures.zip`, 6.8 MB, 5,307 files of sample birth, chart, and reading data). `docs/handoff/SETUP.md` says to keep it out of Git. One demo profile (1979-03-30 06:30 Sofia) appears throughout the docs. **Confirm that none of the demo profiles are real people** before committing or pushing.

---

## B. Feature inventory (frontend to backend)

Statuses follow the brief: **Working and verified**, **Implemented, unverified**, **Partially implemented**, **Mocked or local-only**, **Missing**, **Blocked**. "Local-only" means it works only against the developer-machine API. **No UI was driven in this audit.** No native build was available, so frontend status comes from code and the prior reports.

| Feature | Frontend status | Backend/API status | Evidence | Gap or blocker | Required work |
|---|---|---|---|---|---|
| Birth-first guest onboarding (core reading before sign-in, 40%→100%) | Implemented, verified (prior, 6 Oct) | Local-only. **Blocked now**: needs `ASTRO_GUEST_ONBOARDING=1` + paid generation, and the budget guard has expired | `app/(auth)/welcome.tsx`, `src/features/onboarding/GuestOnboarding.tsx`, `local-api/guest-onboarding.ts:125-222`, `frontend/GUEST_ONBOARDING_REPORT.md` | Abuse/cost control is an in-memory limit of 5 per IP per hour; generation is blocked by `budget.py:58` | Production anonymous quotas, CAPTCHA/attestation, cost caps |
| Consent | Implemented, unverified | Stored in `me.consents` | `OnboardingScreen.tsx:75-79` writes version `"DRAFT-preview-only"`; `i18n/en.json:36` "DRAFT CONSENT" | Legal text is a draft and fails `release:check` | Legal-approved text, consent versioning, withdrawal flow |
| Email sign-in (OTP / magic link) | Demo OTP: implemented. Real magic link: implemented, **unverified** | Demo: `demo@example.com / 000000` (`app.ts:360-371`). Real: Supabase browser PKCE flow (`browser-auth-routes.ts`, `browser-signin.ts`) | `docs/frontend/ANDROID_ACCEPTANCE_REPORT.md` step 19: **BLOCKED at inbox** | Callback hard-coded to `127.0.0.1:4020` (`browser-signin.ts:7`); demo login only works in `__DEV__` builds (`AuthScreen.tsx:21`) | Public HTTPS callback / app deep links; end-to-end test |
| Google Sign-In | Implemented, verified (prior, Android) | Local-only, single pinned owner | `AuthScreen.tsx:33-36,183`, `oauth.ts`, `AUTH_INTEGRATION.md` | Second user gets 403 (`app.ts:70-74`); Google project in "Testing" mode | Multi-user auth, production OAuth client, publishing verification |
| Apple Sign-In | **Missing** (code path only, no button) | `/auth/apple` route returns 503 unless Supabase is configured; untested | `oauth.ts:52-76`, `app.json` `usesAppleSignIn`; `AuthScreen.tsx:183-184` renders only Google and Email | Likely required by App Store guideline 4.8 alongside Google | Button, Supabase Apple provider, Services ID/keys, private-relay email, revocation |
| Session and token storage | Partial (**regression in working tree**) | Opaque local tokens, 30-day refresh, logout (`app.ts:383-411`) | SecureStore for the token; `storage.ts` diff makes the private cache in-memory | Offline cache, drafts, reminders lost on restart | Fix MMKV/Nitro linking on iOS; revert the in-memory fallback |
| Profiles / multiple charts | Implemented, verified (prior) | **Working and verified (this audit)**: create self + partner, real chart, persists after restart | `app/profile/charts/*`, `app.ts:504-608`; smoke run: POST 201 in 0.25 s, big three returned | Exact birth time is mandatory; 50-profile cap; unknown time unsupported | Product decision on unknown birth time |
| Home dashboard | Implemented, verified (prior) | **Working and verified (this audit)**: `GET /home` 200 (8.0 s cold, includes calendar build) | `HomeScreen.tsx:31`, `local-api/home.ts` | Cold latency; text part needs paid generation | Precompute/caching in production jobs |
| Natal chart and wheel | Implemented, verified (prior) | **Working and verified (this audit)** (`/chart` 200, positions sensible) | `ChartScreen.tsx`, `chart_bridge.py`, `d_layer/compute_chart.py` (Moshier ephemeris, `:55-56`) | No independent accuracy benchmark recorded | Spot-check against a reference ephemeris |
| Natal reading (17 sections) | Implemented, verified (prior) | Implemented. **Blocked now** (returns `status: absent` with paid off; guard expired) | `reading-jobs.ts`, `reading_bridge.py`, `Interpretation_layer/` | About $0.50 per reading (PROJECT_OVERVIEW §5); 20-minute timeout | Production job queue, cost budget, cache reuse |
| Progressive / sectioned reading (ONB_01/02) | Implemented behind flag | Partially implemented (flag `ASTRO_PROGRESSIVE_READING` off) | `progressive-readings.ts`, `ONB_PHASE3_REVIEW.md` | Length/quality target not met; migration incomplete | Editorial decision; finish R5 migration |
| Chart element notes | Hidden (flag `elementNotes` false) | **Missing** (503 verified this audit) | `ChartDetailSheet.tsx:40-51`, `flags.ts:8` | No producer | Build or keep hidden |
| Daily forecast | Implemented, verified (prior) | Facts **working and verified (this audit)**; prose blocked (paid) | `ForecastViews.tsx:54`, `forecast.ts`, `forecast-jobs.ts` | A busy job previously showed a misleading "check your connection" message (3 Oct report, issue 2) | Re-test after the FX fixes |
| Monthly / yearly forecast | Implemented, verified (prior) | Facts **working and verified (this audit)**; prose blocked | `ForecastViews.tsx:262,363` | Same as daily | Same as daily |
| **Solar Return** | Implemented, **hidden** (full screen exists; button shown only if `flags.solarReturn`) | **Missing.** Endpoint registered but no handler: 503 (verified this audit); flag forced false (`app.ts:354`); no Python producer anywhere in the repo | `app/solar-return/[year].tsx`, `ForecastViews.tsx:419-426`, `flags.ts:5` (client default **true**) | If config fails to load, the client default `true` could expose the button; the 404→unavailable kill-switch only reacts to 404, not 503 | Build calculation + grounded reading (new corpus), or remove from release |
| Love / work compatibility | Implemented, verified (prior) | Implemented; job accepted (`status: absent` with paid off, this audit) | `NewMatchScreen.tsx`, `compatibility-jobs.ts`, `compatibility_bridge.py:16` | Paid generation blocked now | Production jobs |
| **Family compatibility** | Implemented, **hidden** (chip filtered by flag, `NewMatchScreen.tsx:132-133`) | **Missing**: `if (input.type === "family") throw issue(503)` (`compatibility-jobs.ts:76`), verified 503 this audit; the bridge maps only love→personal and work→professional | `FE_00_INDEX.md:114,151` planned a `general` fallback that was never built | No family grounding profile in the synastry corpus | Fallback to `general` (small) or a new family profile (larger) |
| Compatibility score (0–100) | Hidden (`compatibilityScore` false) | Not produced | `MatchReportScreen.tsx:131` | Product decision | Decide; build or drop |
| Astro map: lines, parans, heat | Implemented, verified (prior); uncommitted refactor | **Working and verified (this audit)**: lines 1.6 s, love heat 7.3 s | `MapScreen.tsx`, `MapCanvasNative.tsx`, `map.ts`, `map_bridge.py` | **Release builds have no base map** (blank `map_style_url` in `mock-api/fixtures/config.json`) | Choose and license a tile provider; set style URLs |
| City, point, area, line reports | Implemented, verified (prior), one failed point job | Facts implemented; prose via `MapJobs`; blocked now | `ANDROID_ACCEPTANCE_REPORT.md` issue 1 (unresolved) | Point-reading job failure not root-caused | Reproduce and fix |
| "Where should I go?" recommendations | Implemented, verified (prior) | **Working and verified (this audit)** (8.4 s) | `app/map/recommend/*`, `POST /acg/recommendations` | Prose needs paid | — |
| Calendar (month/day/periods/year) | Implemented, verified (prior) | **Working and verified (this audit)** (periods 5.7 s cold, 62 items) | `app/calendar/*`, `calendar_bridge.py` (180 s timeout) | Depends on precomputed `cal_run/_collective/{year}.json` in the repo (`calendar_bridge.py:34-37`) | Generate collective years ahead of time; caching jobs |
| Best Days | Implemented, verified (prior) | **Working and verified (this audit)** | `BestDaysScreen.tsx`, `/best-days` | 8 Moon-timing factors disabled (corpus gap, PROJECT_OVERVIEW §4) | Corpus CAL_06 (optional) |
| Notifications and reminders | Implemented, unverified on device | Candidates endpoint **verified (this audit)** (84 items). **No push server**: scheduling is local via `expo-notifications` and a background task | `notifications.ts:48-51`, `NotificationLifecycle.tsx:62-64` | Sync errors swallowed (`.catch(() => {})`); iOS background tasks are opportunistic; reminder storage now in-memory | Decide local-only vs server push; device QA |
| Ask Astrology (Personal Astrologist) | Implemented, verified (prior): streaming, cards, cancel, history, quota 20/day | Local-only; disabled here (`/ask/threads` POST 503 with `ASTRO_ASK_ENABLED=0`, verified this audit); 86 agent tests pass | `ChatScreen.tsx`, `ask.ts`, `ask_bridge.py`, `astrologist/` | Full benchmark/adversarial/Turkish review not done (R6); 90 s timeout | Evaluation, cost model, production worker |
| Reports: saved list, PDF/PNG export, share | Implemented, verified (prior, Android) | `/reports` **verified (this audit)** | `ExportScreen.tsx`, `exports/native.ts`, `ReportsScreen.tsx` | iOS/physical device untested | Device QA |
| Settings (language, theme, location) | Implemented, verified (prior) | `PATCH /me` **verified (this audit)** | `AccountScreen.tsx` | — | Polish |
| Data export | Implemented | **Working and verified (this audit)** (`POST /me/export` returns a JSON bundle) | `account.ts:4-37` | In non-local mode the app says "sent" but no email delivery exists (`AccountScreen.tsx:219-225`) | Define the export channel (download or email) |
| Account deletion | Implemented (calls `DELETE /me`) | **Partially implemented**: clears the SQLite store and `map-products` only | `account.ts:39-54`; this audit found leftover `.local-data/calendar/<run>_<birthdate>/` and `dossier/` on disk | Supabase identity, calendar caches, dossiers, guest DB, provider logs not deleted | Full deletion pipeline (Apple/Google policy requirement) |
| Subscriptions / paywall / entitlements | **Missing** | **Missing** | `Me.entitlements` in `contracts/` only; no billing SDK in `package.json` | Entire workstream | §F |
| Language support (TR/EN) | Implemented: 513/513 keys, Turkish default | Readings bilingual by design | `src/i18n/*.json`, `i18n/index.ts:11-12` | A few hard-coded English strings (map error, storage failure, About credits) | Translate; native Turkish editorial review |
| Offline, loading, error states | Implemented broadly (skeletons, `ErrorNotice`, persisted query cache, NetInfo) | — | `_layout.tsx:70-72,131-141`, `api/online.ts` | Offline banner only on Chart and Ask; persistence weakened by the in-memory storage change | UX pass (§F) |
| Accessibility | Partial (about 93 `accessibilityLabel`s; reduced motion only in onboarding) | — | `GuestOnboarding.tsx:149-151` | No screen-reader/large-text acceptance | D8 pass |
| Analytics / crash reporting | Sentry only if a DSN is set (none configured); PostHog installed but **never initialised** | No server-side logging (`Fastify({ logger: false })`, `app.ts:57`) | `src/lib/telemetry.ts:60-64` | No production observability | Configure Sentry (app and server) and analytics under consent |
| Developer-only screens | `/gallery` gated by `__DEV__`/`FX_AUDIT`; `/design-system-gallery` route ships in the bundle | — | `Gallery.tsx:41`, `_layout.tsx:87` | Minor exposure | Exclude from release |

---

## C. Backend production assessment

### C1. What the backend is
- **Processes:** one Node process (`tsx local-api/server.ts`). It spawns short-lived Python processes per request or job (`*_bridge.py`), which import the repo-root engines. No separate workers, queue, or scheduler.
- **External services:** Supabase Auth (identity only, verified by calling Supabase's `/user` endpoint on every request, 8 s timeout). Gemini and OpenAI (and Anthropic optionally) via `llm_client.py`. Keys come from environment variables or `~/.{gemini,openai,anthropic}_key`.
- **Mock API:** separate Fastify server on 4010 serving fixtures. Development and demo only.

### C2. Readiness by area

| Area | Status | Evidence | Risk | Remediation |
|---|---|---|---|---|
| Hosting / deployability | Local-only | Bind `127.0.0.1:4020` (`server.ts:22`); `fastify`, `tsx`, `@fastify/cors` in `devDependencies` (`frontend/package.json`); no Dockerfile, Procfile, or infrastructure code; CI only checks contracts/typecheck/lint/native tests/bundle (`.github/workflows/frontend-contract.yml`) | Critical | Container with Node and a pinned Python 3.11 runtime; configurable host/port; staging and production; HTTPS ingress |
| Multi-tenancy and authorization | Missing | Single KV table with no user key (`store.ts:1-12`: "only this user's data"); `bindOwner` pins one identity, a second user gets 403 (`app.ts:70-74`); DB locked to the auth scope hash (`app.ts:60-67`) | Critical | New data model keyed by `user_id` with ownership checks on every route (Postgres recommended; Supabase Postgres is natural) |
| Concurrency | Single-request | A global promise chain (`tail`) serialises **every** request (`app.ts:278-289`). Synchronous calculations block everyone (Home 8 s, heat 7 s, recommendations 8 s cold in this audit; calendar timeout 180 s) | Critical | Stateless request handlers; durable job queue with worker pool; per-user limits |
| Persistence and migrations | Prototype | `node:sqlite` single file, `CREATE IF NOT EXISTS` only, no migrations or indexes beyond the primary key; file mode 0644 with birth data; caches on local disk (`.local-data/calendar`, `map-products`, `dossier`, repo-root `cal_run/`) | High | Managed DB with migrations, encryption at rest, backups and point-in-time recovery; move file caches to object storage or DB keyed by user/chart |
| Jobs | In-process | Job state lives in the KV store; Python subprocess per job with timeouts (chart 60 s, calendar 180 s, readings 20 min, Ask 90 s); `409 busy` when one job of a kind is already running; restart loses in-flight work | High | Durable queue, retries with idempotency, cancellation, stale-job reaper |
| Authentication | Single-owner preview | Supabase remote verification; demo credentials; browser PKCE with loopback callback; Apple untested | Critical | Local JWT verification (JWKS); multi-user; native/deep-link redirects; Apple; account linking; refresh/revoke tests |
| Input validation | Good basis | Zod schema per endpoint (`app.ts:308-313`), date/time/label checks (`app.ts:506-517`), body limit 64 KB | Low | Keep; add fuzz tests |
| Rate limiting / abuse | Minimal | Guest 5 per IP per hour, browser-flow limits, Ask 20 per day; no global rate limiting; no CORS (fine for native, review for web) | High (LLM cost) | Per-user and per-IP limits at gateway and app; anonymous-onboarding protection |
| LLM cost control | **Expired** | `budget.py`: $20 cap per ledger; refuses all paid calls after 9 Oct 2026 (`:58-59`); blocks non-default endpoints | High | Replace with per-user entitlement quotas plus a global daily spend ceiling and alerting |
| Observability | Missing | No server logging, no health endpoint, Python stderr mostly discarded, no metrics or alerts | High | Structured logs, health/readiness checks, Sentry server-side, uptime and cost dashboards |
| Secrets | Developer-machine | Ignored `.local-data/auth-config.json`; key files in the home directory; none found in the repo | Medium | Secrets manager; per-environment keys; rotation |
| Data deletion / export | Partial | §B rows; Supabase identity untouched; caches left behind | High (store policy and law) | Deletion orchestrator across DB, object storage, caches, identity provider, logs; documented retention |
| Engines (calculation, readings, agent) | Reusable | 490 Python tests pass (2 known non-functional failures); deterministic; validated LLM output | Medium | Package as a library/worker image; pin dependencies (`requirements-handoff.txt` is not a full lock; this machine runs 3.14, the handoff ran 3.11.9) |
| CI/CD and rollback | Minimal | One GitHub workflow; no deploy pipeline; private fixtures not in CI by design | Medium | Build, test, and deploy pipeline with staging gate and rollback |
| Documentation for operations | Missing | Only developer setup docs | Medium | Runbooks: deploy, incident, key rotation, restore |

### C3. Privacy and compliance (needs legal review; code inspection can't establish compliance)
- **Data:** birth date, exact time, and place (precise personal data), names of third parties (partners, children, colleagues), free-text Ask conversations, current location.
- **Processors:** Supabase, Google (Gemini), and OpenAI receive or store personal data. Birth data goes into prompts. Data-processing agreements, retention settings, and transfer mechanisms are needed for each.
- **Turkey (KVKK, Law 6698):** privacy notice (*aydınlatma metni*), explicit consent where required, cross-border transfer rules (amended in 2024; standard-contract notification to the Authority), and a VERBİS registration assessment. Legal counsel should also decide whether astrology content could be read as revealing special-category data (for example health), which affects consent wording.
- **GDPR:** likely relevant. Repo artefacts point to Bulgaria/EU (Europe/Sofia timestamps and profiles), and EU users may be targeted. You'd need a lawful basis, data-subject rights (export and deletion already partly exist), records of processing, and a DPIA assessment.
- **Store policies:** Apple 5.1.1(v) and Google Play both require in-app account deletion that actually deletes server-side data. Google Play also requires a web deletion route and a Data Safety form, and Apple requires privacy nutrition labels.
- **Third-party data:** users enter other people's birth data. Terms and the privacy notice must cover this.
- **Licensing (R4):** map tiles and data, fonts, Swiss Ephemeris (AGPL or a commercial licence; `pyswisseph` uses the Moshier mode here, but the licence question remains), and corpus source-text rights for commercial use.

### C4. Conclusion: **Significant backend work required**
The calculation, reading, and agent engines are a sound foundation and can be kept. But the service that exposes them is a single-user, loopback-only harness:
- one global request lock;
- a single-owner KV database;
- remote per-request auth with a pinned owner;
- local file caches;
- no deployment, observability, or tenant isolation;
- an expired spending guard.

Correct local calculations don't make it production-ready. With the engines reused, the work is well-defined (Phase 2 backlog, roughly 45–85 developer-days). It is a rebuild of the service layer, not "minor changes".

---

## D. Android delivery plan

### D1. What happened in this audit
| Question | Result |
|---|---|
| 1. Does the app start? | **Not verified.** No native Android binary exists (`frontend/android/app/build` absent). JavaScript bundles **do** compile for Android and iOS (`expo export`, about 8.5 MB Hermes each, verified). |
| 2. Mock API starts? | **Yes, verified.** Already running on 4010. Profile-scoped fixture endpoints return 200. Some parameter combinations (natal reading, yearly forecast, Solar Return) return 503 "fixture missing". |
| 3. Real local API starts? | **Yes, verified** (isolated worktree, demo auth, paid generation off). |
| 4. Retrieve and persist data? | **Yes at the API level, verified.** Profiles, chart, and forecasts survived a server restart. **Not verified in the app.** |
| 5. APK generated? | **No.** `./gradlew :app:assembleDebug` was attempted. Gradle needs a **Java 17 toolchain** (the React Native Gradle plugin uses `jvmToolchain(17)`), and only JDK 25 (Android Studio's bundled JBR) is installed. The automatic JDK download via foojay stalled earlier (partial `.part` file in `~/.gradle/jdks`), a Homebrew `temurin@17` install had failed, and the Gradle distribution re-download was very slow. I stopped the build rather than leave a multi-hour download running. The NDK is also not installed yet. |
| 6. Would an APK work on a separate device? | **Not as configured.** (a) The default API URL is `http://127.0.0.1:4010/v1` (`src/api/client.ts:11-12`). (b) Release builds disable demo login (`AuthScreen.tsx:21`), and the mock has no browser-auth routes, so **a release APK can't sign in against the mock**. (c) Real auth calls back to `127.0.0.1:4020` and pins one owner. (d) Release builds show no base map without a style URL. (e) Release signing uses the debug keystore (`android/app/build.gradle:110-115`). |

### D2. Exact setup (macOS)
```bash
# Toolchain
brew install --cask zulu@17          # or any JDK 17; Temurin cask had failed here
export JAVA_HOME=$(/usr/libexec/java_home -v 17)
export ANDROID_HOME="$HOME/Library/Android/sdk"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"
# Android Studio > SDK Manager: install the NDK and the compileSdk platform that Gradle requests.
# If a stale partial JDK exists, delete ~/.gradle/jdks/*17*.part and *.lock (after confirming no Gradle runs).

# Python (handoff qualified 3.11.9; this machine has 3.14)
python3.11 -m venv .venv && source .venv/bin/activate && pip install -r requirements-handoff.txt

# Frontend
cd FE && npm ci
unzip ../fixtures/frontend-demo-fixtures.zip -d ..   # only if mock-api/fixtures is missing (present here)
npm start -- --offline --port 8099   # first run only, to generate .expo/types; then Ctrl+C
npm run typecheck && npm run lint && npm test && npm run test:native
```

**Demo (no keys) on the emulator or a USB device:**
```bash
npm run mock                                               # terminal 1
export EXPO_PUBLIC_API_URL=http://127.0.0.1:4010/v1 EXPO_PUBLIC_BACKEND_MODE=demo EXPO_PUBLIC_AUTH_MODE=demo
adb reverse tcp:4010 tcp:4010 && adb reverse tcp:8081 tcp:8081
npx expo run:android                                       # builds and installs the dev client, starts Metro
```

**Real calculations:** `PYTHON=$PWD/../.venv/bin/python ASTRO_ALLOW_PAID=0 ASTRO_ASK_ENABLED=0 ASTRO_GUEST_ONBOARDING=0 ASTRO_PROGRESSIVE_READING=0 ASTRO_PA_ROOT=$PWD/.. npm run local-api`. Use `EXPO_PUBLIC_API_URL=http://127.0.0.1:4020/v1`, `EXPO_PUBLIC_BACKEND_MODE=local`, and `adb reverse tcp:4020 tcp:4020`. Written readings additionally need provider keys, `ASTRO_ALLOW_PAID=1`, an approved budget, **and a code change to the expired guard in `budget.py`**.

**Environment variables (public, baked into the app):** `EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_BACKEND_MODE` (`demo`/`local`), `EXPO_PUBLIC_AUTH_MODE` (`demo`/`supabase`), `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID`, `EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID`, `GOOGLE_IOS_URL_SCHEME` (build-time), `EXPO_PUBLIC_SENTRY_DSN`, `EXPO_PUBLIC_SHARE_URL`, `EXPO_PUBLIC_FX_AUDIT`, `EXPO_PUBLIC_STRICT_CONTRACT`.

**Server-side:** `PYTHON`, `ASTRO_PA_ROOT`, `ASTRO_ALLOW_PAID`, `ASTRO_ASK_ENABLED`, `ASTRO_GUEST_ONBOARDING`, `ASTRO_PROGRESSIVE_READING`, `GEMINI_API_KEY`/`GOOGLE_API_KEY`, `OPENAI_API_KEY`, optional `ANTHROPIC_API_KEY`, `GEMINI_THINKING_LEVEL`, `OPENAI_REASONING_EFFORT`, plus `frontend/.local-data/auth-config.json` for Supabase.

### D3. Shortest path to an Android test build
1. **Local dev build (1–2 days):** JDK 17, NDK, `expo run:android` on the emulator and one USB phone using `adb reverse`. Proves native modules (MapLibre, Skia, MMKV, Google Sign-In) on Android. Revert or resolve the in-memory storage change first.
2. **Internal demo APK for remote reviewers (+2–4 days):** host the mock API over HTTPS (it already supports `MOCK_HOST`/`PORT`). Add an explicit internal-build switch so demo login works outside `__DEV__`. Set a map style URL or enable the preview map. Add an EAS `preview` profile with env values. Build an APK signed with a non-debug key. Shows UI only, with fixture data.
3. **Real-calculation APK for testers:** depends on the **Phase 2 staging API** (hosted, multi-user, HTTPS auth callbacks). Pointing testers at a developer laptop or tunnel won't work for more than one person (pinned owner, global lock).

**Device test steps:** fresh install; onboarding (EN/TR); sign-in; create self and partner charts; each tab and its detail screens; map interaction and heat; export PDF/PNG and share; notifications permission and scheduled reminder; offline relaunch; logout/login; account deletion on a disposable account; small screen and large text.

---

## E. iOS delivery plan

### E1. Current evidence
- Shared code: all screens, API, state, and i18n are cross-platform. The JavaScript bundle for iOS compiles (verified).
- `frontend/ios/` exists (generated, gitignored). CocoaPods installed. Deployment target 16.4, tablet support on, Apple Sign-In entitlement declared.
- Builds attempted from the terminal: `expo run:ios` failed with **"No code signing certificates are available"**. This machine has **0 signing identities** (verified). Simulator iPhone 18 Pro (iOS 27.0) exists.
- The uncommitted workarounds show the iOS binary ran without **MMKV/NitroModules**, **MapLibre**, and **Google Sign-In** native modules linked. Native linking is unresolved.
- EAS: `eas.json` has development, preview, and production profiles, but no project ID, credentials, env, or submit config. `eas` CLI not installed.

### E2. Reusable vs iOS-specific work
| Reusable as-is | Needs iOS changes | Requires real-device validation |
|---|---|---|
| All feature screens, API client, jobs, SSE, i18n, design system, PDF generation logic | Native linking (MMKV/Nitro static linking, MapLibre pod, Google Sign-In URL scheme via `GOOGLE_IOS_URL_SCHEME`); Apple Sign-In UI and backend; final bundle ID (now `com.example.astrology.dev`); safe areas, keyboard, date/time pickers, sheets; permission strings; background-task behaviour | Map/Skia performance, PDF/share/Photos, notifications, sign-in redirects, purchases (sandbox), large text and VoiceOver, iPad layout if kept |

### E3. Required accounts and steps
1. Apple Developer Program (organisation enrolment needs a D-U-N-S number and can take days to weeks). Expo account and EAS project. App Store Connect app record. Final bundle ID.
2. Signing: EAS-managed credentials or Xcode automatic signing; push key if server push is chosen; Sign in with Apple key and Services ID (for Supabase).
3. Simulator build, then a physical-device development build, then a TestFlight internal build, then external TestFlight (Beta App Review).
4. Store submission: privacy labels, review demo account, support URL, privacy policy URL, age rating, IAP products attached.

---

## F. Payments and UX scope

### F1. Existing implementation
None. No StoreKit/Play Billing/RevenueCat dependency, paywall, product catalogue, receipt verification, server notifications, or entitlement enforcement. Ask has a fixed daily quota of 20. The 40%→100% indicator means **sign-in feature access**, not payment (`FRONTEND_TEAM_HANDOFF.md:50`).

### F2. Decisions needed before building
Free vs paid matrix (guest core, natal full reading, forecasts, Match, Map reports, Ask, exports). Model (subscription, credits, one-off reports, or a hybrid). Prices per market and currency. Trials and intro offers. Refund and failed-generation policy. AI usage allowances per tier. Launch markets. Whether to use a billing aggregator (for example RevenueCat) or native APIs directly.

### F3. Store policy
Digital content and features consumed in the app generally **must** use Apple In-App Purchase (guideline 3.1.1) and Google Play Billing. There are region- and programme-specific exceptions (for example US storefront link-outs and EU alternative terms), and these change frequently. **A web checkout alone is not a safe assumption.** Validate against the chosen markets at decision time.

### F4. Payment estimates (developer-days, after decisions)
| Work | With an aggregator (e.g. RevenueCat) | Native APIs directly | Confidence |
|---|---|---|---|
| Backend billing: entitlement model, webhooks/notifications, idempotent updates, account binding | 4–7 | 8–14 | Medium |
| Android billing: products, purchase flow, pending/cancel/error, restore, manage link | 3–5 | 5–8 | Medium |
| iOS billing (shares RN code) | 2–4 | 4–7 | Medium |
| Entitlement enforcement across features, quotas, paywall UI (EN/TR) | 4–8 | 4–8 | Medium |
| Sandbox testing on both stores (renewal, refund, expiry, restore, reinstall, account switch) | 4–7 | 5–9 | Medium |
| Store-policy validation and product setup | 1–3 | 1–3 | Medium |
| **Total** | **18–34** | **27–49** | |

### F5. UX/UI audit (from code and specs; no screen-by-screen visual review was possible without a build)
| Priority | Improvement | User benefit | Design | Implementation | Dependencies |
|---|---|---|---|---|---|
| P0 | Replace generic error copy with specific busy/queued states (3 Oct issue 2); job-pending clarity | Fewer "broken app" impressions | 1 | 1–2 | — |
| P0 | Fix the persistence regression (in-memory storage) | Cache, drafts, reminders survive restarts | 0 | 0.5–1 | iOS linking |
| P1 | Onboarding small-screen fit; 40% copy clarity; consent legal text | Conversion | 2–3 | 2–3 | Legal text |
| P1 | Profiles: "You" vs others; switching keeps context | Less confusion | 1–2 | 2–3 | — |
| P1 | Home, Ahead, Match hierarchy within the existing design direction | Clarity | 3–5 | 4–6 | D1 inventory |
| P1 | Map: legend/search overlap, selected-state discoverability, base map | Usability | 2–3 | 3–5 | Tile provider |
| P1 | Offline banner on all data screens; consistent empty states | Trust | 1 | 2–3 | — |
| P2 | Ask: composer/keyboard, fallback/retry states | Engagement | 1–2 | 2–3 | — |
| P2 | Accessibility: labels, focus order, large text, reduced motion app-wide, contrast | Inclusion; store review | 1–2 | 3–5 | — |
| P2 | Translate remaining hard-coded English; native Turkish editorial review of UI and readings | Market fit | — | 1 + editor | Editor |
| P3 | Brand assets: icon, splash, screenshots, final name | Release | 3–5 | 1 | Final brand |
| **Total** | | | **~15–25 designer-days** | **~21–33 developer-days** | |

A full redesign is **not** recommended. `docs/handoff/DESIGN_DIRECTION.md` defines an approved direction, and targeted refinement meets the requirement.

---

## G. Prioritised implementation backlog

**Phase order change:** Phase 1 (Android test build) is split into a local/demo build (early) and a real-data tester build that **depends on Phase 2 staging**. Payments (Phase 4) depend on multi-user auth from Phase 2.

Estimates are in developer-days (dd). Confidence: H (high), M (medium), L (low).

### Phase 0: Access, repo, and environment
| ID | Task | Pri | Type | Depends on | Acceptance criteria | dd | Conf |
|---|---|---|---|---|---|---|---|
| 0.1 | Obtain role-based access: GitHub, Supabase, Google Cloud OAuth, Expo/EAS, Apple Developer, Play Console, LLM provider keys with a written budget | P0 | Product | Owner | Team can build, sign, and call providers within an approved cap | 0.5 + waiting | H |
| 0.2 | Reconcile repo: bring `7f35bca` and `ba0f5da` onto `main`; decide whether the fixture ZIP belongs in Git (confirm no real birth data); triage uncommitted iOS workarounds into a branch | P0 | Mobile | — | Clean `main`; workarounds reviewed, not silently shipped | 0.5–1 | H |
| 0.3 | Toolchain: JDK 17, NDK, Python 3.11 venv, documented macOS setup | P0 | Infra | — | Fresh macOS checkout runs all suites and `expo run:android` | 1 | H |
| 0.4 | Test hygiene: remove dependence on unshipped `acg_run/` and `prediction_run/` folders (7 Node tests); fix the 2 failing `fx-reliability` native tests; tolerance for the ACG float determinism test; circumpolar fixture | P1 | Frontend/Backend | 0.3 | All suites green on a clean clone and in CI | 1–2 | M |
| 0.5 | Reapprove LLM pricing and replace the 9 Oct hard stop with a configurable dated cap | P0 | Backend | 0.1 | Readings can run within an explicit approved budget | 0.5 | H |

### Phase 1: Android builds you can test
| ID | Task | Pri | Type | Depends on | Acceptance | dd | Conf |
|---|---|---|---|---|---|---|---|
| 1.1 | Local dev build on emulator and a USB phone (mock and real local API) | P0 | Mobile | 0.3 | All tabs open; chart created; data persists after relaunch | 1–2 | M |
| 1.2 | Resolve storage and map changes so Android keeps encrypted MMKV and MapLibre | P0 | Mobile | 1.1 | Cache survives restart; map renders | 0.5–1 | M |
| 1.3 | Internal demo APK: hosted mock over HTTPS, internal demo-login switch, map style or preview, EAS preview profile, non-debug signing key | P1 | Mobile/Infra | 1.2 | APK installed on a remote phone signs in and browses demo data | 2–4 | M |
| 1.4 | Device smoke test script (§D3) run on 2 Android devices | P1 | QA | 1.3 | Written results with screenshots | 1 | H |

### Phase 2: Production backend and infrastructure
| ID | Task | Pri | Type | Depends on | Acceptance | dd | Conf |
|---|---|---|---|---|---|---|---|
| 2.1 | Architecture decision record: hosting provider, DB (Postgres), queue, object storage, regions (KVKK/GDPR) | P0 | Backend/Product | 0.1 | Approved ADR and cost estimate | 1–2 | M |
| 2.2 | Multi-tenant data model and migration of every store key prefix; ownership checks on every route; tests proving user A can't read user B | P0 | Backend | 2.1 | Automated cross-tenant tests pass | 10–18 | M |
| 2.3 | Auth: local JWT/JWKS verification, remove the pinned owner, mobile deep-link redirects for Google/email, Apple Sign-In, refresh/revoke, account linking | P0 | Backend/Mobile | 2.2 | Two users sign in concurrently on devices; Apple works on iOS | 5–9 | M |
| 2.4 | Remove the global lock; durable job queue and Python worker pool; idempotency, retries, cancellation, timeouts; per-user concurrency | P0 | Backend | 2.2 | 50 concurrent synthetic users without cross-blocking; restart loses no jobs | 8–15 | M |
| 2.5 | Package engines: container image (Node + Python 3.11, locked deps, corpus, collective calendar data); move file caches to object storage/DB | P0 | Infra/Backend | 2.1 | Reproducible image; no writes to the local repo tree | 5–10 | M |
| 2.6 | Environments: staging and production, HTTPS, secrets manager, CI/CD with rollback, backups and restore drill, health checks | P0 | Infra | 2.5 | Deploy and rollback demonstrated; restore tested | 6–12 | M |
| 2.7 | Observability: structured logs, server Sentry, metrics, uptime, LLM cost dashboard and alerts | P1 | Infra | 2.6 | Alerts fire in staging tests | 2–4 | H |
| 2.8 | Abuse and cost: gateway rate limits, anonymous onboarding protection, per-user AI quotas, global spend ceiling | P0 | Backend | 2.4 | Load and abuse tests stay under caps | 4–8 | M |
| 2.9 | Privacy lifecycle: full deletion (DB, storage, caches, Supabase identity), export delivery, retention jobs, consent versioning | P0 | Backend | 2.2 | Deletion leaves no user data (verified by script); in-app and web deletion | 4–7 | M |
| 2.10 | Load/perf test and per-user cost model | P1 | Backend | 2.4 | Documented p95 latencies and cost per active user | 2–4 | M |
| 2.11 | (Optional) Server push notifications | P2 | Backend/Mobile | 2.3 | Push delivered on both platforms | 4–8 | L |
| | **Phase 2 total (excluding 2.11)** | | | | | **47–89** | |

### Phase 3: Finish existing and missing functionality
| ID | Task | Pri | Type | Depends on | Acceptance | dd | Conf |
|---|---|---|---|---|---|---|---|
| 3.1 | Decide release scope for Solar Return, family compatibility, element notes, and score; harden flags (client defaults `false`, kill-switch also on 503) | P0 | Product/Frontend | — | No unsupported feature reachable | 0.5–1 | H |
| 3.2 | Solar Return: calculation, API, grounded reading (may need a corpus delta) | P2 | Backend | 3.1 | Matches contract `FE_02 §7.5`; editorial sign-off | 8–15 | L |
| 3.3 | Family compatibility: `general` fallback (small) or new family profile (larger) | P2 | Backend | 3.1 | Family report generated and reviewed | 2–3 / 6–12 | L |
| 3.4 | Fix the known failures: map-point reading job; verify email-link sign-in end to end | P1 | Backend | 2.3 | Reproduced, fixed, regression test | 2–4 | M |
| 3.5 | Ask quality: golden and adversarial benchmark, fallback analysis, Turkish editorial review, latency and cost | P1 | Backend/Product | 0.5 | Benchmark report meets agreed thresholds | 5–10 | L |
| 3.6 | Reading quality and latency acceptance; progressive-reading decision; ONB_02 migration (R5) | P2 | Backend | 2.4 | Agreed acceptance met; no duplicate generation | 6–14 | L |
| 3.7 | Analytics (consented) and crash reporting configured | P1 | Mobile | 2.6 | Events and crashes visible in staging | 1–2 | H |
| | **Phase 3 core (3.1, 3.4, 3.5, 3.7)** | | | | | **9–17** | |
| | **Optional scope (3.2, 3.3, 3.6)** | | | | | **16–41** | |

### Phase 4: UX improvements and subscriptions
| ID | Task | Pri | Type | Depends on | dd | Conf |
|---|---|---|---|---|---|---|
| 4.1 | UX design inventory and refinements (§F5) | P1 | Product design | 0.1 | 15–25 designer-days | M |
| 4.2 | UX implementation (§F5) | P1 | Frontend | 4.1 | 21–33 | M |
| 4.3 | Payments end to end (§F4, aggregator route) | P0 for paid launch | Backend/Mobile | Owner decisions, 2.3 | 18–34 | M |

### Phase 5: iOS, QA, and release
| ID | Task | Pri | Type | Depends on | Acceptance | dd | Conf |
|---|---|---|---|---|---|---|---|
| 5.1 | iOS native linking (MMKV/Nitro, MapLibre, Google Sign-In), simulator and device builds | P0 | Mobile | 0.1 | Debug and release builds run on device | 2–5 | M |
| 5.2 | iOS platform adaptation (safe areas, keyboard, pickers, sheets, permissions) | P1 | Mobile | 5.1 | Design review passes on iPhone (iPad if kept) | 3–6 | M |
| 5.3 | Android release prep: Play App Signing, target API check, Data Safety, store listing, closed testing track | P0 | Mobile/Release | 2.6 | Closed test live | 2–4 + waiting | M |
| 5.4 | TestFlight pipeline, privacy labels, review account, metadata | P0 | Mobile/Release | 5.1 | External TestFlight approved | 2–3 + waiting | M |
| 5.5 | Full regression QA on staging, both platforms, physical devices | P0 | QA | All above | Written acceptance; no P0/P1 defects | 8–15 | M |
| 5.6 | Legal and brand: privacy policy, terms, consent, KVKK/GDPR review, licences (map, ephemeris, fonts, corpus) | P0 | Product/Legal | Owner | Signed-off documents; `release:check` passes for real reasons | 1–2 dev + legal | L |
| | **Phase 5 total** | | | | | **18–35** | |

---

## H. Timeline and resource estimate

### Effort totals (active engineering, developer-days)
| Scenario | Includes | Engineering dd | Designer days |
|---|---|---|---|
| **Optimistic** | Phases 0–5 core, aggregator billing, Solar Return/Family deferred | ~120 | ~15 |
| **Expected** | As above, mid-range estimates plus ~15% integration overhead | ~175 | ~20 |
| **Conservative** | Upper ranges, native billing, plus Solar Return, Family, ONB_02, push | ~280 | ~25 |

### Calendar duration
Assumes a team of 3 engineers (1 backend/platform, 1 mobile, 1 full-stack), each at about 4 productive days a week, plus a part-time designer and a QA person in the last third.
- **Optimistic:** about 12–14 weeks.
- **Expected:** about 16–20 weeks.
- **Conservative:** about 26–32 weeks.
- A **single developer** should expect roughly 8–12 months at the expected scope.

### Parallel tracks
- **Backend (Phase 2)** is the critical path.
- **Mobile** can work on Phase 1, iOS linking (5.1–5.2), UX implementation (4.2), and the client side of billing at the same time.
- **Design (4.1)** can start immediately.
- **Legal and brand (5.6)** and **billing decisions** can start immediately and run in the background.

### Waiting time (not engineering effort)
- Apple Developer organisation enrolment: days to weeks.
- App Review and TestFlight external review: about 1–3 days per round, possibly several rounds.
- Google Play: new personal developer accounts may need a closed test (for example 12 testers for 14 days) before production; confirm for your account type.
- Google OAuth app verification: days to weeks.
- Legal review: varies.
- Payment-provider and tax/banking setup in both stores: days.

### What could change the estimates
- The payment model you choose.
- Whether Solar Return and Family are required at launch.
- Hosting choice and data-residency constraints.
- Editorial and quality bars for AI readings.
- Whether server push is required.
- Unknown native iOS issues.
- LLM latency and cost at scale.

### Excluded
- Marketing and ASO.
- Customer support tooling.
- Web app.
- Unknown-birth-time support.
- New corpus sources (CAL_06, rising signs, and so on).
- OpenAI/ChatGPT account login (explicitly out of scope).
- Legal fees.
- Ongoing operations after launch.

---

## I. Decisions required from the owner
1. **Free vs paid:** which features, and how much AI generation, each tier gets.
2. **Billing model:** subscription, credits, or one-off; prices, currencies, trials, refunds, and handling of failed generations.
3. **Launch markets and languages:** Turkey only, or also the EU/US; Turkish and English only?
4. **Launch scope:** Solar Return, family compatibility, compatibility score, element notes, unknown birth time, server push.
5. **Brand:** final app name, publisher, bundle/package IDs, icon, splash.
6. **Legal:** privacy policy, terms, consent wording, KVKK/GDPR controller details, support contact, retention periods.
7. **Infrastructure:** hosting provider, region, monthly budget, LLM spend ceiling, map tile provider and licence.
8. **Accounts:** Apple Developer (organisation?), Google Play Console, Expo, and who owns them.
9. **Quality bars:** reading editorial sign-off process, Ask benchmark thresholds.
10. **Fixtures in Git:** confirm whether demo profiles contain real people's birth data, and whether the ZIP may be committed.
11. **Target release date and acceptance criteria** for "launch-ready".

---

## J. Recommended immediate next steps (in dependency order)
1. **Clean up the repository state:** bring the two missing handoff commits onto `main`, move the uncommitted iOS workarounds to a branch, and resolve the fixture ZIP question (task 0.2).
2. **Install JDK 17 and get a local Android dev build** on the emulator and one phone against the mock and real local API (0.3 → 1.1 → 1.2). That's the first app-level proof on this machine.
3. **Owner decisions on access, budget, launch scope, and billing model** (0.1, 0.5, 3.1, §I). They unblock readings testing, payments design, and the Phase 2 architecture.
4. **Write and approve the backend architecture decision record** (2.1), then start multi-tenant data and auth (2.2–2.3). This is the critical path.
5. **Start design refinement (4.1) and iOS native linking (5.1) in parallel**, using the existing design direction.

---

## 10. Test and verification log (this audit, 13 October 2026)

| Suite / check | Command | Result | Notes |
|---|---|---|---|
| TypeScript | `npm run typecheck` | **Pass** | With uncommitted changes; `.expo/types` present |
| ESLint | `npm run lint` | **Pass** | |
| Node/API tests | `npm test` (paid off) | **117 pass, 7 fail**, 0 skipped | All 7 fail with ENOENT on gitignored historical run folders (`acg_run/…`, `prediction_run/…`): `tests/map-jobs.test.ts:151` (1) and `tests/wheel.test.ts:18` (6). Handoff recorded 124/124 on the owner's workstation, which has those folders. Environment dependency, not a code defect. |
| Native component tests | `npm run test:native` | **55 pass, 2 fail** (17/18 suites) | `tests/native/fx-reliability.test.tsx:133` "blocker completion resumes B…" times out. **Also fails on a clean `HEAD` checkout**, so not caused by the uncommitted changes. Root cause not investigated (possibly Node 24.20 vs 24.14 timing). CI runs this suite. |
| Natal/synastry/predictive/LLM client | `pytest Interpretation_layer/test_l4.py synastry_reading/test_s3.py prediction_reading/test_forecast_reading.py principles_grounding/test_ground_house_policy.py test_llm_client.py` | **114 pass, 1 skipped** | |
| Calendar/predictive | `pytest Calendar calendar_reading prediction_reading Forecast_compute/test_forecast.py principles_grounding/test_forecast_grounding.py` | **85 pass** | |
| Personal Astrologist | `pytest astrologist` | **86 pass** | |
| Dossier | `pytest test_profile_dossier.py test_dossier_products.py` | **14 pass** | |
| Chart engine | `pytest d_layer` | **1 pass, 1 fail** | Known circumpolar fixture (Placidus undefined in the Arctic), documented in PROJECT_OVERVIEW §6 |
| Astrocartography | `pytest Astrocartography acg_reading` | **187 pass, 1 fail, 2 skipped** | `test_acg_affinity.py` determinism: last-digit float difference on macOS/Python 3.14 |
| Budget guard | `python tests/budget_test.py` | **3 pass** | |
| Release check | `tsx scripts/release-check.ts` | **Fails (by design)** | "Legal consent is still a draft", "Application identifier is a placeholder" |
| JS bundles | `expo export --platform android --platform ios` | **Pass** | Hermes bundles about 8.3–8.5 MB |
| Mock API | HTTP smoke on the running instance (4010) | **Pass for fixture paths** | Some parameter combinations return 503 "fixture missing" |
| Real local API | HTTP smoke in an isolated worktree (4020), synthetic births | **Pass for all calculation endpoints**; readings `absent` (paid off); Solar Return, element notes, family, Ask (disabled) return 503; restart persistence passed | |
| Android native build | `./gradlew :app:assembleDebug` | **Blocked** | JDK 17 toolchain download stalled; build stopped |
| iOS native build | Prior terminal attempts | **Blocked** | No code-signing identities; native modules unlinked (per workarounds) |
| Authentication/authorization tests | Within Node suite (`auth-integration`, `browser-auth-routes`) | Pass | Single-owner model only; **no multi-user tests exist** |
| Subscription/entitlement tests | — | **None exist** | |
| End-to-end UI tests (Detox/Maestro) | — | **None exist** | Prior Android checks were manual |
| Database tests | Store covered indirectly in API tests | Partial | No migration tests (no migrations) |

**Not verified in this audit:** any app UI on a device or emulator; written readings or Ask (no keys, expired guard); Supabase/Google/email sign-in; notifications; PDF export; iOS.
