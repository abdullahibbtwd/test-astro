# RENAME_SPEC.md — instructions for the coding agent

You are modifying `compute_chart.py` so the **output data structure** uses
technical / data-structure terminology instead of astrology-flavored container
names. This is a rename of *structural keys only*. Do not change any computed
values, any math, any astrology logic. The goal is purely to make the emitted
object read as a clean typed data structure.

Read all of section 1 before touching anything — it is the rule that prevents
you from breaking the system.

---

## 1. The one rule that must not be broken: keys vs. values

The output contains two kinds of strings, and they are treated completely
differently.

**Structural keys** = the names of fields/slots in the data structure
(`bodies`, `houses`, `aspects`, `sect`, `dignities`, `a`, `b`, `system`, …).
These are ours. **Rename these** per the mapping in section 2.

**Domain values** = the string *contents* of fields
(`"Gemini"`, `"Saturn"`, `"sextile"`, `"placidus"`, `"whole_sign"`, `"day"`,
`"Mercury"`, `"conjunction"`, …). These are **foreign keys** into a separate
dataset (`all_principles.json`) and into the downstream interpretation layer.
They are the join column between the chart and the meaning layer.
**NEVER rename, recode, abbreviate, or translate a domain value.**

Examples to make the boundary unambiguous:

- `"sign": "Gemini"` → the *key* `sign` may be kept or renamed if listed in
  section 2; the *value* `"Gemini"` must stay exactly `"Gemini"`.
- `"system": "modern"` → rename the key to `scheme` (section 2), but the value
  `"modern"` stays `"modern"`. Same for `"whole_sign"`.
- `"placidus"` and `"whole_sign"` appearing as **keys** inside the sector object
  (`{"placidus": 9, "whole_sign": 9}`) are a special case — see section 3.

If you are ever unsure whether a string is a key or a value: keys are on the
left of the colon and name a slot; values are on the right and carry data. When
in doubt, do not rename it.

---

## 2. Structural key renames (apply exactly)

Rename the following output keys. Left = current, right = new. Anything not in
this table keeps its current name (most leaf fields are already technical:
`longitude`, `sign`, `sign_index`, `degree_in_sign`, `speed`, `retrograde`,
`orb`, `applying`, `confidence`, `meta` — leave all of these unchanged).

| Current key | New key | Notes |
|---|---|---|
| `bodies` | `points` | the array of chart entities |
| `aspects` | `relations` | this array is an edge list over `points` |
| `a` (inside a relation) | `source` | graph-edge endpoint |
| `b` (inside a relation) | `target` | graph-edge endpoint |
| `system` (inside a relation) | `scheme` | value stays `"modern"` / `"whole_sign"` |
| `house` (per-point object) | `sector` | the 12-fold partition placement for one point |
| `houses` (top-level cusp object) | `sectors` | the cusp geometry |
| `dignities` (per-point object) | `classifications` | table-lookup classifications |
| `sect` (top-level `"day"`/`"night"`) | `is_diurnal` (boolean) | **transform, see section 4** |
| `angles` | `axes` | Ascendant/MC reference axes |
| `lots` | `derived_points` | points computed by formula, not observed |

**KEEP `traditional` as-is.** Do not rename it. It stays the per-point boolean
flag named `traditional` with value `true`/`false`.

---

## 3. Special case: house-system keys inside `sector` / `sectors`

Today the per-point placement looks like:

```jsonc
"house": { "placidus": 9, "whole_sign": 9 }
```

After the `house` → `sector` rename it becomes:

```jsonc
"sector": { "placidus": 9, "whole_sign": 9 }
```

Here `placidus` and `whole_sign` are acting as **keys**, but their names are
also domain identifiers used by the principles dataset to know which house
system a value came from. **Keep these sub-keys exactly as `placidus` and
`whole_sign`.** Do not rename them to e.g. `system_a`/`system_b`. The same
applies to the cusp lists, which become:

```jsonc
"sectors": {
  "placidus_cusps": [...] | null,   // null above the polar circle — preserve this
  "whole_sign_cusps": [...]
}
```

Keep `placidus_cusps` / `whole_sign_cusps` as-is.

---

## 4. The one value transform: `sect` → `is_diurnal`

This is the only place a value changes form, and it is a lossless boolean
collapse, not a rename of a domain token.

- Current: top-level `"sect": "day"` or `"sect": "night"`.
- New: top-level `"is_diurnal": true` (was `"day"`) or `false` (was `"night"`).

