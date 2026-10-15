# CAL 02: daily scores, supportive/challenging periods, notification candidates

*Deterministic. The same philosophy as ACG_08: corpus-derived affinities × a geometric intensity → scores → bands.
The LLM is never involved in any number here.*

## 1. Life areas

The 11 goals of ACG_08 §1 (the definitions are reused verbatim).

## 2. Goal tags on modern predictive records (`tag_goals_transits.py`)

- Generalise `tag_goals_acg.py` (ACG_07 §5) into a shared tagger with a `--scope` argument. Run it on every
  **modern** predictive record: transits (~785), lunation records, and any retrograde/eclipse records found in the Phase 0 audit.
- Output field: `goal_effects: {goal: supportive|challenging|mixed}`, max 3 goals, per-goal polarity.
  The same validation, caching and idempotence as ACG.
- Guard: ≥ 80% of transit records carry ≥ 1 goal; each goal appears on ≥ 20 transit records. A failure is reported but not blocking.

## 3. Transit affinity table (`build_transit_affinity.py` → `cal_transit_affinity.json`)

The key is `(T, a, N)`: transiting planet, aspect, natal point. **Match the key granularity of the Hand records** (Phase 0
item 2). If records are per aspect *family* (hard = conj/sq/opp, soft = sext/trine), key by family and expand to aspects.

```
s, c, m = Σ citation-weighted supportive / challenging / mixed tags over the matching records   (as in ACG_08 §2)
net = (s' − c') / (s' + c' + 2);   A(T,a,N,g) = net · min(1, (s'+c')/5)      A ∈ [−1, 1]
```

Store `contributors` (record ids) per cell. **Review gate:** Radul reviews `cal_transit_affinity_review.md`
(e.g. Jupiter trine Sun → career/money positive; Saturn square Moon → family/rest negative). If an expectation fails, fix the
tagging, **never** the numbers.

## 4. Daily score

For each local day d (evaluated at **local 12:00** in the user tz), each goal g:

```
intensity_e(d) = max(0, 1 − |sep_e(d) − a_e| / orb_e)                   (transit episodes, CAL_01 §3.1)
m_e            = min(1, I_e / 6)                                       (importance scaling, CAL_01 §3.1)
contrib_e,g(d) = intensity_e(d) · m_e · A(T_e, a_e, N_e, g)
P_g(d) = Σ max(0, contrib)     N_g(d) = Σ max(0, −contrib)     S_g(d) = P_g − N_g
```

Lunations, eclipses and stations **don't add to the scores in v1** (they're events with texts). If the Phase 0 audit finds goal-taggable
modern lunation-in-house records, add them in v1.1 with weight 0.5 on the lunation day ±2 days.

**Bands per day** (initial thresholds in `cal_constants`, calibrated at §7):

| Band | Condition |
|---|---|
| `quiet` | P + N < 0.15 |
| `mixed` | max(P,N) ≥ 0.30 and min(P,N) ≥ 0.5·max(P,N) |
| `strongly_supportive` | S ≥ 0.80 |
| `supportive` | S ≥ 0.30 |
| `strongly_challenging` | S ≤ −0.80 |
| `challenging` | S ≤ −0.30 |
| `quiet` | otherwise |

**Day tone** (for the calendar grid colour): `favorable` if ≥ 2 goals are supportive+ and 0 are challenging−; `challenging` if ≥ 2 goals are
challenging− and 0 are supportive+; `mixed` if both are ≥ 1; `quiet` otherwise.

Output `day_scores.json`: per day `{local_date, tone, goals: {g: {S, P, N, band}}, drivers: {g: [top 3 event ids by |contrib|]}}`.

## 5. Periods

Per goal:
1. Mark days whose band is `supportive`/`strongly_supportive` (favorable) or `challenging`/`strongly_challenging` (challenging).
2. Build runs; **merge runs separated by ≤ 1 day**; keep runs of **≥ 2 days** (a 1-day run is kept only if it contains the exact day of a `major` driver).
3. For each period: `{id, goal, kind: favorable|challenging, start_local, end_local, peak_local, peak_S, strength: strong|normal,
   drivers: [event ids, ranked by summed contribution], importance: major|moderate}`.
   - `strength = strong` if any day is `strongly_*`.
   - `importance = major` if any driver is `major`, else `moderate`.
