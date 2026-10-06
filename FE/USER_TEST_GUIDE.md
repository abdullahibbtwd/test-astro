> Historical test-session guide (3 October). The quoted spend is a snapshot, not the current remaining allowance. Use the [current handoff](FRONTEND_TEAM_HANDOFF.md) and [setup guide](handoff/SETUP.md) for fresh team environments and current guest/Ask support.

# Android real-user test guide

Prepared 3 October 2026. Use the open Astrology Android emulator and sign in as **radul.shishkov@gmail.com**. Google and email links both target this configured test account. Apple and OpenAI account login are deferred.

## Ready to test

Live Gemini/OpenAI API generation is enabled for this testing session. Existing backend keys stay on this computer. Reading requests send the relevant chart/relationship/location context to the configured providers. Google sign-in identifies your app account; it does not pay for AI requests.

The combined API budget remains **US$20 total**, including earlier tests. Immediately before your testing, the durable ledger records **$0.434003 spent or reserved**, leaving **$19.565997**. Reservations include calls with unknown outcomes, so this is a conservative local tally, not a provider invoice. Requests that cannot fit their reservation into the remaining budget are refused. The pricing guard blocks further generation after **9 October 2026** until prices are reviewed; no automatic cap increase or expiry bypass is enabled.

Keep this computer, local API, Metro and emulator running with internet access. No deployment or physical phone is required for these tests. Open a reading once and let it finish; opening a new reading/date/focus can start paid generation automatically. Existing identical reports should reopen from cache. Start with one profile, one focus and one result per feature before trying many combinations. Only one forecast can generate at a time. If changing the date or focus shows a generic connection error while another forecast is running, let that job finish, then tap Try again once. A full reading can take several minutes; if it is still pending after 20 minutes, report the failure instead of repeatedly tapping Retry. Changing birth details invalidates related cached results and may require fresh paid generation.

## Test in this order

