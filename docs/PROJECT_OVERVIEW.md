# Astrology App — Project Overview

*State as of 2026-09-29. One page for someone who needs to understand the whole system.*

## 1. What it is

A pipeline that turns birth data into grounded, bilingual (Turkish first, English
second) astrological readings. Its defining rule is the **no-hallucination
contract**: the model may only write claims that trace to a principle in a curated
corpus, and every principle must be verified true of the chart before it reaches
the model. The readings share the same machinery:

| Reading | Entry point | What it produces |
|---|---|---|
| Natal (one chart) | `run.py` | 17-section character reading + ratable statements + scoresheet |
| Synastry (two charts) | `synastry_run.py` | relationship reading (general / personal / professional) + statements |
| Predictive (transits, one chart) | `run_predictive.py` | forecast readings per horizon + English |
| Astrocartography (one chart × places) | `run_acg.py` | map lines + goal heat layers; city / country / region readings with 6 suitability cards; "Where Should I Go?" ranking (spec set `docs/acg/`, notes `Astrocartography/ACG_BUILD_NOTES.md`) |
| Personal calendar + Best Days (one chart, 12 months / 90 days) | `run_calendar.py` | day-by-day calendar (transits, new/full moons, eclipses, retrogrades, void Moon), supportive/challenging periods per life area, push-notification candidates, Best Days for 10 activities, short grounded texts, readable month/day/year documents (spec set `docs/cal/`, notes `Calendar/CAL_BUILD_NOTES.md`) |

Every run writes all artifacts into its own folder under `runs/`, `synastry_run/`,
`prediction_run/`, `acg_run/` or `cal_run/` (gitignored: they hold real birth data).
The calendar also keeps caches in `cal_run/_collective/` (global sky events, shared by
all users) and `cal_run/_cache/<chart_key>/` (per chart, including every generated text).

## 2. Architecture (the layers)

```
birth data ──► L1 chart engine ──► L2/L3 grounding ──► L4 interpretation ──► L5 distiller
              d_layer/            principles_grounding/  Interpretation_layer/   Eval_harness/
              compute_chart.py    ground.py              l4_*.py                 distill.py
```

- **L1 — chart engine** (`d_layer/compute_chart.py`). Swiss Ephemeris. Emits a
  deterministic `chart.json`: 10 planets + lunar nodes with sign, degree, speed,
  house placement in **both Placidus and whole sign**, classical dignities for the
  seven traditional bodies, angles, house cusps, Lots, sect, aspects, and
  `sector_rulers` (per house: sign on cusp, traditional ruler, and — since 2026-09-21
  — the modern co-ruler: Pluto / Uranus / Neptune for Scorpio / Aquarius / Pisces).
  Types in `chart_types.py`, schema in `chart_schema.json`. A Node module
  (`Chart_wheel/`) renders the wheel SVGs.

- **L2/L3 — grounding** (`principles_grounding/ground.py`). Filters the corpus down
  to the principles that are *true of this chart*: domain gate → subject
  reconciliation against chart facts → dependency satisfiability. **House policy:
  Placidus only** (since 2026-09-21): every house claim is verified against the
  Placidus placement whatever house system the source book used. Output:
  `personal_principles.json` (kept records, bundled by chart factor) plus a drop report.

- **L4 — interpretation** (`Interpretation_layer/`). Deterministic routing of kept
  principles into sections (`l4_routing.py`), one model call per section (parallel),
  one Turkish synthesis call per section with the other drafts as context, one
  English translation call per section, a forbidden-word "detox" rewrite when
  needed, then a validator that refuses to ship any contract violation
  (`l4_validate.py`). Prompts in `l4_prompts.py`, section model in `l4_sections.py`,
  readable text in `l4_render.py`. Spec: `L4_INTERPRETATION_SPEC.md`.

- **L5 — eval harness** (`Eval_harness/distill.py`). Distils the English reading
  into atomic, jargon-free statements a stranger could rate true/false, with a
  category and a trace back to sections and principle ids, and writes a scoresheet
  CSV. A human fills the scores; `score_report.py` reads them back. This is the
  project's only quality instrument, and the intended way to compare models,
  prompts and corpus changes.

Synastry has its own grounding (`ground_relationship.py`) and reading layer
(`synastry_reading/s3_*.py`, spec `SYNASTRY_READING_SPEC.md`); predictive has
`Forecast_compute/` for transit computation and `prediction_reading/pr_*.py`.

**Predictive** (`run_predictive.py`, horizons day / month / year):
- `--current-location` anchors the day/month/year window in the user's current tz
  (houses stay natal; `compute_forecast(..., window_tz=)`).
