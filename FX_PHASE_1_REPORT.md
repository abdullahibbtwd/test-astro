# FX Phase 1 — reliability fixes

5 October 2026. Implementation branch: `fx/phase-1-reliability`. **Ready for phase review; not merged.** FX_02–FX_04 have been read but have not been implemented, in accordance with FX_00 §2.1.

## What changed

| Item | Implementation |
|---|---|
| FX1.1 | Removed ten-minute local failures in job hooks, embedded reading blocks and lifecycle notifications. `job-timing.ts` defines three-/twenty-minute slow states; `job-policy.ts` backs polling off to 10/30 seconds. `use-parent-jobs.ts` immediately checks hydrated jobs and reconciles terminal/missing jobs once with the normal parent request. Pending jobs have no Retry button. |
| FX1.2 | All four local job classes now expose HTTP-409 `busy` problems with the actual `blocking_job_id`. Forecast/map responses preserve their GeneratedPart envelopes. Active screens watch the blocker and resume once; leaving a screen prevents starting its waiting reading. New compatibility creation uses the same focus-bound behavior. |
| FX1.3 | Added `api/errors.ts`, network-error normalization, offline query handling, differentiated EN/TR messages, rate-limit countdown, and shared ErrorNotice/JobProgress/Generated rendering. Disabled generation produces `generation_paused` absence responses, including natal and compatibility. Contract responses include GenerationAbsent. |
| FX1.4 | Changed the Zod generator to delegate to `contract-validation.ts`: strict development/staging, tolerant release objects/arrays with structural diagnostics, and shallow geometry envelopes. Full geometry fixture validation remains in `contract.test.ts`; local API input validation remains strict. Added neutral/skip fallbacks for unknown enum values and glyphs. |
| FX1.5 | Query retention is seven days by default, Infinity for saved/generated report resources; persistence lasts 30 days. Excludes poll queries, errors, static geography and all but three recent heat layers. Cache buster uses generated contract version 1.1.0 plus cache-shape version 2. Dev persistence logs byte counts only. |
| FX1.6 | Added one-time telemetry initialization, scrubbed error/contract reporting, route-boundary reporting and a 50-entry development diagnostics ring visible in Gallery. Sentry stays uninitialized without a DSN; no vendor account was created. |
| FX1.7 | Added live `/home` using the existing deterministic day builder and self profile. `ForecastJobs.peek` never starts generation. Home now works in both modes, links absent readings to Today, and refreshes on focus/pull/local-midnight foreground instead of every minute. Removed LocalHomeScreen; added a mock `not_generated` Home variant. |

Contract source amendments are recorded in `scripts/build-contract.ts`, which owns the generated `contracts/spec-types.ts`, OpenAPI and contract-version outputs. `scripts/build-zod.ts` owns generated Zod changes; generated files were rebuilt rather than hand-edited. No Python pipeline or bridge was changed.

## Validation

- **92 API/logic tests passed**, including the original 83 and nine new tests.
- **28 native tests passed**, including the original 16 and twelve new tests.
- `npm run typecheck` and `npm run lint`: passed.
- Contract build, TypeScript contract generation and Zod generation: passed; full fixture validation remains enabled.
- New coverage: all error categories; pending thirty-minute jobs; hydration → success; missing job → exactly one normal parent fetch; focused/blurred busy resumption; all four server busy guards with held fake generators; paused generation; Home with/without cached prose and zero generator calls; release enum tolerance/development rejection; geometry envelopes; cache exclusions and three-day-old reading hydration; scrubbed bounded diagnostics; Today, place and calendar-day rendering with unknown enums.
- Native rate-limit test verifies the Retry button stays disabled until its countdown ends.
- Search of `src` and `app` finds no `600000` or `180000` timeout literals.

### Android evidence

[Open the screenshot gallery](FE/artifacts/fx-phase-1/index.html).

| Check | Evidence / result |
|---|---|
| Previous Home | [3 October baseline](FE/artifacts/acceptance-2026-10-03/18-google-return.png), reused from the existing acceptance run. |
| Live Home | [Summary](FE/artifacts/fx-phase-1/home-light-top.png) and [cached reading/upcoming events](FE/artifacts/fx-phase-1/home-light-reading.png). |
| Busy waiting | [Real shared component with synthetic busy state](FE/artifacts/fx-phase-1/busy-message.png); focus/automatic resumption verified by native tests. |
| Very slow pending | [Light](FE/artifacts/fx-phase-1/pending-light-final.png), [dark](FE/artifacts/fx-phase-1/pending-dark-final.png), [font scale 2.0](FE/artifacts/fx-phase-1/largest-pending-light.png). No failure or Retry button. |
| Paused generation | [Shared paused notice](FE/artifacts/fx-phase-1/paused-message.png). The existing natal profiles already had cached readings, so this screenshot uses a development example rather than altering their data. Server absence responses are tested with fake stores. |
| Offline without cache | [Uncached calendar day](FE/artifacts/fx-phase-1/offline-uncached-day.png), with emulator Wi-Fi/mobile data disabled. Correct message and retry action. |
| Offline cached reading | [Reading after app force-stop/relaunch](FE/artifacts/fx-phase-1/offline-cold-reading.png), still with connectivity disabled. The three-day-age variant is automated; the emulator clock itself was not changed. |
| Geometry performance | Android development log: countries **0.87 ms**, AcgLines **0.18 ms**, both below 20 ms. Only schema names and durations were logged. |
| Cache size | Repeatable fixture benchmark: **2,069,236 → 32,078 bytes**, retaining a natal reading and excluding country geometry. This is a like-for-like fixture comparison, not a historical device-cache measurement. Observed device persisted cache after map load: **110,862 bytes**. |

