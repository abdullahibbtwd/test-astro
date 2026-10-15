# CHART_SECTOR_RULERS_SPEC.md

Spec for adding a precomputed **sector rulership** block to `compute_chart.py`.

This is an additive change to Layer 1 (the chart computation engine). It introduces
no new astronomy and no ephemeris calls — it is pure restructuring of facts the
engine already computes, exposed in a form Layer 3 can *read* rather than *derive*.

---

## 1. Why this exists

Layer 3 (interpretation) must read precomputed facts, never derive them. The
"life-domain" movement of the reading needs, for each house (sector), the planet
that **rules** it and where that ruler sits — so the engine can say, as fact,
"the ruler of sector 1 is Venus, placed in Taurus in sector 8."

Today the chart exposes raw cusp longitudes (`sectors.placidus_cusps`,
`sectors.whole_sign_cusps`) but does **not** expose the sign on each cusp or its
ruler. Computing that requires two derivation steps — longitude → sign, and
sign → ruler — which are exactly the kind of derivation the two-layer boundary
forbids Layer 3 from performing. The engine already performs both steps for every
*point* (each point carries `sign` and `classifications.sign_ruler`); it simply
has never applied them to *cusps*. This spec closes that inconsistency.

---

## 2. Scope

- **In:** a new top-level `sector_rulers` block, computed for **both** house
  systems already present (`placidus`, `whole_sign`).
- **Out:** no change to any existing field, no new house system, no time-precision
  handling (exact-time charts only for now — see §8).
- **Addendum (2026-09-21):** each block ALSO carries the modern co-ruler of the cusp
  sign — see §11. This is additive; `ruler` and every dignity stay on the
  traditional map.

---

## 3. Canonical ruler map — reuse, do not redefine

> **HARD REQUIREMENT.** The engine already commits to a sign → ruler mapping: it
> is whatever function/table currently populates `classifications.sign_ruler` for
> points. The sector-ruler computation **MUST** call that same function/table.
> Do **not** introduce a second ruler map. Two ruler maps in one chart would let
> a house ruler and a point's `sign_ruler` disagree for the same sign, which
> corrupts the principles foreign keys.

For verification only (not as a source of truth), the existing map is the
traditional domicile rulership and must resolve to:

| Sign | Ruler | | Sign | Ruler |
|---|---|---|---|---|
| Aries | Mars | | Libra | Venus |
| Taurus | Venus | | Scorpio | Mars |
| Gemini | Mercury | | Sagittarius | Jupiter |
| Cancer | Moon | | Capricorn | Saturn |
| Leo | Sun | | Aquarius | Saturn |
| Virgo | Mercury | | Pisces | Jupiter |

If the engine's existing map does not match this table, **stop and surface it** —
do not silently reconcile. The mismatch is a domain decision for the owner, not
an implementation detail.

---

## 4. Output shape

Add one top-level key `sector_rulers`, a sibling of `sectors`, `axes`,
`derived_points`. It contains one sub-object per house system. Each maps the
string house number `"1"`–`"12"` to a ruler record.

```json
"sector_rulers": {
  "placidus": {
    "1": {
      "sign_on_cusp": "Libra",
      "ruler": "Venus",
      "ruler_sign": "Taurus",
      "ruler_sector": 8
    },
    "2": { "...": "..." }
  },
  "whole_sign": {
    "1": { "...": "..." }
  }
}
```

### Field semantics

| Field | Meaning | Type | Source |
|---|---|---|---|
| `sign_on_cusp` | Zodiac sign on this house's cusp | string (sign FK) | `int(cusp_longitude // 30) % 12` → sign name |
| `ruler` | Domicile ruler of `sign_on_cusp` | string (planet FK) | canonical map (§3) |
| `ruler_sign` | Sign the ruling planet occupies | string (sign FK) | the ruler's own `point.sign` |
| `ruler_sector` | House the ruling planet occupies **in this same house system** | integer 1–12 | the ruler's own `point.sector.<system>` |

### Self-containment rule for `ruler_sector`