- Since 2026-09-29 every reading also receives a **calendar context**
  (`prediction_reading/pr_calendar.py`): the calendar's major/moderate transits with
  their phase, and the life-area periods (plus the day's life-area picture for DAY),
  sliced per beat, so the reading and the app calendar agree. `--no-calendar` turns it off.
- `ground_forecast.py` matches transit records **directed** (transiting → natal) and
  **modern only** (fixed 2026-09-29 in a separate session).

**Calendar + Best Days** (`Calendar/` engines, `calendar_reading/` texts, `run_calendar.py`):
deterministic first, LLM last.
- `collective_events.py`: global sky events per year.
- `personal_events.py`: transit *episodes* with orb windows and retrograde passes
  merged, lunations/eclipses by natal house, stations on natal points.
- `cal_scoring.py`: daily scores for the 11 ACG life areas, from a transit × goal
  affinity table built from LLM goal tags on the Hand records; supportive/challenging
  periods; notification candidates from a fixed TR/EN template catalogue.
- `best_days.py`: 12 electional factors, each enabled only if grounded in modern
  records; today the 4 personal ones are on and the 8 Moon-timing ones are off.
- Texts: `cr_*`, with a validator (trace, no numbers, no jargon, no event
  prediction, no body parts, Turkish planet names, "sen" register). They are cached
  and re-checked against the current rules on every run.
- Day boundaries use the **current-location** tz. Houses are natal Placidus.

## 3. The natal reading (current section model)

**Basis: modern astrology.** Placidus houses only; all ten planets are full
participants (Uranus, Neptune, Pluto included); rulership names the traditional
ruler and the modern co-ruler. Whole-sign "classical texture" is gone; only
dignities and lord-of-house material still read as classical colour.

**Part one — who you are:** `core_identity` (Sun, Moon by sign, Ascendant, chart
ruler(s)), `sun_house` and `moon_house` (short notes on the luminary's house),
`inner_drives` (Mercury, Venus, Mars), `chart_shape` (aggregate + Jupiter, Saturn,
Uranus, Neptune, Pluto, nodes by sign and house).

**Part two — one section per house**, with these reader-facing names:

| H | key | EN | TR |
|---|---|---|---|
| 1 | identity | Identity | Kimlik |
| 2 | values_money | Values and Money | Değerler ve Para |
| 3 | communication_learning | Communication, Studying, Siblings | İletişim, Öğrenim ve Kardeşler |
| 4 | family_home | Family and Home | Aile ve Yuva |
| 5 | joy_creativity_children | Joy, Artistic Talents and Kids | Neşe, Sanatsal Yetenekler ve Çocuklar |
| 6 | health_routine_pets | Health, Routine, Pets | Sağlık, Rutin ve Evcil Hayvanlar |
| 7 | partnerships | Partnerships | Ortaklıklar |
| 8 | transformation_intimacy | Transformation and Intimacy | Dönüşüm ve Yakınlık |
| 9 | travel_philosophy | Distant Travels and Philosophy | Uzak Seyahatler ve Felsefe |
| 10 | status_vocation | Social Status and Vocation | Toplumsal Statü ve Meslek |
| 11 | friendships_future | Friendships and the Future | Arkadaşlıklar ve Gelecek |
| 12 | subconscious_solitude | Subconscious and Solitary | Bilinçaltı ve Yalnızlık |

Each house section covers the house's meaning, every planet placed in it, and the
cusp sign with its ruler(s). Empty sections are omitted, never emitted blank.

## 4. The corpus

`principles_grounding/all_principles.grounded.json` — **2,770 records** (mirrored to
`Interpretation_layer/`, checksum sidecar `.sha256`). Each record: id, domain,
tags, rule, conditions, judgment, tradition, plus the grounding blocks `about`
(typed subject: planet_in_sign, planet_in_house, dignity, house_domain, general, …)
and `requires`. Sources so far:

- a traditional Arabic/medieval corpus (whole-sign, natal/horary/mundane/electional);
- Arroyo's *Chart Interpretation Handbook* (modern natal: planets in signs, house
  meanings, elements, aspects methodology);
- Hand's *Planets in Transit* (785 predictive records; the predictive superset holds it
  twice, see "Predictive corpus" below);
- **the planets-in-houses delta (2026-09-21): 617 modern natal records**, 10 planets ×
  12 houses × 5–6 principles each, extracted from `TXT/Planets_in_houses.txt`.

Adding a source follows `principles_grounding/CORPUS_DELTA_HOWTO.md`:
`extract_houses.py` (pattern) → `merge_houses_delta.py` → `finish_delta.py`.
Extractors must force the id / conditions / tags shape so `backfill.py` classifies
records deterministically. Source texts live in `TXT/` (gitignored, copyright-sensitive);
the extraction prompt captures technique and meaning only, never wording.

