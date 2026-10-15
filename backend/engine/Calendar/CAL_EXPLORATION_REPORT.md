# CAL Phase 0: exploration report

*2026-09-28. Answers CAL_00 §7. No code was written. All paths are relative to the repo root.
Abbreviations: CF = `Forecast_compute/compute_forecast.py`, CC = `d_layer/compute_chart.py`, GF = `principles_grounding/ground_forecast.py`,
RP = `run_predictive.py`, CORPUS = `principles_grounding/all_principles_grounded.with_predictive.json` (3880 records; this is the file
GF and RP load, GF:315-317, RP:64-65).*

## 0. Summary for review

| # | Finding | Impact | Proposal |
|---|---|---|---|
| F1 | CF finds **exact perfections only**. It has no orb entry/exit windows, no episode merging (a retrograde triple pass is 3 unlinked events, CF test 269-280), no stations and no VOC. | CAL_01 needs all of these. | Build a new `Calendar/` package that **imports CF/CC primitives** (grid + bisection, `_house_of`, eclipse typing). Don't extend `compute_forecast()`: its horizon filters (YEAR = slow bodies only, CF:391-394) and grid steps are keyed to day/month/year. **Keep the `Calendar/` layout of CAL_00 §4.** |
| F2 | CF's orb table is `1.5 if Sun/Moon else 1.0` (CF:150-154), but it applies **only to "standing" aspects at the window start**. | CAL_01 §1 says "reuse CF's orbs if they exist". Those orbs weren't designed to define transit windows. | **Decision needed (Q1):** use the CAL_01 fallback orbs (inner 1.5°, Jup/Sat 2.0°, outers 1.5°), not CF's. |
| F3 | Ephemeris = **Moshier** (`FLG_MOSEPH`, CC:55-56), and `set_ephe_path` is never called. | Fine for CAL: E1/E2 fixtures verified (§1.7). | Reuse `EPHE_FLAG` as the spec says ("same flags as L1"). |
| F4 | Modern predictive corpus = **1589 records = two extractions of Hand's *Planets in Transit***. One copy is structured (`about.factor_type = aspect`, 517), the other is almost all `unclassified` (737 of 785). | Double counting in affinity if both copies are used; half the corpus is invisible to GF. | Use the structured copy for keys. Deterministically backfill `about` from `principle_id` for the unclassified copy (a regex parses 655 of them), then treat the copies as corroborating citations, **or** dedupe. **Decision (Q2).** |
| F5 | **Transits to ASC/MC exist (full 9×5 coverage for both), but every one is `unclassified`**, and GF excludes angle targets anyway (GF:48, 113-114). | CAL_01 counts ASC/MC as natal points; without them, ASC/MC transits get no text and no score. | Backfill `about.aspect.target = "Ascendant" / "Midheaven"` from ids (deterministic). |
| F6 | GF keys aspect records on **`frozenset({transiting, natal})` + type** (GF:84, 118), so direction is lost. 442 of 487 directed keys also exist in the reverse direction, e.g. an event "transiting Sun square natal Saturn" also pulls "Saturn square Sun" (transiting Saturn). | Wrong-direction grounding in predictive today. It would pollute the CAL affinity table. | CAL keys by the **directed** `(T=source, a, N=target)`. Separately, flag the GF bug (outside CAL scope). |
| F7 | **Gaps (modern):** VOC = **0**, Mercury/Venus/Mars retrograde periods = **0**, Moon-sign timing = **0**, electional = **2** (Moon affliction for social occasions), lunation-by-house = **0**. Eclipse/lunation = a handful of **generic** records. | CAL_04 C1–C5 cannot be enabled. CAL_03 `collective_event` texts for retrograde, ingress and lunation-by-sign have no grounding. | As CAL_04 §3.3 expects: a modern lunar-timing/electional TXT source → corpus delta (CAL_06). Until then these stay labels only + `gaps`. |
| F8 | The predictive reading pipeline has **no detox, no trace check, and no number check other than 4-digit years**. English is a single translation call with no validation (RP:289-328). | CAL_03 CV1–CV5 cannot simply "reuse pr_validate". | For CAL_03, reuse the **ACG reading** machinery (`acg_reading/ar_generate.py` detox loop, `ar_validate.text_problems` with AV2/AV8, AV3/AV12 trace checks), plus pr_prompts' forbidden lists. |
| F9 | GF has **no tradition filter** (32 traditional records in the predictive+timing slice). | Violates D3 if reused as is. | The CAL selector filters `tradition == "modern"` explicitly. |
| F10 | Records have **no `citation_count`**. | The ACG_08 formula reduces to cit = 1 per record. | Fine. With F4 the "citations" become the copy count (max 2). |