4. `mixed` days are **not** periods. They show in the day view only.

Output `periods.json`, sorted by start.

## 6. Notification candidates (data only; the frontend schedules and throttles, CAL_00 D4)

`notifications.json`: a list of candidates.

| type | Created when | trigger_local_date | priority (1 high) |
|---|---|---|---|
| `period_start` | period with `importance = major` or `strength = strong` | start − 1 | 1 if major and strong, else 2 |
| `favorable_window` | Best Days window of ≥ 2 days (CAL_04 §5) | window start − 1 | 2 |
| `lunation_in_house` | new or full moon with importance ≥ moderate | the lunation local date | 2 (major) / 3 |
| `eclipse_hit` | eclipse with ≥ 1 hit | eclipse date − 2 | 1 |
| `station_on_point` | CAL_01 §3.3 with importance major | station date − 1 | 1 |
| `retrograde_start` | Mercury retrograde begins (collective) | station date − 1 | 3 |

Candidate shape:

```json
{"id": "n:period_start:career:2026-10-12", "type": "period_start", "trigger_local_date": "2026-10-11",
 "suggested_local_time": "09:00", "priority": 1, "template_id": "period_start_favorable",
 "slots": {"goal": "career"}, "text_tr": "Yarın kariyerin için önemli bir dönem başlıyor.",
 "text_en": "Tomorrow an important period for your career begins.",
 "deep_link": {"view": "period", "ref": "per:career:2026-10-12"}}
```

**Texts come only from `notification_templates.json`** (a fixed, reviewed catalogue with TR/EN strings and slot word forms). There's no LLM here.
Minimum catalogue:

| template_id | TR | EN |
|---|---|---|
| period_start_favorable | Yarın {goal_tr_gen} için önemli bir dönem başlıyor. | Tomorrow an important period for your {goal_en} begins. |
| period_start_challenging | Yarın {goal_tr_gen} açısından daha dikkat isteyen bir dönem başlıyor. | Tomorrow a more demanding period for your {goal_en} begins. |
| favorable_window | Önümüzdeki {n} gün {activity_tr_for} destekleyici. | The next {n} days are supportive for {activity_en}. |
| lunation_in_house_new | Bugünkü yeni ay {area_tr} alanında. | Today's new moon falls in your {area_en} area. |
| lunation_in_house_full | Bugünkü dolunay {area_tr} alanında. | Today's full moon falls in your {area_en} area. |
| eclipse_hit | {n} gün sonra bir tutulma haritandaki önemli bir noktaya denk geliyor. | In {n} days an eclipse touches a key point in your chart. |
| station_on_point | Yarın {planet_tr} haritandaki önemli bir noktada yön değiştiriyor. | Tomorrow {planet_en} changes direction on a key point in your chart. |
| retrograde_start | Yarın Merkür retrosu başlıyor. | Mercury retrograde begins tomorrow. |

Slot word forms are enumerated in the catalogue:
- `goal_tr_gen`, e.g. career → "kariyerin", love → "aşk hayatın", family → "ailen", money → "maddi durumun".
- `activity_tr_for`, e.g. conversation → "önemli konuşmalar için", contract → "sözleşme imzalamak için".
- `area_tr` = the house area names from `PROJECT_OVERVIEW` §3.

Radul approves the catalogue once. Unit tests render every template with every slot value.

## 7. Calibration gate

On 10 real charts × 12 months, report per goal the share of days in each band and the number of periods per month.
Targets: favorable days 10–25%, challenging 10–25%, quiet ≥ 40%; ~1–4 periods per goal per quarter.
Adjust **thresholds only**.

## 8. Acceptance (`test_cal_scoring.py`)

| # | Check |
|---|---|
| S1 | Affinity formula fixture (5 supportive citations → A = 0.714). |
| S2 | Intensity is 1 at an exact, 0 at the orb edge, and linear between. |
| S3 | The band precedence order (mixed before strong). |
| S4 | Periods: merging gaps ≤ 1 day; dropping 1-day runs unless they hold a major exact. |
| S5 | Notification candidates: one per (type, ref); every `text_*` is exactly the rendered template; the trigger dates follow the table. |
| S6 | Determinism: byte-identical outputs; changing only the tz shifts local dates but never UTC-based values. |
