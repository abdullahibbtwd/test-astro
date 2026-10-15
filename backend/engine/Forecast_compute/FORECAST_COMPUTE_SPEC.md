# FORECAST_COMPUTE_SPEC.md

Build spec for `compute_forecast.py` — the deterministic event engine of the predictive
layer. This is the analogue of `compute_chart.py`: fully deterministic, no LLM, typed and
schema-validated. It converts (natal chart + target date + horizon) into a **dated event
list**. Everything the corpus cannot supply — phase, cycle-stage, horizon filtering,
day boundaries — is enforced here at compute time.

Downstream, forecast grounding matches these events to predictive principles, and the
reading layer renders them per profile. Neither of those is in this spec.

---

## 0. Core principle

Deterministic-first, LLM-last — same as every other compute layer. `compute_forecast.py`
emits a structured, reproducible event object. Same inputs → byte-identical output. No
randomness, no network, no model calls.

It is an **event engine, not a snapshot**. Natal compute answers "what is the chart." This
answers "what happens across a window, and when." The unit of output is a dated event, not
a static position table.

---

## 1. Inputs and outputs

**Inputs:**
- `natal`: the natal chart object produced by `compute_chart.py` (reused as-is — do not
  recompute natal positions here; take the chart object).
- `target_date`: date the horizon starts on. Default "today" resolved in the **birth
  location's** timezone (see §3).
- `horizon`: one of `day | month | year`. (Week is dropped — do not implement it.)

**NOT an input:** `profile` (general/personal/professional). Profile is a **read-time
lens**, applied after grounding. Compute is profile-agnostic and emits the full event set;
the reading layer selects emphasis. Do not filter events by profile here.

**Output:** a `forecast` object (§11), written to a run folder (§12). Deterministic.

---

## 2. Reuse from `compute_chart.py` — do not reimplement

Import and reuse, do not fork:
- Swiss Ephemeris access (`pyswisseph`) and the position/speed helpers.
- Dignity logic (for dignity-modulation of event valence).
- House computation — **both** Placidus (domain routing) and Whole Sign (classical
  texture), same dual-system stance as natal.
- Sect, and the day/hour ruler computation.
- Timezone resolution via `timezonefinder` (used for the day-boundary anchor).

New code is only the time-windowed event detection below.

---

## 3. Time window construction

**Day-boundary anchor = birth location timezone.** Resolve the birth location's tz from its
coordinates (same path `compute_chart` uses). All horizon windows and all "which calendar
day" decisions use this tz, regardless of where the user currently is. This keeps forecasts
deterministic and independent of request origin.

Window from (`target_date`, `horizon`), all in birth-location local time:
- `day`   → `[target 00:00, target 24:00)` (one local day).
- `month` → `[target 00:00, target + 1 calendar month)`.
- `year`  → `[target 00:00, target + 1 calendar year)`.

Record `window.start`, `window.end`, and `window.tz` in output.

---

## 4. Event families

Detect these families. Each detected event is one object in the output list (§11), carrying
its own dated timestamp(s), the bodies involved, and a **grounding signature** (§9).

### 4a. Transit-to-natal aspects
A transiting body forming a Ptolemaic aspect (conjunction 0°, sextile 60°, square 90°,
trine 120°, opposition 180°) to a natal point.
- **Transiting bodies:** the 10 (seven classical + Sun/Moon already in the seven… i.e. Sun,
  Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto).
- **Natal targets:** the 10 natal bodies + the four angles (ASC, MC, DSC, IC). Lots
  (Fortune/Spirit) as targets are **deferred** — leave a stubbed extension point, off by
  default.
- **Minor aspects out of scope** for v1.
- Primary detection is **perfection-based**: the datetime the aspect goes exact within the
  window. A slow retrograde body may perfect the same aspect up to three times — emit each
  perfection separately, dated.
- Also emit aspects **in orb at window start** but perfecting outside the window (standing
  background), with phase `applying`/`separating` — these matter for month/year framing.
  Orb table in §7.

### 4b. Ingresses
- **Sign ingress:** transiting body crosses into a new zodiac sign (dated).
- **House ingress:** transiting body crosses into a new natal house (dated). Compute against
  **both** house systems; the Placidus house drives domain routing, the whole-sign house is
  classical texture (record both house numbers).
- House ingresses require birth time — see §8 precision fallback.

