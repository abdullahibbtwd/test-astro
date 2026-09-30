# Astrology frontend — Phase 0

Active working copy: `D:\Dev\astrology-app\FE`. This is a native Expo foundation and fixture-backed mock, not the complete application. Read [the exploration report](FE_EXPLORATION_REPORT.md) for coverage, draft contract decisions and the required Phase 0 review.

## Run locally

Use Node 22.13+ (22 LTS recommended) and Python 3 with the existing backend's dependencies available. Keep the original source run folders next to `FE`; they are needed to regenerate private fixtures.

```powershell
Set-Location 'D:\Dev\astrology-app\FE'
npm ci
npm run check
npm run mock
```

Mock: `http://127.0.0.1:4010/v1`. Email: `demo@example.com`; code: `000000`. For direct API inspection use `Authorization: Bearer mock-access`. Fixture date is fixed to 2026-09-29. Mock birth-profile calculations reuse fixture positions deliberately; they are not real calculations for newly entered birth data.

```powershell
Invoke-RestMethod 'http://127.0.0.1:4010/v1/profiles?lang=en' -Headers @{ Authorization = 'Bearer mock-access' }
```

In another terminal, `npm start` starts Metro for a development client. `npm run android` requires Android SDK/JDK/device configuration. `npm run ios` requires macOS/Xcode; alternatively link an EAS project and use the checked-in build profiles. MapLibre/Skia require native development builds. The shell currently has no feature API integration. `npm run bundle` checks both JavaScript/Hermes bundles; it does not compile native binaries.

The mock listens on loopback by default. `MOCK_HOST` can explicitly change the interface for physical-device testing. Use Android emulator host alias `10.0.2.2` when wiring the future client. Do not expose this unauthenticated-development infrastructure publicly.

## Generated files

- Contract: `npm run contract:build`, then `npm run contract:types` and `npm run contract:zod`.
- Fixtures: `npm run fixtures:build`; no model calls, validates every output.
- Checks: `npm run typecheck`, `npm run lint`, `npm test`.
- Do not edit generated `contracts/`, `src/api/schema.d.ts` or `src/api/zod/index.ts` by hand. Proposed spec resolutions are recorded in the report.
- `mock-api/fixtures/`, dependencies and bundle artifacts are gitignored. Do not commit real birth-data fixture outputs.
