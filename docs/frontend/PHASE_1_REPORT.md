# Phase 1 progress — 30 September 2026

The Android development preview is built, installed, and running on this computer. Core Phase 1 flows are implemented and tested. This is a mock-backed development milestone; the full Phase 1 acceptance gate is **not yet closed**.

## See the app

Double-click **D:\Dev\astrology-app\Open Android Preview.cmd**. The launcher starts the local mock, Metro, and Android emulator. No additional setup is needed on this computer. Keep those processes running while using the preview.

- Existing-account demo: **demo@example.com**, verification code **000000**.
- Fresh-account demo: use the welcome screen option, or **new@example.com**, code **000000**.
- The fresh-account option resets the shared in-memory mock account and profiles. Restarting the mock restores the seed dataset. No email is sent.
- Newly entered birth details reuse existing fixture calculations; this preview does not calculate real charts for arbitrary birth data.
- The current emulator may already be signed in as **Sample**, created while testing onboarding.

## Implemented

- English/Turkish onboarding and interface, light/dark/system themes, bundled fonts and catalogues.
- Email-code preview authentication, session restoration, encrypted local cache, logout and local cleanup.
- Consent, name, native birth-date/time pickers, place search with explicit confirmation, current location, optional gender and notification permission.
- Onboarding draft survives app termination; self profile creation resumes into the generated-reading flow.
- My Charts, self-first ordering, Sun-sign avatars, add/edit/delete other profiles, birth-change confirmation, profile details and chart selection.
- Account settings, privacy/account-deletion controls, legal-link placeholders and saved-report list/filter shell.
- Typed API client, response validation, refresh handling, language-aware query keys, persisted queries, generation-job polling and progress/error states.
- Read-only native chart wheel reusing the canonical renderer without changing its geometry. Future Ahead, Match, Map and Ask screens have explicit placeholders.
- One-click Android launcher and rebuild script; tools, APK and logs are kept on D: outside Google Drive.

## Verification

- `npm run check`: PASS — 59 contract operations, 173 generated schemas, 4,451 validated fixtures, strict TypeScript, lint, **30 Node tests + 3 native component tests**.
- `npm run bundle`: PASS — final Android and iOS JavaScript/Hermes bundles. This is not an iOS native build.
- Android Gradle debug build: PASS; x86_64 development APK installed and exercised on API 36 emulator.
- Native UI smoke checks: email sign-in; session restoration; add/edit/delete profile; explicit place confirmation; Turkish/dark settings; sign-out; fresh-account onboarding; force-stop/reopen draft restoration; Home and chart wheel rendering.
- Canonical W1/W3 wheel byte-parity tests remain passing. Native SVG token resolution has a geometry-preservation test.
- `npm run release:check`: intentionally BLOCKED by draft legal consent and placeholder application identifier.

Local screenshots are in `artifacts/screenshots/`, including `chart-en-light.png`, `charts-tr-dark.png`, and `onboarding-resumed-en.png`. They are ignored by Git because preview screenshots can contain profile data.

## Remaining acceptance work

| Area | Remaining work |
| --- | --- |
| Authentication | Real Google/Apple provider configuration and native sign-in; current provider buttons explain their unavailability. Only mock email authentication is exercised. |
| Production configuration | Final application identifiers, legal consent text, privacy/terms URLs, production API and EAS credentials. |
| iOS | Native build and device verification require macOS/Xcode or configured EAS. |
| Accessibility and performance | Full TalkBack/VoiceOver, large-font checks, complete component gallery, and hardware launch/performance measurements. |
| Reliability | Broader end-to-end background/timeout scenarios, global job-ready notification, screen error boundaries, and configured telemetry vendors. Current telemetry helpers only enforce safe fields. |
| Notifications | Permission/settings and cancellation are wired; candidate scheduling, richer preferences and timezone-mismatch prompts remain. |
| Reports and privacy export | Empty saved-report list/filter is available; report deletion and populated-list acceptance remain. Mock data export explicitly reports its unavailability. |
| Chart | Preview wheel is read-only. TypeScript renderer migration, interaction, reveal animation, remaining parity gates and image exports are later work. |
| Place service | Preview uses limited deterministic fixtures; real global geocoding/GPS matching requires the production service. |

## Local artifacts

- Working source: `D:\Dev\astrology-app\FE`, branch `codex/frontend-specs`.
- APK: `android/app/build/outputs/apk/debug/app-debug.apk` — x86_64 emulator build, not a typical ARM phone package.
- Android/JDK/AVD and logs: `D:\Dev\astrology-app\.tooling`.
- Start: `scripts/Start-Android-Preview.ps1`.
- Rebuild after native changes: `scripts/Build-Android-Preview.ps1`.

The original Drive specs and unrelated Claude outputs remain preserved. No release or remote deployment has been made.
