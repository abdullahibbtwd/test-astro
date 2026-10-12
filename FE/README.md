# Astrology mobile app

**Start with [the frontend team handoff](FRONTEND_TEAM_HANDOFF.md)** for current status, setup, priorities and release gaps (6 October 2026).

The Expo/React Native Android preview is connected to the local Python astrology backend. Birth-first guest reading, Google/email account flows, natal chart, forecasts, calendar/Best Days, love/work compatibility, maps/parans and Ask are implemented to the qualification levels recorded in the handoff.

Remaining product work: payment policy/implementation, UI refinement in the current design direction, and native iOS completion. Production hosting/multiuser auth and store acceptance are additional release dependencies.

- [New-developer setup and environment](handoff/SETUP.md)
- [Payments, design, iOS and release backlog](handoff/REMAINING_WORK.md)
- [Verification and acceptance](handoff/ACCEPTANCE.md)
- [Design direction](handoff/DESIGN_DIRECTION.md)

## Existing Windows real preview

```powershell
cd D:\Dev\astrology-app\FE
.\scripts\Start-Android-Preview.ps1 -RealCharts -EnableReadings -EnableAstrologist -RestartApi
```

This workstation-specific command uses the existing private auth configuration, SDK and emulator. Wait for active readings to finish before restarting. The ordinary Open Android Preview launcher opens mock mode.

For a fresh developer checkout, follow SETUP first: `npm ci`, Python dependencies and the private fixture ZIP included at `handoff/frontend-demo-fixtures.zip` are required. Provider keys and the owner's account database are not included. Paid generation needs a separately coordinated budget; the current owner's shared test cap remains $20.

## Core commands

| Command in FE | Purpose |
| --- | --- |
| `npm run mock` | No-cost fixed-data demo, port 4010 |
| `npm run local-api` | Real private backend, port 4020; paid work off unless enabled |
| `npm start` | Metro development-client server |
| `npm run android` / `npm run ios` | Native development build; configured native toolchain required |
| `npm run typecheck` / `npm run lint` | Static checks |
| `npm test` / `npm run test:native` | Backend/logic and native component regressions |
| `npm run bundle` | Android/iOS JS bundle check, not native release validation |
| `npm run release:check` | Known release blockers: draft legal copy and placeholder app ID |

`npm run check` additionally regenerates historical fixtures and needs ignored source run folders. The handoff supplies prebuilt fixtures instead; use the individual checks above. Keep native generated folders, dependencies, live data and credentials out of Git.

Historical BUILD_PROGRESS/HANDOFF_REPORT and phase reports retain their original snapshots. Use the new handoff to resolve conflicting status statements.
