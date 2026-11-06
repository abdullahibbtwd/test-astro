# Mobile hardening notes

| Control | Status | How verified |
| --- | --- | --- |
| Access/refresh tokens in SecureStore | Done | `tokenStorage` + chunked `secure-kv`; Supabase auth uses `secureKvAdapter` |
| Session shell (me) without tokens | Done | Durable file holds non-secret shell only; migrates legacy files on read |
| `allowBackup=false` | Done | `withAndroidReleaseHardening` sets manifest flags |
| Cleartext traffic disabled (release) | Done | Plugin sets `usesCleartextTraffic=false`; debug manifests may still allow |
| `debuggable` false in release | Default | Android Gradle release buildType; confirm on EAS APK |
| No debug menus in release | Done | Gallery/`FX_AUDIT` gated to `__DEV__` only; design gallery already `__DEV__` |
| Logs free of tokens/PII | Done | App `console.*` has no tokens; Sentry scrubbed (`telemetry.ts`) |

## Owner / EAS manual checks

1. After next EAS production prebuild, inspect merged `AndroidManifest.xml` for `allowBackup=false`, no `usesCleartextTraffic` on release.
2. Confirm release APK is not debug-signed (`release:check` / `apksigner`).
3. On a device: after sign-in, confirm no `access_token` string in `kv-session.json` under app documents.
4. Unsigned iOS Simulator: SecureStore may fail without entitlements — treat as BLOCKED for sim-only; TestFlight/device builds are the source of truth.
