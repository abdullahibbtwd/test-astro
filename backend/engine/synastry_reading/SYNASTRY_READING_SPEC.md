# SYNASTRY_READING_SPEC.md — S3 (relationship reading generation)

**Layer:** S3 (compatibility pipeline). Synastry analog of natal L4.
**Implements:** the reading-generation stage (e.g. `read_relationship.py`), consuming grounded output, producing the couple's reading.
**Input:** `personal_relationship_principles.json` (from `ground_relationship.py`, now clean across all four interaction types) + the two `chart.json` files.
**Output:** `relationship_reading.tr.txt` (primary), `relationship_reading.en.txt`, `relationship_statements.json` (for S4/eval), `relationship_reading_routing.json`.
**Model:** `claude-sonnet-5` for section and synthesis calls (matches natal).

This spec folds in the section routing and the noise floor — there is **no separate ranking artifact**. S3 prepares its own inputs.

---

## 1. Contract

S3 turns grounded facts into one coherent, romantic-first relationship reading in Turkish, with English as a faithful secondary. It is an interpretation layer: it **may only make claims traceable to a grounded record's `bound_statement`**, and it must present a single modern surface with no leakage of the classical machinery underneath.

Determinism is not required (it is an LLM stage), but **traceability and the mask are hard invariants** (§10).

---

## 2. Inputs

From `personal_relationship_principles.json`:

- `synastry[]` — 106 in the test run: `overlay` (20), `aspect` (56), `compatibility` (5), `reception` (25). Each carries `bound` (resolved persons/points) and `bound_statement` (person-substituted prose). **S3 reads `bound_statement`, never `rule`.**
- `person_a[]`, `person_b[]` — each person's natal partnering nature (`natal_relational` + one role line per planet).
- `framing[]` — 12 interpretive-stance principles. These shape *how* S3 writes; they are **not** content and never become statements.
- `chart_a`, `chart_b` filenames; `counts`.

From the two charts: `meta.time_precision` for the precision gate (§9); nothing else — S3 must not read raw positions to invent facts.

---

## 3. Section structure

Seven shared sections, plus a short per-person opener. Romantic-first framing throughout.

0. **What each brings** — one short paragraph per person (from `person_a` / `person_b`), their natal capacity to partner. Not a compatibility claim — the standing ground each person walks in with.
1. **Attraction & chemistry**
2. **Emotional needs & security**
3. **Communication & the meeting of minds**
4. **Friction & challenge**
5. **Values, money & shared life**
6. **Commitment & long-term viability**
7. **Shared purpose & growth**

---

## 4. Routing + floor (S3 input prep)

### 4.1 Noise floor — drop before routing

- **Reception `grade: face`** → drop from user-facing content (weight 0.2; too weak to state).
- **Cross-aspects** below the §7 salience of `SYNASTRY_COMPUTE_SPEC` (outer-planet-only contacts, or `sig_importance == 0`) → drop.
- Keep reception `bound`/`triplicity` but treat as minor (§4.3).

The dropped records still exist in the grounded file; the floor is applied at S3 read time and logged to the routing report. Nothing is deleted upstream.

### 4.2 Route by content, not by bucket

Each surviving `synastry` record routes to one or more sections by its `bound` points, houses, and `topic_tags`:

| section | pulls |
|---|---|
| 1 Attraction | Venus/Mars/Sun/Moon aspects; Venus↔Mars receptions; 5th/8th house overlays; Ascendant/Descendant contacts |
| 2 Emotional | Moon aspects/receptions/overlays; Moon–Saturn, Moon–Venus; 4th/IC overlays |
| 3 Communication | Mercury aspects/receptions/overlays; 3rd/9th overlays; air compatibility |
| 4 Friction | square/opposition aspects on any significators; Mars–Saturn; malefic-receiver receptions; debilitated-receiver reception |
| 5 Values/life | Venus/Jupiter/Saturn; 2nd/6th/10th overlays; earth/modality/sign compatibility |
| 6 Commitment | Saturn contacts; 7th overlays; 7th-lord reception; **mutual receptions**; Sun–Moon |
| 7 Purpose | Jupiter/Nodes; outer-planet overlays into personal houses; 9th/11th/12th overlays; MC contacts |

A record may serve two sections (a Venus–Mars square feeds both Attraction and Friction) — allowed; dedup narration in synthesis (§5).

### 4.3 Per-section ordering and cap

Within each section, order the routed records by weight (aspect salience; reception grade weight domicile 1.0 → face 0.2; mutual +0.2). Lead with the strongest. **Cap each section's input at ~8 records** so section prompts stay lean; overflow drops to the routing report, not the reading. A section with zero surviving records is written briefly or omitted — never padded.

---

## 5. Generation architecture

Mirror L4: **7 parallel section calls + 1 synthesis call** (the per-person opener can ride in synthesis or as an 8th light call).

