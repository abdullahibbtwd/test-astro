# CHART_TYPES_SPEC.md — instructions for the coding agent

You will produce a **formal, machine-checkable specification of the chart data
structure** in two forms:

1. `chart_types.py` — Python `TypedDict` definitions (in-process static typing).
2. `chart_schema.json` — a JSON Schema (language-agnostic cross-service
   contract).

Both describe the **same** structure: the output of `compute_chart()` *after*
the renames in `RENAME_SPEC.md` are applied. Apply the renames first (or in the
same change set); the types below already use the new names.

The point of this work: the chart object is the hard boundary between the
deterministic engine and the interpretation/retrieval layers. Today that
boundary is an untyped dict — a handshake. Typing it turns the contract into
something tooling enforces: typos and wrong-type accesses are caught by `mypy`
before runtime, the JSON can be validated at service boundaries, and a new
engineer learns the exact shape by reading one file.

---

## 0. Authoritative rule: model absence and nullability precisely

This is the most important part. The type system must distinguish three states,
because they encode the no-hallucination contract:

- **Required field** — always present for that chart kind.
- **`null` value** — the concept exists for this chart but is undefined here
  (e.g. `placidus` sector above the polar circle; `classifications` for a
  non-classical point). Model as a union with `None`.
- **Absent key** — the concept does not exist for this chart at all (e.g.
  `axes`, `is_diurnal`, `derived_points` when there is no birth time). Model as
  optional (`NotRequired` in TypedDict; not in `required` in JSON Schema).

Absent and null are NOT interchangeable. Encode each exactly as specified below.

---

## 1. `chart_types.py` — TypedDict definitions

Use `from __future__ import annotations`, `from typing import TypedDict,
NotRequired, Literal`. Target Python 3.11+. Use `X | None` for nullable and
`NotRequired[X]` for optional keys. Use `Literal[...]` for closed domain-value
sets so the type checker also validates the allowed values.

Define the following types. Field names are exact. Domain-value `Literal` sets
are listed; keep their spelling identical to what the engine emits.

### Leaf types

```
Position:
  longitude: float
  sign: Sign                      # Literal of the 12 sign names
  sign_index: int                 # 0..11
  degree_in_sign: float

Sector:                           # per-point house placement, both systems
  placidus: int | None            # 1..12, or None above polar circle
  whole_sign: int                 # 1..12

TriplicityRulers:
  day: Planet
  night: Planet
  participating: Planet

Classifications:                  # essential dignities; only for classical 7
  sign_ruler: Planet
  in_domicile: bool
  in_detriment: bool
  in_exaltation: bool
  in_fall: bool
  triplicity_ruler: Planet | None # None when sect is unknown (no birth time)
  triplicity_rulers_all: TriplicityRulers
  in_triplicity: bool | None      # None when sect is unknown
  bound_ruler: Planet
  in_own_bound: bool
  face_ruler: Planet
  in_own_face: bool
```

### Point types

A point has an optional `range` (only the Moon, only in the unknown tier) and an
optional `sector` (absent in the unknown tier). `classifications` is nullable
(null for non-classical points). Model with NotRequired where the key can be
absent and `| None` where the value can be null:

```
MoonRange:                        # only present on the Moon in the unknown tier
  start: Position
  end: Position
  note: str

Point:
  name: str                       # domain value (planet/point name); keep open str
  traditional: bool
  longitude: float
  sign: Sign
  sign_index: int
  degree_in_sign: float
  speed: float
  retrograde: bool
  sector: NotRequired[Sector]             # absent in unknown tier
  classifications: Classifications | None # null for non-classical points
  range: NotRequired[MoonRange]           # present only on Moon, unknown tier
```

(Decision you may make: split into `ObservedPoint` vs a base type if it improves
clarity, but a single `Point` with NotRequired fields is acceptable and
simpler. If you split, keep the JSON shape identical.)

### Relation type (edge in the aspect graph)

```
Relation:
  source: str                     # point name
  target: str                     # point name
  type: AspectType                # Literal: conjunction/sextile/square/trine/opposition
  scheme: Scheme                  # Literal: "modern" | "whole_sign"
  orb: NotRequired[float]         # present only for modern relations
  applying: NotRequired[bool]     # present only for modern relations
```

Note: whole-sign relations carry no `orb`/`applying` (no degree orb in that
scheme), so those two keys are NotRequired, present only when `scheme ==
"modern"`. Do not emit them as null for whole-sign; omit them.

### Container types