Apply the same transform **everywhere sect is consumed internally** so behavior
is identical:
- The dignity/classification code that selects the triplicity ruler by sect must
  now branch on the boolean (`is_diurnal` True → day ruler, False → night ruler,
  and the "sect unknown" path is unchanged: when there is no birth time, the
  field is absent and the triplicity ruler stays `null`).
- The lots/`derived_points` formulas that swap by sect must branch on the
  boolean.

Do **not** rename the `"day"`/`"night"` strings anywhere they are a *domain
value inside the dataset* — this transform applies only to the chart's own
sect field, which we are redefining as a boolean. Inside
`classifications.triplicity_rulers_all` the sub-keys `day` / `night` /
`participating` are structural keys describing the Dorothean scheme — **keep
those as-is** (they are not the chart's sect field).

---

## 5. `derived_points` shape

`lots` becomes `derived_points`. Keep the inner structure identical: an object
keyed by the lot name with a point object value.

```jsonc
"derived_points": {
  "fortune": { "longitude": ..., "sign": "...", "sign_index": ..., "degree_in_sign": ... },
  "spirit":  { "longitude": ..., "sign": "...", "sign_index": ..., "degree_in_sign": ... }
}
```

The keys `fortune` / `spirit` are domain values (names of specific lots used by
the principles dataset) — **keep them as-is**. Only the container key `lots`
changes to `derived_points`.

Conceptual note for your understanding (do not encode this as text in the
output): these are called "derived" because their coordinates are computed by a
formula over other points (e.g. Fortune = Ascendant + Moon − Sun in a diurnal
chart), as opposed to the `points` array whose coordinates are read from the
ephemeris. Like the axes and sectors, derived_points depend on the Ascendant,
so they remain **absent** (not null) when there is no birth time.

---

## 6. Preserve the absence/nullability contract exactly

The rename must not weaken the existing structural guarantees. After renaming,
the following must still hold:

- For `time_precision == "unknown"`: the keys `axes`, `sectors`, `is_diurnal`,
  `derived_points`, `planetary_day`, `planetary_hour` are **absent entirely**
  (not present-but-null), and each point has **no `sector` key**.
- For circumpolar latitudes: `sectors.placidus_cusps` is `null` and each point's
  `sector.placidus` is `null`, while whole-sign values remain populated.
- `classifications` is `null` for non-classical points (outer planets, nodes).
- `is_diurnal` is absent when there is no birth time (it is not derivable
  without the Ascendant/horizon).

Absent vs. null is meaningful and must be preserved: **absent = "this concept
does not exist for this chart"; null = "this concept exists but is undefined
here."** Do not convert one into the other.

---

## 7. Demo / smoke expectations after the change

Update the `__main__` demo if needed so it still runs. After your changes, an
`exact` chart's top-level keys should be:

```
meta, confidence, points, axes, sectors, is_diurnal,
derived_points, planetary_day, planetary_hour, relations
```

(plus `unstable_fields` for the approximate tier).

A per-point object should look like:

```jsonc
{
  "name": "Mars",
  "traditional": true,
  "longitude": ..., "sign": "...", "sign_index": ..., "degree_in_sign": ...,
  "speed": ..., "retrograde": false,
  "sector": { "placidus": 7, "whole_sign": 8 },
  "classifications": { ... } | null
}
```

A relation object:

```jsonc
{ "source": "Mars", "target": "Venus", "type": "square",
  "scheme": "modern", "orb": 2.1, "applying": true }
```

(`type` stays `type`; its values `conjunction`/`sextile`/`square`/`trine`/
`opposition` are domain values and stay unchanged.)

---

## 8. Acceptance checklist

- [ ] No domain value (sign name, planet name, aspect type, scheme name, lot
      name, house-system name) was altered anywhere.
- [ ] All keys in section 2 renamed; `traditional` left unchanged.
- [ ] `sect` field converted to boolean `is_diurnal` and all internal sect
      branching updated; `triplicity_rulers_all` sub-keys untouched.
- [ ] Absent-vs-null contract (section 6) verified for exact, approximate,
      unknown, and circumpolar cases.
- [ ] Output is still JSON-serializable and the demo runs.
- [ ] The output now conforms to `chart_types.py` and the JSON Schema produced
      per `CHART_TYPES_SPEC.md` (do that spec in the same change set).
