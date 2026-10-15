> Historical Android acceptance (3 October). Current tests, later fixes and selected shareable evidence are summarized in [the current handoff](FRONTEND_TEAM_HANDOFF.md) and [acceptance guide](handoff/ACCEPTANCE.md). Artifact links below refer to the original private workstation and are not all included in the team package.

# Android connected-backend test results

Completed 3 October 2026, Europe/Sofia. **Main connected flows worked, but this is not an all-clear:** one map-point AI job failed, busy forecast requests produce a misleading connection error, and email-link completion remains unverified.

[Open the screenshot gallery](artifacts/acceptance-2026-10-03/index.html)

Tests ran in the existing Android emulator against the real local API on port 4020, Supabase owner authentication and live Gemini/OpenAI reading pipelines. Fresh requests used fictional profiles. The new `QA test partner` profile was created, edited and deleted solely for these tests. The two original profiles remain unchanged; new successful forecasts/recommendations for the existing fictional self profile remain available.

Some navigation used app deep links to reach known routes, then native taps, scrolling, pickers and share sheets. This was not an exhaustive test of every navigation permutation. Screenshots capture individual viewports, not entire long reports. UI XML is included for supporting evidence.

## Results by guide step

| Step | Result | What was checked | Screenshot |
|---|---|---|---|
| 1. Account identity | PASS | Configured Google email displayed. | [View](artifacts/acceptance-2026-10-03/01-account.png) |
| 2. Birth profile and editing | PASS for exact time | Created fictional QA test partner. Changing 12:00 to 13:00 changed Aries rising to Taurus and invalidated its natal cache. Unknown-time profiles are unsupported. | [View](artifacts/acceptance-2026-10-03/02-edited-profile-result.png) |
| 3. Current location | PASS | Selected Sofia and verified it persisted in Settings. GPS and a different city were not exercised. | [View](artifacts/acceptance-2026-10-03/17-settings.png) |
| 4. Chart calculations | PASS for integration | Wheel, planet degrees, houses and aspects loaded from the backend. No independent astronomical accuracy comparison. | [View](artifacts/acceptance-2026-10-03/04-planet-values.png) |
| 5. Natal reading | PASS, fresh | Generated for the new chart; reopened from cache; contents and section navigation worked. | [View](artifacts/acceptance-2026-10-03/05-section-navigation.png) |
| 6. Daily forecasts | PASS after retry | 3 October and 4 October facts and prose completed. Rapid switching first produced a busy error, described below. | [View](artifacts/acceptance-2026-10-03/06-tomorrow-text.png) |
| 7. Monthly/yearly forecasts | PASS after retry | Fresh General month/year and a Work & career month completed. Alternate focus required retry after another forecast finished. | [View](artifacts/acceptance-2026-10-03/07-professional-complete.png) |
| 8. Calendar | PASS | Month view, day, transit list and Venus retrograde event detail opened. Separate month-navigation variation not exercised. | [View](artifacts/acceptance-2026-10-03/08-calendar-day.png) |
| 9. Best Days | PASS | Ranked activities, Love date calendar and 21 October Good date detail opened. | [View](artifacts/acceptance-2026-10-03/09-best-day-detail.png) |
| 10. Love and Work compatibility | PASS, fresh | Both generated for the original self profile and QA partner; both reopened with correct pair/type and written sections. | [View](artifacts/acceptance-2026-10-03/10-work-text.png) |
| 11. Map lines | PASS | Layers, Legend, List, Sun rising line, nearby cities, sheet and full-screen routes worked. | [View](artifacts/acceptance-2026-10-03/11-line-detail.png) |
| 12. Map goal heat | PASS | Love selection rendered a heat grid over the base map with planetary lines. | [View](artifacts/acceptance-2026-10-03/12-heat-rendered.png) |
| 13. City and selected point reports | PARTIAL / one failed job | Fresh Torshavn city facts and text succeeded. Selected-point facts loaded, but its AI job failed. A similar isolated point diagnostic passed; original failure remains unresolved. | [View](artifacts/acceptance-2026-10-03/13-place-reading.png) |
| 14. Area report | PASS, fresh country | Bulgaria facts, goal bands and written overview completed. Separate regional report not exercised. | [View](artifacts/acceptance-2026-10-03/14-area-reading.png) |
| 15. Recommendations | PASS | World/Overall ranked destinations and explanations completed. A 500 km filter excluding Oceania produced a narrower result set and saved text. Zero-results case was not reached. | [View](artifacts/acceptance-2026-10-03/15-filtered-complete.png) |
| 16. Saved reports | PASS for sampled reports | Reopened natal, compatibility, recommendation and forecast reports with correct context. QA-linked reports were invalidated by the edit and removed with the disposable profile. | [View](artifacts/acceptance-2026-10-03/16-saved-reports.png) |
| 17. Language and exports | PASS | Turkish settings and reading text worked; English restored. Chart PDF (3 pages) and full-report PDF (16 pages) exported; readable cover and text page inspected. Android share sheet opened without sending externally. | [View](artifacts/acceptance-2026-10-03/17-full-report-share-ready.png) |
| 18. Restart, logout and Google sign-in | PASS with preview limitation | Account persisted after cold restart and selecting the local Expo server. Logout and Google re-entry succeeded; profiles remained. | [View](artifacts/acceptance-2026-10-03/18-google-account.png) |
| 19. Email-link sign-in | BLOCKED at inbox completion | One request succeeded. No callback arrived before the 10-minute timeout. Delivery and complete sign-in are unverified; no repeated email was sent. | [View](artifacts/acceptance-2026-10-03/19-email-final-status.png) |
| 20. Data export and deletion | PASS for tested tools | JSON export opened the share sheet. Deleted only QA test partner after testing. Both original profiles remain. Full-account deletion and standalone report deletion were not exercised. | [View](artifacts/acceptance-2026-10-03/20-profile-deleted.png) |

