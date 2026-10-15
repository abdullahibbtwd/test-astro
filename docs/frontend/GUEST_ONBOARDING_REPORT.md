# Birth-first onboarding — implementation and verification

Implemented 6 October 2026 in `D:\Dev\astrology-app\FE`.

## What the user sees

1. ASTROLOGY, the existing gold artwork, and **Let us know where it all starts**.
2. Birth date and exact time in one row; a searchable birthplace below. The selected calendar date uses a compact format so the year stays visible.
3. A short consent checkbox and **Find out who I am**. Missing or invalid birth details cannot submit.
4. An animated emblem while the actual chart is calculated and its core identity reading is generated. Reduced-motion settings stop the rotation.
5. The generated core identity on the next screen, **40% unlocked**, and a pinned **Sign in for more** button.
6. Google or email sign-in. The completed preview transfers into the account; an existing self chart is preserved. If the chart already exists, its saved reading and reading progress take precedence.
7. **100% unlocked** with **What’s ahead**, **Who’s for me**, and **Where to be**. These open the existing Ahead, Match and Map tabs. The percentages describe feature access, not calculation progress.
8. The saved core identity remains available in Chart. A later full natal request reuses that core instead of generating it again.

The EN/TR selector is pinned at the bottom, outside the scroll area. Terms and Privacy use small, borderless text links with accessible tap targets. Google and email remain supported; Apple and OpenAI account login remain outside this change.

## Verification

- TypeScript and ESLint passed.
- Backend/contract suite: **124/124 passed**. Saved output: `artifacts/guest-onboarding/regression-tests.txt`.
- Native component suite: **55/55 passed** across 17 suites.
- Guest API tests cover validation, token isolation, expiration, rate limits, idempotence, authenticated claiming, existing self-chart preservation, matching-chart prose/progress preservation and core reuse after sign-in.
- Android emulator: completed birth input → place search/confirmation → live generation → 40% reading → Google account sign-in → 100% unlock → saved core visible in Chart.
- Actual approved test chart: **28 December 1988, 13:00, Plovdiv**. This created an additional “My chart” test profile; the existing self chart was retained.
- Google sign-in and reopening the saved core made **no further provider calls**. The live guest generation increased the shared ledger by **$0.373361**, to **$3.493167 of the approved $20 cap**.
- Tested EN and TR welcome layouts. Footer and primary form fit the current 1080×2400 emulator without scrolling. Long reading text scrolls while the sign-in button stays visible.
- Backed up the emulator session privately, then reset only app-local data to leave the blank English welcome ready to test. Account/backend data remains intact.

## Screenshots

All captures are local and ignored by Git, under `artifacts/guest-onboarding/`:

| Capture | State |
| --- | --- |
| `01-welcome-final.png` | Blank English first-launch form |
| `02-birth-details.png` | Completed approved fixture input |
| `03-generating.png` | Rotating emblem during real generation |
| `04-core-identity.png` | Actual reading and 40% progress |
| `05-core-reading-scroll.png` | Reading scroll position |
| `06-sign-in.png` | Google/email choices |
| `08-unlocked.png` | Successful Google sign-in and 100% unlock |
| `10-saved-core-chart.png` | Same saved reading in Chart |
| `11-welcome-tr.png` | Turkish first-launch layout |

Session `.tar` backups in this directory are private recovery files, not shareable screenshots.

## API and retention

This extends the existing single-owner local preview, not a public multiuser deployment. The API still binds to `127.0.0.1`; Android reaches it through ADB port forwarding.

- `POST /v1/onboarding/reading`: strict birth input + explicit consent; a client-generated private `X-Guest-Token` identifies one preview. Identical submissions resume it.
- `GET /v1/onboarding/reading?lang=en|tr`: only public status and core text, never model drafts, internal principles, account data or provider usage.
- `DELETE /v1/onboarding/reading`: release an idle preview and its private chart data.
- `POST /v1/me/onboarding/claim`: normal authenticated owner session plus `guest_token`. Claim is serialized with account edits, idempotent for that owner and single-use for guest access.
- Contracts: `contracts/guest-onboarding.ts`. These private preview endpoints are separate from the generated product endpoint inventory, like the existing browser sign-in endpoints.
- Tokens are kept in device SecureStore and hashed in a separate `onboarding-guests.sqlite`. Guest query responses are excluded from the long-term query cache. Preview lifetime is 24 hours; expired idle data and dossier references are collected. Five new attempts per IP per hour and 20 retained previews bound anonymous creation. The existing durable $20 provider cap also applies.
- The approved normal reading pipeline is used. The experimental single-pass ONB comparison pipeline is not enabled.

## Running it later

The current API and Metro are running at ports **4020** and **8082**. For a deliberate restart after active readings finish:

```powershell
cd D:\Dev\astrology-app\FE
.\scripts\Start-Android-Preview.ps1 -RealCharts -EnableReadings -EnableAstrologist -RestartApi
```

The preview script now supplies `ASTRO_GUEST_ONBOARDING=1` for the real backend. Paid calls still require `-EnableReadings` and the existing provider budget authorization. The old root `Open Android Preview.cmd` still opens the mock demo; use the command above for this real onboarding flow.

This work does not declare the broader ONB_02 backend migration or public-store release complete. Live email delivery was not repeated in this walkthrough; its existing tests passed. Apple sign-in remains deferred as agreed.