**Decisions (2026-09-29).** Radul approved Q1 and delegated Q2–Q4:
- **Q1: CAL_01 fallback orbs.** Sun/Mercury/Venus/Mars 1.5°, Jupiter/Saturn 2.0°, Uranus/Neptune/Pluto 1.5°.
- **Q2: keep both Hand copies as grounding, but count the book once.** Both copies stay available as text grounding (more wording for the LLM). In the affinity sums each copy of a cell gets weight `1/n_copies`, so one book never counts twice.
- **Q3: CAL-local index; the main corpus is untouched.**
  - `Calendar/cal_corpus.py` builds a derived, deterministic index keyed by directed `(T, a, N)`, with ASC/MC parsed from the `principle_id`.
  - It covers modern records only.
  - The shared corpus file and `ground_forecast.py` are not modified; the predictive grounding fix runs as its own task.
- **Q4: every C-factor ships disabled in v1, including C7/C8.** Moon-to-natal records don't honestly ground a Moon-to-transiting-planet factor. P1–P4 are enabled. The C-factors are enabled later via CAL_06 (a modern lunar-timing source).

**Open questions for Radul (resolved above):** Q1 orbs (F2) · Q2 duplicate Hand copies (F4) · Q3 whether to backfill angle transit `about` in the main corpus (affects predictive too) or only in a CAL-local index · Q4 whether the CAL_04 C-factors wait for CAL_06 or ship disabled in v1 (the spec already allows disabled).

---

## 1. `compute_forecast.py`

### 1.1 Public signature (CF:850-855)
```python
def compute_forecast(natal: dict, target_date, horizon: str, *,
                     latitude: Optional[float] = None, longitude: Optional[float] = None,
                     config: Optional[ForecastConfig] = None,
                     now: Optional[datetime] = None, run_id: Optional[str] = None) -> Forecast
```
- `horizon` ∈ {"day", "month", "year"}; anything else raises `ValueError` (CF:866-867).
- `natal` = the `compute_chart()` dict. It reads `meta.timezone`, `points`, `axes`, `sectors.placidus_cusps` and `confidence` (CF:337-356, 871).
- `Forecast` = `{meta, window, events, counts, rulers?}` (forecast_types.py:159-164).
- Other public helpers:
  - `write_forecast(forecast, runs_dir=None)` (CF:959)
  - `mint_run_id(now_utc)` (CF:836)
- Detectors (internal `_Forecaster`, CF:320), called in this order at CF:895-899:
  - `transit_aspects`
  - `sign_ingresses`
  - `house_ingresses`
  - `lunations`
  - `profections` (a stub; it raises if enabled, CF:762-768)

### 1.2 Event schema (forecast_types.py:102-117, one flat shape; `_event` CF:774-793)
```python
class Event(TypedDict):
    event_id: str; family: Family; datetime: str; standing: bool; bodies: Bodies
    aspect: AspectType | None; phase: Phase | None; cycle_stage: int | None
    speed_class: SpeedClass | None; house_placidus: int | None; house_wholesign: int | None
    sign: Sign | None; dignity: DignityPair | None; segment: Segment | None; grounding: Grounding
```
- `Family` = transit_aspect | ingress_sign | ingress_house | lunation | eclipse | profection.
- `Phase` = applying | separating | perfecting.
- `event_id = f"{family}-" + md5(family|transiting|natal|aspect|extra|jd)[:10]` (CF:294-297).
- Eclipse kind is stored **only in `topic_tags`** (CF:721-723).
- **No station, retrograde, VOC or return families.**

### 1.3 Orbs (CF:150-154)
```python
# ORB TABLE (SPEC §7) — used only for standing (in-orb-at-window-start) aspects.
# Perfection events need no orb. Orbs are NOT widened by horizon.
def _orb_allow(transiting: str) -> float:
    return 1.5 if transiting in LUMINARIES else 1.0
```
The orb is the same for all aspects. Lunation-to-natal tagging uses a separate hard-coded orb of 3.0° against the bodies only, not the angles (CF:749-757). See F2.

### 1.4 Phase and multiple passes
- In-window exact crossings: `phase = "perfecting"`, with `cycle_stage` taken from the elongation (CF:474-476, `_STAGE_BY_ELONG` CF:124).
  Both elongations of each aspect are tested (square at 90/270; CF:113-119).
- Standing events: applying/separating by a finite-difference speed test (CF:468-473):
  ```python
  d_next = _norm360((lon + spd * 1e-3) - nat_lon)
  approaching = abs(_signed180(d_next - e)) < abs(_signed180(d - e))
  ```
