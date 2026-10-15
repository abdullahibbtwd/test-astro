# PA 01: personal dossier, evidence and tools

*Deterministic. No model calls anywhere in this spec (test T9 patches `llm_client` to raise). Every tool **reuses** an
existing layer's loaders, grounding selectors and label catalogue; nothing here re-implements grounding. PA is
read-only over other layers' outputs and writes only to its own cache.*

## 1. Purpose

Turn a plan (PA_02) into **evidence**: the only material the composer (PA_03) may use. Evidence is the person's
grounded records, masked chart facts, deterministic data items, already-validated texts, and card and link candidates.

## 2. Personal dossier (`pa_dossier.py`)

### 2.1 Build

`build_dossier(chart_key, chart_json_path, personal_principles_path, l4_output_path | None) -> Dossier`

Inputs: `chart.json` (L1), `personal_principles.json` (the chart's kept natal principles, bundled by factor; Phase 0
item 1), `l4_output.json` if it exists. If `personal_principles.json` doesn't exist for the chart, run the existing
natal grounding for it first (deterministic; Phase 0 confirms it needs no model). Target ≤ 2 s warm.

### 2.2 Schema (`dossier.json`, `schema_version: pa-dossier-1`)

```json
{
  "schema_version": "pa-dossier-1",
  "chart_key": "…",
  "versions": {"corpus_sha256": "…", "routing_version": "…", "catalogue_version": "…"},
  "facts": {
    "f:natal:venus":  {"kind": "placement", "body": "venus", "sign": "taurus", "house": 7, "retrograde": false},
    "f:natal:asc":    {"kind": "angle", "angle": "asc", "sign": "aries"},
    "f:natal:mc":     {"kind": "angle", "angle": "mc", "sign": "capricorn"},
    "f:natal:house:7": {"kind": "house", "house": 7, "sign": "libra", "rulers": ["venus"]},
    "f:natal:aspect:venus|mars|square": {"kind": "aspect", "a": "venus", "b": "mars", "type": "square", "rank": 3}
  },
  "records": {"r:natal:<id>": {"factor": "<bundle factor key>", "render": "<L4 prompt rendering>",
                               "polarity": "…|null", "sensitivity": "normal|high|null",
                               "goal_tags": [], "_tradition": "modern|classical"}},
  "bundles": {"<factor key>": ["r:natal:<id>", "…"]},
  "index": {
    "by_topic": {"partnerships": ["<factor key>", "…"]},
    "by_body":  {"venus": ["<factor key>", "…"]}
  },
  "prose": {"p:natal_section:partnerships": {"text_tr": "…", "text_en": "…", "trace": ["r:natal:<id>"]}},
  "availability": {"l4_output": true, "calendar": true, "best_days": true, "acg_map": true}
}
```

- **Facts** come from `chart.json` with the FE_02 §7.2 mapping: Placidus houses, `rulers` = `[ruler, modern_ruler]`
  de-duplicated, aspects from `relations[]` **where `scheme == "modern"` only**. `rank` = order by orb ascending (the
  orb itself is not stored in facts). No masked field is ever copied (FE_02 §6.4): no whole-sign data,
  `classifications`, `derived_points`, `sect`, `planetary_day/hour`. Degrees stay in `chart.json`; only cards read them.
- **Records:** every kept record of `personal_principles.json` exactly once, keyed `r:natal:<id>`. `render` is produced by
  the **L4 prompt renderer** (Phase 0 item 2), not a new one. `_tradition` is internal (used for the quota, never shown).
- **`by_topic`** = the L4 routing from factor bundles to the 17 section keys (FE_02 `NatalSection.key`), in L4 order.
  **`by_body`** = every bundle whose factor involves that body, ordered: sign, house, aspects by `rank`, then lordship.
- **Prose:** the `l4_output.json` sections with their `principle_ids` mapped to `r:natal:` ids. Absent → `{}`.

### 2.3 Natal retrieval

`select_natal(dossier, topics, bodies, cap) -> [record ids]`, deterministic:

1. Candidate bundles: for each topic in the given order, its `by_topic` bundles; then each body's `by_body` bundles.
   De-duplicate bundles, keeping first occurrence.
