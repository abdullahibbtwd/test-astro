# Setup and operating guide

## Obtain the delivery

Clone the private repository and check out `codex/frontend-team-handoff-2026-10-06`, or extract `astrology-app-source.zip`. The ZIP contains an `astrology-app/` root. Verify the SHA-256 values in the delivery manifest.

The separate `frontend-demo-fixtures.zip` contains `FE/mock-api/fixtures/`. Extract it **into the repository root**. These are the existing three-profile internal demo outputs, not the live account database. They contain sample birth/chart/reading data and are for this internal handoff, not a production dataset. Keep the ZIP and extracted data private and out of Git.

The prebuilt fixture pack is necessary even for the real local API's configuration/catalogue defaults. It contains its manifest. A source-only clone without it cannot start these preview servers.

## Toolchain

The handoff was checked with **Node 24.14.1 / npm lockfile** and **Python 3.11.9** on Windows. `package.json` supports Node >=22.13 and <25. Install Java/Android SDK using your development environment; SDK/JDK installations and emulators are not shipped.

```powershell
# Repository root, outside Drive-synced folders
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-handoff.txt
cd FE
npm ci
# First clone only: let Metro reach "Waiting", then stop it with Ctrl+C.
# This generates .expo/types/router.d.ts; do not commit generated files.
npm start -- --offline --port 8099
npm run typecheck
npm run lint
npm test
npm run test:native
```

Expo route types do not ship in Git. Skipping that first-start step can produce tuple/route TypeScript errors in `app/_layout.tsx`. The setup was checked in an isolated source archive plus fixture pack: 12 demo/real-API/parity checks and TypeScript passed. This reused the workstation's installed Node/Python dependencies; a fresh dependency installation and macOS build remain team acceptance steps.

macOS/Linux: activate with `source .venv/bin/activate`. The requirements file records direct packages observed in the working environment; it is not a fully resolved cross-platform deployment lock. Qualify Linux/macOS dependency builds during production setup.

`npm run check` also **regenerates** fixtures from historical ignored run folders that are not shipped. For this prebuilt-fixture handoff, use the individual checks above. Do not delete the fixture pack and then expect `fixtures:build` to work without those source runs. Contract generation remains available through `contract:build`, `contract:types`, and `contract:zod`.

## Fast UI demo: no keys, no paid calls

Terminal 1, in FE:
```powershell
npm run mock
```

Terminal 2, in FE:
```powershell
$env:EXPO_PUBLIC_API_URL = 'http://127.0.0.1:4010/v1'
$env:EXPO_PUBLIC_BACKEND_MODE = 'demo'
$env:EXPO_PUBLIC_AUTH_MODE = 'demo'
adb reverse tcp:4010 tcp:4010
adb reverse tcp:8081 tcp:8081
npm start -- --localhost --port 8081
```

Build/install a native development client with `npm run android` on a configured Android environment. MapLibre/Skia and other native modules mean Expo Go is insufficient. Only one Metro instance should generate Expo typed routes for a checkout.

Demo login: **demo@example.com / 000000**. This is a mock credential, not an account-service password. The demo reuses fixed chart positions for entered births; use the real API to test calculations.

## Real local calculations on a fresh development checkout

In FE, with the Python environment active:
```powershell
$env:PYTHON = (Get-Command python).Source
$env:ASTRO_ALLOW_PAID = '0'
$env:ASTRO_ASK_ENABLED = '0'
$env:ASTRO_GUEST_ONBOARDING = '0'
$env:ASTRO_PROGRESSIVE_READING = '0'
$env:ASTRO_PA_ROOT = (Resolve-Path '..').Path
npm run local-api
```

In the Metro terminal use `EXPO_PUBLIC_API_URL=http://127.0.0.1:4020/v1`, `EXPO_PUBLIC_BACKEND_MODE=local`, `EXPO_PUBLIC_AUTH_MODE=demo`, port 8082, and reverse ports 4020/8082. Fresh local databases without real-auth configuration use the private demo login. This tests real calculations; fresh paid readings and guest reading generation remain disabled.

The local API binds loopback in code. Use this private setup locally. A real phone and a public iOS app need a reachable HTTPS backend and production callbacks; pointing them to 127.0.0.1 will not reach a developer's computer.

## Existing owner's Android preview

On the current Windows workstation, SDK/JDK/AVD and a development APK already exist under the local checkout:

```powershell
cd D:\Dev\astrology-app\FE
.\scripts\Start-Android-Preview.ps1 -RealCharts -EnableReadings -EnableAstrologist -RestartApi
```

This existing launcher is tailored to `.tooling/` and the `Astrology_Preview` AVD. It is not a toolchain installer for a new developer. Wait for active readings to finish before restarting. The root `Open Android Preview.cmd` opens the older mock mode; use the explicit command for real guest onboarding/Ask.

The current signed-in owner uses Supabase mode. Do not overwrite that checkout's `.local-data`, change the pinned owner, downgrade auth or reset the app to reproduce a clean first launch. Use a separate clone/emulator for destructive/reset tests.

## Authentication and keys

`handoff/auth-config.example.json` shows the shape only. On a fresh checkout, place real project values in ignored `FE/.local-data/auth-config.json` when configuring your authorized test identity. The server validates the project and pins the first verified owner. Copying/changing owner configuration does not turn this adapter into multiuser auth.

For real auth set `EXPO_PUBLIC_AUTH_MODE=supabase`, configure the Supabase Google provider and callback allowlist, and restart API and Metro. Browser endpoints are documented in `FE/AUTH_INTEGRATION.md`; guest endpoints are in `FE/contracts/guest-onboarding.ts`. A physical device/production callback architecture remains to be implemented.

Server-side provider keys: `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) and `OPENAI_API_KEY`; the existing client also supports private home-directory key files. Never put these in `EXPO_PUBLIC_*`, app source or a handoff archive.

Paid generation additionally needs `ASTRO_ALLOW_PAID=1`. Ask needs `ASTRO_ASK_ENABLED=1` and the complete root/astrologist tree. Guest preview needs `ASTRO_GUEST_ONBOARDING=1` plus paid generation. `ASTRO_PROGRESSIVE_READING` stays off unless its separate rollout is approved.

The owner's existing **$20 total** test cap is enforced by `local-api/budget.py` and its private durable ledger; its pricing guard expires after **9 October 2026**. A new clone's empty ledger does not grant a new $20 allowance. Obtain a separately approved team budget or coordinate the remaining shared allowance before paid tests. Do not bypass the expiry or copy/reset live ledgers casually.

## iOS development entry point

Use the same FE source and lockfile. On macOS with Xcode, `npm run ios` builds a native development app. EAS build profiles are in `eas.json`; account/project/signing configuration is still required. The current iOS configuration targets 16.4 and enables tablet support, but neither is a completed device acceptance claim.

Client URL/auth variables must point to the appropriate development/staging service. Port forwarding instructions above are Android-specific. See the iOS workstream before choosing final IDs, entitlements and sign-in callbacks.

Official build reference: [Expo build setup](https://docs.expo.dev/build/setup/), checked 6 October 2026. Account fees and build plans are to be verified when the team selects its release setup; none was purchased in this handoff.
