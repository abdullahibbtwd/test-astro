# CAL 05: `run_calendar.py` (orchestrator)

*Status: **partial**. Stages, outputs and caching are fixed. Calls are wired to real signatures after Phase 0 (the wiring table is in §6).*

## 1. Inputs

| Flag | Meaning |
|---|---|
| `--date --time --location` | birth data (as in the other orchestrators) |
| `--current-location "Istanbul"` | **required for local outputs**; resolves the IANA tz (CAL_00 D1). Default = the birth location, with a warning. |
| `--mode` | `collective` · `events` · `calendar` · `month YYYY-MM` · `day YYYY-MM-DD` · `best-days` · `all` |
| `--from YYYY-MM-DD` | horizon start (default: today in the current tz) |
| `--activity <key>` | restrict `best-days` to one activity (default: all 10) |
| `--dry-run` | everything except model calls; writes the prompts |
| model flags | as in the other orchestrators |

## 2. Stages

```
1 collective     ensure collective_<year>.json exists for every year the horizon touches  (global cache)
2 natal          compute_chart (existing L1)
3 events         personal_events.json (12 months)                                       (CAL_01 §3)
4 scores         day_scores.json + periods.json                                          (CAL_02 §4–5)
5 best_days      best_days.json (90 days)                                                (CAL_04)
6 notifications  notifications.json (from periods, lunations, eclipses, stations, windows) (CAL_02 §6)
7 texts          texts_tr/en.json for the units the requested view needs + prewarm       (CAL_03)
8 views          calendar_<YYYY-MM>.json / day_<date>.json (assembled, see §3)
9 manifest
```

The `mode` decides which stages run: `events` = 1–3, `calendar` = 1–4 + 6 + 8 (and the texts for the first month),
`best-days` = 1–3 + 5 + 7, `all` = everything.

## 3. Assembled views (what the frontend reads)

**`calendar_<YYYY-MM>.json`**, per local day:

```json
{"local_date": "2026-10-10", "tone": "favorable",
 "moon": {"sign": "libra", "phase": "new", "voc_local": [["14:05", "22:40"]]},
 "retrograde": ["mercury"],
 "events": [{"id": "…", "label_tr": "…", "label_en": "…", "importance": "major", "has_text": true}],
 "active_periods": [{"id": "…", "goal": "career", "kind": "favorable"}],
 "goals": {"career": "supportive", "love": "quiet"}}
```

Plus month-level lists: `lunations`, `eclipses`, `retrograde_periods`, `major_transits`, `periods` (those overlapping the month).

**`day_<date>.json`**: the same day entry + `day_note` text + the full texts of that day's major events.

**`best_days.json`**: as CAL_04 §5.

## 4. Caching and refresh

| Artifact | Cache key | Refresh |
|---|---|---|
| collective | year + ephemeris version | built once, reused by everyone |
| personal events, scores, periods | chart_key + tz + horizon start (the month) + corpus/affinity sha | **nightly roll-forward**: append the new last day and drop past days; full rebuild on a tz change or a corpus/affinity change |
| best days | chart_key + tz + date + factor catalogue version | nightly |
| texts | per CAL_03 §1 | lazily, + a nightly 14-day prewarm |

Run folders go in `cal_run/<run_id>/` (the existing run-id scheme); caches go in `cal_run/_cache/<chart_key>/<tz>/`. Everything is gitignored.

## 5. Acceptance

| # | Check |
|---|---|
| O1 | `--mode all` for the 1979-03-30 06:30 Sofia chart with `--current-location Sofia` and then `Istanbul`: both complete; local dates differ where expected; UTC data is identical. |
| O2 | A second run the same day hits the cache for stages 1, 3–6 (the manifest shows `cache_hit`). |
| O3 | `--dry-run` makes zero model calls and writes the prompts. |
| O4 | Every view file references only ids present in `personal_events.json` / collective. |
| O5 | The existing test suite still passes; the `run_predictive.py` change (CAL_00 §6) is covered by its own test. |

## 6. ⏳ Wiring table (fill in from the Phase 0 report before implementing)

| Stage | Call | Real signature |
|---|---|---|
| 2 | `compute_chart(...)` | ⏳ |
| 3 | reuse or extend `compute_forecast` | ⏳ |
| 7 | `llm_client` + the predictive reading helpers (prompt builder, translation, detox, validator) | ⏳ |
| 9 | run-folder + manifest helpers | ⏳ |