**Known gaps:** rising-sign delineations (0 records), modern aspect delineations (0),
modern outer planets by sign (0, generational by design), and the source book's
Sun-house × Moon-house "Polarities" (needs a compound factor type).

**Predictive corpus** (`all_principles_grounded.with_predictive.json`, 3,880 records;
read by the predictive layer and the calendar). What the 2026-09-28 audit found
(`Calendar/CAL_EXPLORATION_REPORT.md`):
- The 1,589 modern predictive records are **two extractions of Hand's *Planets in
  Transit***. One is structured (`about.factor_type = aspect`); the other is mostly
  `unclassified` but parseable from its ids.
- The calendar reads both through its own index (`Calendar/cal_corpus.py`) and
  counts the book once per cell. Coverage is 535 of 540 transit cells; the 5 missing
  are impossible in a lifetime. Transits to ASC/MC and the Saturn return are included.
- 21 angle-transit records had a wrong `about.aspect.target` (Sun etc. instead of
  Ascendant/MC). They were corrected in place on 2026-09-29
  (`principles_grounding/fix_angle_transit_about.py`, backup `.bak-pre-angle-fix`).
- Goal tags for the transit records live in a sidecar,
  `principles_grounding/transit_goal_tags.json` (`tag_goals_transits.py`, GPT-6 Luna),
  not in the corpus.
- **Modern predictive gaps:**
  - 0 records for void-of-course Moon, retrograde periods, lunations by house or
    sign, eclipses by sign/kind, and electional timing (2 generic records).
  - So the calendar's collective event texts are label-only, and the Best Days
    Moon-timing factors are disabled.
  - A modern lunar-timing / electional source (planned CAL_06 corpus delta) would
    enable both.

## 5. Models and providers

All model calls go through `llm_client.py` at the repo root. The provider is chosen
from the model id: `claude-*` → Anthropic, `gemini-*` → Google, `gpt-*` → OpenAI
(or force with `anthropic:` / `gemini:` / `openai:`). Keys come from environment
variables or a file in the user's home directory (`~/.gemini_key`, `~/.openai_key`,
`~/.anthropic_key`) — never from the Drive-synced repo.

| Stage | Natal | Synastry | Predictive | Calendar |
|---|---|---|---|---|
| Turkish drafts and synthesis | Gemini 3.7 Flash | Gemini 3.7 Flash | Gemini 3.7 Flash | Gemini 3.7 Flash (per-event texts, cached) |
| English translation | GPT-6 Luna, falls back to Flash | GPT-6 Luna, falls back to Flash | GPT-6 Luna, falls back to Flash | GPT-6 Luna (+ detox rewrites) |
| Statements / distiller | GPT-6 Luna, falls back to Flash | GPT-6 Luna, falls back to Flash | — | — |

Corpus goal tagging (ACG and transits) uses GPT-6 Luna: in a trial, Gemini Flash
over-tagged "relocation". The calendar computes everything else without a model. A
first `--mode all` for a new chart writes about 100 texts (a few cents); repeat runs
reuse the cache.

Defaults: `llm_client.DEFAULT_MODEL = gemini-3.7-flash`, `DEFAULT_CHEAP_MODEL =
gpt-6-luna`. Gemini thinking level defaults to **low** (`GEMINI_THINKING_LEVEL`);
OpenAI reasoning effort defaults to low. Flags on every orchestrator: `--model`,
`--synthesis-model`, `--translation-model`, plus `--distill-model` (natal) or
`--statements-model` (synastry); `same` binds a stage to the synthesis model.

Operational behaviour: Gemini 429s honour Google's retry delay with exponential
fallback; OpenAI "no credits" is recognised as non-retryable and triggers the
fallback instead of retries; Gemini concurrency is capped at 8.

Reference costs (Sept 2026): Flash $0.75 / $3.75 per 1M tokens (doubles 1 Jan 2027);
Luna $0.10 / $0.50; Sonnet 5 $2 / $10 rising to $3 / $15. A natal reading costs about
$0.50 on the current split; a corpus extraction of a 1 MB book about $1.

## 6. How to run

```bash
python run.py                      # natal: prompts for date, time, place
python synastry_run.py             # synastry: two births + reading type
python run_predictive.py           # predictive: birth + horizon; --dry-run skips model calls
python run_acg.py                  # astrocartography: map / --city / --country / --recommend GOAL
python -m pytest -q Interpretation_layer/test_l4.py synastry_reading/test_s3.py \
    prediction_reading/test_forecast_reading.py principles_grounding/test_ground_house_policy.py \
    test_llm_client.py             # 107 tests, all passing
python -m pytest -q Calendar calendar_reading prediction_reading Forecast_compute/test_forecast.py \
    principles_grounding/test_forecast_grounding.py   # calendar + predictive: 85 tests, all passing
```