```
Axes:
  ascendant: Position
  mc: Position

Sectors:
  placidus_cusps: list[float] | None      # null above polar circle
  whole_sign_cusps: list[float]

DerivedPoints:
  fortune: Position
  spirit: Position
  # keep open to additional named lots later

Meta:
  time_precision: Literal["exact", "approximate", "unknown"]
  zodiac: str
  ephemeris: str
  pyswisseph_version: int | str
  house_systems: list[str]
  node_type: str
  timezone: str
  utc: str
  approx_bucket: NotRequired[str]   # only when approximate
  note: NotRequired[str]            # only when unknown

UnstableFields:                     # only when approximate
  asc_sign: NotRequired[bool]
  mc_sign: NotRequired[bool]
  is_diurnal: NotRequired[bool]
  moon_sign: NotRequired[bool]
  house_placements: NotRequired[list[str]]
```

### Top-level type

```
Chart:
  meta: Meta
  confidence: Literal["exact", "approximate", "unknown"]
  points: list[Point]
  relations: list[Relation]
  axes: NotRequired[Axes]                  # absent in unknown tier
  sectors: NotRequired[Sectors]            # absent in unknown tier
  is_diurnal: NotRequired[bool]            # absent in unknown tier
  derived_points: NotRequired[DerivedPoints]   # absent in unknown tier
  planetary_day: NotRequired[str | None]   # absent in unknown tier; null if circumpolar
  planetary_hour: NotRequired[str | None]  # absent in unknown tier; null if circumpolar
  unstable_fields: NotRequired[UnstableFields]  # only when approximate
```

### Literal alias definitions to include

```
Sign      = Literal["Aries","Taurus","Gemini","Cancer","Leo","Virgo",
                    "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
Planet    = Literal["Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn"]
AspectType= Literal["conjunction","sextile","square","trine","opposition"]
Scheme    = Literal["modern","whole_sign"]
```

Note `Planet` is the set used for *dignity rulers* (the classical seven). Point
`name` is a broader set (includes Uranus/Neptune/Pluto/North Node/South Node),
so keep point `name` typed as `str`, not `Planet`, to avoid over-constraining.

---

## 2. `chart_schema.json` — JSON Schema

Produce a JSON Schema (Draft 2020-12) describing the **same** structure. This is
the cross-service contract: it validates the actual emitted JSON regardless of
what language consumes it (important if the interpretation layer is ever a
separate service).

Requirements:

- Mirror the TypedDicts exactly: same field names, same enums (use `enum` for
  the Sign/Planet/AspectType/Scheme value sets).
- Encode the three tiers. The cleanest approach: a base schema plus a
  `oneOf`/`allOf` with conditional `required` arrays driven by
  `meta.time_precision` (e.g. `if meta.time_precision == "unknown" then axes,
  sectors, is_diurnal, derived_points, planetary_day, planetary_hour are NOT
  required and points items do not require sector`). If conditional schemas get
  unwieldy, an acceptable simpler alternative is three named definitions
  (`ExactChart`, `ApproximateChart`, `UnknownChart`) combined with `oneOf` —
  choose whichever you can make correct and readable, and say which you chose in
  a comment/README note.
- Nullable fields (`placidus`, `placidus_cusps`, `classifications`,
  `triplicity_ruler`, `in_triplicity`, `planetary_day`, `planetary_hour`) use
  `{"type": ["<type>", "null"]}`.
- Optional/absent fields are simply omitted from the relevant `required` array —
  do NOT model them as nullable. Keep the absent-vs-null distinction intact.
- Set `additionalProperties: false` on the object types so unexpected keys are
  caught. (If this proves too strict for forward-compat on `meta`, relax it on
  `meta` only and note why.)

---

## 3. Wiring & validation

- The engine module should import the types from `chart_types.py` and annotate
  `compute_chart() -> Chart` and the relevant helpers. The goal is that running
  `mypy` over the engine passes cleanly.
- Add a lightweight self-check (a test or a `__main__` assertion) that validates
  the demo charts for all three tiers against `chart_schema.json` using a JSON
  Schema validator (e.g. the `jsonschema` package). This proves the two
  specifications agree with the actual output.
- Generate at least three fixture charts (exact, approximate, unknown) plus one
  circumpolar exact chart, and assert all four validate against the schema.

---

## 4. Acceptance checklist

- [ ] `chart_types.py` defines every type above with exact field names.
- [ ] Absent (`NotRequired`) vs null (`| None`) modeled exactly per section 0;
      no field that should be absent is modeled as nullable, and vice versa.
- [ ] `Literal` sets match the engine's emitted domain values verbatim.
- [ ] `point.name` is `str` (not `Planet`); dignity ruler fields use `Planet`.
- [ ] `chart_schema.json` mirrors the TypedDicts, encodes the three tiers, and
      uses `enum` for closed value sets.
- [ ] `compute_chart()` is annotated `-> Chart` and `mypy` passes.
- [ ] Exact, approximate, unknown, and circumpolar fixtures all validate against
      the JSON Schema in an automated check.
- [ ] No domain value was renamed (this spec must not contradict
      `RENAME_SPEC.md`; values stay, structural keys use the new names).
