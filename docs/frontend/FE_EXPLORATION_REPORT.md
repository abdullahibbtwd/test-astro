# Frontend exploration report — Phase 0

Date: 2026-09-30. Working copy: `D:\Dev\astrology-app`, branch `codex/frontend-specs`.

## Status and review gate

**Reviewable foundation; Phase 0 is not yet fully accepted. The feature application has not been implemented.**

Delivered: an Expo native shell; a draft OpenAPI 3.1 contract with 59 operations and 173 schemas; generated TypeScript and Zod; a local Fastify mock; 4,451 validated fixtures adapted from existing outputs; and an initial wheel adapter parity baseline. No original specification or backend algorithm was changed. The D: copy includes the existing local backend and fixture files so development no longer relies on Drive's filesystem.

`FE_00_INDEX.md` §6 requires “Radul reviews the report, `openapi.yaml` and the mock” before Phase 1. §9 requests the Phase 0 report with “no feature code”. This report is that review artifact. The following prevent claiming the complete Phase 0 gate:

- All routes are registered, but several successful response variants lack matching fixtures or a resolved mapping. Those return an explicit 503 problem instead of fabricated content.
- iOS and Android **JavaScript/Hermes bundles compile**, but no native development build has been compiled or launched on a device. This Windows host has no configured Android SDK/JDK and cannot build iOS locally; EAS credentials/project linkage have not been supplied.
- Proposed contract resolutions below need review. Phase 1–7 screens, persistence, auth integrations, analytics, map interactions, exports, accessibility/device acceptance, and store builds remain outstanding.

## 1. Runtime and pinned stack