Connectivity, light theme and font scale 1.0 were restored. The emulator is signed in to the existing owner account. The development reload required re-sign-in; no account/profile was created, edited or deleted for this phase.

## Paid-call ledger

| | Calls | Charged microdollars | Dollars | Unsettled calls |
|---|---:|---:|---:|---:|
| Before | 302 | 1,217,258 | $1.217258 | 0 |
| After | 302 | 1,217,258 | $1.217258 | 0 |

**No paid generation during this phase.** The local API was restarted with `ASTRO_ALLOW_PAID=0` before interactive checks and remains disabled for this fix/review cycle. Cached readings still open. No budget ledger was reset or edited.

## Review limits and found, not fixed

- No Sentry DSN was supplied. Disabled initialization and privacy behavior were tested; live delivery to Sentry/native crash capture was not tested. PostHog remains off.
- Waiting/slow screenshots use development examples. Recovery from thirty-minute pending jobs and busy completion were exercised through native tests with controlled responses, rather than leaving a paid job running.
- The device clock was not advanced three days; an aged persisted reading was tested by dehydration/hydration and offline restart was checked separately on Android.
- The cache benchmark uses identical fixture data before/after filtering; no pre-change encrypted device cache snapshot was available.
- Full before screenshots are from the earlier acceptance set. This phase changes Home and shared reliability states; unchanged screen layouts were not recaptured exhaustively.
- Large headers, stacked profile controls, raw dates/country codes, large-font tab label clipping, map layout, generic completion toast, list virtualization and duplicate lifecycle/screen polling remain for FX_02–FX_04. No changes from those later phases were started.
- New Turkish strings below require native-language review.

## Version control

Contrary to the index's assumption, the project already had a Git repository at `D:/Dev/astrology-app` with baseline HEAD `70e27706cb2aa0841777de151fd0f163a062605b`. It was preserved; no nested Git repository was initialized. A new phase branch was created before editing. Existing changes to `FE/PHASE_1_REPORT.md`, `FE/USER_TEST_GUIDE.md`, the earlier acceptance report and `Claude outputs/` were preserved and excluded from this phase's implementation commit. Artifacts and local configuration remain ignored.

## Turkish review list

| Key | Turkish copy |
|---|---|
| `slow` | Bu işlem normalden uzun sürüyor. Bu ekrandan ayrılabilirsiniz; hazır olduğunda size haber vereceğiz. |
| `verySlow` | Bu işlem beklenenden çok daha uzun sürüyor. Tamamlanmazsa lütfen bildirin. |
| `errorOffline` | İnternet bağlantınız yok. Kaydedilen yorumları açabilirsiniz. |
| `errorBusy` | Başka bir yorum hazırlanıyor. Bu yorum, diğeri tamamlandığında başlayacak. |
| `errorRateLimited` | Çok fazla istek gönderildi. Biraz sonra tekrar deneyin. |
| `errorGeneration` | Bu yorum hazırlanamadı. Tekrar deneyin. |
| `generationPaused` | Bu önizlemede yeni yorumlar duraklatıldı. Kaydedilen yorumları açabilirsiniz. |
| `notGenerated` | Bu yorum henüz hazırlanmadı. |
| `errorServer` | Hizmet şu anda yanıt vermiyor. Birkaç dakika sonra tekrar deneyin. |
| `errorNotFound` | Bu öğe artık mevcut değil. |
| `errorRange` | Bu tarih kullanılabilir aralığın dışında. |
| `errorInvalid` | Bu istek desteklenmiyor. |
| `errorConflict` | Bu öğe başka bir yerde değiştirildi. Devam etmek için yenileyin. |
| `retryCountdown` | {{seconds}} sn sonra tekrar deneyin |
| `refresh` | Yenile |
| `requestReading` | Yorum hazırla |
| `diagnostics` | Tanılama |
| `readTodayForecast` | Bugünün öngörüsünü oku |

## Next phase gate

FX_00 §2.1 states: “After each phase stop, deliver the phase report (§4) and wait for Radul's approval before starting the next phase.” Please review this Phase 1 result and the verification limits above before authorizing FX_02. The phase branch has not been merged.
