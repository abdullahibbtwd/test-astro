# L4_INTERPRETATION_SPEC.md

Layer 4 — Interpretation. Turns grounded principle bundles into a layered Turkish reading.
This spec is implementation instructions for the coding agent. It defines inputs, the
section model, the per-section generation calls, the single synthesis pass, the output
schema, and the invariants that hold the no-hallucination contract.

Scope for this version: **exact birth time only.** Approximate/unknown precision tiers are
out of scope and must not be handled here.

---

## 0. Vocabulary discipline (read first)

Two kinds of strings appear in this layer. They are not interchangeable.

- **Domain values** — `"Gemini"`, `"Saturn"`, `"sextile"`, `"placidus"`, etc. These are
  foreign keys into the principles dataset and the chart object. **Never rename, translate,
  or normalize them in code.** They are matched verbatim. Turkish translation of these terms
  happens only inside generated reading text, never in keys or routing logic.
- **Structural keys** — the section keys defined in §2, the chart container keys
  (`points`, `relations`, `axes`, `derived_points`, `sector`, `classifications`,
  `is_diurnal`, `scheme`, etc.), and the output JSON keys. These are stable contract keys.
  Once written here they are locked; renaming any of them breaks the render contract.

The seventeen section keys defined in §2 become foreign keys the app renders against.
Treat them with the same discipline as chart domain values: locked.

---

## 1. Inputs

L4 receives exactly two inputs.

### Input 1 — `chart` (the full chart object)
The complete, unmodified output of `compute_chart.py` (`chart.json`). Pure computed fact:
`points` (with sign/`sector`/`classifications`), `axes`, house cusps, `sector_rulers`,
`derived_points` (Fortune/Spirit), `is_diurnal`, `relations`. No interpretation.
Used by every section call as cross-reference context (e.g. when writing the Saturn bundle,
the call needs to see where the Moon is and what rules what).

