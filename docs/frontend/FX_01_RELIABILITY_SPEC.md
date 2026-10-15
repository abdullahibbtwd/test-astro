# FX 01: Reliability (Phase 1)

*Goal: the app never reports a failure that did not happen, always says what actually went wrong, survives
contract drift and restarts, and keeps readings the user already has. Ground rules: FX_00 §2.*

| Item | Title | Size |
|---|---|---|
| FX1.1 | Job state comes from the server, not from elapsed time | M |
| FX1.2 | "Another reading is being prepared" becomes a waiting state | M |
| FX1.3 | Error copy per error kind | S–M |
| FX1.4 | Contract validation: strict in development, tolerant in release | M |
| FX1.5 | Offline persistence keeps readings | S–M |
| FX1.6 | Error reporting sink | S |
| FX1.7 | Live Home in local mode | M |

---

## FX1.1 Job state comes from the server, not from elapsed time

**Problem**
- `src/api/jobs.ts` (`useGenerated`) stores `{ kind: "pending", job, started: Date.now() }` in a query that is
  persisted and has `staleTime: Infinity`. `expired = elapsed >= 600000` turns the state into `"failed"` and
  disables polling. After an app restart more than 10 minutes later, a reading that is still running, or already
  finished on the server, shows as failed and is never re-checked.
- The same 10-minute rule is duplicated as literals in `src/api/job-policy.ts` (`jobState`),
  `src/api/resource.ts` (job polling `enabled` and `refetchInterval`), `src/features/shared/Blocks.tsx`
  (`Generated`: `expired`, `slow`), and `src/lib/JobLifecycle.tsx` (scan filter and `refetchInterval`).
  Jobs older than 10 minutes are skipped by the watcher and never invalidated, so a screen can also stay
  "pending" forever.
- `USER_TEST_GUIDE.md` tells testers a full reading can take several minutes and to report only after 20 minutes,
  which contradicts the 10-minute failure.

**Change**
1. New `src/api/job-timing.ts` with the only timing constants: `JOB_SLOW_MS = 180_000`,
   `JOB_VERY_SLOW_MS = 1_200_000`, and helpers `jobAgeMs(job, now) = now - Date.parse(job.created_at)` (server
   time) and `jobPhase(job, now): "normal" | "slow" | "very_slow"`. Remove every `600000` / `180000` literal.
2. **Failure only comes from the server**: `job.status === "failed"`, a `GeneratedPart` with `status: "failed"`,
   or an HTTP error on the parent request. Elapsed time never yields `failed`. Delete the `expired` logic in all
   five places.
3. **Polling never stops because of age.** `pollingDelay(attempt, ageMs)`: 1 s, 2 s, 3 s, then 4 s while the job
   is younger than 2 min, 10 s until 20 min, 30 s after that. Polling still pauses in the background and stops on
   `succeeded` / `failed`.
4. **Re-check on resume.** When a pending parent is rendered (mount, app foreground, cache hydration), request
   `GET /jobs/{job_id}` immediately. If it returns 404 (the local API restarted and the job is gone), refetch the
   parent resource once without `retry=true`; the server then answers ready, a new job, or failed.
5. Drop `started` from the cached shape of `useGenerated` (use `job.created_at`). Change the persister buster
   (FX1.5) so old shapes are discarded.
6. UI by phase (wired in FX2.7): `slow` → "This is taking longer than usual. You can leave this screen; we'll let
   you know when it's ready." `very_slow` → "This is taking much longer than expected. If it doesn't finish, please
   report it." No Retry while the server says the job is running (the local API returns the same running job for
   `?retry=true`); Retry appears only for `failed`.

**Acceptance**
- Unit (`tests/`): a hydrated pending job created 30 min ago whose `/jobs/{id}` returns `succeeded` → the hook
  refetches the parent and ends `ready`; it never reports `failed`.
- Unit: `/jobs/{id}` returns 404 → the parent is refetched exactly once.
- Unit: `pollingDelay` schedule for ages 0, 90 s, 5 min, 25 min.
- `grep -rn "600000\|180000" src app` returns nothing.
- Manual (mock API, fake clock or a job fixture with an old `created_at`): kill and reopen the app on a pending
  reading → progress or the result is shown, never the failed state.

---

## FX1.2 "Another reading is being prepared" becomes a waiting state

