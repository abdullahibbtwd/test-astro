# ACG 01: `compute_acg` (line computation)

*Deterministic. No LLM. No network. Depends on: `pyswisseph`, and the natal UTC instant from L1.*

## 1. Purpose

Given the natal UTC instant, compute the four angular lines (MC, IC, ASC, DSC) of each
body as geographic polylines. Emit `acg.json` (canonical) and `acg.geojson` (for the map UI).

## 2. Inputs

| Field | Source | Notes |
|---|---|---|
| `jd_ut` | natal `chart.json` metadata, or recomputed from the UTC instant exactly as L1 does | It must be **bit-identical** to the instant L1 used. Read it; don't recompute it differently. |
| `time_precision` | natal `chart.json` | Gate (§8). |
| `bodies` | `acg_constants.BODIES` | Sun…Pluto (Swiss Ephemeris ids 0–9) + the node L1 uses (mean or true: mirror L1). |
| ephemeris flags | mirror L1 (Phase 0 item 3) | Add `FLG_EQUATORIAL`. Keep `FLG_SPEED`. |

## 3. Per-body equatorial data

```
(ra, dec, dist, ra_speed, dec_speed, dist_speed), _ = swe.calc_ut(jd_ut, body, L1_FLAGS | swe.FLG_EQUATORIAL)
gast_deg = swe.sidtime(jd_ut) * 15.0          # Greenwich apparent sidereal time, degrees
```

- `ra` and `dec` are apparent, referred to the true equator of date. `swe.sidtime` is apparent
  sidereal time (it includes nutation), so the two are consistent. **Do not mix in mean sidereal time.**
- Store `ra`, `dec` and `gast_deg` in the output (`bodies[].equatorial`, `meta.gast_deg`). They
  are needed downstream and for the tests.

Normalise every longitude with `n180(x) = ((x + 180) % 360) - 180`, giving (−180, 180].
Convention: **east longitude positive**.

## 4. Line formulas

Hour angle: `H = LST − RA`, where `LST = GAST + λ`.

| Line | Condition | Longitude λ at latitude φ | Defined for |
|---|---|---|---|
| **MC** | H = 0 | `λ = n180(ra − gast)` (independent of φ) | all φ in sampling range |
| **IC** | H = 180° | `λ = n180(ra − gast + 180)` | all φ in sampling range |
| **ASC** | H = −H₀ | `λ = n180(ra − H₀ − gast)` | \|tan φ · tan δ\| ≤ 1 |
| **DSC** | H = +H₀ | `λ = n180(ra + H₀ − gast)` | \|tan φ · tan δ\| ≤ 1 |

with `H₀ = degrees(acos(−tan φ · tan δ))`, H₀ ∈ [0°, 180°].

**Circumpolar limit.** ASC/DSC exist only for \|φ\| ≤ φ_lim = 90° − \|δ\|.
- At `φ = −sign(δ)·φ_lim`: tan φ tan δ = −1, so H₀ = 0 and ASC and DSC both meet the **MC** line.
- At `φ = +sign(δ)·φ_lim`: tan φ tan δ = +1, so H₀ = 180° and ASC and DSC both meet the **IC** line.
- Always insert these exact limit points (if inside the sampling range) so that the curves
  close visually onto the meridian lines. Clamp `acos` arguments to [−1, 1] after the
  existence check to absorb float noise.
- If \|δ\| < 1e-9, then φ_lim = 90° and the curves span the whole sampling range.

(These formulas were verified numerically against `swe.houses_ex` ARMC and `swe.azalt`
for all 10 planets. Residuals are < 1e-12°.)

## 5. Sampling

| Constant | Value |
|---|---|
| `LAT_MIN`, `LAT_MAX` | −80.0, +80.0 |
| `LAT_STEP` | 0.25° (ASC/DSC curves) |
| MC/IC | two endpoints are enough geometrically, but emit them at the same `LAT_STEP` so every line has uniform vertices for distance queries |

Vertices are ordered by ascending latitude.

## 6. Antimeridian handling (`acg_geo.split_antimeridian`)

For GeoJSON, split a polyline wherever two consecutive vertices differ by more than 180°
in longitude. Insert an interpolated vertex at ±180 on both sides of the split, and emit
a `MultiLineString`. `acg.json` keeps the unsplit vertex list (canonical); only
`acg.geojson` is split.

## 7. Output

### 7.1 `acg.json`

