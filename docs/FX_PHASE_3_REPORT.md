# Phase 3 — copy, formatting and accessibility

Implementation checkpoint. User explicitly waived further phase approval pauses; continuing directly to Phase 4.

## Changes

- FX3.1: UTC calendar-date formatters (month/day/short/compact ranges), applied to Calendar, Best Days, Day, Year, item details, export details, compatibility and Ask history. English/Turkish fixture tests reject raw ISO date text.
- FX3.2: Generated 239-country English/Turkish lookup from the existing worldview fixture; screen-reader-hidden flags; country names in place and line reports and recommendations; descriptive city-size labels.
- FX3.3: Local compatibility Saved titles use chrome labels, not model capitals; screen heading uses the two people. Place Saved titles include city and country. Model prose is unchanged.
- FX3.4–5: Shared shaped BandChip in scores, place/area/recommendation cards and day grades; no separate chip for no-emphasis place cards, preventing duplicate wording.
- FX3.6: Localized month pager, mixed/quiet days unringed, today bold with dot, selected date filled, rating/event legend, accessible dates and event names; Best Days legend and avoid dashed outline.
- FX3.7: Line skeletons for pending text, two lines in place cards; no shimmer.
- FX3.8: Radio/checkbox checked states, action chips use button role, named report rows, flags hidden from speech, unrestricted body text scaling, tab labels capped at 1.3, chat announces completed text once. Large-text pager can wrap.
- FX3.9: Formatted Best Day date, grade chip, primary reminder and Calendar action; empty reason sections omitted. Inspection confirmed the real engine emits label_en/label_tr reasons and calendarFixtures already maps them; no fabricated explanations or Python changes.
- FX3.10: Living/travel and city-size copy, reading-save caption under inline reading, retrograde bodies shown as one line.

## Validation

- 94 API/logic tests: full run had 92 passing plus two obsolete model-title expectations; both affected report suites passed after updating expectations to the required chrome titles.
- 46 native tests passed in 15 suites; typecheck and lint passed. New tests cover English/Turkish Calendar, Best Days, Best Day, Day/Month/Year content, accessible interactive names, calendar ring semantics, country labels, empty reasons, date compaction and country fallback.
- Android screenshots in frontend/artifacts/fx-phase-3 (Calendar, Best Days, Best Day, Today/place/Chart at 200% text). Phase 2 screenshots supply before views. The emulator was restored to normal font scale after checks.
- TalkBack was enabled briefly and restored. Only visual/accessibility-tree inspection was possible; a complete spoken TalkBack audit, iOS VoiceOver and every-screen maximum-font pass are NOT claimed as complete. Cold-start deep links sometimes returned Home during capture; these diagnostic captures are not used as evidence of a place screen.
- No live model generation. Ledger before/after: 302 calls, 1,217,258 microdollars ($1.217258), unchanged.

## Turkish review

Review these new/changed chrome keys: `favorable`, `challenging`, `big`, `mid`, `small`, `seeInCalendar`, `livingTravel`, `largeCities`, `unknownCountry`, `newMoon`, `fullMoon`, `eclipse`, `station`, `excellent`, `good`, `avoid`. Generated country names inherit the existing bilingual source fixture.

## Remaining verification / found, not fixed

- Full spoken accessibility audit and iOS runtime checks need those test environments. Tests and Android checks do not substitute for speech review.
- Existing model prose is preserved verbatim even if its own text contains dates or capitals. Chrome formatting is covered separately.
- Precise timeline geometry and large list performance continue in Phase 4.
- No backend reason gap was found: dates without contributing reasons legitimately omit those sections.

## Final follow-up in Phase 4

The complete suite now passes: 98 API/logic tests and 47 native tests. The Best Days activity grid received a regression fix for its internal month value and a test that requires actual date buttons. Activity rows now show the next-day grade, recommendation city sizes use neutral chips, and calendar legends display matching ring samples. Updated Android evidence is in the Phase 4 gallery. Spoken/iOS accessibility limitations above remain unchanged.