### Input 2 — `personal_principles.json` (this chart's kept principles)
The per-chart output of L3 grounding (`ground.py`). **This is the file L4 reads** — not the
2,153-record corpus (that is `ground.py`'s input), and **not** `grounding_report.json`
(that is `ground.py`'s diagnostic sibling — counts and a drop log, no kept principle
content; L4 ignores it).

Top-level shape:

```json
{
  "reading": "natal",
  "kept_count": 117,
  "principles": [ { …full principle record… } ],
  "bundled_by_factor": { "Sun in Gemini": [ {…record…} ], "general": [ … ], … }
}
```

- **`principles`** — the flat array of kept records. **This is L4's primary input.** Route
  every record in it (§3).
- **`bundled_by_factor`** — the same records pre-grouped under human-readable factor labels
  (`"Sun in Gemini"`, `"placidus house 4 domain"`, `"lord of whole_sign house 1 in house 8"`).
  Convenience only; L4 does **not** route off these label strings. Route off each record's
  typed `about` block, which is more reliable than parsing English labels. `bundled_by_factor`
  may be used for logging/QA grouping.
- `reading` is the scope tag (`"natal"` for this version). `kept_count` must equal
  `len(principles)`; assert it.
- `house_policy` (since 2026-09-21) is `"placidus"`: L3 verified **every** house claim
  against the Placidus placement, whatever `house_system` the source book declared. A
  record's `about.*house_system` is therefore provenance only; L4 never routes on it
  and strips it from the prompt view.

Each record in `principles` carries the dataset fields plus the two grounding blocks
(`about`, `requires`) conforming to `grounding_schema.json`:

```json
{
  "principle_id": "moon-element-instinct-security",
  "rule": "…",
  "tradition": "modern | traditional",
  "topic_tags": ["…"],
  "conditions": "…", "judgment": "…", "notes": "…",
  "about": {
    "factor_type": "planet_in_sign | planet_in_house | planet_in_sign_and_house | aspect | dignity | node | ascendant | house_ruler | house_domain | house_lord_relative | general | unclassified",
    "point": "Sun | … | South Node",
    "sign": "Aries | …",
    "house": 1, "house_system": "placidus | whole_sign",
    "aspect": { "source": "…", "target": "…", "type": "conjunction|sextile|square|trine|opposition" },
    "dignity": "domicile | detriment | exaltation | fall | triplicity | bound | face",
    "subject_house": 1, "subject_house_system": "whole_sign",
    "placement_house": 1, "placement_house_system": "whole_sign",
    "extraction_confidence": "high | medium | low",
    "extraction_source": "deterministic | llm | manual"
  },
  "requires": [ { "kind": "sign_element" } ],
  "reclassified_from": "unclass…",   // present on some records; provenance only
  "reclassify_rule": "…"             // present on some records; provenance only
}
```

`principle_id` is the traceability anchor — every claim L4 writes carries the id(s) it rests
on. Which `about` subfields are present is governed by `factor_type` (the conditional rules
in `grounding_schema.json`); §3 routes on exactly those fields. `requires`,
`reclassified_from`, and `reclassify_rule` are provenance — **not** used for routing.

**Note on the real per-chart distribution** (from a representative natal run, 117 kept):
`general` 51, `house_domain` 36, `dignity` 14, `planet_in_sign` 7, `planet_in_house` 7,
`house_lord_relative` 1, `node` 1. Tradition split ~89 modern / 28 traditional. The large
`general` slice is why §3.3 sub-routes it rather than dumping it into one section.

---

## 2. Section model

**Basis: modern astrology.** Houses are **Placidus only** — the grounding gate
(`ground.py`, `house_policy="placidus"`) verifies every house claim against the Placidus
placement, so L4 never sees a house that is not the Placidus house and never mentions a
house system to the reader. All ten planets are full participants — Uranus, Neptune and
Pluto included — plus the lunar nodes. House rulership names the traditional ruler and,
for Scorpio / Aquarius / Pisces cusps, the modern co-ruler (Pluto / Uranus / Neptune)
carried by `chart.sector_rulers.placidus[h].modern_ruler`.

Seventeen sections, in two movements. Order below is the canonical render order.

### Movement 1 — structural portrait ("who you are")
| key | covers (chart factors) |
|---|---|
| `core_identity` | Sun and Moon **by sign**, the Ascendant, the chart ruler(s) (1st-house ruler + modern co-ruler). The spine. |
| `sun_house` | **Short note** (3–5 sentences): the Sun's Placidus house — where identity, vitality and purpose are focused. |
| `moon_house` | **Short note** (3–5 sentences): the Moon's Placidus house — where emotional needs and safety are focused. |
| `inner_drives` | Mercury, Venus, Mars — mind, values/attraction, will/action. |
| `chart_shape` | Chart-level aggregate (dominant element/modality, sect, hemisphere emphasis, tightest configurations) **and** Jupiter, Saturn, Uranus, Neptune, Pluto and the nodes read individually by sign and house as personal factors. |

### Movement 2 — one section per Placidus house ("where it lands")
| key | house | reader-facing name (EN) | reader-facing name (TR) |
|---|---|---|---|
| `identity` | H1 | Identity | Kimlik |
| `values_money` | H2 | Values and Money | Değerler ve Para |
| `communication_learning` | H3 | Communication, Studying, Siblings | İletişim, Öğrenim ve Kardeşler |
| `family_home` | H4 | Family and Home | Aile ve Yuva |
| `joy_creativity_children` | H5 | Joy, Artistic Talents and Kids | Neşe, Sanatsal Yetenekler ve Çocuklar |
| `health_routine_pets` | H6 | Health, Routine, Pets | Sağlık, Rutin ve Evcil Hayvanlar |
| `partnerships` | H7 | Partnerships | Ortaklıklar |
| `transformation_intimacy` | H8 | Transformation and Intimacy | Dönüşüm ve Yakınlık |
| `travel_philosophy` | H9 | Distant Travels and Philosophy | Uzak Seyahatler ve Felsefe |
| `status_vocation` | H10 | Social Status and Vocation | Toplumsal Statü ve Meslek |
| `friendships_future` | H11 | Friendships and the Future | Arkadaşlıklar ve Gelecek |
| `subconscious_solitude` | H12 | Subconscious and Solitary | Bilinçaltı ve Yalnızlık |

Notes:
- Every house has its own section; there are no paired houses any more. Each house
  section covers the house's meaning, **every planet placed in it (outer planets
  included)**, and the cusp sign with its ruler(s) and their placement.
- `sun_house` / `moon_house` are exempt from the §5.2 callback-trimming: they are the
  reading's deliberately short "luminary by house" notes and must stay self-contained.
- A section with no principles routed to it (rare, but possible for sparse charts)
  is **omitted entirely** from the output — not emitted empty. The no-hallucination contract
  forbids writing a section with nothing to ground it.
- Section titles are display-only (`l4_render.py`). House sections render as
  "N. Ev — <name>" / "House N — <name>"; the luminary notes render with the actual house
  ("Güneş 9. Evde" / "Sun in the 9th House") read from the §6 `house` field.