- **Prompt caching:** cache one block across all calls = the two charts' summary + the `_CONTRACT` (mask rules, attribution rule, stance from `framing[]`, tone). Only the per-section record list varies.
- **Section call** receives: the section's capped, ordered `bound_statement`s (+ the `bound` role data so it gets person attribution right) and writes that section's prose.
- **Synthesis call** receives the seven section drafts and produces the final woven reading: resolves cross-section repetition, writes the per-person opener, and adds a short honest overall characterization (see §6 — qualitative, never a score).
- **Language:** author in **Turkish** (the quality target). Produce English by a faithful translation pass over the final Turkish, preserving every claim 1:1 so the eval statements map across both. *(Implemented 2026-09-24: synthesis emits `text_tr` only; one bounded translation call per section runs in parallel on the cheap translation model — `--translation-model`, falling back to the synthesis model — exactly as the natal pipeline does.)*

---

## 6. Output shape — qualitative, no score

Per the locked product decision: a **multi-axis qualitative profile**, not a 0–100 number. The synthesis may characterize each of the seven axes in plain language (e.g. strong / easy / effortful / volatile) and give an honest overall sense, but must **not** emit or imply a single compatibility percentage or grade. If a summary line is wanted, it names the axes' texture, not a scalar.

---

## 7. Person-attribution (hard rule)

Every person reference in the output must come from `bound`/`bound_statement`, which already encode the correct direction. **S3 must never** infer "A" or "B" from a record's `rule`, `person_a_point`, or id — those are pre-binding template labels and are wrong ~half the time (this is the exact bug fixed in Pass 1). If a section prompt needs the persons, pass `bound`, not `rule`.

Use the couple's real names/labels if supplied; otherwise stable neutral labels ("you" / "your partner" if the reading is addressed to one person, or two consistent names). Whatever the convention, `mover`/`receiver`/`p1`/`p2` map to it through `bound`.

---

## 8. Tradition mask (hard rule)

The reading presents one modern voice. The classical scaffolding is invisible. **The following vocabulary must never appear in user-facing output** (tr or en):

> reception, receive/receives/receiving/received (in the technical sense), domicile, exaltation, exalted, triplicity, bound(s), face/decan, overlay, house cusp, orb, applying/separating, significator, dignity, debility, detriment, fall, peregrine, sect, diurnal/nocturnal, and any tradition names (classical, traditional, Hellenistic, Arabic, modern, Ptolemaic).

Note the grounded `bound_statement`s sometimes still contain scaffolding (e.g. the reception sample read *"…in the received planet's affairs…"*). S3 must **translate the meaning into plain relational language**, not echo the phrasing. Reception content becomes ordinary language about welcome, accommodation, drawing-out, or holding — never "receives by domicile." A section call that emits a banned term fails the mask invariant (§10) and must be regenerated.

House meanings surface as life-areas in plain words (career, home, intimacy), never as "your 10th house."

---

## 9. Asymmetry & precision

- **Asymmetry:** one shared reading. Where a contact is directional and the asymmetry is load-bearing (one-way reception, a hard overlay one way only), state it explicitly and plainly ("this asks more emotional patience of your partner than of you"). Do not flatten genuine one-sidedness into false mutuality.
- **Precision tier:** if the grounded file was produced with `houses_valid == false` (either birth time not exact), the `overlay` records are absent. Sections that lean on house overlays (2 home, 5 life-areas, 7 purpose) must degrade gracefully — write from the aspect/reception material and **state that some house-based detail is unavailable without confirmed birth times**, rather than inventing it.

---

## 10. Invariants (fail → regenerate the offending call)

1. **Traceability.** Every claim in the reading maps to at least one routed `bound_statement`. No placement, aspect, or dynamic is asserted that isn't grounded. No invented positions.
2. **Attribution.** No person reference derives from `rule`/`person_a_point`/id; all from `bound`. Spot-check: on the test pair the Mercury contact must read as *B's* Mercury shaping *A's* public life, never the reverse.
3. **Mask.** No banned term (§8) in tr or en output.
4. **No score.** No numeric or letter-grade compatibility rating anywhere.
5. **Floor applied.** No face-grade reception and no sub-floor aspect appears in the reading.
6. **Statements traceable.** Every entry in `relationship_statements.json` links to the grounded record id(s) it came from (for S4 resonance scoring).

---

## 11. Artifacts

- `relationship_reading.tr.txt` — primary.
- `relationship_reading.en.txt` — faithful translation, claims aligned 1:1.
- `relationship_statements.json` — atomic self-scorable statements, each with source record id(s), for the eval harness.
- `relationship_reading_routing.json` — per-section record lists, floor drops, overflow drops, token usage. The audit trail.

---

## 12. Out of scope

- No composite/Davison narrative (deferred to v2).
- No predictive/timing content (transits to the synastry, relationship lots) — deferred to the predictive layer.
- No numeric scoring surface.
- No new astrology: S3 interprets only what `ground_relationship.py` grounded.