- **Retrograde passes:** each crossing is a separate event, with no link between them and no pass index. The only marker is a `"retrograde"` topic tag (CF:486-487).
- **Root finding:**
  1. Grid scan (`_GRID_STEP`: day 10 min, month 60 min, year 6 h; CF:183-187).
  2. Sign change of `_signed180(elong − e)`, with a wrap guard (CF:412-416).
  3. 60-step bisection (CF:248-262, 654-664). The result is effectively sub-second and is rounded to the second (CF:213-219).
- **Risk:** on the 6 h year grid, two crossings inside one step near a station could be missed. CAL must use a finer grid, or bracket on the speed = 0 roots first.

### 1.5 Coverage
- Transiting bodies: Sun…Pluto, **including the Moon** (CF:76-81).
- Nodes are excluded (CF:74-75).
- Natal targets: the 10 bodies + Ascendant, MC, Descendant, IC (CF:346-351, 381-388). Angles are dropped when the chart is degraded.
- Aspects: 0/60/90/120/180 (CF:107-110).
- Horizon filters: YEAR = slow bodies only (CF:391-394). YEAR emits eclipses but no ordinary lunations (CF:628-632).

### 1.6 Lunations and eclipses
- **Syzygies** (`_syzygies`, CF:635-652): a grid scan of `(Moon − Sun) mod 360` crossing 0 or 180, then bisection:
  ```python
  f = _signed180(_norm360(mlon - slon) - e)
  if (pf < 0) != (f < 0) and abs(pf) + abs(f) < 180.0:
      jd_x = self._bisect_syzygy(e, pjd, pf, jd, f)
  ```
- **Eclipses** (CF:666-694):
  - Found with `swe.sol_eclipse_when_glob(jd, EPHE_FLAG, 0, False)` / `swe.lun_eclipse_when(...)`, taking `tret[0]` (the maximum).
  - Kind comes from `ECL_*` bits (CF:811-830).
  - A lunation within 0.12 d of an eclipse is re-tagged as `eclipse` (CF:697-702).
  - This matches CAL_01 §2 and can be reused directly.
- **No** station detection, VOC or Moon ingress. The Moon gets no sign ingresses (CF:519-524).

### 1.7 Swiss Ephemeris and fixture check
- `EPHE_FLAG = swe.FLG_MOSEPH | swe.FLG_SPEED` (CC:55-56). `set_ephe_path` is never called.
- Functions used: `calc_ut`, `revjul`, `houses` (CC:437, 441), the eclipse finders.
- **Verified with those flags** (a script run in this session):
  - Every E1 eclipse date and kind matches: solar 2026-02-17 annular, 2026-08-12 total, 2027-02-06 annular, 2027-08-02 total; lunar 2026-03-03 total, 2026-08-28 partial, 2027-02-20 / 07-18 / 08-17 penumbral.
  - E2 Mercury stations (6 h scan) match: R 02-26, D 03-21, R 06-29, D 07-24, R 10-24, D 11-13.
  - **The spec fixtures are sound.**

### 1.8 Windows and timezone
- `tz = ZoneInfo(natal["meta"]["timezone"])` (CF:871-872), i.e. the **birth tz**.
- The window is `[local 00:00, +1 day/month/year)` (CF:884-889). `_add_horizon` clamps the day of month (CF:190-205).

### 1.9 Reusable helpers
- In CC, imported by CF:56-68:
  - `_norm360`, `_sign_index` (CC:206)
  - `_deg_in_sign` (CC:210)
  - `_angular_sep` (CC:214)
  - `_house_of(lon, cusps)` (CC:363-372, Placidus with a whole-sign fallback when circumpolar)
  - `dignities_for` (CC:275)
- In CF:
  - `_signed180`
  - `_lon_at` / `_lon_speed_at` (CF:236-242)
  - `_bisect_elongation` / `_bisect_predicate` / `_bisect_syzygy`
  - `_iso_local`

---

## 2. How `ground_forecast.py` selects records

- **Domain gate:** `PREDICTIVE_DOMAINS = {"predictive", "timing"}` (GF:44, applied at 80 and 241). **There is no tradition filter** (F9). The comment at GF:209, "all predictive is modern", is wrong: 32 records are traditional.
- **Index** (GF:74-101):
  - `aspect`: key `(frozenset({source, target}), type)`
  - `planet_in_house`: key `(point, house, system)`
  - `house_domain`
  - `planet_in_sign`
  - `general` and `unclassified` records are **not indexed**.
