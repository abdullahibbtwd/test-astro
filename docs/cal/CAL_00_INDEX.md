# Personal calendar and Best Days: spec index

*Spec set v1, 2026-09-28. Client requirements §11 (personal astrological calendar) and §12 (Best Days).
Backend only. Read this file first, then the specs in order.*

## 1. What gets built

| Feature | What the backend delivers |
|---|---|
| **Calendar (§11)** | For the next **12 months**, per user: major transits, new moons, full moons, eclipses, retrograde periods, important personal aspects, and **supportive / challenging periods** per life area, each with short grounded texts. It also returns **notification candidates as data** (§3 D4). |
| **Best Days (§12)** | For the next **90 days**, per user and per activity (10 activities): graded days, top days, days to avoid, and good multi-day windows, each with a short "why". |

## 2. Files

| # | File | Scope |
|---|---|---|
| 0 | `CAL_00_INDEX.md` | decisions, layout, phases, exploration report |
| 1 | `CAL_01_EVENTS_SPEC.md` | collective events engine + personal events engine (deterministic) |
| 2 | `CAL_02_PERIODS_SPEC.md` | transit goal tagging, daily scores per life area, supportive/challenging periods, importance, notification candidates |
| 3 | `CAL_03_TEXTS_SPEC.md` | grounded texts for events and periods: caching, lengths, validator |
| 4 | `CAL_04_BEST_DAYS_SPEC.md` | electional scoring for 10 activities, 90-day horizon, grounding gate per factor |
| 5 | `CAL_05_ORCHESTRATOR_SPEC.md` | `run_calendar.py` modes, caching, refresh rules, outputs (**partial**: wired after Phase 0) |

## 3. Locked decisions (Radul, 2026-09-28)

| # | Decision |
|---|---|
| D1 | **Day boundaries and all local times use the user's _current location_ timezone** (IANA tz from the current city). This replaces the earlier predictive decision "day anchored to the birth-location timezone" for the calendar, Best Days **and** `run_predictive.py`. See §6 for the change to predictive. |
| D2 | Horizons: **calendar 12 months** (rolling), **Best Days 90 days** (rolling). |
| D3 | **Modern only.** No classical/Arabic records anywhere in these features. Only records with `tradition: modern` are eligible. |
| D4 | **Push notifications are the frontend's job.** The backend only returns *notification candidates* as data (trigger date, priority, template id and slots, texts). It does no scheduling, sending, throttling or quiet-hours logic. Suggested frontend defaults: max 1/day, max 3/week. |
| D5 | Best Days activity "Срещи" = **meetings and appointments in general** (not romantic dates; romance is "Love"). |
| D6 | Deterministic-first, LLM-last (the project rule). Events, scores, periods, grades and rankings are computed. The LLM only writes texts, grounded in corpus records, with the existing validator discipline. |
| D7 | **Houses = natal Placidus** (the birth chart), not relocated. The current location affects only the timezone and local times. |
| D8 | Life areas = the **11 goals from ACG_08 §1** (love, career, business, money, family, education, creativity, spirituality, rest, travel, relocation). One taxonomy across the product. |

## 4. Target layout

```
Calendar/
    cal_constants.py            # orbs, weights, thresholds, horizons
    collective_events.py        # CAL_01 §2 (global, per year)
    personal_events.py          # CAL_01 §3 (per user)
    cal_scoring.py              # CAL_02
    best_days.py                # CAL_04
    test_cal_events.py  test_cal_scoring.py  test_best_days.py
calendar_reading/
    cr_sections.py cr_prompts.py cr_generate.py cr_validate.py cr_render.py   # CAL_03
    notification_templates.json                                               # CAL_02 §6
    test_cal_reading.py
principles_grounding/
    tag_goals_transits.py        # CAL_02 §2 (goal tags on modern predictive records)
    best_days_factors.json       # CAL_04 §3 (factor catalogue + grounding ids)
run_calendar.py                  # CAL_05
cal_run/                         # run folders + caches (gitignored)
```

If Phase 0 shows that extending `Forecast_compute/` is cleaner than a parallel `Calendar/` package, propose it in the report. Don't decide silently.

## 5. Phases

| Phase | Deliverable | Gate |
|---|---|---|
| **0: Exploration** | `Calendar/CAL_EXPLORATION_REPORT.md` (§7), no code | Radul reviews it |
| 1: Collective events | CAL_01 §2 | CAL_01 §5 tests (eclipse/station/lunation fixtures) |
| 2: Personal events | CAL_01 §3 | CAL_01 §5 tests |
| 3: Scoring + periods | CAL_02 incl. the tagging pass | Radul reviews the transit affinity table and the calibration |
| 4: Texts | CAL_03 | validator passes on 1 real chart × 3 months |
| 5: Best Days | CAL_04 | factor grounding gate + Radul reviews 90 days × 10 activities for 1 chart |
| 6: Orchestrator | CAL_05 | end-to-end on the 1979-03-30 06:30 Sofia chart, current location Sofia and Istanbul |

## 6. Change to the existing predictive layer

`run_predictive.py`: add an optional `--current-location` (default = the birth location, so existing behaviour is unchanged when it's omitted).
When given, the DAY/MONTH/YEAR windows are anchored to that location's timezone. Add a test showing that a DAY forecast for
Istanbul vs Tokyo covers different UTC windows for the same calendar date.

## 7. Phase 0: exploration report (answer with file:line references and excerpts)

1. `Forecast_compute/compute_forecast.py`: the public signature, the event schema, the orbs used per planet, how
   applying/separating phases and multiple passes (retrograde) are represented, which bodies and aspects are covered,
   and how lunations are computed.
2. How `ground_forecast.py` selects records for a transit event (keys, the `about` type for transit records), with
   3 full example transit records (Saturn square Sun, Jupiter trine Venus, a lunation record if any).
3. **Corpus audit** (counts, tradition = modern only):
   (a) transit records by transiting planet × natal point × aspect;
   (b) lunation records (new/full moon, by house or sign?);
   (c) eclipse records;
   (d) retrograde / station records (Mercury, Venus, Mars…);
   (e) void-of-course Moon records;
   (f) Moon-sign or Moon-phase timing records;
   (g) anything usable for choosing a day for an activity (contracts, travel, purchases…).
   Report gaps explicitly. Best Days factors without grounding stay disabled (CAL_04 §3).
4. `prediction_reading/pr_*`: the section model, prompt builder, validator entry points and forbidden-word list, to reuse in CAL_03.
5. The timezone resolution code (`timezonefinder` usage) and how a "current location" could be passed.
6. Anything in these specs that contradicts the code. Flag it; don't adapt silently.
