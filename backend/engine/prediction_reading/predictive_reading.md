# PREDICTIVE_READING_SPEC.md

Build spec for the predictive **reading layer** — the L4-analogue of the predictive
pipeline. It consumes the grounded event list (forecast events + their matched principles)
and emits a sectioned Turkish reading, lensed by profile. This is the only LLM stage in the
predictive pipeline; everything upstream is deterministic.

Two hard inheritances from prior layers:
- **Reframe over filter** (the synastry insight): grounding ran once; the profile does not
  just drop non-matching events, it *reinterprets the same events* through its lens.
- **Literal prompt blocks below** (§7): the synastry specs gave ingredients but not the
  actual prompt strings, and the coding agent had to guess. This spec ships the strings.

---

## 0. Role and boundaries

Input: the grounded forecast object — `compute_forecast.py` events, each already carrying a
`grounding` block AND (added by the forecast-grounding step) a set of matched principle
texts (rule + judgment, already paraphrased, tradition-masked at the corpus level).

Output: a JSON reading object, section keys + Turkish prose (§1).

The reading LLM **interprets only what it is given**. It performs no astrology computation,
introduces no events, planets, or dates not present in the payload, and never contradicts
the grounded meaning. If the payload is sparse, the reading is short and calm — it does not
pad with invented movement.

Profile (`general | personal | professional`) enters HERE, at read time — never in compute.

---

## 1. Output shape per horizon

Word targets are enforced with tolerance (§8). All prose is Turkish.

**day** — single block.
```json
{ "reading": "<120–180 words>" }
```

**month** — overview + beginning/middle/end + one profile-domain paragraph.
```json
{ "overview": "<80–120w>", "early": "<50–80w>", "mid": "<50–80w>",
  "late": "<50–80w>", "focus": "<80–120w>" }
```

**year** — overview + four quarter beats + one profile-domain paragraph.
```json
{ "overview": "<100–140w>", "q1": "<60–90w>", "q2": "<60–90w>",
  "q3": "<60–90w>", "q4": "<60–90w>", "focus": "<100–140w>" }
```

Plus a `meta` block on every reading: `horizon, profile, target_date, natal_ref, run_id,
model, grounded_event_count, sparse` (bool).

---

## 2. Call graph (parallel beats + synthesis)

Mirror L4: per-section LLM calls in parallel, then one synthesis pass. Shared system +
event context is identical across a horizon's calls, so use **prompt caching** on that
prefix and **batch** the beat calls.

- **day** → 1 call (the block). No separate synthesis.
- **month** → 3 beat calls (`early`/`mid`/`late`) in parallel, each seeing only its segment's
  events; then 1 **synthesis** call that sees the full event list + the three drafted beats
  and writes `overview` + `focus`, and lightly harmonizes transitions.
- **year** → 4 beat calls (`q1..q4`) in parallel; then 1 synthesis call → `overview` + `focus`.

Segment membership comes from the compute layer's `segment` field (`early|mid|late` /
`q1..q4`) — do not recompute it.

---

## 3. Profile as a reframe-lens

The profile does three things, in this order: **select emphasis**, **reframe valence**, and
**own the `focus` paragraph**. It never changes which events *exist*.

Domain routing uses the **Placidus** house on each event (`house_placidus`) and the natal
target planet. Whole-sign is internal texture only; never route or surface on it.

| Profile | Lead houses (Placidus) | Lead planets (as natal target) | `focus` paragraph is about |
|---|---|---|---|
| general | — (dominant events regardless of area) | — | the single strongest theme of the period, area-neutral |
| personal | 1, 3, 4, 5, 7 | Moon, Venus, Mars; contacts to natal Moon/ASC/IC | close relationships, home, body, feeling-life |
| professional | 2, 6, 10, 11 | Sun, Mercury, Saturn, Jupiter; contacts to MC/natal Sun | work, money, standing, responsibility |

**Emphasis:** events in the profile's lead set open and anchor each beat; off-domain events
become brief texture (month/year) or are dropped for space (day). General leads with
whatever is objectively strongest (tightest orb / slowest body / angle contact).

**Reframe (the core mechanism):** the same event carries different valence per profile.
Worked examples the prompt must embody:

- *A demanding Saturn contact to the natal Sun.*
  - personal → strain on how one shows up for close others; a call to steady self-worth.
  - professional → a structural asset: endurance, authority-building, foundations that last.
  - general → a season asking for patience and structure around self-direction.
- *An easy Jupiter contact to natal Venus.*
  - personal → warmth and opening in relationship and pleasure.
  - professional → goodwill, useful alliances, a favorable window for asking.
  - general → a supportive, expansive stretch worth using.

The prompt instructs the model to *state the same underlying movement in the profile's
register*, not to pretend off-profile events are absent when they are strong.

---

## 4. Grounding discipline