**Problem**
The local API allows one paid generation at a time (a budget guard that must stay). When a second one is
requested it answers in four different ways, none of which the app understands:
- `local-api/forecast-jobs.ts` (`get`, the `this.running.size` branch): `GeneratedPart` `failed` with
  `code: "generation_failed"`, `title: "Another forecast is being prepared"`.
- `local-api/map-jobs.ts` (the `this.running.size` branch): the same shape, "Another map reading is being prepared".
- `local-api/reading-jobs.ts`: throws HTTP 503 "Another reading is running" (generic `upstream_unavailable`).
- `local-api/compatibility-jobs.ts`: `if (!this.enabled || this.running.size) throw issue(503)`, which mixes
  "busy" and "generation disabled".
The app shows "We couldn't complete that. Check your connection and try again." (`ANDROID_ACCEPTANCE_REPORT.md`,
issue 2; `USER_TEST_GUIDE.md` workaround).

**Change**
1. **Contract** (FX_00 §2.8): add `'busy'` to `Problem.code` and an optional `blocking_job_id?: string` to
   `Problem`. HTTP status 409.
2. **Local API**: every one-at-a-time guard returns `busy` with the running job's id:
   - in `GeneratedPart` endpoints (forecasts, map): `{ status: "failed", error: { type: "about:blank", title:
     "Another reading is being prepared", status: 409, code: "busy", blocking_job_id } }`;
   - in top-level endpoints (natal reading, compatibility create/regenerate): HTTP 409 `application/problem+json`
     with the same body.
   Keep the guard: do not queue new paid jobs. Separate "generation disabled" from "busy" (see FX1.3, reason
   `generation_paused`).
3. **App**: a `busy` part or error renders a waiting notice (not an error): "Another reading is being prepared.
   This one will start when it's done." The app watches `blocking_job_id` with the normal polling policy
   (FX1.1). When that job ends (`succeeded` or `failed`) **and this screen is still focused**, the app re-requests
   the resource once with a normal GET (which starts it). If the user has left the screen, nothing starts.
4. Rapid switching (date, lens, focus goal) must never start more than the resource currently on screen.

**Acceptance**
- Local API tests with fake generators (no provider calls): A running, request B → B is `busy` with A's id, for
  forecasts, map, natal reading, and compatibility.
- App test (mock API scenario `busy`): B shows the waiting notice and no "connection" text; completing A starts B
  once while focused; leaving B before A completes → no request for B.
- The acceptance report's tomorrow / focus-switch scenario no longer shows an error.

---

## FX1.3 Error copy per error kind