2. Walk the bundles round-robin (one record from each bundle per pass, records in bundle order) until `cap` is reached.
3. Apply the L4 **2:1 modern:classical** ratio inside the cap: when classical records would exceed one third of the
   selection, skip further classical records and continue with modern ones. If modern runs out, stop (never pad with
   classical).
4. Default `cap`: 24 for one topic or body, 32 for two or more.

### 2.4 Goal → natal topics (domain table)

Used when the plan names a goal for a natal question ("what does my chart say about my love life?").

| Goal | Natal topics (in order) |
|---|---|
| love | `partnerships`, `joy_creativity_children`, `transformation_intimacy` |
| career | `status_vocation`, `health_routine_pets`, `identity` |
| business | `status_vocation`, `values_money`, `friendships_future` |
| money | `values_money`, `transformation_intimacy` |
| family | `family_home`, `joy_creativity_children` |
| education | `communication_learning`, `travel_philosophy` |
| creativity | `joy_creativity_children`, `identity` |
| spirituality | `subconscious_solitude`, `travel_philosophy` |
| rest | `subconscious_solitude`, `family_home` |
| travel | `travel_philosophy`, `communication_learning` |
| relocation | `family_home`, `travel_philosophy` |

Personality questions ("who am I?", "what am I like?") map to `core_identity`, `inner_drives`, `identity` (PA_02 §3).

### 2.5 Invalidation

Rebuild when `chart_key`, the corpus sha, the routing version or the catalogue version changes, or when
`l4_output.json` appears or changes (prose and availability only).

## 3. Evidence pack

### 3.1 Schema (one per executed call)

```json
{
  "call_id": "c1",
  "tool": "natal_topics",
  "args": {"topics": ["partnerships"]},
  "forced": false,
  "status": "ok | absent | out_of_range | needs_input | not_ready",
  "absence": null,
  "clamped": null,
  "source_kinds": ["chart"],
  "facts":   [{"id": "f:natal:venus", "label": "Venüs: Boğa burcunda, Ortaklıklar alanında"}],
  "records": [{"id": "r:natal:<id>", "render": "…", "polarity": "supportive", "sensitivity": "normal"}],
  "items":   [{"id": "i:period:per:love:favorable:2026-11-02", "label": "…", "dates": ["2026-11-02", "2026-11-19"],
               "band": null, "grade": null, "band_label": null}],
  "prose":   [{"id": "p:natal_section:partnerships", "text": "…"}],
  "card_candidates": [{"id": "k:c1:0", "card": {"type": "chart_fact", "...": "..."}}],
  "link_candidates": [{"id": "l:c1:0", "label": "…", "route": "/chart?section=partnerships"}],
  "needs_input": null
}
```

- `status` values: `absent` carries an FE_02 `Absence` (`reason` from the layer, or `not_generated`,
  `item_not_found`, `tool_timeout`); `out_of_range` carries the allowed range; `needs_input` carries
  `{kind: place_ambiguous | place_not_found | person_unknown, options: […]}`; `not_ready` means a deterministic
  stage is still computing after the timeout (§7).
- `clamped`: `{asked: {from, to}, used: {from, to}}` when a range was cut to the horizon (the answer must say so).
- `records[].render` and `prose[].text` are in the form the composer sees. Internal fields (`_tradition`, factor keys,
  scores `S/P/N/R`, contributions) never enter the pack.

### 3.2 Labels, never numbers

Facts and items reach the model as **labels in `lang`** from the existing catalogue (Phase 0 item 10):