```json
{
  "schema_version": "acg-1",
  "meta": {
    "jd_ut": 2446138.895833,
    "gast_deg": 0.0,
    "flags": ["SWIEPH", "SPEED", "EQUATORIAL"],
    "node_type": "mean|true",
    "method": "in_mundo_geometric_horizon",
    "sampling": {"lat_min": -80.0, "lat_max": 80.0, "lat_step": 0.25},
    "time_precision": "<L1 enum value>",
    "line_uncertainty_deg_per_min": 0.2507
  },
  "status": "ok | absent",
  "absence": null,
  "bodies": [
    {
      "body": "venus",
      "read_in_v1": true,
      "out_of_scope": null,
      "equatorial": {"ra": 0.0, "dec": 0.0},
      "circumpolar_lat_limit": 0.0,
      "lines": {
        "MC":  {"vertices": [[lon, lat], "..."]},
        "IC":  {"vertices": ["..."]},
        "ASC": {"vertices": ["..."], "joins": {"MC_at_lat": 0.0, "IC_at_lat": 0.0}},
        "DSC": {"vertices": ["..."], "joins": {"MC_at_lat": 0.0, "IC_at_lat": 0.0}}
      }
    }
  ]
}
```

- Nodes: `read_in_v1: false` and `out_of_scope: "acg_nodes_v1"`. Only the North Node is
  computed. The South Node's lines are the North Node's lines with ASC↔DSC and MC↔IC
  swapped; the UI can derive them, so don't store them.
- `joins` is `null` for a side that falls outside the sampling range.
- `line_uncertainty_deg_per_min` = 0.2507 (sidereal rotation). It's used by the UI later for
  uncertainty bands and isn't read in v1.

### 7.2 `acg.geojson`

A `FeatureCollection` with one `Feature` per (body, angle). `properties: {body, angle,
read_in_v1}`. Geometry: `MultiLineString` after the antimeridian split. Coordinates are rounded to
4 decimals (~11 m). Round only in GeoJSON, never in `acg.json`.

### 7.3 Schema

`acg_schema.json` validates `acg.json`. Validate on write.

## 8. Precision gating (absence contract)

Mirror L1's absence-contract shape (Phase 0 item 5). If `time_precision` is not the
exact-time tier:

```json
{"status": "absent", "absence": {"reason": "birth_time_not_exact", "detail": "<tier>"}, "bodies": []}
```

The closed enum for `absence.reason` is: `birth_time_not_exact`, `missing_utc_instant`,
`ephemeris_error`. `acg.geojson` is still written, as an empty `FeatureCollection`.

## 9. Acceptance invariants (`test_acg.py`)

Use one fixed fixture chart (any exact-time chart; e.g. 1985-03-14 09:30 UT).
Tolerances are in degrees unless stated.

| # | Invariant | Tolerance |
|---|---|---|
| C1 | For every body, pick 4 latitudes (−60, 0, 41, 60) on the MC line: `swe.houses_ex(jd, lat, lon, b'P')[1][2]` (ARMC) ≡ `ra` (mod 360) | 1e-6 |
| C2 | IC longitude = n180(MC longitude + 180) | 1e-9 |
| C3 | Every ASC/DSC vertex: `swe.azalt(jd, swe.EQU2HOR, (lon, lat, 0), 0, 0, (ra, dec, dist))[1]` (**true** altitude, index 1, not apparent) ≈ 0 | 1e-6 |
| C4 | ASC vertices have hour angle `n180(gast + lon − ra) ≤ 0` (the body is east); DSC vertices have it ≥ 0 | 1e-9 |
| C5 | No ASC/DSC vertex has \|lat\| > φ_lim + 1e-9 | exact |
| C6 | The ASC and DSC curves each end on the MC line at `−sign(δ)·φ_lim` and on the IC line at `+sign(δ)·φ_lim` (when inside the range) | 1e-6 |
| C7 | Time sensitivity: at `jd + 4/1440` each MC line moves by `−1.002738 + Δra` degrees (westward), where Δra is the body's RA change over those 4 minutes (Sun ≈ −1.0002; Moon ≈ −0.96) | 1e-4 |
| C8 | Determinism: two runs give byte-identical `acg.json` | exact |
| C9 | GeoJSON: no segment has a \|Δlon\| > 180 | exact |
| C10 | Non-exact precision → `status: absent` with reason `birth_time_not_exact`, and no bodies | exact |
| C11 | `acg.json` validates against `acg_schema.json` | — |

**Golden check (manual, Phase 1 gate).** For one of Radul's real charts, compare the MC
line longitudes of all 10 planets and the ASC/DSC longitudes at 3 latitudes with a public
reference (e.g. astro.com's AstroClick Travel). Record the differences in the exploration
report. Expect ≤ 0.1°. Larger differences almost always come from a timezone/UTC mismatch;
don't "fix" them by tweaking formulas.

## 10. Non-goals (v1)

Parans, line crossings, local-space lines, asteroids/Chiron, uncertainty bands, and transits
to lines. Don't build hooks for them beyond `schema_version`.