---

## 3. Principle → section routing

Deterministic. Each grounded principle is assigned to one or more sections by its
`about` block. **Overlap is allowed and intended** — do not dedup at routing time; dedup
happens only in synthesis (§5). The goal is that each section is *context-complete* on its
own so the section calls run in parallel with no cross-dependencies.

### 3.0 Shared helpers (used by the rules below)

- **`section_for_point(p)`** — Movement-1 home of a point:
  - Sun, Moon → `core_identity`
  - each **chart ruler** — the placidus 1st-house `ruler` **and** its `modern_ruler`
    when different (resolve via `sector_rulers` in `chart`) → `core_identity`
  - Mercury, Venus, Mars → `inner_drives`
  - Jupiter, Saturn, Uranus, Neptune, Pluto, North Node, South Node → `chart_shape`
- **`luminary_section(p)`** — Sun → `sun_house`, Moon → `moon_house` (house records only).
- **`domain_section_for_house(h)`** — Movement-2 home of a house number, per the §2 map
  (one section per house: 1→`identity`, 2→`values_money`, … 12→`subconscious_solitude`).
- **House policy (locked): Placidus.** L3 has already verified every house claim in
  Placidus (§1 `house_policy`). `about.*house_system` is provenance; the router never
  branches on it and no record is "classical texture" merely for coming from a whole-sign
  source. `texture: classical` remains for dignities and `house_lord_relative` (classical
  apparatus by construction).
- **Point-occupancy & rulership (from `chart`, not from `about`):** independently of the
  rules below, for every subject point `p` of a record, also route the record to
  `domain_section_for_house(house_of(p))` and to `domain_section_for_house(h)` for every
  house `h` that `p` rules — as traditional `ruler` **or** as `modern_ruler`. Use the
  **placidus** `sector` for occupancy. (This is what makes Venus-in-H7 land in both
  `inner_drives` and `partnerships`, and Pluto material land in the house Pluto occupies.)

### 3.1 Routing by `about.factor_type`

1. **`planet_in_sign`** → `section_for_point(about.point)`.
2. **`planet_in_house`** → `domain_section_for_house(about.house)` **and** either
   `luminary_section(about.point)` when the point is the Sun or the Moon (the house record
   feeds the short "by house" note, not `core_identity`, which reads the luminaries by
   sign) or `section_for_point(about.point)` otherwise.
3. **`planet_in_sign_and_house`** → `section_for_point`, `luminary_section` (if a luminary)
   **and** the house domain.
4. **`dignity`** → `section_for_point(about.point)`. (Dignity is character/condition of the
   point; it is classical apparatus → flag `texture: classical`.)
5. **`node`** → `section_for_point(about.point)` (Nodes resolve to `chart_shape`) **and**, if
   `about.house` present, `domain_section_for_house(about.house)`.
6. **`aspect`** → for **each** of `about.aspect.source` and `about.aspect.target`:
   route to `section_for_point(endpoint)` **and** `domain_section_for_house(house_of(endpoint))`.
   If both endpoints are among {Sun, Moon, Mercury, Venus, Mars}, also `inner_drives`.
   The aspect additionally informs `chart_shape` (configuration).
7. **`ascendant`** (keyed on `about.ascendant_sign`) → `core_identity` **and**
   `identity` (H1). The rising sign is both spine and the H1 section.
8. **`house_ruler`** (`about.point` rules `about.house`) →
   `domain_section_for_house(about.house)` **and** `section_for_point(about.point)`.
