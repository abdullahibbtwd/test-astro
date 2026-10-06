# Frontend team handoff
**Astrology app · 6 October 2026 · Owner: Radul**

## Start here

This is the current handoff. The project has a working Android development preview connected to real chart calculations, reading generators and the Personal Astrologist. It is **not a production release**.

The owner's remaining product priorities are:
1. Define the payment policy and implement purchases.
2. Refine the UX/UI in the current design direction.
3. Finish and validate the iOS app.

Use [setup](handoff/SETUP.md), [remaining work and decisions](handoff/REMAINING_WORK.md), and [acceptance checklist](handoff/ACCEPTANCE.md). Older phase reports are historical evidence; their statements that Ask, guest onboarding or Google login are missing are superseded here.

**Repository:** https://github.com/radulshishkov/astrology-app (private)

**Delivery branch:** `codex/frontend-team-handoff-2026-10-06`

**Working source:** `D:\Dev\astrology-app`; frontend: `FE/`.

**Drive delivery:** `G:\My Drive\Tech\Astrology app\FE\Frontend-team-handoff-2026-10-06`.

The entire repository is needed: the frontend API launches sibling Python calculation/reading modules. Copying only `FE/src` is insufficient. The delivery manifest identifies the exact commit and archive checksums. The existing `main` branch is an older backend baseline, not this handoff.

## What exists

| Area | Current state | Qualification still needed |
| --- | --- | --- |
| Birth-first welcome | Birth date/exact time/place; consent; animated live core-identity preview before sign-in | Production anonymous abuse/cost controls; smaller-device review |
| Conversion | 40% feature access, then Google/email sign-in and 100% feature access; guest reading claimed and retained | Email-link end-to-end repeat; clarity when an existing account already has its own chart |
| Accounts | Supabase Google sign-in verified on Android; email-link flow implemented; saved sessions/profiles | Multiuser production auth; cloud account deletion; public OAuth configuration |
| Home | Real day summary; discreet “Still in [city]? Change” reminder below date | Visual hierarchy, personalized naming, loading/empty/error polish |
| Natal chart | Actual chart/wheel, facts, sections, stored reading, progressive-reading infrastructure | Full editorial/latency acceptance of experimental reading work |
| Ahead / Calendar / Best Days | Live deterministic calculations plus supported daily/monthly/yearly written readings | Wider date/location/timezone/device acceptance |
| Match | Love/work relationship calculations, reports, persistent jobs/history | Family mode remains disabled; further pair/language coverage |
| Map | MapLibre, chart lines, heat, locations, area reports, destination recommendations | Production map service/licensing, low-end device and iOS checks |
| Parans | Visible, ultra-thin lines (0.35 width in current styling) | Preserve legibility while refining map UI |
| Ask Astrology | Connected local agent; streaming, grounded cards/links, cancellation, history, quota, feedback | Full question benchmark, adversarial evaluation, native Turkish editorial review |
| Exports / saved reports | PDF/image/share, local data export, saved reading navigation | Physical-device/iOS validation; full cloud data lifecycle |
| Design / localization | Supplied charcoal/gold design, Aboreto/Poppins, Night/Parchment, English/Turkish | Complete screen-by-screen consistency and accessibility pass |
| Payments | No billing SDK, store products, purchase verification or implemented paywall | Entire payment workstream |
| iOS | Shared React Native code, plugins and build configuration exist | Native build, platform UX, sign-in, purchases, device QA, TestFlight |

## Preserve the agreed product direction

- Keep ASTROLOGY as the temporary name until Radul chooses the final brand.
- The first screen asks where it all starts, with birth details and **Find out who I am**.
- Generate the real core-identity paragraph before requiring sign-in.
- Keep the loading animation, readable preview and **Sign in for more** step.
- The **40% / 100% indicator describes feature access**, not completed calculation, reading length or payment. Sign-in currently unlocks Ahead, Match and Map. Any paid restriction needs an explicit product decision and matching copy.
- Keep the language selector visible near the bottom without scrolling, and small borderless Terms/Privacy links with usable tap targets.
- Refine the existing charcoal, warm gold, thin line-art, Aboreto/Poppins direction. Do not replace it with a new visual concept.
- Keep the current-city reminder secondary; the greeting and main content lead.
- Keep paran lines ultra-thin. Preserve map selection, card navigation and chart calculations.
- OpenAI/ChatGPT account login and using a user's ChatGPT allowance are **outside the current scope**. Server-side OpenAI API usage is a separate, existing integration.
- Apple sign-in was deferred during Android development; include it in the iOS planning and release review.