- **Matching** (`_structural_candidates`, GF:107-135):
  ```python
  if fam == "transit_aspect":
      if natal in ANGLE_TARGETS or natal is None or trans is None:
          return []
      return list(idx.aspect.get((frozenset({trans, natal}), event.get("aspect")), []))
  ...
  if fam in ("lunation", "eclipse"):
      hp = event.get("house_placidus")
      if hp is not None:
          return list(idx.house_domain.get((hp, "placidus"), []))
  ```
  - Key granularity is the **exact aspect type**, not the family, so CAL_02 §3 keys per aspect.
  - Direction is **lost** (F6).
  - Angles are excluded (F5).
  - Lunations look up `house_domain`, but the predictive/timing slice has **no** `house_domain` records, so in practice lunations and eclipses ground to 0 records.
- **Post-gates:**
  - `invariant_violation(about)`
  - `_gate_c` (requirements satisfiable in the natal chart; ground.py:410-415)
  - de-duplication
  - sort by id
  - cap 6 (GF:50)
- **The reading side** passes **only the first judgment, truncated to 25 words** (pr_events.py:164-171).

### 2.1 Example records (full)

**Saturn square Sun**: two copies, one structured and one unclassified:
```json
{"principle_id": "saturn-square-sun", "domain": "predictive", "topic_tags": ["Saturn","Sun","square","transit"],
 "rule": "Saturn square natal Sun tests projects begun roughly seven years earlier, often via difficulties with authority figures, lowered vitality, and possible cardiovascular strain; endeavors lacking real validity tend to fail now.",
 "conditions": ["transiting Saturn square natal Sun"],
 "judgment": "A trial period distinguishing valid undertakings from those that should be abandoned; patience with authority figures is advised over confrontation.",
 "attribution_in_text": null, "notes": null, "tradition": "modern",
 "about": {"factor_type": "aspect", "aspect": {"source": "Saturn", "target": "Sun", "type": "square"},
           "extraction_source": "llm", "extraction_confidence": "medium"},
 "requires": [{"kind": "other"}]}
```
```json
{"principle_id": "saturn-square-sun-transit", "domain": "predictive",
 "topic_tags": ["Saturn","Sun","square","crisis","testing","vitality"],
 "rule": "Transiting Saturn square natal Sun marks the first crisis point for projects begun approximately seven years prior at the conjunction. Vitality is low; authority figures may obstruct plans. Projects lacking genuine validity tend to fail at this juncture. Cutting losses on failed initiatives at this point is preferable to sustaining them until the opposition seven years hence, when consequences become more severe. Cardiovascular health requires monitoring.",
 "conditions": ["transiting Saturn square natal Sun"],
 "judgment": "Crisis test for seven-year-old initiatives; low vitality; authority resistance; invalid projects fail; early loss-cutting preferred to delayed reckoning; cardiovascular health risk.",
 "tradition": "modern",
 "about": {"factor_type": "unclassified", "unclassified_reason": "no_subject_in_text", "extraction_confidence": "low", "extraction_source": "llm"},
 "requires": [{"kind": "other"}]}
```

**Jupiter trine Venus**: only the unclassified copy exists under that id. It is invisible to GF today:
```json
{"principle_id": "jupiter-trine-venus-transit", "domain": "predictive",
 "topic_tags": ["Jupiter","Venus","trine","transit","sociability","pleasure","love","money","beauty"],
 "rule": "Jupiter trine natal Venus by transit is strongly pleasure-oriented, promoting sociability, lightheartedness, and amusement. A new love may begin, more likely as a flirtatious encounter than a deep relationship. Financial gain is possible but not the primary manifestation. Strong self-indulgent tendencies, especially with food and drink, require moderation. Tastes may lean toward the gaudy.",
 "conditions": ["transiting Jupiter trine natal Venus"],
 "judgment": "Pleasurable social and romantic period; possible financial benefit; overindulgence in food and drink is a health risk; productivity is reduced.",
 "tradition": "modern",
 "about": {"factor_type": "unclassified", "unclassified_reason": "no_subject_in_text", "extraction_confidence": "low", "extraction_source": "llm"},
 "requires": [{"kind": "other"}]}
```
(The structured copy of the same cell exists under a different id pattern; the 9×10×5 matrix in §3a counts it.)

**Lunation record** (generic, `general`, not indexed by GF):
```json
{"principle_id": "lunation-eclipse-activates-natal-planet", "domain": "predictive",
 "topic_tags": ["Moon","lunation","eclipse","natal planet"],
 "rule": "A new Moon, full Moon, or eclipse falling on a natal planet activates and emphasizes the significations of that natal planet for an extended period.",
 "conditions": ["lunation or eclipse conjunct/aspecting natal planet"],
 "judgment": "The life themes ruled by that natal planet become prominent for the duration noted (weeks for lunations, up to months for eclipses).",
 "tradition": "modern", "about": {"factor_type": "general", "extraction_source": "llm", "extraction_confidence": "medium"},
 "requires": [{"kind": "point_aspects"}]}
```

