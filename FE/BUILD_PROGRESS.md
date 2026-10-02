> **2 October integration update:** Real charts, saved profiles, calendar, Best Days and daily/monthly facts now work in the separate local preview. See [LIVE_INTEGRATION.md](LIVE_INTEGRATION.md) for current status. The approved fresh natal reading passed backend and bilingual schema validation and displays in Android under Fictional AI test; the budget guard records US$0.305641 of the US$20 cap. The earlier snapshot below describes the sample demo.

# Frontend preview — 1 October 2026

Working copy: `D:\Dev\astrology-app\FE`. Open `D:\Dev\astrology-app\Open Android Preview.cmd`.
Sign in with **demo@example.com**, code **000000**. The launcher opens the Android emulator, API and Metro.

## Implemented

- Turkish/English app shell, themes, onboarding, saved birth profiles, account/preferences, secure local storage and report history.
- Home, daily/monthly/yearly forecast views, lenses, profile/date navigation, optional Solar Return screen and capability flags.
- Interactive canonical chart wheel with zoom/pan, body/sign/house/axis/aspect selection, detail sheets, reading links, accessible tables and contents sheet.
- Chart PNG/JPG, vector PDF, full reading PDF, and feed/story share cards with birth details hidden by default.
- Compatibility creation, relationship type selection, report, chart links, sharing/PDF, history and deletion.
- Calendar month/day/item/period/year screens, goal filters, semantic bands, timeline, Best Days and reminders.
- Notification permissions/preferences, quiet hours, rolling caps, deduplication, background/foreground refresh and notification deep links.
- Native map, planet/angle layers, glyph sprites, heat layers, city/area search, line lists, place/area/point report screens, filterable recommendation requests and list/map results.
- Ask threads, six starters, context chips, streaming, Stop/retry recovery, offline/quota states, structured cards, copy/share and feedback.
- Composite job polling, ready notifications, retry handling and completed-report history.

## Useful preview paths

| Flow | Available sample |
|---|---|
| Home / forecasts / calendar | **Person A**. Preview today is 2026-09-29. Daily calendar facts cover the supplied year. |
| Natal reading and exports | **Person B or Person C** → Chart → Read your chart / Export. |
| Compatibility | Person A + Person B → **Love**. Text is from the matching existing synastry run. |
| Map city reports | Person A → search Istanbul, Sofia, İzmir, Berlin, London, Barcelona or Hong Kong. |
| Map area reports | Person A → Turkey, Bulgaria, Germany, United Kingdom or Spain; selected region links. Bands and city rankings are deterministic backend results. |
| Recommendations | Person A → default Overall, or Love, Career, Travel, Permanent Relocation, with the stored world/default filters. |
| Ask | Person A → starters replay clearly labelled saved-data samples/cards. This is not a live AI service. |
| Notifications | Your space → Notifications → enable → Send a test notification. Uses real device time, not the fixed preview date. |

The local basemap uses the project's Natural Earth Turkey-POV geometry. It is a development fallback; release still needs its provider/style configuration and final worldview review.

## Data boundaries (do not confuse these with live calculations)

The contract server is a local preview, built from existing outputs and deterministic scans. New birth inputs reuse sample chart positions. Arbitrary profile/date/lens combinations, unrepresented city/point reports and recommendation filters can return an explicit unavailable state.

The saved monthly prose is a **rolling September 29–October 29** reading, not a calendar-month reading. Monthly screens therefore show exact calendar facts and an absent-reading notice rather than falsely relabelling that prose. The saved yearly reading displays its actual September 29, 2026–September 28, 2027 range. Person A has no matching natal prose fixture. Area summaries have calculated facts but no generated overview prose. Work/family compatibility, Solar Return and element-note success data are not supplied for the preview profiles; optional capabilities stay disabled where appropriate.

Mock account/thread/report state resets with the API process. Sign in again after a server restart. No emails or paid model requests are made.

## Validation and remaining release work

- `npm run check`: 5,302 fixtures validate; 47 Node tests and 9 native component tests pass. Strict TypeScript, ESLint, contract validation, Node and native component tests cover formatting, numeric parity, W1/W3 byte parity, W4 native SVG chord props, exports, notification policy, SSE, idempotency, history and job completion.
- Android and iOS Hermes bundles build; the Android x86_64 development APK builds and is installed. This does **not** establish an iOS native/device pass.
- Android smoke checks include auth, home/chart facts, real streamed preview answer, compatibility creation/read, calendar, native map, place bottom sheet/full screen, PDF/PNG sharing and local notification delivery.
- Generated export checks: 2048×2400 PNG; chart PDF with vector wheel; full 17-page reading PDF with no raster images. Local evidence is in `artifacts/exports` and `artifacts/screenshots` (Git-ignored).
- Native test coverage does not replace a full TalkBack/VoiceOver, physical-device performance, iOS background delivery or store-release audit.

Still required for fully live functionality: production HTTP API/job/SSE adapter over the Python services; live generation and complete forecast data; authentication/email transport and account-export service; Google/Apple app credentials; final legal text and app identifiers; production map styles. No production deployment or store submission has been performed.

The frontend is available for preview testing; the complete live product is **not** represented as finished.
