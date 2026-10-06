# FX phases 3–4: implementation and verification

Date: 5 October 2026. Working copy: `D:\Dev\astrology-app`. The user waived further approval pauses. Phase 3 is committed at `7b79f1a`; Phase 4 follows it on `fx/phase-4-performance-cleanup`.

## What changed

- **Copy/accessibility:** localized dates and country names, flag labels hidden from screen readers, shaped rating chips, quieter calendar grids with ring/icon legends, radio/checkbox states, larger text support, clearer report titles, and completed-answer announcements. Final review also fixed a Best Days bug: localized month headings are now separate from the ISO month used to build the grid. Activity rows include the next-day grade; city sizes use neutral chips.
- **Map:** one language-independent country query with infinite freshness; bounding-box lookup before polygon testing; 239 country identities/properties retained. Simplified geometry is **345,149 bytes**, down from 2,036,762 compact bytes (**83.1% smaller**). The original source fixture remains unchanged. The build script registers the new file in the fixture manifest, and both local and mock APIs serve it.
- **Heat:** adjacent same-level cells merge into rectangles and then at most four MultiPolygon features. Fill antialiasing is disabled. Coverage tests check the same area, cell membership and gaps.
- **Lists:** windowed report/profile/history/calendar/line/area lists; month-grouped year events and grouped recommendations use SectionList; Saved supports pull-to-refresh and automatic next pages. Ask uses an inverted FlatList and Jump to latest. Report rows are memoized. Profile-picker rows integrate with the bottom-sheet list. A 200-report fixture uses the actual report row without inserting records into the account.
- **Jobs:** a single serial scheduler spaces all requests by at least one second, pauses in background, resumes in foreground, updates shared job status, invalidates owning parent resources and emits completion events. Only initial hydration scans the cache; later registrations inspect the changed parent. Focus-bound handling of blocked work is preserved.
- **Routes/dependencies:** API links pass through an internal-route allowlist with a safe tab fallback; common map/calendar/job/notification routes use builders. Navigation `as never` casts are removed; the three remaining openapi-fetch casts are explained. Dead TabScreen removed; LocalHomeScreen was already removed. Fastify, CORS and YAML moved to devDependencies with the lockfile updated. Lucide now uses supported individual icon imports.

## Automated verification

- **98/98 API and logic tests pass**, including local/mock APIs, real deterministic chart/calendar/map pipelines, geometry coverage and worldview identity, scheduler spacing/background behavior, and route rejection. No provider generation is used by these tests.
- **47/47 native tests pass across 15 suites**, including the newly added Best Days calendar regression.
- TypeScript and ESLint pass. Android x86_64 release build succeeds.
- `git diff --check` reports only the pre-existing trailing whitespace in the user's `FE/PHASE_1_REPORT.md`; that document is not part of this change.
- AI ledger remains **302 calls, $1.217258 charged, zero unsettled**. Paid generation remains disabled during this work.

## Bundle measurement

Measured with Expo Android export, `--no-bytecode --source-maps`, then temporary `npx source-map-explorer --no-border-checks`. This is minified JavaScript size, not Hermes bytecode or APK size.

| | Before | After |
|---|---:|---:|
| JavaScript bytes | 7,711,652 | 5,918,590 |
| Mapped Lucide bytes | 1,564,281 | 14,624 |
| Unmapped bytes | 830,046 | 662,378 |

JavaScript reduction: **23.3%**. Source-map attribution leaves about 11% unmapped; the table below excludes synthetic unmapped/no-source entries.

| Largest mapped source modules after changes | Bytes |
|---|---:|
| `@sentry-internal/replay/build/npm/esm/index.js` | 123,346 |
| `react-native/Libraries/Renderer/implementations/ReactFabric-prod.js` | 119,643 |
| `react-reconciler/cjs/react-reconciler.production.js` | 109,620 |
| `expo/virtual/streams.js` | 62,513 |
| `zod/v3/types.js` | 61,421 |
| `/src/api/zod/index.ts` | 58,009 |
| `@sentry-internal/feedback/build/npm/esm/index.js` | 48,238 |
| `@gorhom/bottom-sheet/src/components/bottomSheet/BottomSheet.tsx` | 47,764 |
| `entities/lib/esm/generated/decode-data-html.js` | 47,667 |
| `i18next/dist/esm/i18next.js` | 44,489 |
| `@sentry/core/build/esm/index.js` | 40,788 |
| `@react-native/virtualized-lists/Lists/VirtualizedList.js` | 26,541 |
| `react-native-reanimated/src/layoutReanimation/defaultAnimations/Zoom.ts` | 25,439 |
| `entities/lib/esm/generated/encode-html.js` | 23,496 |
| `@formatjs/icu-messageformat-parser/index.js` | 22,319 |