---

## 3. Corpus audit (tradition = modern only)

Modern records: 2749 in total. By domain:

| Domain | Records |
|---|---|
| predictive | 1589 |
| natal | 950 |
| basics | 186 |
| timing | 21 |
| electional | 2 |
| dignities | 1 |

The 1589 modern predictive records by `about.factor_type`:

| factor_type | Records |
|---|---|
| unclassified | 830 |
| aspect | 517 |
| planet_in_house | 168 |
| general | 74 |

- **Copies (F4):**
  - The 804 records from `predictive_delta.clean.json` are the structured copy (517 aspect / 120 pih / 93 unclassified / 74 general).
  - The other 785 are almost all unclassified (737).
- **Parseability:**
  - A strict `^(T)-(aspect)-(N)` id regex parses **655** of the unclassified records as T-a-N transits.
  - The remaining 175 are general principles (cycle stages, triple transits, "transit-in-house" ids for Sun/Mercury/Venus/Uranus: 49 records).

### (a) Transit records, T × N × a (structured copy, `factor_type = aspect`)
- Structure: `about.aspect = {source: <transiting>, target: <natal>, type}` (all 517; the key set is always `{source, target, type}`).
- Aspect counts: square 105, conjunction 104, trine 104, sextile 102, opposition 102.

Coverage for T ∈ Sun…Pluto × N ∈ 10 planets × 5 aspects = **436 of 450 cells**. Cell digits are the counts in order conj, sext, sq, tri, opp:
```
Sun      Sun:01121 Moo:11111 Mer:11111 Ven:11111 Mar:11111 Jup:11111 Sat:11111 Ura:11111 Nep:11111 Plu:21111
Mercury  Sun:11111 Moo:11111 Mer:11121 Ven:11111 Mar:11111 Jup:11111 Sat:11111 Ura:11111 Nep:11111 Plu:11111
Venus    Sun:12112 Moo:11111 Mer:11111 Ven:11111 Mar:11111 Jup:11111 Sat:21111 Ura:11111 Nep:21111 Plu:11111
Mars     Sun:42331 Moo:11111 Mer:11111 Ven:11111 Mar:11111 Jup:11111 Sat:11111 Ura:11111 Nep:11111 Plu:41113
Jupiter  Sun:11121 Moo:11111 Mer:11111 Ven:11111 Mar:11111 Jup:01111 Sat:11111 Ura:11111 Nep:11111 Plu:11112
Saturn   Sun:11211 Moo:11111 Mer:11111 Ven:11111 Mar:11111 Jup:11111 Sat:01111 Ura:11111 Nep:11111 Plu:11111
Uranus   Sun:11112 Moo:11111 Mer:11111 Ven:11111 Mar:11111 Jup:11111 Sat:11111 Ura:00011 Nep:11111 Plu:11110
Neptune  Sun:21211 Moo:11111 Mer:11111 Ven:11111 Mar:11111 Jup:11111 Sat:11111 Ura:11111 Nep:01111 Plu:01111
Pluto    Sun:21121 Moo:11111 Mer:11111 Ven:11111 Mar:11111 Jup:11111 Sat:11111 Ura:11111 Nep:11100 Plu:01200
```
- **The 14 missing cells:**
  - Self-conjunctions (returns): Sun, Jupiter, Saturn, Uranus, Neptune, Pluto.
  - Uranus sextile/square Uranus.
  - Uranus opposition Pluto.
  - Neptune conj Pluto.
  - Pluto trine/opposition Neptune.
  - Pluto trine/opposition Pluto.
- Most of these are generational or impossible in a lifetime, so the gap is effectively zero.
- **ASC and MC:** 45/45 (T × a) covered for **both**, but only in `unclassified` records (parsed from ids: `sun-conjunct-midheaven`, `moon-sextile-midheaven-transit`, …). See F5.
- **Transiting Moon aspects:** 52 structured records (for CAL_04 P4 and the day notes).

### (b) Lunation records
- **Lunation-by-house: 0.**
- **Lunation-by-sign: 0.**
- Generic lunation records (≤ 8):
  - `lunation-eclipse-activates-natal-planet` (general)
  - `lunation-activates-natal-planet`
  - `transiting-moon-new-full-extended`
  - `transiting-moon-duration-planet`
