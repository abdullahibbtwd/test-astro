# ONB checkpoint — progressive reading API and shared A0 dossier

Historical Phase 2 checkpoint. See [the subsequent Phase 3 review](ONB_PHASE3_REVIEW.md) for current live costs, findings and remaining work.

Date: 2026-10-06. Working checkout: `D:\Dev\astrology-app`.

## What is ready

ONB_01 Phases 1–2 are implemented and tested offline. A new profile can prepare its chart data once, generate only the first reading section, and prepare the next section as the reader opens the current one. After three distinct sections are opened, completion prepares the remaining allowed sections. Requests for the same section share one job. Saved Turkish prose stays unchanged; English is added only when requested.

Implemented endpoints:

- `GET /profiles/{id}/natal-reading/outline`
- `GET /profiles/{id}/natal-reading/sections/{key}`
- `POST /profiles/{id}/natal-reading/progress`
- `POST /profiles/{id}/natal-reading/complete`
- `POST /feedback/reading`
- Existing full-reading endpoint uses progressive completion when the feature flag is enabled.

The generated OpenAPI, TypeScript and Zod contracts and mock server include these routes. The mock exercises pending-to-ready transitions and the anonymous 403/409 rules. Real anonymous authentication is deliberately still unavailable pending Phase 4.

Feedback replaces an earlier rating of the same target. Private comments are exported with the account and erased with it. Public section responses omit drafts, grounding identifiers, usage and prompt context. Account export includes dossier manifests, chart data and grounded identifier lists, without exporting the corpus or intermediate reading drafts.

Existing batch readings are preserved. Their prose is reused without model calls and indexed for the astrologist. Missing historical grounding provenance is explicitly marked as reconstructed from the current plan.

## ONB_02 work included

The shared **A0 foundation** now stores the chart, natal grounding, section plan and astrologist dossier. Atomic files and process/thread locks prevent concurrent duplicate builds. Product versions invalidate dependent data while keeping ready reading prose immutable. The existing app chart key remains the identity.

The astrologist can read ready app sections from the dossier index and answer from grounded records when a section has not been generated. This path never starts section generation. Its natal chart and dossier loaders reuse A0; CLI behavior remains supported.

Deletion uses explicit profile references. Removing one of two references keeps the dossier. Removing its last known reference deletes only the verified chart directory; unrelated charts and untracked legacy data remain intact. Automatic approval review rejected an earlier whole-folder deletion proposal; that proposal was not applied.

## Validation

| Check | Result |
|---|---|
| Final `npm run check` | Passed: contracts, 5,302 fixtures, typecheck, lint, 117 Node tests, 50 native tests across 16 suites |
| Python regression run: L4, dossier, PA dossier/tools/cards/pipeline | 141 passed |
| Final focused dossier/bridge run, including two additional tests | 7 passed; overlaps the broader run |
| Offline authenticated HTTP flow | Profile creation, initial-only generation, progress/read-ahead, completion, saved-report history, feedback, export and erasure passed |
| Fake generation | Exactly draft + finalize on initial creation; one additional section after opening core; no eager English; concurrent requests join |
| Restart and failure handling | Interrupted completion requires retry; failed English preserves ready Turkish; retry translates without redrafting |
| Ownership | Three supplied fixtures plus the saved self chart checked; self chart has 17 sections, core owns 26 identifiers and inner drives owns 12 |
| A0 cold benchmark | 9 fresh processes over 3 fixtures: p95 313.62 ms inside Python, 420.43 ms including process startup |
| Paid model calls | Zero; ledger remains $1.228581 under the existing $20 cap |

Evidence is in `FE/artifacts/onb-phase2/check.log`, `a0-timings.json`, and `private-check-summary.json`. The last file contains only aggregate results, not birth details. A pre-existing whitespace issue in `FE/PHASE_1_REPORT.md` was left untouched; the implementation diff passes the whitespace check.

## What is not complete

This is **not completion of all ONB_02 work**. Remaining work:

1. A1: shared wheel, map, city scan, goal scan, rankings and place-grounding products.
2. B: rolling calendar events, scores, Best Days, notifications and forecast products, including refresh on date/location changes.
3. C: shared relationship products and pair lifecycle.
4. Rewire all remaining bridges and astrologist calendar/map/relationship loaders; replace prewarm with the lower-priority dossier background job. Prove warm consumers make zero compute/grounding calls and measure full background time.
5. ONB_01 Phase 3: guarded live comparisons and the optional single-pass experiment; prose quality, real latency and real cost remain unverified.
6. ONB_01 Phase 4: anonymous authentication, rate limits, conversion and account claiming. Anonymous production access stays disabled.
7. New onboarding screens are outside these backend specs and need the follow-on FE_ONB design.

## Runtime and required review gate

The running Android preview was not restarted. Existing preview behavior remains available. The new pipeline is opt-in through `ASTRO_PROGRESSIVE_READING=1`, and model calls additionally require the existing `ASTRO_ALLOW_PAID=1` guard. The feature flag has not been enabled in the running preview.

ONB_01 §11 explicitly gives Phase 2 the gate **“Stop”**, before the live comparison. This report is that review checkpoint. No pricing date was extended and no anonymous provider setting was changed.

Next work is the remaining ONB_02 deterministic integrations and the separately gated live reading comparison. The latter must stay under the existing $20 limit and pass the current pricing-validity guard (expires 2026-10-09). No API keys or new paid service are needed for this checkpoint.