## Issues to address

1. **Map-point reading reliability:** selected-point facts displayed, but job `d79c42cd-0a8e-458d-8a93-b9da6e90e450` failed after about 30 seconds with HTTP 503 / `generation_failed` / “Map reading unavailable.” This was verified from the job store, not a captured error dialog. The public error intentionally omits private engine traces. An isolated live test at 28°N, 49°E with Love focus succeeded (5 text sections, 6 card goals); it is a similar case, not a reproduction at the exact original coordinates. See [diagnostic summary](artifacts/acceptance-2026-10-03/point-diagnostic.json). Do not treat the original failure as fixed.
2. **Busy forecast feedback:** requesting another forecast while one was running produced “We couldn’t complete that. Check your connection and try again.” The backend explicitly returns “Another forecast is being prepared,” but the frontend renders a generic error. Waiting for completion and tapping Try again worked for tomorrow and the Work & career month. [Tomorrow error](artifacts/acceptance-2026-10-03/06-tomorrow.png), [focus error](artifacts/acceptance-2026-10-03/07-focus-professional.png), [successful retry](artifacts/acceptance-2026-10-03/07-professional-complete.png). The practical workaround is to finish one new forecast before switching date/focus.
3. **Email login needs inbox verification:** the request was accepted and the app waited for a link callback; none arrived before timeout. This is not proof that delivery failed. A new supervised attempt is required when the user can open the email promptly.
4. **Known preview limits:** exact birth time is mandatory; unknown-time support is absent. The test guide has been corrected. A cold launch of this development build needs the `127.0.0.1:8082` server selected. Privacy displays “Birth-data consent: Not accepted” for the migrated test account; no consent was given on the user's behalf. Review that state before wider testing.

## Evidence and verification

- Backend/interface tests: **83 passed, 0 failed** — [log](artifacts/acceptance-2026-10-03/automated-tests.log).
- Native tests: **16 passed, 0 failed across 9 suites** — [log](artifacts/acceptance-2026-10-03/native-tests.log).
- PDF text extraction found Turkish characters in both PDFs. The full report has 30,474 extracted characters across 16 pages. Cover and reading page inspected visually; all pages rendered. Poppler emitted Type 3 glyph bounding-box warnings; no defect was observed on the inspected pages. This is not a full visual proof for every page.
- [Chart PDF](artifacts/acceptance-2026-10-03/qa-test-partner-dogum-haritasi.pdf), [full Turkish report PDF](artifacts/acceptance-2026-10-03/qa-test-partner-dogum-haritasi-report.pdf), [cover render](artifacts/acceptance-2026-10-03/17-pdf-render-01.png), [reading-page render](artifacts/acceptance-2026-10-03/17-pdf-reading-render-04.png).
- PNGs and UI XML are stored in this folder. Some early captures show loading/previous screens because navigation had not settled; the curated gallery and table above point to verified results. No screenshot was fabricated.
- Authorization-browser screenshots are excluded. Automatic approval review blocked an OAuth browser capture because it could preserve codes/session material. Safe in-app sign-in screenshots were used; the initial browser PNG was removed.

## Budget and final state

Total durable API ledger: **$1.095768 of the $20 cap**, including earlier work. This session added **$0.661765** from the starting $0.434003. **$18.904232 remains.** All 286 recorded calls are settled and no reading jobs were active at the final check. This is the application's conservative ledger, not a provider invoice.

Live generation remains enabled under the existing cap and pricing-guard deadline. The user is signed back in as radul.shishkov@gmail.com. English is restored. QA test partner and its dependent reports were removed after capturing evidence; the exported PDFs/screenshots remain. No whole-account deletion, original-profile deletion or external file sharing occurred.
