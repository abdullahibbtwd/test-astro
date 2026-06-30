# Layer 1 — Deterministic Chart Computation

Handoff doc for `compute_chart.py`. This is the **only** layer that touches
astronomy or astrology tables. It produces a chart object that the
interpretation layer (the LLM) consumes. Read this before changing the code;
the astrology decisions below are deliberate, not arbitrary.

---

## 1. What this layer is

A pure function:

```
BirthData  ->  compute_chart(bd)  ->  chart object (JSON-serializable dict)
```

No interpretation, no narrative, no meaning. It computes planetary positions
from an ephemeris and applies fixed lookup tables (dignities) and fixed
formulas (lots, sect, aspects, planetary hours). Every value is reproducible
from the inputs.

### The hard contract (this is the whole point)

The reason this layer exists as a strict boundary is **no hallucinated chart
data**. The LLM never computes positions; it only reads what this layer
emits. Three guarantees enforce that:

1. **A field exists only if it is real.** If birth time is unknown, the output
   has no `angles`, no `houses`, no `sect`, no `lots` keys — they are *absent*,
   not null, not faked to noon. Absence is the signal: "cannot speak to this."
2. **Time-dependent fields carry confidence.** `confidence` is `"exact"`,
   `"approximate"`, or `"unknown"`. Approximate charts additionally get an
   `unstable_fields` block listing values that flip across the plausible time
   window.
3. **No interpretation leaks in.** Sect, dignity, lots, planetary hour are all
   table lookups or formulas computed here. The model receives e.g.
   `"sect": "night"` and `"in_own_bound": true` as hard facts.

This directly closes known gaps in `all_principles.json`: even if the
"dignity" or "sect" tag is missing on a principle, the chart object *states*
the dignity/sect as data, so retrieval misses don't produce wrong output.

---

## 2. Locked astrology decisions (and why)

You should not need to make astrology calls to maintain this. They are fixed:

