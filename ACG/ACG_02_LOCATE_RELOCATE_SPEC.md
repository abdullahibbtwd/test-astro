# ACG 02: locate, relocate, city scan

*Deterministic. No LLM. Network only via the existing geocoder (cached).*

## 1. Purpose

1. **Locate:** place → which lines pass within orb, with the distance and the tier.
2. **Relocate:** place → the relocated chart (natal UTC instant, new coordinates).
3. **City scan:** for a committed gazetteer, list which cities sit on which lines. This is
   for the map UI ("where is your Venus line?"), with no LLM.

## 2. Place resolution (`acg_locate.resolve_place`)

The input is one of:
- `--city "<text>"`: first look in `gazetteer.json` (case- and diacritic-insensitive
  match on `name`, `name_tr` and `aliases`), then fall back to the **existing L1 geocoder**
  (Phase 0 item 4). Never add a second geocoder.
- `--lat --lon`: manual coordinates, `source: "manual"`.

The output `place` block is `{query, name, name_tr, lat, lon, country_code, source:
"gazetteer|geocoder|manual"}`. On geocoder failure: absence `{"reason": "place_not_found"}`,
and the orchestrator stops before grounding.

## 3. Distance from a place to a line (`acg_geo`)

Use a spherical Earth with R = 6371.0 km. All distances are **perpendicular great-circle
distances** to the line.

- **MC / IC (meridians):** closed form. With Δλ = n180(λ_place − λ_line):
  `d = R · asin(cos φ_place · |sin Δλ|)` if |Δλ| ≤ 90°; otherwise the line is on the far side
  of the globe and is not reported.