**Problem**
`ErrorNotice` (`src/design/components/index.tsx`) always renders `t("error")` ("We couldn't complete that. Check
your connection and try again."); `JobProgress` uses the same key for failed jobs. `ApiError` already carries
`status`, `code` and `retryAfter` (`src/api/client.ts`), but nothing reads them. Network failures from `fetch`
are not distinguished from server errors.

**Change**
1. In `request()` wrap the transport call: a thrown `TypeError` / network failure becomes `NetworkError`.
2. New `src/api/errors.ts`: `describeError(error | Problem): { kind, titleKey, bodyKey?, action, retryAfterSec? }`
   with this mapping (EN copy; add TR):

| Input | kind | Copy | Action |
|---|---|---|---|
| `NetworkError`, or `onlineManager.isOnline()` false | `offline` | "You're offline. Saved readings are still available." | Retry when back online (auto-retry on reconnect) |
| code `busy` | `busy` | FX1.2 | wait (no button) |
| code `rate_limited` (429) | `rate_limited` | "Too many requests. Try again in a moment." | Retry, disabled for `Retry-After` seconds with a countdown |
| code `generation_failed` | `generation_failed` | "This reading couldn't be prepared. Try again." | Retry (`?retry=true`) |
| `absent` reason `generation_paused` | `paused` | "New readings are paused in this preview. Saved readings still open." | none |
| `absent` reason `not_generated` | `not_generated` | "This reading hasn't been prepared yet." | a primary button that requests it (only where FX1.7 / the screen spec allows) |
| code `upstream_unavailable`, `internal`, other 5xx | `server` | "The service isn't responding right now. Try again in a few minutes." | Retry |
| code `not_found` | `not_found` | "This item is no longer available." | Back |
| code `out_of_range` | `out_of_range` | "This date is outside the available range." | none |
| code `validation_error` | `invalid` | "That request isn't supported." | none (and report it, FX1.6) |
| code `conflict` | `conflict` | "This changed somewhere else. Refresh to continue." | Refresh |
| code `unauthorized` | — | no notice (refresh / sign-out flow) | — |
| `ContractError` (FX1.4) | `server` | as `server` | Retry (and report it) |

3. `ErrorNotice`, `JobProgress` (failed) and `Generated` (failed part) render from `describeError`.
4. Local API: when paid generation is disabled, return `absent` with reason `generation_paused` everywhere
   (natal reading currently throws 503 "Paid generation disabled" in `reading-jobs.ts`; compatibility throws 503).
   Forecasts already return `absent: not_generated` when disabled; change that reason to `generation_paused` and
   keep `not_generated` for FX1.7.

**Acceptance**
- Unit: a table test for `describeError` covering every row.
- Component test: `ErrorNotice` renders the right copy and action for `offline`, `busy`, `rate_limited` (countdown
  disables the button), `server`.
- Manual: airplane mode on a screen with no cache shows the offline copy; with the local API generation disabled,
  opening an uncached natal reading shows the paused copy, not an error.

---

## FX1.4 Contract validation: strict in development, tolerant in release

**Problem**
`validate()` in `src/api/zod/index.ts` calls `schema.parse(value)` in every build. FE_01 §1 asks for validation
in dev and staging builds with violations logged. In a release build any new enum value or missing field from the
backend throws and the screen shows an error. Large geometry is also fully parsed on the JS thread (country
GeoJSON is about 2.2 MB of coordinates; `AcgLines`, `AcgHeat`).

**Change**
1. Keep the generated file untouched; change the generator template (`scripts/build-zod.ts`) so the emitted
   `validate` behaves as follows:
   - `__DEV__` or `EXPO_PUBLIC_STRICT_CONTRACT === "1"` → `parse` (throws), as today.
   - Otherwise `safeParse`. On failure: report `contract_violation` (schema name and issue `path` + `code` only,
     never values) via FX1.6, then return the raw value as `T` when its top-level type matches the schema
     (object or array). If it doesn't (e.g. HTML error page, `null` where an object is required), throw
     `ContractError`.
   - For `FeatureCollection*`, `AcgLines` and `AcgHeat`: validate only the envelope in all builds
     (`FeatureCollection`: `type` and a `features` array; `AcgLines`: `chart_key` plus `lines.features` and
     `parans.features` arrays; `AcgHeat`: `chart_key`, `goal`, `grid_step_deg` and a `points` array). Full validation of these stays in the contract tests against
     fixtures.
2. **Unknown enum values never crash rendering.** Every map keyed by an API enum needs a fallback: band colours
   (`src/design/bands.ts`), planet colours and glyphs, catalogue lookups (`catalogue.goals[g]`,
   `catalogue.bodies[b]`, …). Fallback: neutral colour, the API's own `*_label` field if present, otherwise skip
   the item. Add a test that renders the main blocks with an unknown band, goal and body.

**Acceptance**
- Unit: release-mode `validate` with an unknown band value returns the data and calls the reporter once;
  dev-mode still throws.
- Render test: Today, place report and calendar day with unknown enum values render without throwing.
- Timing log (dev): validating `AcgLines` and countries GeoJSON takes < 20 ms on the emulator.

---

## FX1.5 Offline persistence keeps readings

**Problem**
`app/_layout.tsx` persists the query cache with `maxAge: 86400000` and `src/api/query.ts` sets
`gcTime: 86400000`, so every persisted entry, including generated readings the user already has, is dropped after
24 hours. FE_01 §3.3 requires generated readings to persist indefinitely. The whole cache, including the
countries GeoJSON (≈ 2.3 MB of JSON), is persisted to MMKV through the sync persister, which re-serialises the
entire cache after changes.

**Change**
1. `query.ts`: default `gcTime` 7 days. Generated readings (`["generated", …]` keys and resource paths for natal
   reading, month and year forecasts, compatibility by id, ACG place / point / country / region reports,
   recommendations, solar return) use `gcTime: Infinity` and `staleTime: Infinity`.
2. Persister: `maxAge` 30 days. `dehydrateOptions.shouldDehydrateQuery` persists only successful queries and
   pending-job parents; never `["job", …]` polling queries, errors, `/geo/*` (static, re-fetchable, FX4.1), or
   heat layers beyond the 3 most recently used goals (FE_01 §3.3).
3. Replace the ad-hoc buster `"phase1-map-readings-v1"` with one derived from the contract version
   (`info.version` of `openapi.yaml`; make `contract:build` export it as a constant) plus a local cache-shape
   version constant,
   so contract changes clear the cache intentionally.
4. Dev only: log the persisted blob size after each write; warn above 5 MB.

**Acceptance**
- Test: dehydrate filter keeps a natal reading, drops a `job` query and `/geo/countries.geojson`.
- Manual: open a cached natal reading, move the clock forward 3 days (or mock `Date.now`), enable airplane mode,
  relaunch → the reading renders.
- Dev log shows the persisted blob shrank after excluding `/geo/*` (state both numbers in the report).

---

## FX1.6 Error reporting sink

**Problem**
`@sentry/react-native` and `posthog-react-native` are dependencies but neither is initialised anywhere in `app/`
or `src/` (`src/lib/telemetry.ts` only defines `safeEvent` and `scrubError`). Crashes and contract violations in
testers' builds are invisible. FE_01 §3.5 requires error boundaries to report.

**Change**
1. `src/lib/telemetry.ts`: `initTelemetry()` (called once in `app/_layout.tsx`), `reportError(error, context)`,
   `reportContractViolation(schema, issues)`.
2. With `EXPO_PUBLIC_SENTRY_DSN` set: `Sentry.init` with `sendDefaultPii: false`, a `beforeSend` that applies
   `scrubError`, removes request and response bodies, and replaces path segments after `/profiles/`, `/places/`,
   `/compatibility/` with `:id`. Breadcrumbs: navigation (route names only) and HTTP status codes; no URLs with
   query strings.
3. Without a DSN: no vendor calls. In dev, keep the last 50 reports in memory and show them in `app/gallery.tsx`
   (or the existing dev screen).
4. PostHog stays off unless a key is provided (unchanged).
5. Do not create vendor accounts or projects; Radul supplies a DSN if he wants one.

**Acceptance**
- Without a DSN: no network requests to Sentry hosts (network log).
- With a test DSN (if supplied): a forced crash from the route error boundary arrives with no birth data, names or
  coordinates (FE_01 FA8).

---

## FX1.7 Live Home in local mode

**Problem**
`src/features/home/HomeScreen.tsx` renders `LocalHomeScreen` when `EXPO_PUBLIC_BACKEND_MODE === "local"` because
the local API has no `/home` route (`local-api/app.ts` falls through to `default: throw issue(503)`). Testers
therefore see a profile list instead of the FE_04 §2 Home (greeting, Your Day, today's text, coming up, quick
access). `DemoHomeScreen` also refetches `/home` every 60 s.

**Change**
1. **Local API** `GET /home?lang=` → `HomeSummary` (FE_02 §7.3) for the self profile:
   - `date`, `tz` from `me.current_place` (`calendarContext`), `greeting_name` = self profile label.
   - `tone`, `tone_label`, `score_10`, `tiles` (love, career, money, family) from `dayForecast(...)` (the same
     deterministic builder used by `/profiles/{id}/forecast/day`).
   - `moon` from the calendar day.
   - `today`: add `ForecastJobs.peek(context, lang)` that returns the cached general-lens day reading (`ready`),
     the existing job (`pending`), a failed job (`failed`), or `absent` with reason `not_generated`.
     **`peek` never starts a job**: Home must not spend money.
   - `next_up`: the first three notification candidates from tomorrow, as FE_02 §7.3 describes.
2. **App**: one `HomeScreen` for both modes (FE_04 §2). When `today` is `absent: not_generated`, show a row
   "Read today's forecast" → Ahead / Today (where opening the day is the explicit request). Remove the 60 s
   interval; refetch on focus, on pull-to-refresh, and when the app is foregrounded after local midnight.
3. Delete `LocalHomeScreen.tsx` once Home works in both modes; keep its "My Charts" entry reachable from the
   profile menu (it already is).
4. Mock API: add the `not_generated` variant to the Home fixture.

**Acceptance**
- Local mode: Home shows blocks 2–8 of FE_04 §2 for the self profile.
- Local API test: `GET /home` with a fake generator creates no job and does not touch the ledger, with and without
  a cached day reading.
- "Coming up" rows open the right screens (FE_08 §6.4 deep-link table).