## Export renderer comparison

Both Android images are saved at 2048 × 2400 using the same chart and captions: `fx-skia.png` and `fx-viewshot.png`. The existing Skia output is sharper. View-shot captures a screen-sized SVG and scales it, so this comparison does not prove that a specially arranged full-resolution view-shot export would be equivalent. Skia remains installed and active, as the spec requires.

The release APK's x86_64 `librnskia.so` contributes **11,754,224 bytes**. This is the measured library contribution, **not a measured total APK delta from removing Skia**; no renderer-removal build was made. A real replacement decision still requires an equivalent full-resolution export and an isolated APK comparison.

## Performance evidence and remaining work

- Emulator: x86_64 Android, software graphics (SwiftShader), 1080 × 2400. No physical Android or iOS device was available.
- Heat: **13,931 cells → 4 features in 16.3 ms** on the emulator, under the 50 ms target. Screenshots show the heat layer without cell-edge seams at the captured scales.
- Persisted query payload in the preview log: **538,324 bytes** after map usage, below 5 MB. Encrypted MMKV allocation measured about 2,072 KiB before the final map session; allocation is not identical to payload size.
- Cold release Activity launch: **3,308 ms** (`am start -W`), above the 2.5 s target even before a separate Home-content-ready measurement. Suggested next step: trace startup on a physical mid-range device and defer heavy non-Home modules.
- Release 200-report scroll: **268 frames, 61.94% janky, p50 57 ms, p95 105 ms** in Android gfxinfo. Populated rows remain present in the captured scrolled view. This does **not** meet the smooth-scrolling target. The recording is a separate debug run, not evidence of release FPS. Suggested next step: compare hardware rendering on a physical device, profile Swipeable row/UI-thread work and tune batch/window sizes from that trace.
- Android gfxinfo reported zero UI frames during the MapLibre pan run, confirming that this surface is not measured by that counter. Its sentinel 4950 ms percentile is invalid and must not be treated as a timing sample. No 55-FPS map pass is claimed.
- Precise cached tab-to-content (<300 ms), cached place-content p50 (<500 ms), warm country-tap (<150 ms), and before/after first-map-render metrics remain unverified. Screenshots prove rendered state, not timing. Cold deep links sometimes returned Home during capture; those diagnostic captures are excluded from the gallery.
- Country simplification now uses pinned build-only Mapshaper 0.6.13, weighted 12% with keep-shapes and 0.001-degree precision. This replaced independent ring simplification after a zoom inspection showed coarse borders. Every country record/property and non-null geometry is checked. The tool reports 459 unrepaired intersections; full cartographic/topology parity is not claimed and this remains a map-quality follow-up.
- Full spoken TalkBack/VoiceOver and every-screen maximum-font acceptance remain open, as stated in the Phase 3 report. Visual/accessibility-tree checks do not replace them.

The release benchmark APK explicitly enables local audit fixtures and the Natural Earth preview map. A temporary network-security overlay allowed cleartext **only for 127.0.0.1** to reach the existing local API. Both temporary XML files were removed after the audit build; normal release policy is unchanged. A normal distributable build still needs the separately planned hosted API/map configuration.

## Files to inspect

- `FE/artifacts/fx-phase-4/index.html`: curated screenshots, scrolling recording and export comparison.
- `FE/artifacts/fx-phase-4/api-tests.log`, `native-tests.log`: test evidence.
- `before-analysis.json`, `verified-analysis.json`: full source-map analysis.
- `release-start.txt`, `list-release-frames.txt`, `map-release-frames.txt`: raw diagnostics. Map timing limitations above apply.
- `FX_PHASE_3_REPORT.md`: earlier copy/accessibility evidence and remaining checks.

The new geometry build was followed by five passing geometry/local-API checks. A network dependency audit also reported existing framework/toolchain advisories (67 total); no forced framework upgrades were attempted. The simplifier was pinned to the audit-recommended version rather than retaining the initially evaluated latest version.

Unrelated user documents and Claude outputs were not staged. An attempted formatting-only restoration was rejected by automatic approval review due to the risk of overwriting uncommitted work. Those formatting changes were preserved instead; no destructive cleanup was performed.
