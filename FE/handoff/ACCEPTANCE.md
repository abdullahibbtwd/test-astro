# Verification and delivery acceptance

## Recorded baseline, 6 October 2026

| Check | Result | Evidence |
| --- | --- | --- |
| Frontend Node/API tests | 124 pass, 0 fail, fresh handoff run | Delivery `verification/handoff-node-tests.log` |
| React Native component tests | 57 pass, 18 suites, fresh handoff run | Delivery `verification/handoff-native-tests.log` |
| Clean source + supplied fixtures | 12 API/demo/parity checks and TypeScript pass after Expo route generation; installed dependencies reused | Delivery `verification/clean-copy-smoke.log`, `clean-copy-typecheck.log` |
| TypeScript / ESLint | Pass after latest Home change | Re-run with setup commands |
| Personal Astrologist Python tests | 86 pass in preceding answer-validation fix | `FE/ASK_ANSWER_FIX_REPORT.md` |
| Android guest conversion | Real core generated, Google sign-in, 100% unlock and saved core verified earlier today | `FE/GUEST_ONBOARDING_REPORT.md` |
| Android Ask | Original failed timing question now returns a composed validated response | `FE/ASK_ANSWER_FIX_REPORT.md` |
| Android current city | Compact reminder rendered, Change opens location picker | Delivery `screenshots/home-city-reminder.png` |
| Payments / native iOS | Not implemented / not accepted | Remaining-work backlog |
| Release check | Expected to fail for draft consent and placeholder app ID | `FE/scripts/release-check.ts` |

Screenshots document selected current states. Historical reports contain older counts and do not override this baseline. No paid model tests were required to package this handoff.

## Team's first acceptance pass

- Clone/extract into a fresh nonsynced working folder, restore the fixture ZIP, install dependencies and run the individual checks in SETUP.
- Start the no-cost demo and open each primary tab and its detail screens.
- Start real calculations with paid generation disabled; create a synthetic exact-time chart, inspect facts and switch profiles.
- With a separately approved provider budget and configured auth, test fresh guest generation, cancellation/retry, 40% preview, sign-in claim and no duplicate generation.
- Test welcome/core/reading with small screen, large text, EN/TR and both themes.
- Test Home's small city link, location changes, calendar midnight/timezone changes and cached reading reopening.
- Test relationship context, map parans/heat/selection, chat contextual cards, export/share and saved reports.
- Verify logout/refresh/account switching, offline cache isolation, deletion and interrupted jobs on a disposable account.
- Apply the payment and iOS acceptance rows in REMAINING_WORK before release.

Do not run destructive account tests on the owner's existing preview account. A local app reset does not erase the backend account, and deleting local app data does not prove cloud identity deletion.

## Packaging boundaries

Included: all tracked application/backend source, contracts, tests, specs, runtime design assets, direct Python dependency baseline, example configuration, original design kit, selected screenshots, internal prebuilt demo fixtures and test logs.

Excluded: API keys, Supabase sessions, OAuth tokens, provider/admin credentials, live SQLite account/guest/budget databases, session backup TARs, arbitrary generated personal run folders, node_modules, SDK/JDK installs, native build directories, signing materials and private raw model diagnostics.

The source archive is generated from the handoff Git commit. Update 12 October: the validated fixture ZIP and its checksum manifest are also included in the private branch under `FE/handoff/`; all 5,307 JSON files were checked against the original clean-copy snapshot. The design kit/screenshots remain in the separate private Drive delivery. The manifest supplies SHA-256 hashes. Existing source licences and font licences remain with the code/assets; commercial distribution rights still require the release review listed in R4.
