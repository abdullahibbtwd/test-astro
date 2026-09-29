# CORPUS_DELTA_HOWTO.md — adding a new source to the principles corpus

The natal reading only ever says what a grounded principle supports, so a gap in the
corpus is a gap in the reading. This is the procedure for adding a **delta** (a new
set of records from one source) without disturbing the existing corpus. It is the
generalised form of `TXT/PREDICTIVE_EXTRACTION_MERGE.md`, and it is what the
planets-in-houses delta (2026-09-21) followed.

## The four steps

| Step | Script | Output |
|---|---|---|
| 1. Extract | a per-source extractor, e.g. `extract_houses.py` | `<tag>_delta.raw.json` (9 extractor fields, no `about`/`requires`) |
| 2. Merge into the clean corpus | `merge_houses_delta.py` (copy + adapt per source) | `<tag>_delta.clean.json`; appended to BOTH `TXT/all_principles.clean.json` and `principles_grounding/all_principles.clean.json`; backups `*.backup-pre-<tag>.json`; merge + near-dupe reports |
| 3. Ground + gate + append | `finish_delta.py --delta-clean <tag>_delta.clean.json --tag <tag> --expect <factor_type>` | `<tag>_delta.grounded.json`; appended to `all_principles.grounded.json` (+ `.sha256`), mirrored to `Interpretation_layer/`, added to `all_principles_grounded.with_predictive.json`; `all_principles_grounded_reclassified.json` refreshed |
| 4. Verify | `pytest Interpretation_layer/test_l4.py principles_grounding/test_ground_house_policy.py` + a dry run of `ground()` on a chart | section counts move as expected |

## What the extractor must guarantee (so grounding is deterministic)

`backfill.py` Tier-1 classifies a record from its **id + conditions + tags**. Force
these in code, never trust the model for them:

- `principle_id` = `{planet}-{N}{st|nd|rd|th}-{theme-slug}` for planet-in-house
  (`sun-9th-recognition-drive`), `{planet}-sign-{sign}-{slug}` for planet-in-sign.
- `conditions` = `{"planet": "Sun", "house": 9}` (dict form), or `["Sun in Aries"]`.
- `topic_tags` ⊇ `{"Sun", "9th house"}`.
- `domain` and `tradition` forced (`natal`, `modern`); the model never sets them.
- Exactly the nine extractor fields: `principle_id, domain, topic_tags, rule,
  conditions, judgment, attribution_in_text, notes, tradition`.

Modern + unmarked house records default to `house_system: placidus`; traditional to
`whole_sign`. Either way the natal gate verifies the house in **Placidus** (house
policy, `ground.py`).

## Why `finish_delta.py` and not `backfill.py --in delta`

`backfill.py`'s build gate checks corpus-wide natal floors, so a delta-only run is
always rejected (that is what `predictive_delta.grounded.rejected.json` is).
`finish_delta.py` runs the same deterministic `backfill()` and applies the gate that
fits a delta: every record resolved at high confidence to the expected factor type,
schema-valid, zero invariant violations, no id collisions, count parity.

## Re-running

Both merge and finish refuse to run twice on the same delta (the ids are already in
the corpus). To redo a delta: restore from the `*.backup-pre-<tag>.json` files, delete
the delta outputs, and start again.

## Remaining known gaps (2026-09-21)

- The planets-in-houses source also carries, per chapter, "House Polarities" text:
  Sun-in-house × Moon-in-house combinations (144). The schema has no compound factor
  type for two placements, so `extract_houses.py` cuts them out. Adding a
  `luminary_polarity` factor (gate: Sun house AND Moon house both match) would let the
  Sun/Moon notes use them.
- Rising-sign delineations (Ascendant sign × 12): none in the corpus.
- Modern planets-in-signs for Uranus / Neptune / Pluto: none (generational by design).
- Modern aspect delineations: none (`factor_type: aspect` count is 0).