| Decision | Choice | Why |
|---|---|---|
| Zodiac | **Tropical** | Matches the modern Turkish guide and both Western + Hellenistic traditions. Sidereal would be a different product. |
| House systems | **Placidus + Whole Sign, both stored** | The two source traditions disagree about the same sky. Modern interpretation reads houses off Placidus; the classical (Sahl) material uses Whole Sign. A planet can be 9th in one and 10th in the other. Storing both and tagging by system lets "modern governs, classical enriches" work without forcing a tradition through the wrong geometry. |
| Bodies | 7 classical + Uranus/Neptune/Pluto + mean lunar nodes | Each body is flagged `traditional: true/false` so retrieval never feeds Pluto to a Sahl rule that predates it. **Nodes are flagged traditional** — they are the Head/Tail of the Dragon (Ra's/Dhanab), heavily used in the Arabic material. |
| Node type | **Mean** node | The traditional choice; smoother and standard for this material. |
| Triplicity scheme | **Dorothean** | This is the scheme Sahl/Dorotheus use. |
| Bounds/terms | **Egyptian** | The traditional default. |
| Faces/decans | **Chaldean order** | Standard. |
| Sect | Computed geometrically (Sun above/below horizon) | Gates a large part of the Sahl material (sect light, benefic/malefic of sect). Cheap to compute, unlocks thin dataset coverage. |
| Lots | **Fortune + Spirit**, sect-sensitive | The Arabic-astrology differentiator. Fortune's formula swaps day/night by sect. Easy to extend to more lots. |
| Aspects | **Both** modern (degree orbs, applying/separating) and traditional (whole-sign by sign distance) | Same two-tradition split as houses; tagged by `system`. |

Anything that is a table lookup or a formula belongs **here**, not in the LLM.

---

## 3. The three precision tiers

Birth time is load-bearing: the Ascendant moves ~1° per 4 minutes and most of
the classical apparatus (houses, sect, lots) depends on it. The intake offers
three options, and the layer handles each structurally.

### `exact`
User knows the clock time. Full chart. Everything populated. This is the only
tier where the classical/Arabic layer fires at full strength.

### `approximate`
User picks a named bucket (e.g. "morning"). The layer:
1. computes the chart at the bucket **midpoint**,
2. recomputes at the bucket's **window edges**,
3. diffs the volatile fields and reports anything that flips in
   `unstable_fields`.

Stable fields (usually the planets, Moon sign, sect) are trustworthy. Fields
that flip across the window (often the Ascendant and house placements) are
flagged. The interpretation layer must treat flagged fields like missing ones
— it does not build claims on them. This is more honest than faking precision
*or* discarding the whole chart.

Buckets live in `APPROX_BUCKETS` as `(midpoint_hour, window_start, window_end)`
and are freely tunable. Windows may cross midnight (handled).

### `unknown`
No time. The layer **omits** Ascendant, houses, sect, lots, planetary hour
entirely, and emits the Moon as a daily **range** (`bodies[Moon].range`) since
it moves up to ~15°/day. This is a Sun-plus-planets reading; the classical
layer goes mostly dark, which is correct.

---

## 4. Output schema (annotated)

```jsonc
{
  "meta": {
    "time_precision": "exact",          // exact | approximate | unknown
    "zodiac": "tropical",
    "ephemeris": "moshier",
    "pyswisseph_version": 20230604,
    "house_systems": ["placidus", "whole_sign"],
    "node_type": "mean",
    "timezone": "Europe/Istanbul",
    "utc": "1990-06-15T11:30:00+00:00",
    "approx_bucket": "morning",         // only when approximate
    "note": "..."                       // only when unknown
  },
  "confidence": "exact",                // mirrors precision
  "bodies": [
    {
      "name": "Mars",
      "traditional": true,              // gate for retrieval
      "longitude": 192.34, "sign": "Libra", "sign_index": 6,
      "degree_in_sign": 12.34,
      "speed": 0.61, "retrograde": false,
      "house": { "placidus": 7, "whole_sign": 8 },  // null if no time / circumpolar
      "dignities": {                    // null for outer planets & nodes
        "sign_ruler": "Venus",
        "in_domicile": false, "in_detriment": false,
        "in_exaltation": false, "in_fall": false,
        "triplicity_ruler": "Mercury", // null if sect unknown
        "triplicity_rulers_all": { "day": "...", "night": "...", "participating": "..." },
        "in_triplicity": false,
        "bound_ruler": "Jupiter", "in_own_bound": false,
        "face_ruler": "...",  "in_own_face": false
      }
    }
    // ... South Node is derived (North Node + 180)
  ],
  "angles": { "ascendant": {...}, "mc": {...} },     // omitted if unknown
  "houses": {
    "placidus_cusps": [...],            // null above polar circle
    "whole_sign_cusps": [...]
  },                                                 // omitted if unknown
  "sect": "night",                                   // omitted if unknown
  "lots": { "fortune": {...}, "spirit": {...} },     // omitted if unknown
  "planetary_day": "Mars",                           // omitted if unknown
  "planetary_hour": "Jupiter",                       // null at circumpolar lat
  "unstable_fields": {                               // only when approximate
    "asc_sign": true,
    "house_placements": ["Sun", "Moon", ...]
  },
  "aspects": [
    { "a": "Mars", "b": "Venus", "type": "square",
      "system": "modern", "orb": 2.1, "applying": true },
    { "a": "Sun", "b": "Moon", "type": "square", "system": "whole_sign" }
  ]
}
```

Each `{...}` point object is `{longitude, sign, sign_index, degree_in_sign}`.

---

## 5. The interpretation-layer contract

What the downstream LLM layer may and may not do with this object:

- **May** assert any field that is present.
- **Must not** assert anything about a field that is absent (e.g. no Ascendant
  key ⇒ no rising-sign claims).
- **Must not** build a claim on a field listed in `unstable_fields`.
- **Must** route house-based principles by tradition: modern principles read
  `house.placidus`, classical/Sahl principles read `house.whole_sign`. Same for
  aspects via the `system` field.
- **Must not** apply a classical principle to a body with `traditional: false`
  (no Sahl judgment about Pluto).

This contract is what keeps the no-hallucination guarantee intact end to end.

---

## 6. Validation status & things to double-check

Tested and passing:
- All three precision tiers produce correct shapes.
- Planetary day/hour verified against weekday (Fri→Venus; a 2 AM birth correctly
  rolls back to the previous astrological day, Thu→Jupiter).
- Known dignities spot-checked (Mars domicile in Aries, Sun exalted at 19° Aries,
  Saturn exalted at 0° Libra).
- Egyptian bounds table: all 12 signs have 5 terms ending at 30°.
- Turkey DST: 1990 summer and post-2016 permanent +3 both resolve to the
  expected UTC.
- Circumpolar latitude degrades gracefully (Placidus → null, Whole Sign still
  works) instead of crashing.

**Still validate before commercial launch:**
- [ ] **Bounds table values** — transcription typos are the single most likely
      error. Cross-check every cell against a printed reference.
- [ ] **Planetary hours** against an established calculator; the weekday is
      taken from the sunrise date in UT (a minor boundary approximation).
- [ ] **Turkey timezone test suite** — build a set of known charts spanning the
      DST-rule changes and the 2016 switch to permanent UTC+3. This population
      is exactly where timezone bugs surface. Pre-1970 `tzdata` is historically
      unreliable; flag births before then.
- [ ] **Triplicity/face/exaltation tables** against the same reference, once.

---

## 7. Reproducibility

- **Ephemeris:** defaults to **Moshier** (`swe.FLG_MOSEPH`) — self-contained,
  no external files, fully deterministic, arcsecond-accurate for the modern
  era. To upgrade precision, switch `EPHE_FLAG` to `swe.FLG_SWIEPH` and call
  `swe.set_ephe_path(<dir>)` with pinned `.se1` files — but then you must ship
  and version those files.
- **Pin `pyswisseph`** in the lockfile. The version is recorded in
  `meta.pyswisseph_version` on every chart so you can detect drift.
- Identical `BirthData` must always yield a byte-identical chart. If it doesn't,
  the ephemeris source or library version changed.

---

## 8. Known limitations / open extension points

- **Placidus undefined above ~66.5° latitude.** Returns null there; Whole Sign
  still works. Never triggers for Turkey (36–42° N).
- **Approximate stability check** currently covers Ascendant sign, MC sign,
  sect, Moon sign, and per-body house placements. Extend `_volatile_signature`
  if you want finer-grained flags (e.g. dignity changes across the window).
- **Lots:** only Fortune and Spirit. Sahl uses more; add formulas in
  `compute_lots` (most are sect-sensitive — follow the existing pattern).
- **Aspects:** modern aspects exclude the nodes by design; traditional aspects
  cover only the classical seven. Adjust the body filters in
  `compute_modern_aspects` / `compute_traditional_aspects` if needed.
- **Not yet computed** (deliberately out of scope for v1, all good candidates if
  you want to strengthen the classical/predictive layer): planetary antiscia,
  profections, solar/lunar returns, secondary progressions, transits to the
  natal chart for the reading date. The `reading_date_utc` field on `BirthData`
  is reserved for the transit/timing work.

---

## 9. How to run

```bash
pip install pyswisseph timezonefinder tzdata   # Python >= 3.9 (uses stdlib zoneinfo)
python3 compute_chart.py                        # prints a demo Istanbul chart
```

**Platform notes:**

- **`pyswisseph` needs a C toolchain when no prebuilt wheel exists.** On Windows
  with CPython 3.12 there is no published wheel, so `pip` compiles it from C
  source and fails unless the **MSVC C++ Build Tools** are installed
  (`winget install Microsoft.VisualStudio.2022.BuildTools --override "--quiet --wait
  --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"`, then run
  pip from a `vcvars64.bat` shell). The easy alternative is a prebuilt binary from
  conda-forge (`conda install -c conda-forge pyswisseph`).
- **`tzdata` is required on Windows.** Windows ships no system IANA timezone
  database, so `zoneinfo.ZoneInfo("Europe/Istanbul")` raises
  `ZoneInfoNotFoundError` without the `tzdata` pip package. It's a no-op on Linux/
  macOS (which have the system db), so it's listed above as a safe default.
- **On Windows use `python`, not `python3`.** `python3` triggers the Microsoft
  Store app-execution alias ("Python was not found...") rather than the installed
  interpreter. Run `python compute_chart.py`.

Programmatic use:

```python
from compute_chart import BirthData, compute_chart

bd = BirthData(
    year=1990, month=6, day=15,
    latitude=41.0082, longitude=28.9784,
    time_precision="exact", hour=14, minute=30,
)
chart = compute_chart(bd)   # JSON-serializable dict, ready for the LLM layer
```

For approximate births pass `time_precision="approximate", approx_bucket="morning"`.
For unknown, just `time_precision="unknown"`.