| Step | Where and what to do | Expected result |
| --- | --- | --- |
| 1. Your identity | Open **Your space** from the top-left account button. | Your Google email appears, not demo@example.com. Existing profiles are still listed under My Charts. |
| 2. Your birth details | **Your space → My Charts**. Open the profile marked **You** and edit it if it still has fictional details. Set your birth date, local birth time and birthplace selected from search. Save. Use Add person for a second profile. | Saved details match your entry; the computed chart changes accordingly. An exact birth time is required by the current form. Unknown-time profiles are not supported in this preview; do not substitute a guessed time. |
| 3. Current location | **Your space → Settings → Current location**. Select where you live now, distinct from birthplace. | The selected city persists and location-dependent forecasts use it. |
| 4. Chart calculations | **Home → your profile → Chart** (or Chart tab with your profile selected). Inspect the wheel, planet positions, houses and aspects. | Facts appear for your actual birth details. Compare a few positions with your already approved calculation output if available. These facts are calculated, not invented by an LLM. |
| 5. Natal reading | **Home → your profile → Reading**. Wait for the full text. Open its sections and contents. | A new reading completes for your profile, with usable section navigation. It should refer to that chart, not the fictional sample. Leave and reopen: the saved reading returns. |
| 6. Daily forecast | **Ahead → Day**, choose your profile and **General**. Read the facts and written forecast, then try tomorrow. | Date, transits and text match the selected day. The new date can require a new AI call. |
| 7. Monthly/yearly forecasts | **Ahead → Month**, then **Year**. Start with General, then test Personal or Professional on one view. | Correct period and focus are shown. Text finishes; changing focus produces the corresponding result. Check links from the yearly view into months. |
| 8. Calendar | **Home → Calendar** or Calendar inside Ahead. Change month and open a day/event. | Real events, dates and details display for the selected profile. Check month navigation and return links. |
| 9. Best Days | **Home → Best Days**. Select an activity/goal and available date range, then open a result. | Ranked dates and supporting facts load. Changing the activity changes the query; an empty result should explain that no matching days were found. |
| 10. Love/work compatibility | Create a second profile under **My Charts → Add person**. Open **Match**, choose two different profiles, select **Love**, then **Create reading**. Repeat once for **Work**. | A report completes for the chosen pair and relationship type. It appears in Match history and Saved reports. Family is intentionally unavailable. Use details you are comfortable submitting to the reading providers. |
| 11. Map lines | **Map**, select your profile, choose **Lines**. Try Layers, Legend and List; open a planetary line and a nearby city. | Lines, line facts and nearby cities load. Switching profiles updates the map. |
| 12. Map goals/heat | In **Map**, choose a goal such as Love or Career. | The heat layer and goal context change. You can still inspect places. |
| 13. Place report | Search for a city on Map and open it. Also test a selected map point via Explore spot when offered. | Location facts load, followed by a written place reading when requested/opened. Check the displayed location and profile. |
| 14. Area report | Open a country/region report through the map's area selection. | The report refers to the selected area, with facts and a written interpretation. |
| 15. Where should I go? | **Map → Where should I go?** Choose a goal, scope and filters, then **Find places**. Start with broad filters. | Ranked destinations appear with explanations. Open a destination. Try one narrower filter; zero matches is a valid result if explained. |
| 16. Saved reports | **Your space → Saved reports**. Open your completed natal, monthly/yearly, compatibility and location/recommendation reports. | Each opens the correct profile, period and focus. Daily readings are reopened through Ahead, not listed as standalone saved reports. |
| 17. Language and sharing | Change English/Turkish in Settings and reopen an existing report. Try the available PDF/share actions. | Labels and report text use the selected language; exported text is readable, including Turkish characters. Review share destinations before sending. |
| 18. Persistence and logout | Close/reopen the app normally. Then sign out from Your space and sign in again with Google. | Profiles and readings remain; logout returns to sign-in. After browser success, switch straight back to Astrology within a minute. |
| 19. Email-link login | After signing out, choose **Continue with email**, enter your configured test email, and request the link. Open it on this computer or in the emulator, then return directly to Astrology. | The same account and saved data appear. Request and use a fresh link while the app's waiting screen is still open. Free email delivery has rate limits; avoid repeated requests. |
| 20. Data tools (optional) | **Your space → Privacy → Download my data**. For deletion tests, use a disposable extra profile/report. | Android sharing opens a JSON export. Delete only an item you intend to lose. Full Delete account clears the local test data; leave that until you are finished and have exported anything needed. It does not currently remove the Supabase identity. |

When testing profile edits, use a disposable additional profile first: change its time, save, then reopen its chart and reading. You should not see stale results for the previous time. Remove that test profile when finished.

## Do not count these as failures

Ask Astrology, Solar Return and family compatibility are not connected in the real preview and remain disabled. Apple/OpenAI login are outside this test scope. The preview base map and local Home screen are not the final store-release presentation. Background notification timing depends on Android scheduling and is not proof of a backend calculation failure.

## If something fails

Send: screen/feature; selected profile label (no need to paste full birth details); date/focus/location; steps you took; expected result; actual message; approximate time; screenshot if useful. Example: “Ahead → Month → Personal, October 2026: facts loaded but reading showed an error after 4 minutes.” Stop repeated retries and let me inspect it. Do not send passwords, API keys or sign-in links.

## Restart or disable live generation

You do not need to run these now; the preview is already being enabled for you. In PowerShell, if restarting later:

```powershell
cd D:\Dev\astrology-app\FE
.\scripts\Start-Android-Preview.ps1 -RealCharts -EnableReadings -RestartApi
```

To disable new paid readings while keeping saved reports available:

```powershell
.\scripts\Start-Android-Preview.ps1 -RealCharts -RestartApi
```

Wait for active readings to finish before restarting. A plain launcher invocation does not replace an already-running API; use RestartApi when changing generation mode. You can also ask me to check remaining budget or disable generation.

Provider pricing reviewed for the existing conservative guard: [OpenAI model rates](https://developers.openai.com/api/docs/models/gpt-6-luna) and [Gemini rates](https://ai.google.dev/gemini-api/docs/pricing). The guard retains the conservative OpenAI input/cache-write rate and existing deadline.