- `moon-conjunct/opposition-sun-transit` are *transiting Moon to natal Sun* records, not lunations proper.
- **Consequence:** CAL_03 `personal_lunation` can ground on the generic "lunation on a natal planet" record (when there are hits) plus a modern `house_domain` natal record for `natal_house`:
  - There are 48 modern house_domain records, but only 24 carry a house number.
  - House 10 has only 1.
  - They are domain `natal`, so the CAL selector must allow them explicitly.
- CAL_02 v1.1 (lunations in the score) has **no** taggable modern records.

### (c) Eclipse records
Generic only (7):
- `eclipse-natal-activation`
- `eclipse-natal-planet-duration`
- `eclipse-activation-natal-planet`
- `eclipse-delayed-trigger`
- `inner-planet-complex-on-natal-planet`
- the two lunation+eclipse records

There is no eclipse-by-sign and nothing by kind. `collective_event` eclipse texts ("Total solar eclipse in Leo") **have no sign/kind grounding**. Only "eclipse on your natal point" personal texts are groundable.

### (d) Retrograde / station records
- **Mercury, Venus and Mars retrograde periods: 0.**
- Station records: generic only:
  - `stationary-transit-intensification` (+ `-2`)
  - `jupiter-transit-stationary-retrograde-relief`
  - `triple-transit-*` (4)
- **Consequences:**
  - CAL_03 collective retrograde texts get label only + `gaps`.
  - CAL_04 C2–C4 are **disabled**.
  - `station_on_point` (CAL_01 §3.3) can ground on `stationary-transit-intensification`.

### (e) Void-of-course Moon
**0 modern** (14 traditional, excluded by D3). C1 and the VOC hard gates are **disabled**.

### (f) Moon-sign / Moon-phase timing
- **0** in the predictive domain.
- The only hits are `basics`: `waxing-hemicycle-theme` / `waning-hemicycle-theme`. These are natal hemicycle theory, not timing. **I don't recommend them as C6 grounding.**
- **Transiting Moon in house:** 12 houses × 2 copies = 24 records (`moon-1st-house-transit` …, `moon-transit-1st-house` …), plus the generic `moon-house-transit-focus-area`. **P3 is groundable.**

### (g) Choosing a day for an activity
- Modern `electional` domain: **2 records**. Both say to avoid social occasions when the transiting Moon afflicts natal planets:
  - `avoid-social-occasions-moon-affliction`
  - `moon-affliction-electional-caution`
- These partly ground **P4** (negative side). The positive side of P4 grounds on the 52 transiting-Moon aspect records.
- Hand's transit records often mention activities in their judgments (travel, contracts, negotiation; 144 predictive text hits). That supports P1/P2 **per record**, but it isn't a timing rule.
- There's nothing for contracts, purchases or moving as electional rules.

### Best Days grounding verdict (proposed factor lists for Radul to approve)

| Factor | Status | Proposed grounding |
|---|---|---|
| C1 voc_fraction | **disabled** | none (modern) |
| C2 mercury_rx / C3 venus_rx / C4 mars_rx | **disabled** | none |
| C5 eclipse_window | **disabled** (weak) | the eclipse records are about natal activation, not "avoid starting things". I'd keep it disabled. |
| C6 waxing_moon | **disabled** | none |
| C7 moon_benefic_aspects | enable? | transiting Moon conj/sext/trine Venus/Jupiter records. **Caveat:** these are Moon-to-*natal* records, while C7 is the collective Moon-to-*transiting* Venus/Jupiter. Semantically a stretch; Radul decides. |
| C8 moon_malefic_aspects | enable? | the same caveat; plus the 2 electional "Moon affliction" records |
| P1 benefic_transits / P2 hard_transits | **enable** | the Hand aspect records per (T, a, N), incl. ASC/MC after the backfill (F5) |
| P3 moon_in_house | **enable** | the 24 `moon-*-house-transit` records + `moon-house-transit-focus-area` |
| P4 moon_to_key_points | **enable** | the 52 transiting-Moon aspect records + the 2 electional records |

DSC and IC (CAL_04 §2) have **no** transit records of their own. The ASC opposition and MC opposition records cover them; the mapping `(T, a, DSC) ≡ (T, opp∘a, ASC)` would need a decision.

---

## 4. `prediction_reading/pr_*` (for reuse in CAL_03)

- **Section model** (pr_events.py:36-58):
  - `HORIZON_KEYS` = day: `reading`; month: overview/early/mid/late/focus; year: overview/q1–q4/focus.
  - `WORD_TARGETS` per key.
  - `SPARSE_THRESHOLD = {"day":1, "month":3, "year":6}`.
  - Profiles general/personal/professional (pr_profiles.py:56-100).
