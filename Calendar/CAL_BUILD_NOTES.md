# CAL build notes (status + decisions)

*Updated 2026-09-29. The specs are in `CAL/`, the Phase 0 report is `CAL_EXPLORATION_REPORT.md` (decisions Q1–Q4 are at its top).
Radul delegated every review gate: "you decide" (Q2–Q4), then "fix the 3 problems yourself and continue".*

## Status: all six phases built

| Phase | State | Evidence |
|---|---|---|
| 0 Exploration | ✅ | `CAL_EXPLORATION_REPORT.md` |
| 1 Collective events | ✅ | `collective_events.py`; cache `cal_run/_collective/2026…2031.json`; E1–E4, E6, E7 |
| 2 Personal events | ✅ | `personal_events.py`; E5, E7, E8 |
| 3 Scoring + periods | ✅ gate closed (delegated) | tagging, affinity, day scores, periods, notifications; S1–S6 |
| 4 Texts | ✅ gate: 1 chart × 3 months, 14/14 units validate | `calendar_reading/cr_*`; T1–T5 |
| 5 Best Days | ✅ gate: grades + reasons spot-checked | `best_days.py`, `principles_grounding/best_days_factors.json`; B1–B6 |
| 6 Orchestrator | ✅ O1 run for real: 1979-03-30 06:30 Sofia chart, current location Sofia and Istanbul | `run_calendar.py`; O1–O4 (+ O5 below) |

Tests:
- `python -m pytest Calendar calendar_reading -q`: 38 pass. The runs use dry-run mode, fake geocoders and fake generators, so they make no network or model calls.
- O5: the existing suites still pass:
  - `Forecast_compute` + `prediction_reading`: 27, including the new `test_window_tz_current_location`
  - `principles_grounding/test_forecast_grounding.py`: 15
  - ACG: 189 + 20

Run it:
```
python run_calendar.py --date 1979-03-30 --time 06:30 --location Sofia --current-location Istanbul --mode all
python run_calendar.py ... --mode month 2027-01 | --mode day 2026-11-07 | --mode best-days [--activity contract] | --dry-run
```

## Changes outside the new folders

- `principles_grounding/all_principles_grounded.with_predictive.json`: `fix_angle_transit_about.py` corrected `about.aspect.target` on **21** angle-transit records. The backfill had labelled them Sun, Mercury etc.; they are now Ascendant / MC. Backup: `.bak-pre-angle-fix`. This also fixes predictive readings, which were serving these records for the wrong planet.
- `principles_grounding/tag_goals_acg.py`: the `Tagger` prompt is injectable (default behaviour unchanged).
- `Forecast_compute/compute_forecast.py`: new optional `window_tz=`. The default is the birth tz, so nothing changes when it is omitted.
- `run_predictive.py`: new `--current-location` (CAL_00 §6). It sets the window tz, and the DAY planetary hour uses the current coordinates. The natal chart stays on the birth coordinates.
- `.gitignore`: `cal_run/`.

## Decisions taken under delegation

- **Transit goal tagging** uses `gpt-6-luna`. `gemini-3.7-flash` tagged "relocation" on ~50% of records.
- **Saturn return:** the records exist (`saturn-return-first/second`, `saturn-conjunct-saturn-return`). The CAL index now recognises the `<planet>-return` ids and `general` records whose id names a transit. Missing cells: 5 of 540, all geometrically impossible in a lifetime (e.g. Pluto conjunct natal Pluto).
- **Day-score bands:** 0.04 × the spec thresholds (`CAL_CALIBRATION.md`).
  - Transit affinity is capped at |A| ≤ 0.067 because there is one source book, so the spec thresholds give 100% quiet days.
  - Career and family land inside the targets. The other goals are one-sided because Hand's book is: education and creativity are almost always supportive, rest mostly challenging.
  - The spec forbids tuning numbers per goal. Improving this needs more modern transit sources.
- **Best Days grade thresholds:** excellent ≥ 1.25, good ≥ 0.55, avoid ≤ −0.8 (`CAL_BEST_DAYS_CALIBRATION.md`, version `bd-1.1`). With the C-factors disabled, the spec thresholds leave ~90% of days neutral. Weights are unchanged.
- **Notification catalogue:** approved, `version cal-notif-1`.
- **Text rules added** on top of CAL_03 (CV3 extension):
  - no body parts or medical terms, and no "clumsiness"
  - planet names in Turkish only
  - the "sen" register (formal "siz" is flagged)
  - Turkish aspect words count as jargon next to "açı"

  Cached texts are re-checked against the current rules on every run, so tightening a rule refreshes only the texts that now fail.

## Readable documents (added 2026-09-29 on request)

Every mode also writes Markdown documents in TR and EN (`<name>_<birthdate>.tr.md` / `.en.md`) next to its JSON:

| Mode | Documents |
|---|---|
| collective | `sky_events` |
| events | `year_overview` |
| month | `calendar_<YYYY-MM>` |
| day | `day_<date>` |
| best-days | `best_days` |
| calendar | `calendar_<month>` for every month, `year_overview`, `notifications` |
| all | everything above |

Two related changes:
- **Texts for the whole year:** `calendar`, `all` and `events` now generate texts for the whole 12-month horizon, not just the first month + a 14-day prewarm. This deviates from CAL_03's lazy approach, at the user's request. Texts are cached, so each chart pays once.
- **Notification triggers:** candidates whose trigger date falls before the horizon start are dropped.

## Known simplifications / follow-ups

- **Roll-forward caching:** CAL_05 §4 asks for a nightly roll-forward that appends a day and drops a day. Instead the caches are keyed by the horizon start date and rebuilt in full (~6 s per chart), and a same-day re-run hits the cache (O2).
- **Collective texts:** every collective event text (lunation by sign, eclipse, retrograde, slow ingress) is label-only plus `gaps`. The modern corpus has no grounding for them. They, and the Best Days C1–C8 factors, switch on when a modern lunar-timing / electional source is added (CAL_06 corpus delta).
- **Periods with no constructive angle:** challenging periods whose drivers have no mixed/supportive record for the goal stay label-only (CV4). That is 12 of 55 on the test chart.
- **Stations on natal points:** these have labels but no prose unit, because CAL_03 §1 defines none.
