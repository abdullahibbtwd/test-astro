# Astrology frontend — Android preview

Active working copy: `D:\Dev\astrology-app\FE`. Phase 1 now has an Android development preview. Double-click **Open Android Preview.cmd** in this folder to open it. Use **demo@example.com**, code **000000**. The welcome screen also offers a fresh-account onboarding demo. Read [the Phase 1 report](PHASE_1_REPORT.md) for verified flows and remaining acceptance gaps. The original [exploration report](FE_EXPLORATION_REPORT.md) records Phase 0 findings.

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

In another terminal, `npm start` starts Metro for a development client. `npm run android` requires Android SDK/JDK/device configuration. `npm run ios` requires macOS/Xcode; alternatively link an EAS project and use the checked-in build profiles. MapLibre/Skia require native development builds. The Phase 1 screens use the local mock API. `npm run bundle` checks both JavaScript/Hermes bundles; it does not compile native binaries.

The mock listens on loopback by default. `MOCK_HOST` can explicitly change the interface for physical-device testing. Use Android emulator host alias `10.0.2.2` when wiring the future client. Do not expose this unauthenticated-development infrastructure publicly.

## Generated files

- Contract: `npm run contract:build`, then `npm run contract:types` and `npm run contract:zod`.
- Fixtures: `npm run fixtures:build`; no model calls, validates every output.
- Checks: `npm run typecheck`, `npm run lint`, `npm test`.
- Do not edit generated `contracts/`, `src/api/schema.d.ts` or `src/api/zod/index.ts` by hand. Proposed spec resolutions are recorded in the report.
- `mock-api/fixtures/`, dependencies and bundle artifacts are gitignored. Do not commit real birth-data fixture outputs.

## Android preview on this computer

- **Open:** double-click `Open Android Preview.cmd`, or run `powershell -ExecutionPolicy Bypass -File scripts/Start-Android-Preview.ps1`.
- **Rebuild after native dependency/config changes:** `powershell -ExecutionPolicy Bypass -File scripts/Build-Android-Preview.ps1`.
- Tools live outside Drive in `D:\Dev\astrology-app\.tooling`. The emulator uses API 36, x86_64, WHPX acceleration and software graphics for this host.
- The development APK is `android/app/build/outputs/apk/debug/app-debug.apk`. It targets the local x86_64 emulator, not a typical ARM phone.
- The launcher starts Metro and the mock locally, forwards ports 8081 and 4010, and opens the native app. Initial emulator boot takes about a minute. Metro needs IPv4-first DNS for Android port forwarding on this Windows host.
- Local logs: `../.tooling/metro.log`, `mock.log`, `emulator.log`, and corresponding error logs. Do not publish birth fixtures or debug output.
- `npm run check` runs the complete fixture and native component checks; `npm run release:check` intentionally fails while legal consent and application identifiers remain placeholders.
- Mock state resets when its server restarts. A stale session returns to sign-in. No real email is sent by the mock.