- **Event serialisation:** `serialize_event` (pr_events.py:246-252) makes one line per event, `[{astro descriptor}] {motion_word} — {plain_area} | strength | meaning: {gloss}`.
  `events_block(events, profile, *, segment=None, limit=None, astro_detail="plain")` (270-286).
  - `motion_word` (105-130) is the "building / at its peak / easing" analogue that CAL_03 §3 wants for `phase`.
- **Prompt builders** (pr_prompts.py):
  - `build_system_block(*, surface_planets=True, astro_detail="modern")` (155-159)
  - `build_day_user` (181)
  - `build_beat_user` (196)
  - `build_synthesis_user` (211)
  - `build_reask_user` (236)
- **Generator** (pr_generate.py):
  - `LLMGenerator(system_block, *, model, synthesis_model, max_tokens=4096, temperature=0.7, max_workers=4)` (92-106) → `llm_client.complete(model, system, user, *, max_tokens, temperature, schema, timeout_s, label, thinking) -> LLMResponse` (llm_client.py:500-511).
  - `DEFAULT_MODEL = "gemini-3.7-flash"`, `DEFAULT_CHEAP_MODEL = "gpt-6-luna"` (llm_client.py:44, 49).
- **Translation:** `run_predictive.translate_reading(reading, model, fallback_model=None)` (RP:289-328) is one call with **no detox and no validation** (F8).
- **Validator** (pr_validate.py):
  - `validate(reading, ctx) -> list[str]` (124-199)
  - `is_build_blocking` (202-204)
  - `ValidationContext` (109-117)
  - Rules:
    - key set
    - mask lint by `astro_detail`
    - words ±15%
    - allowed planets
    - **years only** as the numbers check (`_YEAR_RE`, 89)
    - focus keywords
  - **No trace check.**
- **Forbidden-word lists** (pr_prompts.py):
  - `TIER_A_HARD` (34-41, 23 items: lots, hyleg, almuten, triplicity, firdaria, profection, zodiacal releasing, decan, sect…)
  - `TIER_A_CONTEXT` (43-48, 7 regexes)
  - `MODERN_HARD` (51-55, 13 items incl. TR `kavuşum`, `karşıtlık`, `retrograd`)
  - `MODERN_CONTEXT` (56-59)
  - `TECH_HARD` (62-65: applying, separating, perfecting, placidus, ingress, orb…)
  - `TECH_CONTEXT` (66-70: house-number regexes, useful for CV2)
- **What CAL_03 should reuse instead** (F8):
  - `acg_reading/ar_validate.py`: `text_problems(text, lang)` (109-132) with AV2_TR/EN and AV8_TR/EN (53-61, EN inflections 74-75).
  - AV3/AV12 sentence-id trace checks.
  - `ar_generate.detox_unit` (177-186) and the detox loop (288-296).
  - `ar_prompts.build_detox_prompt` (251).
  - CV2 (no numbers) is new code: generalise `_YEAR_RE` + `TECH_CONTEXT` to all digits and TR/EN number words.

---

## 5. Timezone resolution and the current location

- **Only instance:**
  - `d_layer/compute_chart.py:58` `_tf = TimezoneFinder()`
  - `resolve_timezone(lat, lon)` (CC:223-231): `timezone_at`, then `closest_timezone_at`, else `ValueError`.
  - Stored in `meta.timezone` (CC:729).
- **Geocoding:** RP `geocode(location)` (RP:128-153, Nominatim, cached in `.cache/geocode.json`), and a twin in run.py:137-149.
- **Birth-tz anchoring:**
  - RP `_resolve_target(raw, tzname)` (RP:238-242) with `tzname = natal.meta.timezone` (RP:425)
  - CF:871-881
- **Proposed `--current-location` for `run_predictive.py`** (CAL_00 §6):
  1. Add the flag (RP ~717-722) and thread it through `_build_request_from_args` (682-711) / `_collect_request_interactive` (644-679).
  2. Geocode it in `resolve_input` (156-208), then call `resolve_timezone`.
  3. Use it in `_resolve_target`.
  4. Add a **new keyword `window_tz: Optional[str] = None` to `compute_forecast`**, default = natal tz. This is preferred over overriding a copy of `natal.meta.timezone`, because `_natal_ref` hashes the whole natal dict (CF:841-844).
  5. Pass the current lat/lon for the DAY planetary hour (RP:467-470).
- **The CAL packages** take `tz: str` as an explicit argument everywhere and never read `natal.meta.timezone`.

---

## 6. Contradictions between the specs and the code (flagged, not adapted)

