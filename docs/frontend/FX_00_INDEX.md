# FX 00: Frontend fixes after the demo review (index and ground rules)

*Audience: the frontend coding agent working in `D:\Dev\astrology-app\FE`. Source: the review of the Android
preview of 5 October 2026 (code, `HANDOFF_REPORT.md`, `ANDROID_ACCEPTANCE_REPORT.md`, `USER_TEST_GUIDE.md`, and the
acceptance screenshots). The FE_00–FE_09 specs remain the product reference; this set says what to fix in the
existing build and where FE specs are amended.*

## 1. Documents

| Doc | Phase | Scope | Size |
|---|---|---|---|
| FX_01_RELIABILITY_SPEC | 1 | Job state and timeouts, "busy" handling, error copy, contract validation, offline persistence, crash reporting, live Home | ~3 days |
| FX_02_SHELL_NAVIGATION_SPEC | 2 | Shared components, headers and safe area, profile switcher, Ahead controls, life-area grid, Chart layout and wheel gestures, full-screen Map, job progress and toast, sheets instead of alerts, Saved reports | ~1 week |
| FX_03_COPY_FORMAT_A11Y_SPEC | 3 | Dates, country names, report titles, band chips, calendar legend, skeletons, accessibility pass, Best Day detail | ~3–4 days |
| FX_04_PERFORMANCE_CLEANUP_SPEC | 4 | Country geometry, list virtualisation, one job poller, heat layer, bundle audit, dead code and typed routes | ~2–3 days |

Item ids are `FX<phase>.<n>` (e.g. FX1.3). Every item has **Problem** (with file references as of 5 Oct 2026),
**Change**, and **Acceptance**. File and line references are pointers, not guarantees; re-locate them before editing.

## 2. Ground rules (binding)

1. **Approval per phase.** Implement one phase at a time. After each phase stop, deliver the phase report (§4) and
   wait for Radul's approval before starting the next phase. Do not start work outside the listed items; record
   anything else you find under "Found, not fixed" in the report.
2. **Version control first.** The FE folder is not a git repository. Before any change: `git init`, add a
   `.gitignore` (`node_modules/`, `android/build/`, `android/app/build/`, `android/.gradle/`, `.expo/`, `dist*/`,
   `.local-data/`, `artifacts/`, `.env*`), and commit the current state as `baseline: demo 2026-10-05`. One branch per phase
   (`fx/phase-1-reliability`, …), merged only after approval. Never commit secrets (check `.env*`,
   `.local-data/`, `auth-config.json`).
3. **No paid AI generation.** The total AI budget is US$20 and is partly spent. Do not trigger any new paid
   generation while implementing or testing: use the mock API (`EXPO_PUBLIC_BACKEND_MODE=demo`), cached reports in
   the local API, and the injectable generators of the local API job classes (`ForecastJobs`, `ReadingJobs`,
   `MapJobs`, `CompatibilityJobs`) with fakes in tests. The spending ledger must be unchanged at the end of each
   phase (state it in the report). If an acceptance check truly needs a live generation, ask first.
4. **Keep the suite green.** The current 83 API/logic tests + 16 native tests, `tsc --noEmit` and lint pass today
   and must pass after every phase. Add the tests named in each item.
5. **i18n parity.** Every new user-facing string goes into both `en.json` and `tr.json` (same keys). Mark new
   Turkish strings for native review in the phase report. No hard-coded English in components.
6. **Privacy.** No birth data (dates, times, places, names of saved people) in logs, telemetry, or error reports
   (FE_01 §10.1).
7. **Backend scope.** You may change the local API (`local-api/*.ts`) where an item says so. Do not change the
   Python pipelines or bridges (`*_bridge.py`, `budget.py`, `map_place.py`).
8. **Contract changes** go through `openapi.yaml` + `contracts/spec-types.ts`, then `npm run contract:build` and
   `npm run contract:zod`; never hand-edit `src/api/zod/index.ts` or `src/api/schema.d.ts`. Update mock-api
   fixtures and handlers to match.

## 3. Amendments to the FE specs

These items intentionally change earlier specs. Treat the FX text as authoritative where they differ.

| FE spec | Was | Now | Item |
|---|---|---|---|
| FE_01 §3.4 | Poll to 10 min, then show failed | Time never produces "failed"; only the server does. Slow states at 3 and 20 min; polling backs off but never stops while the screen or watcher needs it | FX1.1 |
| FE_01 §3.3 | Persist policy (no max age stated) | Persisted cache max age 30 days; generated readings never garbage-collected; `/geo/*` never persisted | FX1.5 |
| FE_02 §5 | Problem codes | New code `busy` (HTTP 409) with `blocking_job_id`; absence reasons `not_generated` and `generation_paused` get chrome copy | FX1.2, FX1.3 |
| FE_04 §2 | Home `today` is the day reading | Home never starts a paid generation; when no cached day reading exists, `today` is `absent: not_generated` and Home links to Today | FX1.8 |
| FE_08 §2.1, CB1 | Tone ring on mixed days | Rings only on favourable and challenging days; legend under the grid | FX3.6 |

## 4. Phase report (deliver at the end of each phase)

A markdown file `FX_PHASE_<n>_REPORT.md` in the repo root containing:
- Items done, with one line each on what changed and the files touched; items skipped and why.
- Before/after screenshots of every screen that changed (Android emulator, light theme; dark theme for one
  screen per phase), at default font size and at the largest font size for one screen.
- Test results (counts), typecheck and lint status, new tests added.
- Spending ledger value before and after (must be equal).
- New strings needing Turkish review.
- "Found, not fixed": issues noticed outside scope.

## 5. Definition of done (all phases)

- All acceptance checks of the phase pass and are stated in the report.
- No `Alert.alert` used for choices or for success messages (FX2.8) after Phase 2.
- No raw ISO date or country code visible in any screen after Phase 3 (FX3.1, FX3.2).
- The six P0 issues from the review are closed after Phase 1: false "failed" after restart, 10-minute cutoff,
  generic error for busy, strict validation in release, 24-hour cache expiry, missing live Home.