Each event arrives with one or more matched principle texts. The model interprets **from
those texts**, not from its own astrological priors. If an event's matched principles
conflict, modern governs (already enforced at corpus level; restate in prompt as a
tiebreaker). Never assert a meaning the grounded texts don't support. No fabricated events,
planets, dates, or numbers.

---

## 5. Tradition mask + machinery-hiding (hard rules)

Two tiers of banned surface vocabulary, enforced by a deterministic lint (§11):

**Tier A — classical vocabulary (absolute, inherited project-wide):** no lot / Part of
Fortune / Spirit / hīlāj / alcocoden / sect / triplicity / bound / term / decan / firdaria /
profection / lord of the year / zodiacal releasing / almuten — in any form, ever.

**Tier B — technique machinery:** no house numbers, no aspect-geometry names
(square/trine/sextile/opposition/conjunction), no cycle-stage labels, no
applying/separating/perfecting, no Placidus/whole-sign, no transit/ingress as jargon,
no orb/retrograde-as-mechanism.

**Allowed as accessible anchors (default ON, `surface_planets` toggle):** plain planet names
and common sky language (full moon, new moon, eclipse) may appear as everyday hooks —
"a full moon this month brings something to a head." This is a product/style call; the
toggle lets you turn even these off. Tier A and B are not toggleable.

The input payload DOES use technical terms (that's the model's working material); the
**output** must translate them to plain psychological Turkish. Give the model this
translation guide in-prompt:

- tension aspects → friction, a push-pull, pressure, something asking to be worked through
- flowing aspects → ease, support, a door that opens, momentum
- conjunction → a fresh start on that theme, an intensifying, a merging
- building/applying → a theme approaching, gathering, on its way
- peaking/perfecting → coming to a head now, culminating
- winding down/separating → releasing, integrating, letting settle
- house domain → the plain life area (relationships, work, home, money, health, self)

---

## 6. Dignity + phase → tone

**Dignity modulation (the L4 calibration lesson):** a dignified planet under a hard contact
reads as *consolidation under pressure*, not depletion; an afflicted planet under the same
contact reads as genuine strain. The event's `dignity` block carries this. Dignified-vs-
afflicted tone MUST differ — do not paint every hard contact as difficulty.

**Phase → narrative shape:** use `phase`/`cycle_stage` only to set *tense and motion* in the
prose (approaching / peaking now / winding down; waxing = initiating, waning = integrating).
Never name the mechanism.

---

## 7. LITERAL PROMPT BLOCKS

Copy-paste templates. `{tokens}` are filled per call. Prompts are English scaffolding with
Turkish-output directives; localize to Turkish if tone testing favors it. Temperature 0.7,
`response_format` JSON where the call returns JSON.

### 7.1 Shared system block (cached prefix for every call in a horizon)

```
You are an astrologer writing for a Turkish-speaking audience in warm, grounded, modern
psychological language. You write about lived experience — mood, timing, where to lean in
and where to be patient — never about astronomical mechanics.

ABSOLUTE RULES:
1. Interpret ONLY the events given to you below. Do not invent planets, dates, themes, or
   movement that is not in the event list. If the list is short, write a shorter, calmer
   piece. Never pad.
2. Base each interpretation on the "meaning" text attached to each event. Do not overrule it
   with your own astrological ideas. If two meanings clash, prefer the psychological one.
3. NEVER use technical vocabulary in your output. Forbidden: house numbers; the words
   square/trine/sextile/opposition/conjunction; applying/separating/perfecting; transit,
   ingress, orb, retrograde-as-jargon; and ANY classical terms (lot, Part of Fortune,
   Spirit, sect, profection, lord of the year, triplicity, bound, term, firdaria, releasing).
   Translate every technical fact into plain feeling-language using this guide:
     - tension → friction, a push-pull, pressure to work through
     - flow → ease, support, momentum, an opening
     - a fresh start on a theme → beginnings, intensifying
     - building → approaching, gathering; peaking → coming to a head now;
       winding down → releasing, settling
     - life areas in plain words: self, relationships, home, work, money, health.
   {planet_surface_clause}
4. When a strength is noted for a factor, write pressure on it as consolidation and
   endurance, NOT as depletion. Only genuine weakness reads as real strain.
5. Output MUST be valid JSON with exactly the keys requested. Turkish prose only inside the
   values. No commentary outside the JSON.
```

`{planet_surface_clause}` = when `surface_planets` ON:
`"You MAY name planets and common sky moments (full moon, new moon, eclipse) as everyday
hooks, but never the mechanics around them."`
when OFF: `"Do not name planets or sky events at all; speak purely in terms of lived themes."`

### 7.2 Event serialization (built deterministically, inserted into every call)

One line per event, segment-filtered for beat calls, full list for synthesis. Format:

```
- ({segment}) {motion_word} — {plain_area} | strength: {dignity_word} | meaning: {principle_gloss}
```
where the builder maps, from each event: `motion_word` from phase/aspect via the §5 guide
(e.g. "pressure building", "support peaking", "a fresh start settling"); `plain_area` from
`house_placidus` + natal target (e.g. "close relationships", "work and standing", "self and
vitality"); `dignity_word` ∈ {strong, mixed, vulnerable, —}; `principle_gloss` = the matched
principle's judgment, ≤25 words, already plain. Lunations/eclipses render as
"a culmination in {plain_area}" / "a fresh cycle in {plain_area}".

### 7.3 DAY block prompt

```
{system_block}

PROFILE: {profile}  — {profile_lens_line}

EVENTS FOR THIS DAY:
{events_block}

TASK: Write ONE flowing paragraph of 120–180 words in Turkish for this day, seen through the
{profile} lens: lead with what matters most for {profile_domain}, and cast every theme in
that register. If the day is quiet, say so honestly and keep it brief. Return JSON:
{"reading": "..."}.
```

### 7.4 MONTH beat prompt (run 3×: early / mid / late)

```
{system_block}

PROFILE: {profile}  — {profile_lens_line}

EVENTS IN THIS PART OF THE MONTH ({segment_label}):
{events_block_for_segment}

TASK: Write 50–80 words in Turkish covering the {segment_label} of the month through the
{profile} lens. Concrete and grounded; no preamble. Return JSON: {"beat": "..."}.
```

### 7.5 MONTH synthesis prompt

```
{system_block}

PROFILE: {profile}  — {profile_lens_line}

ALL EVENTS THIS MONTH:
{events_block_full}

THE THREE PARTS ALREADY WRITTEN:
early: {early_beat}
mid:   {mid_beat}
late:  {late_beat}

TASK (Turkish, JSON):
1. "overview": 80–120 words naming the month's dominant thread through the {profile} lens and
   how it moves across the three parts.
2. "focus": 80–120 words specifically on {profile_domain} — the profile's home ground. For
   "general", make this the single strongest theme of the month, area-neutral.
Return {"overview": "...", "focus": "..."}.
```

### 7.6 YEAR beat prompt (run 4×: q1..q4) and synthesis

Quarter prompt is 7.4 with 60–90 words and `{segment_label}` = the quarter. Synthesis is 7.5
with the four quarter beats, `overview` 100–140w, `focus` 100–140w.

### 7.7 `{profile_lens_line}` values (inject per profile)

```
general:      "Lead with the period's strongest movement whatever life-area it touches; keep the voice balanced across life as a whole."
personal:     "Foreground close relationships, home, body and feeling-life; read every theme for what it means to the heart and private life."
professional: "Foreground work, money, standing and responsibility; read every theme for what it means to effort, ambition and structure."
```
`{profile_domain}` = "life as a whole" / "close relationships and inner life" / "work,
money and standing".

---

## 8. Length & structure enforcement

Deterministic post-pass: word-count each section against its target with ±15% tolerance;
on violation, one bounded re-ask of only the offending section (do not regenerate the whole
reading). Verify the JSON has exactly the horizon's key set and nothing else.

---

## 9. Sparse-period handling

If `grounded_event_count` is below a threshold (suggest: day <1, month <3, year <6 after
profile emphasis), set `meta.sparse=true` and instruct via a `{sparse_clause}` appended to
the task: honest "quieter stretch" framing, shorter output allowed (floor = 60% of the word
minimum), zero fabricated movement. A quiet forecast is a valid forecast.

---

## 10. Persistence + eval

- Save the reading into the SAME run folder as its forecast, `reading_{horizon}_{profile}_{target_date}.json`.
- The reading is the eval distiller's source (L5-analogue). Emit it in the shape the distiller
  expects; the human-filled score readback stays deferred, as in natal.

---

## 11. Invariants (tests)

1. Output JSON carries EXACTLY the horizon's section keys (+ `meta`), no extras, no missing.
2. Tier-A and Tier-B lint: zero banned tokens in any prose value (case-insensitive, Turkish
   and English forms). Tier-A failure is build-blocking.
3. Word counts within ±15% per section (after the §8 re-ask).
4. `focus` present for every horizon that has it; for non-general profiles it stays on the
   profile's domain (spot-checkable via a domain-keyword presence heuristic).
5. No date or planet appears in the output that is not present in the input event list
   (lint: extract date/planet mentions, diff against payload; planet lint only when
   `surface_planets` ON).
6. Sparse path: when `meta.sparse=true`, output respects the reduced floor and adds no new
   themes.
7. Every reading is reproducible enough for eval: same payload + pinned model/params yields
   stable structure and theme set (exact wording may vary; the eval harness owns variance).

---

## 12. Non-goals / deferred

- No numeric day/month/year score.
- No profection- or releasing-derived text (those modules ship off; if switched on later,
  their events flow through this same reading layer unchanged).
- No cross-chart / relationship forecasting (synastry track).
- No imagery or per-event mini-readings — the output is the sectioned narrative only.
- The reading never exposes which tradition or technique produced a theme.
```
