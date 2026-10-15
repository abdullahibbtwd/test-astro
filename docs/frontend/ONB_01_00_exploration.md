# ONB_01 Phase 0 — progressive natal reading

Date: 2026-10-06. Working checkout: `D:\Dev\astrology-app`.
Source: `G:\My Drive\Tech\Astrology app\FE\ONB_01_PROGRESSIVE_NATAL_READING_SPEC.md`.
Companion investigation: [ONB_02_00_exploration.md](ONB_02_00_exploration.md).

## Gate and outcome

This is the required read-only Phase 0 investigation, not an implementation-completion report. ONB_01 §11 says Phase 0 is a read-only report and its gate is **Stop**. ONB_02 §8 has the same gate. No application behavior, running server, Supabase settings, existing readings or authentication sessions were changed. Only copied specifications, reports, and isolated benchmark artifacts were written. No model calls were made.

The architecture is feasible. Build the shared dossier A0 and progressive reading together, then move the remaining consumers behind the dossier. Keep existing ready batch readings immutable and serve them as-is.

## Confirmed interfaces

| Existing interface | Observed contract / required change |
|---|---|
| `l4_routing.route(kept, chart)` | Returns `RoutingResult`; kept is a list of principle records, not the whole grounding payload. |
| `RoutingResult.non_empty()` | Returns section-to-RoutedPrinciple lists in `SECTION_ORDER`. |
| `RoutingResult.low_salience_ids()` | Returns a set; sort before persisting deterministic JSON. |
| `RoutedPrinciple` | Carries principle_id, rule, about, reasons, texture and salience. Primary vs occupancy/rulership reasons can implement the specified ownership algorithm without changing routing. |
| `section_houses(chart)` | Produces house numbers for house sections and the two luminary notes. |
| `l4_render.section_title(key, lang, house=None)` | Already supports both languages and luminary house titles. |
| `LLMGenerator.section(key, routed, chart)` | Drafts one section using the existing prompt and bounded `_call_json`; returns `SectionDraft`. |
| `LLMGenerator.synthesize_section(key, own_text_tr, all_drafts, chart, low_salience_ids=None)` | Existing batch finalizer takes all drafts. Add a progressive method that reuses `_call_json` and the same limits, with the new prompt. |
| `LLMGenerator.translate(key, text_tr)` | Returns English text; currently called eagerly by batch `synthesize`. Progressive path must call lazily. |
| `LLMGenerator._detox_text(key, text, lang, tries=2)` | Existing bounded cleanup; reuse and validate again afterward. Cheap-provider fallback can add calls, so the shared guard must wrap all attempts. |
| `l4_validate.validate(output, routed_ids=None)` | Requires both non-empty languages today. Add `langs=('tr','en')`, retaining the default for batch regression. Single-section wrappers still need schema_version, precision_tier, movement and principle_ids. |
| `Store` | Synchronous SQLite key/value store with transaction, get, put, list, remove. No built-in per-user record partition. |
| `ReadingJobs.get(profile, lang, retry=False)` | Serves `reading:{chart_key}` or starts one globally exclusive full-reading job. Must become section-aware with per-chart and global caps. |

`l4_progressive.py`, progressive finalize prompt, section bridge, outline/progress/complete/feedback/claim endpoints, section records, and anonymous-session flow do not exist in this checkout yet. The batch bridge still grounds every reading and runs `interpret()`.

## Ownership proof using supplied fixtures

The Phase 0 probe applies the spec algorithm to current routing reasons; it does not change production routing.

| Fixture date | Kept principles | Non-empty sections | core_identity owned | inner_drives owned | Routed ids without primary reason |
|---|---:|---:|---:|---:|---:|
| 1988-12-28 | 166 | 17 | 26 | 12 | 0 |
| 1984-06-12 | 169 | 17 | 20 | 18 | 0 |
| 1979-03-30 | 169 | 17 | 27 | 12 | 0 |

The spec's quoted 166 / 26 / 12 example matches the 1988 fixture in this checkout; the 1979 fixture produces different counts. Do not hard-code exact counts or infer whose real chart a fixture represents. All three meet the core >=20 / inner >=10 thresholds. The implementation tests must additionally verify all house-fact ownership and the sun_house/moon_house own-all exception.

## Reading storage and reuse

- Current natal records: `reading:{chart_key}` (both languages), `reading-job:{chart_key}`, `job:{job_id}`; reports are indexed separately.
- Save sections under `reading-section:{chart_key}:{section}`, with TR immutable once ready and EN additive. Do not let a retry or prompt-version change overwrite ready text.
- Add profile-specific progress and feedback records. Concurrent consumers of one chart join the same section job.
- Publish each ready section into the dossier reading index before marking its public job complete, so PA immediately sees it.
- Preserve existing ready batch readings as specified. Backfill their sections/index without paying to generate them again, retaining available provenance and marking missing provenance explicitly.
- New API responses must omit drafts, principle ids, usage and context keys. Export remains an authenticated separate path.

## Anonymous authentication: verified project state

Read-only `GET /auth/v1/settings` returned:

- anonymous users: **disabled**;
- email and Google: enabled;
- Apple: disabled;
- signups not globally disabled.

No anonymous user was created and no settings were changed. The local `SupabaseAuth.user()` requires a confirmed owner email. `bindOwner()` pins the store to a single user id. Simply enabling anonymous sign-in would therefore not implement this spec.

Phase 4 needs verified anonymous JWT support, owner-scoped records or separate stores, profile ownership checks, install/IP limits, and a transactional claim operation. Keep `allow_anonymous=false` until those protections and P9 pass. Continue enforcing the configured owner-email restriction for permanent accounts in this private preview.

## Concrete implementation sequence for approval

1. Shared dossier A0 plus deterministic progressive Plan/ownership; single-section generator, prompt and language-aware validation. Fake-generator tests first; no paid calls.
2. Section scheduler and bridge; outline, section, progress, complete and feedback endpoints; unchanged full-reading response; contract/schema/mock generation and `npm run check`. Stop at ONB_01 Phase 2.
3. Dossier remaining tiers, consumer migration and reading index as detailed in ONB_02; keep paid generation out of every deterministic loader.
4. Bounded live quality comparison only at the separate Phase 3 gate. Do not enable the single-pass experiment as the default. Keep the existing $20 cap and existing pricing-expiry guard until explicitly reviewed.
5. Anonymous auth, conversion and claim under a disabled-by-default flag; separate Phase 4 gate.

## Recommended defaults

- Anonymous ceiling: Part One (five sections), not just core_identity.
- Read ahead: one section; full allowed reading after three opened sections; global LLM cap three, per-chart two normally / three in complete mode.
- Exact birth time required; no names inside generated prose; TR first and EN translated only when requested.
- Keep the current paid-call models and the existing $20 shared guard.

## Scope boundary

These two specs explicitly exclude new frontend onboarding screens (ONB_01 §12). The first implementation delivers backend/API/contracts/mocks. Progressive scrolling and the feedback-to-email UI belong to the updated FE_ONB specification after Phase 2; do not claim them complete based on backend work alone.

Acceptance benchmarks P1–P12 have not been run against a new implementation because the required Phase 0 gate has not yet been crossed.