See the copied [original design specification](handoff/design/DS_IMPLEMENTATION_SPEC.md), [current design notes](handoff/DESIGN_DIRECTION.md), and supplied design kit. Older design gates already approved during implementation should not be mistaken for new pending approvals.

## Architecture and ownership

```text
Expo / React Native app (FE/app, FE/src)
  -> typed HTTP / SSE client (FE/src/api)
  -> Fastify local API (FE/local-api)
     -> Supabase identity verification
     -> private SQLite profiles, jobs, conversations
     -> Python bridges
        -> chart / calendar / map / relationship calculations
        -> grounded reading pipelines
        -> Personal Astrologist planner -> tools -> writer -> validator
        -> shared provider spending guard
```

Calculation facts, rankings and chart geometry come from deterministic backend code. The language models explain selected evidence; they must not replace calculations or alter rankings. Keep credentials and payment verification on the server.

| Source | Purpose |
| --- | --- |
| `FE/app/` | Expo Router routes and shared shell |
| `FE/src/features/` | Screen implementations by feature |
| `FE/src/design-system/`, `FE/assets/` | Tokens, typography, glyphs, backgrounds and bundled fonts |
| `FE/src/design/components/` | App component adapters; preserve accessibility and callbacks |
| `FE/contracts/`, `FE/openapi.yaml`, `FE/src/api/` | API contracts, validators, client, query cache and job handling |
| `FE/local-api/` | Real private preview service, auth, persistence, bridges and budget |
| `FE/mock-api/` | Demo server and generated fixture loader; not real chart calculation |
| `astrologist/`, `ask_bridge.py` | Personal Astrologist implementation and stream protocol |
| `d_layer/`, `Calendar/`, `Astrocartography/` | Deterministic calculation layers |
| `Interpretation_layer/`, `calendar_reading/`, `prediction_reading/`, `synastry_reading/`, `acg_reading/` | Approved reading layers |
| `profile_dossier.py`, `dossier_products.py` | Shared chart data foundation and partial product-cache migration |
| `FE/FE_00…09*`, `FE/FX_00…04*`, `FE/ONB_01*`, `FE/ONB_02*`, `PA/` | Product, fixes, onboarding/dossier and agent specifications |

## Boundaries the next team must understand

The current server listens on **127.0.0.1:4020**, Android uses ADB reverse, and the test database accepts one pinned Supabase owner. This is not a hosted service for customers. Supabase currently supplies authentication, not a completed cloud application database.

Production needs a hosted HTTPS API, account isolation, durable jobs/storage, secrets management, backups, abuse controls, observability and complete deletion/export semantics. These are backend/platform tasks coordinated with the frontend, not cosmetic UI work. Do not deploy the local owner-only SQLite service as a multiuser app.

ONB_02 is partially implemented. A0 and product producers exist; all map/calendar/relationship consumers, cache migrations, canonical pair lifecycle and background orchestration are not fully migrated. Existing functional paths work without declaring that optimization complete.

The experimental single-pass/progressive comparison is not the default production-approved writing path. Its approximately 450-word opening target was not met in the recorded comparison. Guest onboarding uses the existing normal reading pipeline. See `GUEST_ONBOARDING_REPORT.md` and `ONB_PHASE3_REVIEW.md`.

Known functional limits: exact birth time is required; Solar Return and family compatibility are disabled; Ask has targeted live testing rather than its complete quality benchmark. A safe fallback can still occur for other unsupported/rejected answers.

## Verification at handoff

- Fresh frontend Node/API suite: **124 passed**.
- Fresh native component suite: **57 passed across 18 suites**.
- Isolated source archive + supplied fixtures: **12 demo/real-API/parity checks and TypeScript passed** after Expo generated route types; existing installed dependencies reused.
- TypeScript and ESLint passed after the latest Home change.
- Latest agent suite from the preceding fix: **86 passed**; no new agent code in this handoff.
- Android: birth-first preview → live reading → Google sign-in → saved core previously verified. Ask contract-timing question now returns a validated written answer; current-city link opens settings.
- Native iOS acceptance, production purchase tests and store release are not complete.
- `npm run release:check` intentionally rejects the draft legal text and development application identifier.

Screenshots in the delivery are selected visual references, not proof that every screen/platform has passed. Test logs and package contents are listed in the acceptance document and delivery manifest.

## What Radul needs to provide next

The team can start design refinement and iOS preparation now. Before shipping paid access, obtain decisions on the free/paid boundary, pricing model, usage allowances, trial/refund handling and launch markets. Also obtain final app identity, legal/support content and appropriate access to GitHub, Supabase, Google OAuth, Expo/EAS and store accounts.

Use role-based project invitations and a secure credential channel. The handoff does not contain provider keys, login tokens, private account databases, signing credentials or session backups.