Predictive and calendar runs:

```bash
python run_predictive.py --date 1979-03-30 --time 06:30 --location Sofia \
    --horizons day,month,year --target today [--current-location Istanbul] [--no-calendar]
python run_calendar.py --date 1979-03-30 --time 06:30 --location Sofia \
    --current-location Istanbul --mode all      # or: collective | events | calendar |
                                                #     month 2026-10 | day 2026-10-10 |
                                                #     best-days [--activity contract]; --dry-run = no model
```

Every calendar mode writes readable `.tr.md` / `.en.md` documents next to its JSON:

| Mode | Documents |
|---|---|
| collective | `sky_events` |
| events | `year_overview` |
| month | `calendar_<YYYY-MM>` |
| day | `day_<date>` |
| best-days | `best_days` |
| calendar / all | all of the above, plus `notifications` |

Pre-existing test failures to ignore: the circumpolar fixture in
`d_layer/test_chart_schema.py` (Placidus undefined above the polar circle) and 13
tests in `principles_grounding/test_grounding.py` (stale fixture path).

## 7. Timeline of this build

- **Initial commits** — natal pipeline L1–L5, synastry pipeline, orchestrators, Sonnet 5 as the model.
- **2026-09-21** — provider-agnostic `llm_client.py`; Gemini 3.7 Flash becomes the default; rate-limit handling. Reading moved to modern astrology: Placidus-only grounding, modern co-rulers, outer planets as full planets, Sun/Moon house notes, twelve house sections. Planets-in-houses corpus delta (+617 records).
- **2026-09-24** — OpenAI provider; GPT-6 Luna for translation, detox, distiller and synastry statements, with automatic fallback; synastry synthesis split into Turkish synthesis + translation pass (matching natal); Gemini thinking set to low.
- **2026-09-25 → 28** — Astrocartography layer (`docs/acg/` specs, `run_acg.py`), incl. parans and destinations (v4).
- **2026-09-28 → 29** — Personal calendar + Best Days (`docs/cal/` specs 00–05), all six phases:
  - collective and personal event engines
  - transit goal tagging and affinity table
  - day scores, periods and notifications
  - grounded texts
  - Best Days
  - `run_calendar.py`
  - readable documents for every mode

  Alongside: the angle-target corpus fix, directed + modern-only predictive grounding,
  `--current-location` for predictive, and the calendar context in the day/month/year
  predictive readings. Radul delegated the review gates; the decisions are recorded in
  `Calendar/CAL_BUILD_NOTES.md`.

## 8. Open questions and next steps

1. **Quality baseline.** No scoresheet has yet been filled for a Flash reading. Score one
   natal run, then compare Flash against Sonnet 5 on synthesis (`--synthesis-model
   claude-sonnet-5`) and low against medium thinking (`GEMINI_THINKING_LEVEL=medium`).
2. **Corpus gaps** listed in §4; rising signs are the most visible missing piece.
3. **Sun-house × Moon-house polarities** from the planets-in-houses source would enrich
   the luminary notes but need a compound factor type in the grounding schema.
4. **Predictive corpus state.** The forecast pipeline reads
   `all_principles_grounded.with_predictive.json`, a superset that still contains a
   predictive delta whose build-gate run was rejected. It also holds Hand's book twice
   (§4). Deduplicating it, or backfilling `about` on the unclassified copy, would
   improve predictive grounding.
5. **Modern lunar-timing / electional source (CAL_06).** The one missing corpus piece
   for the calendar. It would enable:
   - texts for new/full moons, eclipses, retrogrades and ingresses
   - the Best Days Moon-timing factors (void Moon, Mercury retrograde, waxing Moon…)
   - their hard "avoid" gates
6. **Calendar calibration.** Transit affinities are small by construction (one source
   book), so the day-score bands run at 0.04 × the spec thresholds. Only career and
   family land fully in the target band shares; education/creativity read almost
   always supportive and rest mostly challenging, as Hand describes them. More
   modern transit sources would balance this. Best Days thresholds are calibrated
   (`bd-1.1`).
7. **Calendar caching.** CAL_05 asks for a nightly roll-forward; today caches are keyed
   by the start date and rebuilt in full (about 6 s per chart).
8. **Repo hygiene.** Large working-tree changes are uncommitted (incl. `Calendar/`,
   `calendar_reading/`, `run_calendar.py`); a stale `.git/packed-refs.lock` may need
   deleting before the next commit.