The installed stack uses Expo SDK 57, React Native 0.86, and the mandatory New Architecture. SDK selection was checked against the [official Expo SDK 57 release](https://expo.dev/changelog/sdk-57). MapLibre requires a native development build, per its [Expo setup documentation](https://maplibre.org/maplibre-react-native/docs/setup/expo/); Expo Go is not the test target.

`app.json` sets iOS 16.4 and Android API 26, typed routes, MapLibre's config plugin, and iOS scene support. `eas.json` contains development, internal preview and production profiles, with placeholder application identifiers. No EAS project, map provider, auth provider credentials, analytics token, Sentry DSN, or legal URLs were invented.

Every npm dependency is pinned exactly in `package.json` and `package-lock.json`:

| Package | Version |
|---|---|
| `@date-fns/tz` | `1.5.0` |
| `@expo-google-fonts/inter` | `0.4.2` |
| `@expo-google-fonts/source-serif-4` | `0.4.1` |
| `@fastify/cors` | `11.3.0` |
| `@gorhom/bottom-sheet` | `5.2.14` |
| `@maplibre/maplibre-react-native` | `11.4.0` |
| `@react-native-google-signin/google-signin` | `16.1.5` |
| `@sentry/react-native` | `7.11.0` |
| `@shopify/react-native-skia` | `2.6.2` |
| `@tanstack/query-sync-storage-persister` | `5.104.0` |
| `@tanstack/react-query` | `5.104.0` |
| `@tanstack/react-query-persist-client` | `5.104.0` |
| `date-fns` | `4.4.0` |
| `expo` | `57.0.26` |
| `expo-apple-authentication` | `57.0.2` |
| `expo-background-task` | `57.0.21` |
| `expo-build-properties` | `57.0.22` |
| `expo-constants` | `57.0.20` |
| `expo-dev-client` | `57.0.19` |
| `expo-font` | `57.0.4` |
| `expo-linking` | `57.0.11` |
| `expo-localization` | `57.0.2` |
| `expo-location` | `57.0.20` |
| `expo-media-library` | `57.0.5` |
| `expo-notifications` | `57.0.21` |
| `expo-print` | `57.0.2` |
| `expo-router` | `57.0.24` |
| `expo-secure-store` | `57.0.4` |
| `expo-sharing` | `57.0.22` |
| `expo-splash-screen` | `57.0.9` |
| `fastify` | `5.12.5` |
| `i18next` | `26.4.2` |
| `i18next-icu` | `2.4.4` |
| `lucide-react-native` | `1.49.0` |
| `openapi-fetch` | `0.17.0` |
| `posthog-react-native` | `4.78.2` |
| `react` | `19.2.3` |
| `react-i18next` | `17.0.15` |
| `react-native` | `0.86.3` |
| `react-native-gesture-handler` | `2.32.0` |
| `react-native-mmkv` | `4.3.2` |
| `react-native-reanimated` | `4.5.1` |
| `react-native-safe-area-context` | `5.7.0` |
| `react-native-screens` | `4.26.2` |
| `react-native-svg` | `15.15.4` |
| `react-native-view-shot` | `5.1.0` |
| `react-native-worklets` | `0.10.1` |
| `yaml` | `2.9.1` |
| `zod` | `3.25.76` |
| `zustand` | `5.0.15` |
| `@apidevtools/swagger-parser` | `13.1.0` |
| `@testing-library/react-native` | `14.0.1` |
| `@types/fontkit` | `2.0.9` |
| `@types/geojson` | `7946.0.16` |
| `@types/node` | `26.6.3` |
| `@types/react` | `19.2.4` |
| `eslint` | `10.11.0` |
| `eslint-plugin-react-hooks` | `7.1.1` |
| `fontkit` | `2.0.4` |
| `i18next-parser` | `9.4.0` |
| `jest-expo` | `57.0.5` |
| `openapi-typescript` | `7.13.0` |
| `prettier` | `3.9.9` |
| `react-dom` | `19.2.3` |
| `react-test-renderer` | `19.2.3` |
| `test-renderer` | `1.2.0` |
| `ts-json-schema-generator` | `2.9.0` |
| `tsx` | `4.23.15` |
| `typescript` | `5.9.3` |
| `typescript-eslint` | `8.71.0` |

Exceptions and unverified integrations:

- TypeScript 5.9.3 is explicitly excluded from Expo's version alignment: SDK 57 recommends TypeScript 6.0.3, while `openapi-typescript` 7.13.0 declares a TypeScript 5 peer dependency. Strict mode and `noUncheckedIndexedAccess` pass. Revisit when upstream peer support aligns.
- `test-renderer` is pinned to 1.2.0 because 1.3.0 requires React 19.3, while SDK 57 uses React 19.2.3.
- The specified `i18next-parser` 9.4.0 is deprecated and supports Node 18/20/22. CI uses Node 22; this host's Node 24.14.1 emits its engine warning. No replacement was silently selected.
- `expo/fetch` supplies the planned streaming client; no additional SSE library selected. Client streaming integration is Phase 6.
- Maestro is not installed or version-pinned: device tooling is unavailable. Jest/RNTL dependencies are present; Phase 0's pure contract, font, fixture and mock checks run with Node's test runner via `tsx`.
- Expo Doctor reports 21/21 checks passing with the documented TypeScript exception. This does not prove native compatibility of every future feature dependency.
- Last npm audit: 18 moderate findings, no high or critical findings. These include transitive Expo/tooling dependencies; no forced downgrade was applied. Recheck before release.

## 2. Contract and ambiguities

Artifacts: `openapi.yaml`, `contracts/openapi.json`, `contracts/spec-types.ts`, `src/api/schema.d.ts`, `src/api/zod/index.ts`. `scripts/endpoints.ts` inventories every operation, body, response and backend readiness status. `scripts/build-contract.ts` extracts FE_02 and FE_09 TypeScript blocks and supplemental request types; TypeScript and Zod outputs are generated from the resulting OpenAPI. Generic schema names are encoded into valid stable component identifiers. Swagger Parser validates the complete document.

This is a **draft derived from the supplied specs**, not an approved contract change. Before approval, regeneration starts from the spec. After a contract revision, update the generator and specs together to prevent regeneration overwriting a reviewed decision.

| Question | Evidence / current behavior | Decision needed |
|---|---|---|
| Undefined `ThreadSummary` | FE_09 references it without a definition. Draft uses `Omit<Thread, 'messages'>`. | Approve or replace this provisional definition before client code depends on it. |
| Nested notification preference PATCH | FE_02 `Partial<Me>` makes only top-level keys partial; FE_03 describes updating one nested notification field. | Define whether nested fields merge or the entire preferences object is required. Current schema follows top-level partial only. |
| Calendar month/year vs rolling readings | Existing monthly forecast starts 2026-09-29 and ends 2026-10-29; yearly reading starts 2026-09-29 and ends 2027-09-29. FE_04 requires calendar month/year. | Generate matching readings; do not relabel these rolling periods. Routes return 503. |
| Heat layer grid | Existing heat points include off-grid seed coordinates (e.g. -2.6/-70.92 and 176.5/-40.5); required regular-grid metadata is absent. | Specify backend normalization and `grid_step`; heat routes remain unsupported. |
| Overall recommendation band | Raw ranking/scores do not supply the required single `PlaceBand`, nor a rule to derive it. | Provide a backend band or approved mapping; overall recommendations return 503. |
| Dominant paran | A paran has two lines; contract `dominant_line` represents one. | Current adapter returns null instead of choosing one arbitrarily. Confirm this representation. |
| All-region / both-purpose filters | Backend uses `['all']` and `['living','travel']`; contract uses omitted region constraint and `'both'`. | Adapter normalizes these without changing selection semantics; confirm. |
| Job/new infrastructure disabled | `new_off` disables all operations marked NEW, including authentication and polling. | Exercise with a cached mock token; confirm intended job polling behavior when NEW infrastructure is absent. |
| Query validation | Path/query fields are mostly strings in FE_02. Body schemas are validated; supported query selectors have route checks, but complete enum/date/range coverage is not yet defined. | Tighten query schemas and rejection semantics before production transport. |
| Catalogue and mask | Narrative fixtures keep backend translations; adapters allowlist consumer fields and remove internal metadata. Mask tests cover keys and unambiguous tradition terms. | Manual Turkish editorial review remains necessary; automated checks cannot guarantee prose quality. |

## 3. Wheel port plan and first parity result

`packages/wheel-core/adapter.ts` converts API `ChartData` to the canonical engine input without rounding, reordering positions, or computing astrology. `tests/wheel.test.ts` calls the **unmodified** `Chart_wheel/src/render.js`, hashes generated SVGs and compares them with the saved SVG files for three charts in both themes. All six byte comparisons and invariant checks pass.

This establishes the adapter and reference baseline, **not completion of the TypeScript port or all W1–W4 gates**.

Phase 2 plan:

| Canonical module | Port approach |
|---|---|
| `constants.js` | Preserve values/order verbatim; readonly literal types. |
| `transform.js` | Preserve angle/radius calculations and normalization; explicit numeric input/output types. |
| `spread.js` | Preserve collision spreading, tie breaks and sort stability; typed placement records. |
| `glyphs.js` | Preserve all SVG path strings and geometry; typed glyph lookup keys. |
| `theme.js` | Preserve light/dark palette values and defaults; typed theme structure. |
| `invariants.js` | Preserve checks and tolerances; typed violation records, shared by tests. |
| `render.js` | Factor `computeWheel()` geometry from serialization, preserving SVG bytes and draw order. Native SVG view consumes the same geometry; export uses the canonical serializer. |

Types will cover body/sign/angle/aspect enums, positions, houses, aspects, placements, wheel geometry and options, using the API's generated types at the boundary. Do not change numerical formulas for convenience. Run all existing canonical tests, six SVG byte comparisons, W2 interactive geometry checks and W4 export parity after each port step. Native tap targets and raster/PDF output require actual device validation.

## 4. Fixture provenance and mock coverage

`mock-api/scripts/build-fixtures.ts` creates local, gitignored fixture files and a manifest. It makes **no model calls**. Backend catalogues come from `backend-labels.py`; field allowlists strip internal metadata. Fixture validation runs before saving each file and again in the tests.

| Data | Source / available variant |
|---|---|
| Self chart | `prediction_run/20260929-130811_qpm/natal_chart_1979-03-30.json`, Sofia, 06:30 |
| Partner chart and 17-section natal | `runs/20260924-102926_26p_1988-12-28/`, Plovdiv, 13:00 |
| Colleague chart and 17-section natal | `runs/20260922-181953_w1d_1984-06-12/`, Sofia, 14:57 |
| Self daily forecast / Home | `prediction_run/20260929-130811_qpm/reading_day_general_2026-09-29_1979-03-30*`, TR/EN |
| Calendar and Best Days | Existing `run_calendar` outputs; mappings in `mock-api/scripts/calendar.ts`. Calendar 2026-09-28–2027-09-27; Best Days through 2026-12-26. |
| Istanbul report, lines, parans | `acg_run/20260929-105635_kgc/`, confirmed Istanbul coordinates 41.0138, 28.9497 |
| Recommendation / line places / borders | Existing love-world recommendation, city scan, destinations and geography outputs; explicit source paths in `recommend.ts` and `geo.ts`. |

The mistyped “Instanbul” run resolved to Antwerp and is deliberately not used as an Istanbul fixture. A fresh, reviewed fixture pack should retain explicit resolved-place confirmation.

Mock behavior:

- All 59 routes are registered under `/v1`. `scripts/endpoints.ts` and OpenAPI are the complete route inventory.
- Email mock sign-in: `demo@example.com`, code `000000`; preseeded bearer token `mock-access`. Session/profile/thread state is in memory and resets on restart. This is not production authentication.
- TR is default; `lang=en` selects English. Locale parity tests ensure IDs, dates, enums and numbers remain unchanged.
- ETags/304, RFC problem responses, idempotency replay/conflict, 202 jobs, Retry-After, failed-job retry and 24-hour job expiry are exercised.
- Scenario header `X-Mock-Scenario`: `ready`, `slow`, `fail`, `offline`, `rate_limited`, `new_off`, `empty_day`, `absent_polar`, `needs_goal`, `thin_result`. Default generation delay is six seconds; `slow` is 90 seconds for jobs. `MOCK_JOB_SECONDS` changes normal delay.
- Scenario transformations are test cases, not additional real readings. For example, `absent_polar` changes relocation availability and `thin_result` reduces existing results.
- FE_02 §10 explicitly allows new profiles to reuse a fixture chart. The mock chooses a deterministic fixture from the birth triple hash; exact seeded birth triples retain their original chart. Profile UTC/timezone are derived from input, while planetary positions and `big_three` come from that fixture. **This is mock data, never a calculated chart for a newly entered person.** Birth edits invalidate self-specific forecast/calendar/map availability rather than reuse stale self results. Production needs the actual calculation service.
- Birthplace search only searches the small known-place set. `kind=city` and `kind=area` return 503; invalid kinds return 400. Do not interpret this as a global geocoder.
- Ask streams an existing daily reading with status/delta/card/link/done events, persists messages, enforces quota and rejects client-supplied chart data. It is one deterministic daily script; it does not semantically answer arbitrary prompts or satisfy the complete six-script acceptance suite.

Unfinished success cases / required fixture work:

| Gap | Current response / next input |
|---|---|
| Self natal reading | 503; regenerate current 17-section self natal in TR/EN. |
| Full four-profile seed | Three source-backed profiles; child seed still needed. |
| Month/year, personal/professional forecasts | 503; matching calendar-period and lens fixtures needed. |
| Solar Return | Disabled flag / 503; return chart and readings required. |
| Compatibility | Empty list; creation/report 503. Available legacy pair does not match self/partner. Generate general/professional and family cases for intended pairs. |
| Area reports and polar point | Country/region/point reports 503; TR, DE, Antalya and real polar cases needed. Country/region geometry is available separately. |
| Recommendations | Only love/world without custom filters succeeds; career, overall and additional scopes/filters require fixtures/mapping. |
| Place focus goals | Only the fixture's existing focus succeeds; other focuses return 503. |
| Element notes | Optional flag off; complete reading mapping not yet implemented. |
| Saved reports index | Empty; no persistence/indexing integration. |
| Apple/Google sign-in and account email export | 503; no provider or mail transport configured and no pretend successful send. |
| Ask contextual scripts | Only daily fixture stream; remaining five contexts and refusal scripts required. |

These gaps mean “every endpoint from the fixture pack” is not yet achieved. Do not approve full mock coverage solely because every route exists.

## 5. Fonts

Bundled files: `assets/fonts/Inter-Regular.ttf`, `Inter-SemiBold.ttf`, `SourceSerif4-Regular.ttf`. The corresponding OFL license files are included in the same folder. Fontkit tests verify glyph coverage for Turkish `ç ğ ı İ ö ş ü Ç Ğ Ö Ş Ü` and `â î û`; license tests verify redistribution wording. All four tests pass. Fonts are loaded locally in `app/_layout.tsx` and embedded in both platform bundles; no runtime font download.

## 6. Validation evidence

`npm run check` completed successfully on 2026-09-30:

- Rebuilt 59 operations / 173 schemas, generated TypeScript/Zod and 4,451 real-output fixtures.
- Strict TypeScript and ESLint pass.
- **24 tests pass**, including fixture schema/mask validation, locale parity, mock lifecycle/error/idempotency/profile/SSE behavior, fonts, OpenAPI validity and six wheel baseline comparisons.
- 44 map lines and 216 parans compress to 11,898 bytes, below the 150 KB budget; source geometry simplified at 0.05° and duplicate point-only paran crossings excluded.
- `expo export --platform ios --platform android`: both Hermes bundles produced successfully with bundled fonts. No native compilation or device screenshot is claimed.
- Expo Doctor: 21/21 checks pass with the declared TS exception.

`.github/workflows/frontend-contract.yml` defines a Node 22 public-contract/build check. Private birth fixtures are intentionally excluded from Git and hosted CI. Full fixture tests run locally with the source pack. The workflow has not been executed on GitHub.

Review found and fixed: profile key/UTC/fixture consistency, single-profile localization, unsupported place-search kinds, and job expiry. New regression tests cover these paths.

## 7. Next gate

Review `openapi.yaml`, this report and the running mock, resolve the contract questions, and supply/approve the missing fixture variants. Then verify actual native development builds on Android and iOS. Once Phase 0 is accepted, proceed in the specified order: foundations/auth/profiles → chart → Ahead/calendar → Match → Map → Ask → hardening. Product branding, provider selection and credentials remain the open decisions in FE_00 §7.