9. **`house_domain`** — **polymorphic, branch on which key is present** (schema allows
   either, never `sign`):
   - if `about.point` present (element-of-sign character delineation) →
     `section_for_point(about.point)`. **Movement 1.** (These are *not* house-domain reads
     despite the type name; they describe the point's elemental character.)
   - if `about.house` present (genuine house-domain) →
     `domain_section_for_house(about.house)` **Movement 2** — **and** `luminary_section(L)`
     for every luminary `L` whose placidus house is `about.house` (the house's meaning
     grounds the luminary's short note).
10. **`house_lord_relative`** (no `point`; keyed on `subject_house` + `placement_house`) →
    `domain_section_for_house(about.subject_house)` — the **ruled** domain (how that house's
    lord disposes its affairs). Route on `subject_house`, not `placement_house`. Records are
    classical apparatus → flag `texture: classical`.
    *Note: in the current dataset only `subject_house: 1` is populated, so in practice these
    land in `identity`. The rule generalizes if more are added later.*
11. **`general`** → **sub-route by `topic_tags`**, do not dump wholesale into one section.
    `general` is the largest kept slice and is heterogeneous (chart-ruler material,
    angle/MC material, generational outer-planet texture, and interpretive methodology).
    Apply this priority ladder, first match wins; default last:
    - tags include **ascendant ruler / chart ruler / ruling planet** → `core_identity`.
    - tags include **Midheaven / MC / MC ruler** → `vocation_public`.
    - tags name a **specific house lord** (e.g. "lord of 2nd house", "lord of 3rd house") →
      `domain_section_for_house(that house)`.
    - tags name **one or two specific planets** (any of the ten — Uranus, Neptune and
      Pluto included; in the modern reading the outer planets are personal factors, never
      mere backdrop) → `section_for_point(that planet)` **and** the point-occupancy &
      rulership sections of that planet (§3.0). Naming three or more planets signals
      class-level methodology → default bucket.
    - **default** → `chart_shape` (interpretive methodology / whole-chart weighting:
      element balance, orbs, dignity modulation, aspect priority). These are the
      "how to read the chart" principles and belong with overall shape.
    Gate the default bucket by confidence: `low`-confidence `general` records that hit the
    default `chart_shape` bucket are included but marked low-salience so synthesis can prune
    them first if `chart_shape` is overfull (see §5). Never drop a kept record silently.

### 3.2 `unclassified` and unmatched records

In practice L3 drops `unclassified` records before L4 (in the representative natal run, zero
survived into the kept set — they fail the reading-scope/subject gates). So L4 should not
expect them. **If** an `unclassified` record does appear in `principles`, route it to
`chart_shape` as low-salience only when `extraction_confidence` is `high` or `medium`; drop
(and log) `low`-confidence unclassified. Never fabricate a domain home for it.

If a record matches no rule in §3.1 and is not `unclassified`, log it and drop it from
sectioning — a routing gap to surface, never a home to invent.

---

## 4. Per-section generation calls

One call per non-empty section. Parallelizable; no call depends on another's output.

Each call receives:
- the section key and its theme description (from §2),
- the **routed principles** for that section — each carrying its `principle_id`,
  `tradition`, `rule`, and a `texture` flag (`classical` where §3 set it, else absent),
- the **full `chart` object** for cross-reference.

Each call must produce, for its section:
- Turkish reading text for that section,
- an internal per-claim trace: every sentence (or claim unit) tagged with the
  `principle_id`(s) it rests on. This trace is retained through synthesis and stripped at
  render (see §6 output schema — `claims[]`).

Generation rules inside each section call:

- **Modern psychological reading is the body. Classical heritage is texture.**
  Soft separation: weave classical material in as enrichment and cultural color. **Never
  label** anything "modern" or "classical" to the reader. No tradition names surface in the
  output text. A principle arrives marked `texture: classical` when it is classical
  apparatus (dignities, lord-relative, sect) — treat those as texture by construction:
  they may color the read but must never carry the section's verdict alone.
- **Framework: modern astrology, Placidus houses.** Never name a house system to the
  reader. Uranus, Neptune and Pluto are read by house (and sign as background) as personal
  factors whenever principles support it. Rulership names the traditional ruler with the
  modern co-ruler alongside (Pluto/Mars, Uranus/Saturn, Neptune/Jupiter).
- **Tradition priority on conflict:** when a `modern` and a `traditional` principle in the
  same section disagree on verdict, the modern reading governs the actual interpretation;
  the classical one may still contribute texture but must not set the verdict. (This mirrors
  the project-wide tradition hierarchy.)
- **Valence handling:** a classically negative principle is not delivered as a hard verdict.
  Render its content as perspective/heritage texture; the modern reframe governs the read.
  No fatalistic language.
- **Cultural framing:** Arabic-Islamic / Ottoman material is framed as cultural-historical
  heritage, never as religious endorsement.
- **No claim without a ground.** Every interpretive statement traces to at least one
  `principle_id` from the routed principles. The model may use the `chart` object for factual
  cross-reference (positions, rulerships) but must not derive new interpretive claims from
  raw chart facts that no principle supports.
- Second person, warm, plain Turkish. (Voice is finalized in synthesis; section calls need
  not perfectly match each other — that's what the synthesis pass fixes.)

---

## 5. Synthesis pass (single, global)

One pass over **all** section drafts together. It does four jobs, in this priority order.
It is a rewrite/prune pass — **it never adds interpretive claims.**

1. **Voice unification** — rewrite all sections into one consistent Turkish voice
   (second person, warm, psychological-primary). This is the primary reason the pass exists;
   parallel section calls will drift in register.

2. **Cross-section dedup** — when the same chart fact surfaces in multiple sections
   (e.g. Venus-in-H7 in both `inner_drives` and `relationships`):
   - Pick the **canonical home** = the Movement-2 **house section** (the "where it lands"
     section), not the structural section. Domain wins. **Exception:** `sun_house` and
     `moon_house` are deliberately short dedicated notes — keep them intact (3–5
     sentences), never trim them to a callback.
   - In the canonical home, keep the full treatment.
   - In the other section, trim to a one-line callback that points forward — do **not**
     delete the fact silently, and do not repeat the full treatment.
   - If two sections interpret the same fact *differently*, the tradition-priority rule
     (§4) decides which framing is canonical.

3. **Texture balancing** — enforce soft separation globally: if any section leaned too
   heavily classical, re-weight toward the modern psychological body. Classical stays
   texture, never dominant, never labeled.

4. **Contradiction reconciliation** — genuine chart tensions (e.g. Mars square Venus
   reading as both "drive" and "relational friction") must be named as *productive tension*,
   not left as two sections silently disagreeing. Name the tension; don't resolve it into
   blandness, and don't introduce a new claim to bridge it.

5. **`chart_shape` salience pruning** — `chart_shape` receives the `general`-default and
   generational records and can over-accumulate. If it runs long, prune in this order:
   first low-salience generational backdrop, then low-confidence `general`-methodology
   records, keeping the highest-confidence structural claims (sect, dominant element/
   modality, tightest configuration). Pruning **removes** claims (allowed); it never adds.
   Target a `chart_shape` that reads as a tight structural portrait, not a methodology dump.

**Hard invariant for synthesis:** it may only **rewrite, merge, or remove** existing claims
and **rephrase** text. It may **never introduce a claim absent from the section drafts.**
Because it only removes or rephrases, every surviving claim still carries its
`principle_id` trail intact to render-time stripping. After synthesis, re-attach/preserve
the `claims[]` trace for every retained claim.

---

## 6. Output schema

A single JSON object, section-keyed, canonical order from §2. Omitted sections (no bundles)
simply do not appear.

```json
{
  "schema_version": "l4.v1",
  "precision_tier": "exact",
  "sections": [
    {
      "key": "core_identity",
      "movement": 1,
      "text_tr": "….",
      "claims": [
        { "claim_span": "….", "principle_ids": ["…", "…"] }
      ]
    }
  ]
}
```

- `key` — one of the seventeen §2 keys. Locked foreign key.
- `movement` — `1` or `2`.
- `house` — present on every Movement-2 section (its house number) and on `sun_house` /
  `moon_house` (the luminary's Placidus house). Absent on the other Movement-1 sections.
- `text_tr` — the synthesized Turkish reading for the section. This is what renders.
- `claims[]` — the internal trace. `claim_span` references the part of `text_tr` it grounds;
  `principle_ids` are the supporting `principle_id`s. **This array is retained for QA and
  stripped at render** — the app renders `text_tr` only. Every claim_span must carry ≥1
  principle_id; a claim with an empty `principle_ids` is a contract violation and must fail
  validation, not ship.

---

## 7. Invariants (the contract)

These hold at generation time and must be enforced, not assumed.

1. **Every claim traces to a grounded principle ID.** No `claims[]` entry has empty
   `principle_ids`. Validate before output.
2. **Synthesis adds nothing.** No claim in the final output lacks a `principle_id` that was
   present in a section draft. Synthesis only rewrites/prunes.
3. **No tradition labels reach the reader.** The strings "modern"/"classical"/"traditional"
   (and tradition-name equivalents) never appear in `text_tr`.
4. **No empty sections.** A section with no routed principles is omitted, never emitted blank.
5. **Domain values are never renamed in code.** Only translated inside reading text.
6. **Section keys are locked.** The seventeen keys are the render contract.
7. **Exact-time only.** `precision_tier` is always `"exact"` in this version; do not
   implement approximate/unknown handling.

---

## 8. Out of scope (do not build)

- Approximate / unknown birth-time tiers.
- Predictive/transit reading (separate layer).
- Any UI rendering — L4 emits JSON only.
- Re-deriving chart facts — L4 reads `chart`, never recomputes it.
