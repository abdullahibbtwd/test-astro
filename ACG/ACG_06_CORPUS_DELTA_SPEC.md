# ACG 06: corpus delta from the ACG source text

*Follows `principles_grounding/CORPUS_DELTA_HOWTO.md` (extract → merge → finish). It runs
in parallel with Phases 1–2 and **must finish before Phase 3 (grounding)**.*

## 1. Source

`TXT/ACG/The-astro-carto-graphy-book-of-maps-the-astrology-of-relocation.txt`
(Lewis & Guttman, *The Astro\*Carto\*Graphy Book of Maps*, 1989; 648 KB, 13,017 lines, UTF-8).

This is an **OCR scan of the published book**, not a rewrite. The standing TXT rule applies
in full: the file stays in `TXT/` (gitignored), and extraction captures **technique and
meaning only, never wording**. §7 adds mechanical guards for this.

### 1.1 What's in it (verified by inspection)

| Region (approx. lines) | Content | Use |
|---|---|---|
| 1–288 | Cover, blurbs, author bios, foreword, contents | skip |
| 289–~600 | **Introduction:** 9 numbered method principles ("The Voice of Experience"); the relocated-chart concept; **one synopsis per planet** (10); **the meaning of the 4 angles** (MH/ASC/IC/DSC); the natal chart modifying the response | **High value.** Dedicated prompt (§4.1) |
| ~600–690 | "The Maps": conventions (`SU DSC` = line; `SU*UR` = latitude crossing), categories | Conventions only; no records |
| ~690–~11,000 | **~136 case studies** in 8 categories. ~700 explicit line citations; **all 40 planet × angle combinations appear** (min 9, max 28 citations) | Generalised planet-on-angle principles (§4.2) |
| ~11,000–11,750 | Nations and Events (mundane maps) | `acg_scope: mundane`, preserved, not read |
| 11,750–11,920 | Appendix A: birth-data sources | skip |
| 11,921–end | Appendix B: tables of which people had which line | **No principles.** Used only to build the name blocklist (§7) |

### 1.2 OCR hazards the extractor must handle

- **Two-column interleaving:** many lines hold the left and right columns side by side,
  separated by long whitespace runs. The text reads wrong if taken line by line.
- Map/chart label garbage (short strings of symbols, stray letters), page numbers,
  running heads ("Introduction", "Astro\*Carto\*Graphy"), and truncated first characters
  on some lines.
- Abbreviations: `SU MO ME VE MA JU SA UR NE PL` × `ASC DSC MH IC`. **Normalise MH → MC.**
  `X*Y` or `X/ANG * Y/ANG` = a latitude crossing (paran).

## 2. Pipeline (mirrors the houses delta)

```
extract_acg.py        pre-clean → de-column → chunk → LLM extract (per chunk)  → acg_raw.jsonl
consolidate_acg.py    bucket by (scope, planet, angle) → LLM merge/dedupe       → acg_consolidated.json
finish_acg.py         id assignment, schema forcing, guards (§7), backfill      → acg_principles.clean.json
ground-ready          run backfill classification                               → acg_principles.grounded.json
```

All four scripts live in `principles_grounding/`. Every step is idempotent and re-runnable
(count-free), writes its intermediate file, and logs counts.

## 3. Pre-clean and de-column (`extract_acg.py`, deterministic)

1. Split into pages on the page-number/running-head pattern. Keep the page numbers for provenance.
2. **De-column** each page. For each line, find a whitespace run of ≥ 4 spaces nearest the
   page's median split column (estimate it per page as the modal start column of right-column
   text). Put the left part in the left buffer and the right part in the right buffer. Emit the left
   buffer, then the right buffer. Single-column pages (lines with no such run) pass through unchanged.
3. Drop the noise lines: < 40% alphabetic characters, or < 4 characters after stripping.
4. Keep a `source_span: {page_start, page_end}` for every chunk.
5. **Test (C-1):** on the Introduction pages, the de-columned text of principle 6
   ("How Close Do You Have to Be?") must be contiguous: the heading and the string "700
   miles" appear within 400 characters of each other in the output, with no text from the
   right-hand column ("Famous people exhibit") between them.