### 4c. Lunations and eclipses
- New Moon and Full Moon within the window (dated).
- Tag each with the natal house it falls in (both systems) and any aspect it makes to a
  natal point.
- **Eclipses** are lunations flagged as eclipse (solar = New-Moon eclipse, lunar =
  Full-Moon eclipse); detect via the ephemeris eclipse functions. Eclipses are the year
  horizon's backbone — always emit when in window.

### 4d. Profections — OPTIONAL MODULE, stubbed off by default
Annual / monthly / daily profection (whole-sign ascendant advancing 1 sign per period),
emitting the activated house + its ruler ("lord of period") as a focus event. Gate behind a
config flag `enable_profections=False`. Do not wire into the default path. This stays off
pending the corpus-coverage decision; ship the interface so it can be switched on later
without touching the rest of the engine.

---

## 5. Phase and cycle-stage — computed here, not sourced from corpus

The corpus does not reliably carry applying/separating, so compute assigns it.

**Phase** (every aspect event): `applying` (transiting body moving toward exact),
`separating` (moving away), or `perfecting` (exact within window — also carry the exact
datetime). Derive from the transiting body's speed vector relative to the natal point.

**Cycle-stage** (every transit-to-natal aspect): map the signed angular separation onto the
8-stage synodic model the corpus encodes (`transit-cycle-stage-*` records):
1 conjunction (0°) · 2 separating sextile (60°) · 3 separating square (90°) · 4 separating
trine (120°) · 5 opposition (180°) · 6 approaching trine (240°/waning 120°) · 7 approaching
square (270°/waning 90°) · 8 approaching sextile (300°/waning 60°). Compute the stage from
the current separation and waxing/waning direction, and snap aspect events to the nearest
stage. This label is what lets grounding attach the cycle-stage principles.

---

## 6. Horizon inversion filter (the key rule)

Filtering **inverts across the range** — fast bodies matter at short horizons, slow bodies
at long ones. Implement as a per-horizon inclusion filter, NOT one shared orb/threshold.

| | DAY | MONTH | YEAR |
|---|---|---|---|
| Moon events | **yes** (spine) | yes (texture) | **excluded — noise** |
| Fast bodies (Mer/Ven/Sun/Mars) | perfections in-window | perfections + ingresses | excluded except Sun ingress/eclipse |
| Slow bodies (Jup/Sat/Ura/Nep/Plu) | only if perfecting that day | perfections in-orb, dated | **yes — spine** |
| Ingresses | Moon/fast into house | fast + Sun sign/house | slow-body sign/house |
| Lunations | the day's Moon phase if any | both lunations | eclipses only (ordinary lunations demoted) |
| Day/hour ruler | **yes** (target date) | no | no |
| Phase policy | **applying/perfecting only** — no separating events | applying/perfecting/separating | applying/perfecting/separating |

Hard invariants that fall out of this table are enumerated in §13.

---

## 7. Orbs and perfection detection

- **Perfection events** are unambiguous (exact aspect datetime) — no orb needed; these are
  the primary list.
- **Standing in-orb** detection (for month/year background aspects active at window start)
  uses this default orb table (degrees, tunable — this is an astrology-domain default):
  luminaries (Sun/Moon) 1.5°, all other bodies 1.0°, applying and separating symmetric.
- Do not widen orbs by horizon. Horizon is handled by the §6 body filter and by which
  perfections fall in-window, not by orb inflation.

---

## 8. Birth-time precision fallback (stub the branch now)