- Houses → life-area names (e.g. 7 → TR "Ortaklıklar" / EN "Partnerships"), never "7th house".
- Aspects → catalogue names ("kare" / "square"); transit episodes → the calendar label ("Saturn square your Sun") +
  the phase label (building / at its peak / easing, FE_02 §6.3, relative to the call's date).
- ACG lines → planet + angle labels + the tier wording of ACG_04 §3 ("strongly" / "noticeably" / "faintly"); no
  distances.
- Bands, grades, tones → catalogue labels, and the enum value in `band` / `grade` for the validator.
- **Dates are the only digits allowed in labels and `dates`.** No degrees, orbs, house numbers, distances, scores or
  percentages anywhere in a pack except inside `card_candidates`.

### 3.3 Id namespaces (trace tokens)

| Prefix | Meaning | Example |
|---|---|---|
| `f:` | computed fact | `f:natal:venus`, `f:natal:aspect:venus\|mars\|square`, `f:other:<handle>:sun` |
| `r:<layer>:` | grounded record (`natal`, `forecast`, `cal`, `bd`, `acg`, `syn`, `basics`) | `r:acg:acg-venus-dsc-03` |
| `i:` | deterministic data item | `i:day:2026-10-12`, `i:transit:tr:saturn:conjunction:sun:2026a`, `i:bestday:contract:2026-10-14`, `i:place:gn-311046:career` |
| `p:` | already-validated text | `p:forecast:month:2026-10:general`, `p:caltext:<unit_id>`, `p:place:gn-311046:place_overview` |
| `k:` / `l:` | card / link candidate | `k:c2:0`, `l:c2:0` |

Ids are unique within a turn. The layer prefix in `r:` prevents collisions between corpora.

### 3.4 Global evidence cap

Per turn: ≤ **40 records**, ≤ **3 prose texts** (each cut to its first 250 words at a sentence boundary), ≤ **30 items**.
If the calls together exceed a cap, trim from the end of each call's ordered list proportionally, keeping ≥ 4 records
per call that has any. Deterministic.

## 4. Tools

All tools take the turn context `(subject, profiles, lang, today, tz)` plus their arguments. "Reuse" names the
existing function that defines the allowed records; the tool calls it rather than selecting records itself.
Arguments are shown **after** time resolution: the plan gives `day`, `span` and `best_days` a `time` expression, and
`resolve_time` (PA_02 §4) turns it into `date` or `from`/`to` before the tool runs.

| Tool | Arguments | Source kinds | Records (reuse) |
|---|---|---|---|
| `chart_facts` | `bodies?: Body[] ≤ 4`, `angles?: ('asc'\|'mc')[]`, `big_three?: bool` | chart | none (facts only) |
| `natal_topics` | `topics?: SectionKey[] ≤ 3`, `goals?: Goal[] ≤ 2`, `bodies?: Body[] ≤ 3` | chart (+ natal_reading) | §2.3 |
| `natal_section` | `section_key` | natal_reading | the section's `principle_ids` |
| `day` | `date`, `lens` | calendar (+ forecast) | CAL_03 unit sets |
| `span` | `from`, `to`, `goal?`, `lens`, `include[]` | calendar (+ forecast) | CAL_03 unit sets |
| `best_days` | `activities: Activity[1..2]`, `from?`, `to?` | best_days | `best_days_factors.json` grounding |
| `calendar_item` | `item_id` | calendar | CAL_03 unit set |
| `place` | `place_id?` or `place_text?`, `goals?: Goal[] ≤ 2` | acg | `ground_acg` + ACG_08 contributors |
| `recommend` | `goal: Goal \| 'overall'`, `scope: 'world' \| ISO2` | acg | ACG_09 §4 grounding |
| `compatibility` | `other?: handle`, `compatibility_id?`, `type?: CompatType` | compatibility | S2 kept records |
| `astro_basics` | `kind`, `key` | (none) | general modern records |

### 4.1 `chart_facts`

Facts for the requested bodies and angles (default: the big three). Each body fact label: sign, life area, and
"retrograde" when true. Aspect facts for the requested bodies, ordered by `rank`, at most 4. Card candidates: one
`chart_fact` per requested body (≤ 3; angles have no card shape). Link: `/chart`.

### 4.2 `natal_topics`

Goals expand to topics by §2.4 (topics given explicitly come first). Records by §2.3. Facts: placements of the bodies
that appear in the selected records' factors, plus the house fact of each selected topic's house (sign on the cusp and
its rulers, as labels). Prose: the first topic's `p:natal_section:*` if it exists. Cards: `chart_fact` for the first two
distinct bodies in the selected records' factor order. Link: `/chart?section=<first topic>`.

### 4.3 `natal_section`

Prose = the section text in `lang`; records = its `principle_ids` from the dossier (≤ 12, in order). If `l4_output.json`
doesn't exist: status `absent` (`not_generated`), and the tool returns `natal_topics{topics: [section_key]}` evidence in
the same pack (the chat never starts the natal reading job, PA_00 D4). Link: `/chart?section=<key>`.

### 4.4 `day`

Range: today … today + 365 from the calendar caches; past dates (today − 7 … today − 1) only if the caches still hold
the day, else `out_of_range` (`past_not_cached`).

- Items: `i:day:<date>` (tone, the 11 goal bands with labels, Moon phase and sign labels, retrograde bodies), the day's
  calendar events, active transit episodes of importance major or moderate (≤ 4, major first, then by nearness to an
  exact date), and the activities graded excellent or good that day (from `best_days.json`).
- Records: for each kept episode the CAL_03 `personal_transit` set (≤ 4 each); for a lunation or eclipse that day the
  CAL_03 `personal_lunation` or `collective_event` set (≤ 3).
- Prose (only if cached): the day reading for `lens`, the `day_note`, up to 2 transit unit texts.
- Cards: `forecast` (horizon `day`), `transit` (≤ 2). Link: `/ahead?view=today&date=<date>`.

### 4.5 `span`

`from … to` ≤ 12 months, inside the calendar horizon (clamp, §3.1). `include` ⊆ `periods`, `transits`, `lunations`,
`eclipses`, `retrogrades`, `favorable_days` (default: all that apply).

- Items: periods overlapping the range (filtered to `goal` when given), major transits overlapping (plus moderate when
  the range ≤ 31 days), lunations and eclipses in range, retrograde periods overlapping, and the days with tone
  `favorable` / `challenging` when the range ≤ 62 days.
- Records: periods with importance major or strength strong (≤ 3) → CAL_03 `period` set (the drivers' records tagged
  with the period's goal; ≤ 4 each); major transits (≤ 3) → `personal_transit` set (≤ 3 each); lunations and eclipses
  (≤ 2) → their sets (≤ 2 each).
- Prose (only if cached): the month reading's `overview` + `focus` when the range is exactly a calendar month; the year
  reading's `overview` when the range is the year view; up to 2 period or transit unit texts.
- Cards: `period` (≤ 2), `transit` (≤ 1), `forecast` (month or year) when prose was used. Link:
  `/ahead?view=month&month=<YYYY-MM>` or `/ahead?view=calendar`.

A "when" question ("when is a good time for love?") is a `span` over the horizon with `goal` and
`include: [periods]`. The answer then names favourable periods for that goal; it never names an event.

### 4.6 `best_days`

Range default: today … today + 30; must lie in the 90-day horizon (clamp).

- Items per activity: the excellent and good days in range, the avoid days in range, windows in range, and for up to
  3 top days in range their reason labels (top 3 positive, top 2 negative; CAL_04 §5).
- Records: for each of those top days, the grounding records of its **enabled** positive factors (≤ 3 per day). A
  disabled factor is never cited.
- Prose (only if cached): Best Day texts for those days (≤ 2).
- If no day in range is good or better, the items say so; nothing is softened.
- Card: `best_days` per activity with the excellent and good days in range (≤ 7). Link:
  `/ahead?view=best_days&activity=<a>`.

### 4.7 `calendar_item`

The item (FE_02 `CalendarItem` fields as labels and dates), its CAL_03 unit set, its cached text. Card: `transit` or
`period` by kind. Link: `/ahead?view=calendar&item=<id>`. Unknown id → `absent` (`item_not_found`).

### 4.8 `place`

**Resolution.** `place_id` → direct. `place_text` → gazetteer + destinations search with TR and EN names (Phase 0
item 6). One clear match → ok. Two to four close candidates → `needs_input: place_ambiguous` with options
(`place_id`, name, country). None → `needs_input: place_not_found`. **Never** resolve to a distant or unrelated place
silently (the "Instanbul" → Antwerp case): if a geocoder fallback is used, the pack sets `resolved_by: geocoder` and the
answer must name the resolved place (PA_03 PV12).

**Data (deterministic stages only):** locate, goal scores, `ground_acg`. No reading stage.

- Items: the selected lines (planet + angle labels, tier wording), the 11 goal bands with labels, relocation status.
- Records: with `goals`, for each goal (≤ 2) its `contributors` (≤ 8) + the A3 frame of the dominant line + the method
  records `acg-method-ambivalence`, `acg-method-natal-modifies-response`, `acg-method-degree-of-expression`; without
  `goals`, A3 + the top A1 records of each selected line (≤ 4 lines × ≤ 4) + the same method records. `sensitivity` is
  carried on every record.
- Prose (only if cached): the place reading's `place_overview`.
- Card: `place` with the six suitability goals (ACG_07 §6.2), asked goals first. Link: `/map?place=<place_id>`.
- Relocation absent → status ok with natal-only evidence (ACG_03 §5.3). ACG corpus missing → `absent`.

### 4.9 `recommend`

The recommender's deterministic ranking (`--dry-run` path, zero model calls), cached per (chart_key, goal, scope,
default filters). Items: the top 5 places (band label, dominant line labels, `has_tradeoff`) and, for world scope, the
Turkey block's top 3. Records: for the top 3 places and the best Turkey place, their `contributors` (≤ 4 each) + the A3
frame of the dominant line + the ACG_09 §4 intro method ids. Prose: cached explanations for the same key, if any.
Cards: `place` for the top 3. Link: `/map?recommend=<goal>&scope=<scope>`. `thin_result` is carried as an item flag;
the answer must say the list is short.

### 4.10 `compatibility`

**Resolution.** `compatibility_id` → its people and type. Otherwise `other` (a profile handle from PA_02 §5) →
profile. Not one of the user's profiles → `needs_input: person_unknown`.

**Type** (when not given): partner → `love`; colleague, business_partner → `work`; parent, child, family → `family`
(S3 `general` + `family_relation`, FE_00 O4); friend, other → internal `general` (no `CompatType`, so no card unless a
compatibility already exists).

**Data:** S1–S2 for (subject, other) with the lens (love → personal, work → professional, family and general →
general); no S3 call.

- Facts: both people's big three as labels, the other person named by their label (`f:other:<handle>:sun`, …).
- Records: S2 kept records in the lens's order (≤ 30). Universal records stay in; the lens instruction goes to the
  composer (they are reframed, not filtered).
- Prose (only if cached): the first S3 section of an existing compatibility of that type.
- Card: `compatibility` only when a `Compatibility` exists for (subject, other, type). Link: existing →
  `/match/<compatibility_id>`; none → `/match/new?b=<profile_id>&type=<type>`.
- Never a score (FE_00 O1).

### 4.11 `astro_basics`

General, non-personal meaning for an explanation question ("what does a retrograde mean?"). `kind` ∈ `planet`,
`life_area`, `aspect_cycle`, `lunation`, `eclipse`, `retrograde`, `acg_line`; `key` = the body, life area, phase, sign
or angle as the kind requires. Records: modern general records of that kind (Phase 0 lists which record types qualify;
≤ 6). No facts, cards or links; `source_kinds: []`. No qualifying record → `absent` (`no_grounding`).

## 5. Context → forced calls

FE context ids (FE_09 §4.1) force calls before the planner's own. Forced calls count toward the limit of 4 and run
first.

| Context | Forced call |
|---|---|
| `date` | `day{date, lens}` |
| `month` | `span{first … last day of month, lens}` |
| `place_id` | `place{place_id}` |
| `other_profile_id` | `compatibility{other: <handle of that profile>}` |
| `compatibility_id` | `compatibility{compatibility_id}` |
| `item_id` | `calendar_item{item_id}` |
| `activity` (+ `date`) | `best_days{activities: [activity], from: date, to: date}` (without `date`: default range) |
| `section_key` | `natal_section{section_key}` |

## 6. Cards and links (`pa_cards.py`)

Cards are built in the exact FE_09 §4.3 `AskCard` shapes using the FE_02 mapping rules (§6.1 id normalisation, §6.3
labels and phases, §6.4 masking), with labels in `lang`:

| Card | Built from |
|---|---|
| `chart_fact` | `chart.json` via FE_02 §7.2 (`degree_in_sign` at full precision, Placidus `house`) |
| `best_days` | `best_days.json` (activity, `{date, grade}[]`) |
| `place` | goal scores (`goal`, `band`, `band_label`) + place id, name, country |
| `period` | `periods.json` → `PeriodRef` (FE_02 §7.4) |
| `transit` | `personal_events.json` → `TransitEpisode` (FE_02 §7.3), phase relative to the call's date |
| `compatibility` | the existing `Compatibility` (`compatibility_id`, the two labels, `compat_type`) |
| `forecast` | `{horizon, date?, month?, title}`; `title` from a TR/EN label table (day: "Günlük yorum" / "Daily forecast"; month: the localised month name and year; year: "Yıllık yorum" / "Year ahead") |

**Link routes** (provisional; Phase 0 maps them onto the FE route builders, FX4.6 `src/lib/routes.ts`; the app's
validating mapper sends unknown routes to the tab):

| Link | Route template | Label (TR / EN) |
|---|---|---|
| chart | `/chart` · `/chart?section=<key>` | "Haritam" / "My chart" · the section title |
| day | `/ahead?view=today&date=<date>` | "Günün yorumu" / "This day" |
| month | `/ahead?view=month&month=<YYYY-MM>` | the month name |
| calendar | `/ahead?view=calendar` · `&item=<id>` | "Takvim" / "Calendar" |
| best days | `/ahead?view=best_days&activity=<a>` | "En İyi Günler" / "Best Days" |
| place | `/map?place=<place_id>` | the place name |
| recommender | `/map?recommend=<goal>&scope=<scope>` | "Nereye Gitmeliyim?" / "Where Should I Go?" |
| compatibility | `/match/<id>` · `/match/new?b=<profile_id>&type=<type>` | "Uyum" / "Compatibility" |
| add a person | `/profiles/new` | "Kişi ekle" / "Add a person" |

TR labels go to native review with the templates (PA_03 §7).

## 7. Caching, timeouts, prewarm

- Evidence packs are cached per `(chart_key, tz, tool, normalised args, lang, data versions)`. Same inputs → byte-identical
  pack (T12). The cache is dropped when an underlying cache rolls forward or a version changes.
- A tool waits at most `PA_TOOL_TIMEOUT_S = 45` for a deterministic stage. If the stage is still running, the pack is
  `not_ready` (`computing`) and the stage keeps running so the next turn finds it cached (Phase 0 says whether the
  layers can finish in the background; if not, report it).
- `prewarm(subject)` (PA_04 §7) builds the dossier and makes sure the calendar, Best Days and ACG map caches exist. No
  model calls.

## 8. Acceptance (`test_pa_dossier.py`, `test_pa_tools.py`, `test_pa_cards.py`)

| # | Check |
|---|---|
| D1 | Two builds of the dossier for the same chart are byte-identical. |
| D2 | Every kept record id in `personal_principles.json` appears exactly once in `records`; no other id appears. |
| D3 | Facts match `chart.json` (Placidus houses, modern-scheme aspects only); a key scan finds no masked field (FE_02 AC3 key list). |
| D4 | Every record is reachable through `by_topic` or `by_body`; the report lists records reachable through `by_body` only. |
| D5 | Changing the corpus sha or the chart_key rebuilds the dossier; adding `l4_output.json` updates only `prose` and `availability`. |
| D6 | §2.3: one-topic selection ≤ 24 records, classical ≤ one third, round-robin order verified on a fixture. |
| T1 | Every pack validates against the §3.1 schema. |
| T2 | §3.4 caps hold for a 4-call plan; trimming is deterministic. |
| T3 | `day`, `span`, `best_days`, `calendar_item` packs contain no record with tradition ≠ modern and no `predictive_scope: time_lord` record. |
| T4 | No label, render or prose in any pack contains a digit except inside dates; no house-number pattern (ACG_04 AV1) appears. |
| T5 | Horizons: a `day` at today + 400 and a `best_days` at today + 120 → `out_of_range`; a `span` that half-overlaps the horizon → `clamped`. |
| T6 | `place_text: "Instanbul"` never resolves to Antwerp silently: the pack is ok with İstanbul, or `needs_input`; a geocoder resolution sets `resolved_by`. |
| T7 | `recommend` item order and membership = the recommender's dry-run ranking (ACG_09 RV3). |
| T8 | `compatibility`: the relation → type table holds for all 9 relations; an unknown handle → `needs_input: person_unknown`. |
| T9 | No tool calls `llm_client` (patched to raise) and no tool starts another layer's reading stage. |
| T10 | Every card candidate validates against the `AskCard` schema in `openapi.yaml`; every link route matches the §6 table. |
| T11 | Each §5 context row produces exactly its forced call. |
| T12 | Same inputs → byte-identical evidence pack. |
| T13 | The natal, synastry, predictive, calendar and ACG outputs for the fixture chart are byte-identical before and after a PA session (PA writes only to its own cache). |