Chunking: the Introduction is one chunk group (§4.1). The case studies are chunked by
**person profile** where a profile heading is detectable (name line followed by birth data);
otherwise by ~6,000-character windows with a 600-character overlap. Nations/Events chunks are
tagged `region: mundane`.

## 4. Extraction prompts (LLM; the model per `llm_client` defaults, overridable by `--model`)

Common rules for every prompt:
- Output JSON records only. Use the **project's extractor field set** (the same 9 fields as the
  houses delta, per `CORPUS_DELTA_HOWTO.md`), plus the ACG fields in §5.
- **Generalise.** No personal names, no place names, no dates, no biographical events.
  "Saturn on the MC coincided with the subject's forced resignation" → "Saturn on the
  MC: public responsibility can come with exposure to judgement and loss of standing when
  authority is misused."
- **Paraphrase.** No run of more than 7 consecutive words from the source.
- Every record names exactly one scope (§5) and, where applicable, the planet and the angle.
- Conditions only when the source states them (e.g. "when the planet is under stress in the natal
  chart"). Never invent conditions.
- `polarity`: `supportive | challenging | mixed`, as the source frames it.

### 4.1 Introduction prompt (fixed-id targets)

The Introduction must yield exactly these records (the ids are fixed; the consolidation step
must not rename them):

| id | Content to capture | scope |
|---|---|---|
| `acg-method-lines-permanent` | the lines are fixed at birth | method |
| `acg-method-time-activation` | lines are activated over time by transits/progressions (cyclo-carto-graphy) | ccg |
| `acg-method-remote-activation` | a place can affect you through dealings with it from afar | method |
| `acg-method-no-influence` | places with no line accent nothing beyond natal importance | method |
| `acg-method-crossings` | line crossings act along their whole latitude | paran |
| `acg-method-orb-distance` | effects strongest near the line, perceptible up to ~1,000 km, especially if it is the only line; the nearest line is the most potent | method |
| `acg-method-zenith` | zenith points on MC lines, latitudinal effect | zenith |
| `acg-method-polar-convergence` | many lines converging cancel out and feel intense | method |
| `acg-method-ambivalence` | no good or bad planets; the use made of them decides | method |
| `acg-method-natal-modifies-response` | the response to a planet depends on its natal condition (aspects, house) and circumstances | method |
| `acg-method-degree-of-expression` | ordinary people live the same symbols at a smaller scale | method |
| `acg-method-relocated-chart` | in a new place you meet the chart you would have had if born there; angularity = strength | method |
| `acg-angle-mc`, `acg-angle-asc`, `acg-angle-ic`, `acg-angle-dsc` | the meaning of each angle as a place of expression | angle_frame |
| `acg-general-<planet>-NN` (10 planets, 1–4 records each) | the planet's synopsis when dominant in a location: the supportive side and the challenging side as **separate records** | planet_general |

**Test (C-2):** all 16 fixed ids are present after `finish_acg.py`, and each of the 10 planets has ≥ 2
`acg-general-*` records (at least one supportive and one challenging).

### 4.2 Case-study prompt

Per chunk: extract **generalisable** principles about a planet on an angle (`line`), a latitude
crossing (`paran`), a zenith (`zenith`), activation by time (`ccg`), or a mundane map (`mundane`),
and profession–planet tendencies (as `planet_general` with the tag `vocation`). Record
`citation_count: 1` per extracted observation; consolidation sums them.

## 5. ACG record fields (added to the extractor's 9 fields)

```json
{
  "id": "acg-venus-dsc-03",
  "domain": "astrocartography",
  "tradition": "modern",
  "source": "lewis_guttman_1989",
  "acg_scope": "line | angle_frame | planet_general | method | paran | zenith | ccg | mundane",
  "about": {"type": "planet_on_angle", "planet": "venus", "angle": "DSC"},
  "polarity": "supportive | challenging | mixed",
  "sensitivity": "normal | high",
  "citation_count": 7,
  "source_span": {"page_start": 112, "page_end": 113}
}
```

`about.type` by scope:

| acg_scope | about |
|---|---|
| line | `{type: planet_on_angle, planet, angle}` |
| angle_frame | `{type: acg_angle_frame, angle}` |
| planet_general | `{type: acg_planet_general, planet}` |
| method, ccg, zenith | `{type: acg_method, slug}` |
| paran | `{type: acg_paran, planets: [p1, p2]}` (sorted) |
| mundane | `{type: acg_mundane}` |

`sensitivity: high` for any record whose meaning involves death, violence, accident, injury,
illness, crime, addiction or victimisation. (The source's Mars, Saturn, Neptune and Pluto material
contains all of these.) Spec 04 AV8 governs how these are rendered.

**v1 retrieval scopes:** `line`, `angle_frame`, `planet_general`, `method`. The scopes `paran`, `zenith`, `ccg`
and `mundane` are **preserved and excluded** (the same pattern as `predictive_scope: time_lord`).

## 6. Consolidation (`consolidate_acg.py`)

1. Bucket by `(acg_scope, planet, angle)`, or `(paran, p1, p2)`, and so on.
2. Per `line` bucket, merge near-duplicates with one LLM call per bucket. Target **4–10 records
   per planet × angle**, each with a summed `citation_count`, keeping supportive and challenging
   records separate. Buckets with fewer than 4 distinct principles keep what they have. Never pad.
3. Ids: `acg-<planet>-<angle>-NN` (`angle` lowercase, `mc` not `mh`), ordered by `citation_count`
   descending then text. `acg-general-<planet>-NN`. `acg-paran-<p1>-<p2>-NN`. Fixed ids from §4.1 are kept verbatim.
4. The report `acg_consolidation_report.json` gives per-bucket counts before and after, and the
   list of buckets below 4 records.

## 7. Guards (`finish_acg.py`, deterministic, all must pass)

| # | Guard |
|---|---|
| C-3 | **Verbatim guard:** no record text (rule + conditions + judgment) shares an **8-word** n-gram with the de-columned source (lowercased, punctuation stripped). Failures are listed and the build is rejected; re-paraphrase only the failures. |
| C-4 | **Name guard:** no record contains any surname in the blocklist built from Appendix B + the index (e.g. "Taylor", "Kennedy", "Jung"), or any city/country name from `gazetteer.json` + a country list. |
| C-5 | Every `line` record has a valid planet (10) and angle (ASC/DSC/MC/IC); no `MH` remains anywhere. |
| C-6 | Coverage: all 40 planet × angle buckets have ≥ 2 `line` records. Any bucket below 2 is listed in the report; the build is **not** rejected, but spec 03's fallback (planet-in-house records) covers it. |
| C-7 | Ids are unique; the schema is valid; `domain == "astrocartography"` on every record. |
| C-8 | Idempotence: re-running `finish_acg.py` on its own output gives byte-identical output. |

## 8. Classification and storage

- Extend `backfill.py`'s deterministic classification with an `acg-*` id branch that
  sets `about` from the id pattern (Phase 0 must paste the relevant part of backfill.py).
  Target: **100% deterministic** classification. ACG records never go to the Tier-2 LLM residual.
- Output: `principles_grounding/acg_principles.grounded.json` (+ `.sha256` sidecar, mirrored to
  wherever the reading layer loads it, as the main corpus is).
- **Separate file; not merged into `all_principles.grounded.json`.** The natal, synastry and predictive
  grounding must never see ACG records (spec 03 GA10 enforces this).

## 9. Review gate (Radul)

Before Phase 3, Radul reviews `acg_consolidation_report.json` and a sample: 2 buckets
(e.g. `saturn|MC`, `venus|DSC`) plus the 16 fixed ids. Expected size is roughly 250–400 `line`
records, 20–40 `planet_general`, 12 method/frame, and a preserved tail of paran/zenith/ccg/mundane.
Expected cost is about $1–2 in model calls.