`ruler_sector` is reported **in the house system of the block it appears in**.
Inside `sector_rulers.placidus`, `ruler_sector` is the ruler's Placidus house;
inside `sector_rulers.whole_sign`, it is the ruler's Whole Sign house. Each block
is internally consistent in a single house system; never mix systems within a
block.

### Denormalization note

`ruler_sign` and `ruler_sector` duplicate data already in `points[]`. This is a
deliberate, safe denormalization: all three values are produced in the same
deterministic pass from the same chart, so they cannot drift, and pre-joining them
means Layer 3 reads "ruler of X is Venus in Taurus in sector 8" as one atomic fact
with no cross-referencing. The canonical source remains `points[]`; this block is
a convenience projection.

---

## 5. FK discipline

`sign_on_cusp`, `ruler`, `ruler_sign` are **domain values** — foreign keys into
the principles dataset. Emit them in the exact casing/spelling used everywhere
else in the chart (`"Venus"`, `"Taurus"`, `"Libra"`). Do not lowercase,
abbreviate, or localize. Structural keys (`sector_rulers`, `sign_on_cusp`, etc.)
follow the project's renamed structural vocabulary and are free to be what this
spec names them.

---

## 6. Determinism & ordering

- Every house 1–12 is present in every block. There are no nulls and no omissions:
  all twelve signs have a domicile ruler under the traditional map, so a ruler
  always resolves.
- Keys `"1"`–`"12"` as strings (JSON object keys). Insertion order ascending 1→12
  for readability; consumers must not depend on order.
- Output is a pure function of the input chart: identical birth data → byte-identical
  `sector_rulers`.

---

## 7. Types & schema

Extend the existing artifacts from `CHART_TYPES_SPEC.md`.

### TypedDict

```python
from typing import TypedDict, Literal, Dict

class SectorRuler(TypedDict):
    sign_on_cusp: str      # sign FK
    ruler: str             # planet FK
    ruler_sign: str        # sign FK
    ruler_sector: int      # 1..12, in this block's house system

class SectorRulers(TypedDict):
    placidus: Dict[str, SectorRuler]    # keys "1".."12"
    whole_sign: Dict[str, SectorRuler]  # keys "1".."12"
```

Add `sector_rulers: SectorRulers` to the top-level chart TypedDict.

### JSON Schema (Draft 2020-12) fragment

```json
"sector_rulers": {
  "type": "object",
  "required": ["placidus", "whole_sign"],
  "additionalProperties": false,
  "properties": {
    "placidus":   { "$ref": "#/$defs/sectorRulerMap" },
    "whole_sign": { "$ref": "#/$defs/sectorRulerMap" }
  }
}
```

```json
"$defs": {
  "sectorRulerMap": {
    "type": "object",
    "required": ["1","2","3","4","5","6","7","8","9","10","11","12"],
    "additionalProperties": false,
    "patternProperties": {
      "^(1[0-2]|[1-9])$": { "$ref": "#/$defs/sectorRuler" }
    }
  },
  "sectorRuler": {
    "type": "object",
    "required": ["sign_on_cusp","ruler","ruler_sign","ruler_sector"],
    "additionalProperties": false,
    "properties": {
      "sign_on_cusp": { "type": "string" },
      "ruler":        { "type": "string" },
      "ruler_sign":   { "type": "string" },
      "ruler_sector": { "type": "integer", "minimum": 1, "maximum": 12 }
    }
  }
}
```

Add `sector_rulers` to the top-level schema's `required` array.

---

## 8. Extension point (do NOT build now)

When approximate/unknown birth time is introduced later, house cusps may be
absent (no time → no houses). At that point `sector_rulers` must be **structurally
omitted** rather than nulled, consistent with the project's absent-field rule. Mark
the computation with a guard comment:

```python
# EXTENSION POINT: when time_precision != "exact" and cusps are unavailable,
# omit sector_rulers entirely (structural omission, not null). Not implemented:
# current scope is exact-time charts only.
```

For now, assume cusps are always present.

---

## 9. Validation (adversarial — verify rejection, not just acceptance)