House-dependent events (house ingresses, lunation-in-house, angle contacts, profections)
require an accurate birth time. Carry a `precision_tier` from the natal chart. When the tier
is low/unknown:
- **Suppress or flag** house-based and angle-based events; keep planet-to-planet aspects and
  sign ingresses (these don't need houses).
- Emit a `degraded: true` marker on the forecast and a `suppressed_families` list so the
  reading layer can soften language ("timing approximate").
Implement the branch as a clean extension point; full graceful-degradation logic is a
follow-up, but the branch and markers ship now.

---

## 9. Grounding signature per event (so runtime matching stays deterministic)

Each event carries a structured `grounding` block whose keys map to the corpus
`requires.kind` vocabulary already in the grounded records, so the forecast-grounding step
can match by structure before falling back to embeddings:
- transit aspect → `{ kind: "point_aspects", transiting_point, natal_point, aspect, phase, cycle_stage }`
- house ingress / lunation-in-house → `{ kind: "point_house", point, house_placidus, house_wholesign }`
- angle contact → `{ kind: "ascendant" | "midheaven", ... }`
- dignity-modulated tone → include the transiting/natal dignity so `point_dignity` records can attach
- sign ingress → `{ kind: "sign_element", point, sign, element }`
Events with no clean structured key still emit `{ kind: "other" }` plus rich `topic_tags`
for the embedding path. (Recall ~70% of predictive records are `requires: other`, so the
embedding path is load-bearing — populate `topic_tags` generously.)

---

## 10. Segmentation hints

To serve the reading structures (month = beginning/middle/end; year = 4 quarter beats), tag
each event with a `segment`:
- month → `early | mid | late` (thirds of the window),
- year → `q1 | q2 | q3 | q4`,
- day → `null`.
This is a convenience for the reading layer; it does not change event content.

---

## 11. Output schema and typing

Emit a `forecast` object, typed via `forecast_types.py` and validated against
`forecast_schema.json` (JSON Schema Draft 2020-12), mirroring `chart_types.py` /
`chart_schema.json`. Shape:

```
forecast:
  meta:
    natal_ref            # id/hash of the natal chart used
    target_date
    horizon              # day | month | year
    generated_at
    run_id               # YYYYMMDD-HHMMSS_<3char>
    precision_tier
    degraded             # bool
    suppressed_families  # [] unless degraded
  window: { start, end, tz }
  events: [ Event ]      # dated, ordered by datetime
  counts: { by_family, by_segment }   # for eval + sanity

Event:
  event_id
  family               # transit_aspect | ingress_sign | ingress_house | lunation | eclipse | profection
  datetime             # perfection/exact datetime (birth-loc tz); or window-start for standing
  standing             # bool (in-orb-at-start vs perfecting-in-window)
  bodies: { transiting, natal }        # natal null for pure sky events
  aspect               # conj|sext|square|trine|opp|null
  phase                # applying|separating|perfecting|null
  cycle_stage          # 1..8 | null
  speed_class          # fast | slow | null
  house_placidus       # int | null   (domain routing)
  house_wholesign      # int | null   (classical texture)
  sign
  dignity              # modulation inputs
  segment              # early|mid|late | q1..q4 | null
  grounding            # the §9 block
```

Naming conventions must match the existing chart object where fields overlap (`points`,
`house_*`, dignity fields) — confirm against `chart_schema.json` and reuse, don't invent
parallel names.

---

## 12. Persistence

Forecasts are **saved as data**, not ephemeral. Write the forecast object into a run folder
using the existing scheme `YYYYMMDD-HHMMSS_<3char>`, same as natal/synastry runs. Every
generated forecast is retained.

---

## 13. Invariants (enumerate as tests; all must pass on fixtures)

1. Every event `datetime` (or standing window-start) lies within `[window.start, window.end)`.
2. **YEAR horizon contains zero Moon-as-transiting-body events** and zero ordinary (non-eclipse) lunations.
3. **DAY horizon contains no `separating` events** (applying/perfecting only) and no standing background aspects.
4. Every transit-aspect event has non-null `phase` and non-null `cycle_stage`.
5. DAY includes the target-date day/hour ruler; MONTH/YEAR do not.
6. When `precision_tier` is low: no house- or angle-based events unless `degraded=true` and the family is listed in `suppressed_families`.
7. Determinism: identical inputs produce byte-identical output (hash the serialized object in the test).
8. Every event carries a `grounding.kind` from the allowed set; `other` events carry ≥1 `topic_tag`.
9. `counts` totals equal the length of `events` and reconcile per family/segment.
10. Retrograde multi-perfection: a single aspect perfecting N times in-window yields N dated events, not one.

---

## 14. Non-goals / deferred (v1)

- No Zodiacal Releasing (fast-follow).
- No composite/relationship forecasting (that's the synastry track).
- No single numeric "score" for a day/month/year — the output is an event list, not a rating.
- No LLM anywhere in this module.
- Profections off by default (§4d).
- Lots-as-targets off by default (§4a).

---

## 15. Test fixtures

Reuse the natal precision-tier fixtures (exact / rough / unknown time) and the DST /
circumpolar edge cases already used for `compute_chart`. Add: a known slow-transit
retrograde triple-perfection case, an in-window eclipse case, and a year-horizon run
asserting Moon exclusion (invariant 2). Emit a `forecast_report.json` (counts, invariant
results) analogous to the grounding report.