| # | Spec says | Code / corpus reality |
|---|---|---|
| X1 | CAL_01 §1: "reuse compute_forecast's orbs if they exist" | They exist, but only as window-start "standing" orbs (1.5 / 1.0). They don't define transit windows. See Q1. |
| X2 | CAL_01 §1: "same flags and ephemeris files as L1" | L1 uses Moshier with **no ephemeris files** (CC:52-56). The fixtures pass anyway. |
| X3 | CAL_02 §2: "~785 transit records" | 1589 modern predictive = two copies of Hand. 517 structured aspect records + 655 parseable unclassified (incl. 138 ASC/MC). |
| X4 | CAL_02 §2: "generalise `tag_goals_acg.py` with `--scope`" | It hard-codes paths (tag_goals_acg.py:57-61), the `acg_scope` field, an ACG-specific prompt (:75-106), a `subject_of()` switch on ACG factor types (:134-148) and the `source_span` anchor (:66-67). The generalisation must parameterise all of these; `--scope` alone isn't enough. The Tagger / parse_batch / validate_effects / cache logic is reusable. The guard: ACG C-9 uses ≥ 15 records per goal, CAL_02 says ≥ 20 (fine, but note it). |
| X5 | CAL_02 §3: "match the key granularity of the Hand records" | It's per exact aspect, **directed** (source = transiting). GF itself ignores direction (F6). CAL must not copy GF's key. |
| X6 | CAL_02 §3 uses citation weighting | No record has `citation_count` (F10). The weight is 1 per record, or the copy count if both Hand copies are kept. |
| X7 | CAL_03 §1: "Hand transit records for (T,a,N)" for ASC/MC | They exist only as `unclassified` (F5). They need a backfill. |
| X8 | CAL_03: "reuses the predictive reading machinery: TR draft → EN translation → detox → validator" | The predictive layer has no detox and no trace validator (F8). Reuse the ACG reading machinery. |
| X9 | CAL_03 §1 `collective_event`: "retrograde period by body, slow-planet ingress, new/full moon by sign, eclipse by sign and kind" | **0 grounding records for all of these** (§3 b–d). By the spec's own "no grounding, no text" rule, every collective unit ships label-only in v1. That's worth confirming explicitly before building the collective text path. |
| X10 | CAL_05 §4: `chart_key` | Not defined anywhere in the code. Proposal: `sha256(birth date, time, lat, lon rounded to 4 dp, precision)[:16]`. |
| X11 | CAL_05 §4: "the existing run-id scheme" | There are two: `run.py:188-194` (with the birthdate suffix) and `run_predictive._mint_run_id` (without; also used by `run_acg`). Proposal: use run.py's scheme (birthdate-suffixed), matching the repo's "suffix every artifact with birth date" rule. |
| X12 | CAL_00 D1 moves predictive to the current tz | `compute_forecast` hard-reads the natal tz (CF:871). It needs the `window_tz` parameter (§5). |
| X13 | — (latent bug, outside CAL) | RP:415-419 never passes `approx_bucket`, so `--precision approximate` raises (CC:742-743). |
| X14 | — (outside CAL) | GF drops direction (F6) and ignores tradition (F9). This affects the current predictive readings. It deserves its own fix. |

## 7. Wiring table (for CAL_05 §6)

| Stage | Call | Real signature |
|---|---|---|
| 2 | `compute_chart` | `compute_chart(bd: BirthData, *, utc_override: Optional[datetime]=None) -> Chart` (CC:699); `BirthData(year, month, day, latitude, longitude, time_precision="exact", hour=12, minute=0, approx_bucket=None, reading_date_utc=None)` (CC:168-184) |
| 3 | CF primitives (not `compute_forecast()`) | `_lon_speed_at`, `_bisect_elongation`, `_bisect_syzygy`, `_eclipse_instants` / eclipse typing (CF:666-830), `_house_of(lon, cusps)` (CC:363), `resolve_timezone(lat, lon)` (CC:223). Proposal: promote the ones CAL uses to public names in CF (a no-behaviour-change rename, with aliases). |
| 7 | LLM + reading helpers | `llm_client.complete(...)` (llm_client.py:500); ACG: `ar_validate.text_problems`, `ar_generate.detox_unit`, `ar_prompts.build_detox_prompt`; predictive: `pr_prompts` forbidden lists, `pr_events.motion_word` |
| 9 | run folder + manifest | `run.py`: `mint_run_id(now_utc, birth_date)` (188), `suffixed(filename, suffix)` (65), `_write_json(path, obj)` (254); the manifest shape follows RP:368-386 (`run_id, status, created_at, request_hash, natal_ref, corpus_version, stages, params, outputs`). Add `cal_run/` to `.gitignore` next to `acg_run/`. |