Write tests that would **fail loudly** on the likely mistakes:

1. **Cross-map consistency.** For each point P, the `sign_ruler` the engine
   assigns to P's sign must equal the `ruler` this block assigns to any house
   whose `sign_on_cusp` equals P's sign. If they ever differ, two ruler maps have
   crept in — fail.
2. **Denormalization integrity.** For every house record, `ruler_sign` must equal
   `points[ruler].sign`, and `ruler_sector` must equal
   `points[ruler].sector.<that block's system>`. Mutate one and confirm the test
   fails.
3. **Completeness.** Each block has exactly keys `"1"`–`"12"`; assert a block with
   11 keys is rejected by the schema, and a block with a `"13"` key is rejected by
   `additionalProperties: false`.
4. **System self-containment.** Construct a fixture where a ruler sits in
   different houses under the two systems (e.g. a planet near a cusp). Confirm the
   Placidus block reports its Placidus house and the Whole Sign block reports its
   Whole Sign house — never crossed.
5. **FK casing.** Assert all `sign_on_cusp` / `ruler` / `ruler_sign` values are
   members of the canonical sign/planet vocabularies with exact casing; a
   lowercased value must fail.

### Reference fixture (1990-06-15, Libra rising — the working chart)

Placidus block must compute exactly:

| House | sign_on_cusp | ruler | ruler_sign | ruler_sector |
|---|---|---|---|---|
| 1 | Libra | Venus | Taurus | 8 |
| 2 | Scorpio | Mars | Aries | 6 |
| 3 | Sagittarius | Jupiter | Cancer | 10 |
| 4 | Capricorn | Saturn | Capricorn | 4 |
| 5 | Aquarius | Saturn | Capricorn | 4 |
| 6 | Pisces | Jupiter | Cancer | 10 |
| 7 | Aries | Mars | Aries | 6 |
| 8 | Taurus | Venus | Taurus | 8 |
| 9 | Gemini | Mercury | Gemini | 8 |
| 10 | Cancer | Moon | Pisces | 5 |
| 11 | Leo | Sun | Gemini | 9 |
| 12 | Virgo | Mercury | Gemini | 8 |

Use this as a golden test for the Placidus block. (Generate the Whole Sign golden
values from the same chart once implemented; do not hand-author them.)

---

## 10. Acceptance checklist

- [ ] `sector_rulers` present at top level, both systems, houses 1–12 each.
- [ ] Ruler values produced by the engine's existing sign→ruler map (no new map).
- [ ] `ruler_sector` reported in each block's own house system.
- [ ] TypedDict + JSON Schema updated; `sector_rulers` in top-level `required`.
- [ ] All five adversarial tests pass; reference fixture matches §9 table exactly.
- [ ] No existing field changed; no ephemeris call added.
- [ ] Extension-point guard comment present for future time-precision work.


---

## 11. Addendum — modern co-ruler (added 2026-09-21)

The reading moved to a modern-astrology basis (Placidus houses, ten planets). Each
`sector_rulers.<system>.<house>` block now also carries the **modern** ruler of the
cusp sign, so the interpretation layer can name "Mars (co-ruled by Pluto)" as fact:

```json
{
  "sign_on_cusp": "Scorpio",
  "ruler": "Mars",            "ruler_sign": "Aries",          "ruler_sector": 6,
  "modern_ruler": "Pluto",    "modern_ruler_sign": "Scorpio", "modern_ruler_sector": 1
}
```

- `modern_ruler` = `MODERN_DOMICILE[sign_on_cusp]`: Pluto for Scorpio, Uranus for
  Aquarius, Neptune for Pisces, otherwise identical to `ruler`.
- `modern_ruler_sign` / `modern_ruler_sector` follow the same self-containment rule
  as `ruler_sign` / `ruler_sector` (§4).
- §3 still holds for `ruler`: the traditional map is the ONE map dignities use.
  `MODERN_DOMICILE` feeds nothing else — it is a co-ruler annotation, not a second
  dignity scheme.
- Types: `chart_types.ModernRuler`, schema `$defs.ModernRuler`.
