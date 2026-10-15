# ONB Phase 3 live comparison checkpoint

Date: 2026-10-06. Working folder: `D:\Dev\astrology-app`.

## Result and review gate

Three supplied fixtures completed full 17-section Turkish progressive readings. A second run revised the opening prompt after the first produced only 174–187 words. The revision improved length to 292–320 words, still short of the spec's approximately 450. This requirement is **not passed**. Do not enable the experimental pipeline based only on structural validation.

Private side-by-side text: [Open review](artifacts/onb-phase3-v2/review.html). It includes existing batch, progressive, and experimental single-call openings. Text and raw private artifacts are ignored by Git. Review tone, grounded meaning, repetition and single-call quality. No quality judgment by Radul or Claude has yet been recorded.

ONB_01 §11 requires: **“Stop: Radul and Claude review the texts”** after Phase 3. Phase 4 anonymous authentication/claim remains disabled. `ASTRO_PROGRESSIVE_READING` remains off in the preview; no user reading was replaced. Android was not restarted.

## Budget and timing

Explicit permission covers the three fixtures' astrology data and generated text to Google Gemini and OpenAI, excluding account name/email. The automatic approval review initially blocked that egress; the user's explicit provider approval resolved it before execution.

Ledger: $1.228581 before the experiment → $3.119806 afterward. Total additional spend across both runs: **$1.891225**, below the shared $3 experiment ceiling and existing $20 total cap. These are guard estimates from recorded provider usage, not an invoice. Batch artifacts were reused on the second run.

Revised opening generation: p50 **10.146 s**, sample p90 **11.440 s** across three concurrent fixture runs. This excludes chart preparation, app HTTP queueing and emulator rendering; it does **not** establish the end-to-end profile-creation latency target. The sample is too small for a production percentile claim.

| Fixture | Opening seconds | Opening words | Part One TR cost | Full 17-section TR cost |
|---|---:|---:|---:|---:|
| 1 | 10.146 | 319 | $0.069968 | $0.239277 |
| 2 | 8.669 | 292 | $0.066965 | $0.240111 |
| 3 | 11.440 | 320 | $0.069647 | $0.241003 |

English is lazy and was not generated. Single-call comparison covers core_identity only; full-reading equivalence and savings have not been established. The batch comparison uses all 17 batch drafts followed by the existing core finalizer; its displayed opening finalization cost is not a whole batch-reading cost.

| Section | Fixture 1 | Fixture 2 | Fixture 3 |
|---|---:|---:|---:|
| core_identity | $0.014999 | $0.012113 | $0.015835 |
| sun_house | $0.007331 | $0.007619 | $0.007660 |
| moon_house | $0.007463 | $0.007447 | $0.007622 |
| inner_drives | $0.014713 | $0.015625 | $0.014408 |
| chart_shape | $0.025462 | $0.024161 | $0.024122 |
| identity | $0.014331 | $0.011189 | $0.014073 |
| values_money | $0.012240 | $0.012187 | $0.010390 |
| communication_learning | $0.011436 | $0.011620 | $0.012011 |
| family_home | $0.010947 | $0.019186 | $0.010606 |
| joy_creativity_children | $0.016477 | $0.020463 | $0.013393 |
| health_routine_pets | $0.011961 | $0.013703 | $0.015163 |
| partnerships | $0.013622 | $0.014526 | $0.016792 |
| transformation_intimacy | $0.013009 | $0.013994 | $0.013574 |
| travel_philosophy | $0.022043 | $0.012992 | $0.015632 |
| status_vocation | $0.015125 | $0.013847 | $0.013504 |
| friendships_future | $0.013330 | $0.017995 | $0.011440 |
| subconscious_solitude | $0.014788 | $0.011444 | $0.024778 |

## Deterministic dossier work in this increment

Added versioned JSON/NPZ product caching, failure/absence manifest status, and serialization with last-reference deletion. Added CPU-only producers for wheels, map geometry, city/goal scans, heat, calendar scores/events/periods/Best Days/notifications, forecasts/grounding and directional relationship grounding. Calendar scores and periods share one internal score computation.

These new products are **not wired to all app/PA consumers yet**. They do not constitute completed ONB_02. The existing approved A0 integration is unchanged.

Remaining ONB_02 work: A1 rankings/place grounding and old-map-cache migration; complete dependency/version coverage (including calendar read-through cache versions); canonical pair storage/lifecycle; all calendar/map/forecast/relationship bridge and PA rewires; profile background job and refresh orchestration; warm-consumer and background timing acceptance tests. Wheel SVG delivery/aliases also need final spec alignment.

Validation in this increment: 72 offline L4/dossier regression tests passed. The final product suite then passed 7 tests, including one additional real NPZ round-trip and SVG wheel reuse test (6 overlap the regression run). Coverage includes warm reuse, shared scoring, date/location anchors, failure/retry, deletion while building, and progressive-only opening instructions. No model calls occur in those tests. Earlier checks are documented in ONB_IMPLEMENTATION_CHECKPOINT.md and are not presented as fresh validation of unfinished integrations.