- **ASC / DSC (curves):** the minimum over segments of the spherical point-to-arc distance
  (cross-track distance, clamped to the arc endpoints; use the along-track check to decide
  when to clamp). Only consider segments whose vertices lie within ±15° of latitude of the place
  (a performance prefilter; this doesn't change results for orbs ≤ 1,000 km).
- Also return `nearest_point: [lon, lat]` and `side: "east"|"west"` (whether the place is
  east or west of the line at the nearest point). `side` is stored and not read in v1.

**Tiers** (`acg_constants.ORB_TIERS_KM`): `tight` ≤ 150, `strong` ≤ 400, `wide` ≤ 1000.
Lines beyond 1,000 km are not reported.

## 4. `locate.json`

```json
{
  "schema_version": "acg-locate-1",
  "place": {"query": "izmir", "name": "Izmir", "name_tr": "İzmir", "lat": 38.42, "lon": 27.14,
            "country_code": "TR", "source": "gazetteer"},
  "status": "ok | absent",
  "absence": null,
  "lines_near": [
    {"body": "venus", "angle": "DSC", "distance_km": 88.4, "tier": "tight",
     "read_in_v1": true, "nearest_point": [26.3, 38.1], "side": "east"}
  ],
  "relocation": {"status": "ok | absent", "absence": null, "chart_path": "chart_relocated.json"}
}
```

- `lines_near` is sorted by `distance_km` ascending. A body can appear for more than one angle.
- If the natal `acg.json` is `absent`, then `locate.json` is `absent` with the same reason.
- An empty `lines_near` is valid and not an absence ("no line nearby" is a reading in its own right; see spec 03).

## 5. Relocated chart

Call **the existing `compute_chart`** with:
- the **natal UTC instant** (the same `jd_ut`), and
- the place's lat/lon,
- **with no timezone re-resolution.** If `compute_chart` can't do this today, apply the
  minimal change proposed in the Phase 0 report (item 1). Default behaviour must stay
  byte-identical for existing callers, and the existing tests must still pass.

Write the result as `chart_relocated.json` in the run folder (the same schema as `chart.json`),
plus a metadata flag `relocated_from: {natal_lat, natal_lon}` if the schema allows extra
metadata. Otherwise record it in `locate.json.relocation`.

**Polar gate:** if |lat_place| > 66.0 → `relocation.status: "absent"`, with reason
`placidus_undefined_high_latitude`. Lines are still located.

### 5.1 House diff (`acg_locate.house_diff`)

Compare the natal and relocated **Placidus** house placements for each of the 10 planets:

```json
"house_diff": [
  {"body": "saturn", "natal_house": 3, "relocated_house": 10, "angular_after": true}
]
```

Include only the planets whose house changed. Store this in `locate.json`. Spec 03 uses it.

## 6. Gazetteer (`gazetteer.json`, built once by `build_gazetteer.py`, committed)

The record shape is `{id, name, name_tr, aliases[], country_code, lat, lon}`. Coordinates come
from the existing geocoder at build time, and are then frozen. The scan never calls the network.

Contents:
- **All 81 Turkish province centres** (il merkezleri).
- **Diaspora and aspiration cities:** Berlin, Hamburg, Munich, Frankfurt, Cologne, Düsseldorf,
  Stuttgart, Vienna, Zurich, Amsterdam, Rotterdam, Brussels, Paris, Lyon, London,
  Stockholm, Copenhagen, Oslo, Madrid, Barcelona, Lisbon, Rome, Milan, Athens, Sofia,
  Nicosia (Lefkoşa), Baku, Tbilisi, Moscow, Dubai, Doha, Riyadh, New York, Chicago,
  Miami, Los Angeles, San Francisco, Toronto, Montreal, Tokyo, Singapore, Sydney,
  Melbourne.

`name_tr` holds the Turkish exonym (e.g. "Viyana", "Münih", "Köln", "Londra", "Paris").

## 7. City scan (`city_scan.json`)

For each gazetteer city: `lines_near` restricted to `tight` + `strong` and `read_in_v1`
bodies. Plus an inverted index:

```json
"by_line": {"venus|DSC": [{"city_id": "tr-35", "distance_km": 88.4}, "... up to 5, ascending"]}
```

This is computed after `compute_acg` with no place argument. Deterministic.

## 8. Acceptance invariants (`test_acg.py`, continued)

| # | Invariant | Tolerance |
|---|---|---|
| LO1 | A place constructed exactly on a body's MC line (λ = MC λ, φ = 41.0) → that line has `distance_km` < 0.5 and `tier: tight` | 0.5 km |
| LO2 | A place 1.0° of longitude east of a meridian line at φ = 0 → `distance_km` ≈ 111.19 | 0.2 km |
| LO3 | A place on an ASC vertex → distance < 0.5 km. A place offset 2.0° of latitude along the meridian from an ASC vertex has distance ≤ 222.4 km (perpendicular ≤ meridional) | as stated |
| LO4 | Tier boundaries: 149.9 → tight, 150.1 → strong, 399.9 → strong, 999.9 → wide, 1000.1 → not reported | exact |
| R1 | For a place exactly on body X's MC line: `swe.houses_ex(jd, φ, λ, b'P')` ARMC ≡ `ra_X` | 1e-6° |
| R2 | For a place exactly on body X's ASC line: the true altitude of X from `swe.azalt` ≈ 0 | 1e-6° |
| R3 | The relocated chart's planetary longitudes, latitudes, speeds, signs, dignities and aspects are **identical** to the natal chart's; only angles, cusps, house placements, sector rulers and anything house-derived differ | exact (float equality) |
| R4 | The relocated chart's timestamp/jd_ut equals the natal one, **even when the place is in another timezone** (test: natal Istanbul, place New York) | exact |
| R5 | \|lat\| = 70 → `relocation.status: absent`, with reason `placidus_undefined_high_latitude`, while `lines_near` is still computed | exact |
| R6 | Relocating to the natal coordinates → `house_diff` is empty and the relocated chart equals the natal chart apart from metadata | exact |
| G1 | Every gazetteer entry has 81 unique `tr-*` province ids + the diaspora list, a non-empty `name_tr`, and lat ∈ [−90, 90] | exact |
| G2 | The city scan is deterministic (byte-identical over two runs) and makes zero network calls (patch the geocoder to raise) | exact |
