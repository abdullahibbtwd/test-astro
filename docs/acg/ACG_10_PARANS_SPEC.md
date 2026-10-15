# ACG 10: parans (latitude crossings)

*2026-09-28. Adds the dashed horizontal lines seen on professional ACG maps. Applies on top of
specs 01–09. Deterministic compute; grounded reading. Supersedes D4 ("parans fast-follow") for parans only;
zeniths and CCG stay deferred.*

## 1. What a paran is (normative definition)

A paran is a **latitude** at which two planets **A** and **B** are angular at the same moment:
A on angle α and B on angle β. For every such latitude, the ACG lines of A-α and B-β cross on the map,
and (per the source, `acg-method-crossings`) the combined influence applies **along the whole latitude**,
at any longitude.

The two definitions are the same. At latitude φ, line A-α sits at longitude `λ = RA_A + h_α(φ, δ_A) − GAST`
(spec 01 §4). The lines cross where these are equal, i.e.

```
h_α(φ, δ_A) − h_β(φ, δ_B) ≡ RA_B − RA_A   (mod 360)
h_MC = 0,  h_IC = 180,  h_ASC = −H₀(φ,δ),  h_DSC = +H₀(φ,δ),  H₀ = acos(−tan φ · tan δ)
```

That condition doesn't depend on GAST, so the crossing latitude is a latitude-wide property.
(A prototype verified this for the 1979-03-30 test chart: 216 parans; the residual on the invariant was < 1e-12°.)

## 2. Scope (v1)

- Bodies: the 10 planets (nodes excluded, as for lines).
- Angle combinations per unordered planet pair: all α × β **except meridian × meridian** (MC/IC with MC/IC are
  either impossible or latitude-independent). That's 12 combinations per pair × 45 pairs.
- Latitude range: −80…+80, within each body's circumpolar limit (the ASC/DSC side must exist).
- **Not in scope:** zenith points, parans involving the nodes, fixed stars, and "diurnal" parans computed over the whole birth day. Only birth-moment crossings are in scope, which matches the source.

## 3. Compute (`Astrocartography/compute_parans.py`)

For each pair and combination, solve `f(φ) = n180(h_α(φ,δ_A) − h_β(φ,δ_B) − (RA_B − RA_A)) = 0`:
1. Sample φ every 0.05° over the valid range.
2. Find sign changes of f, **skipping wrap jumps** (|Δf| > 90 between samples).
3. Refine each by bisection to 1e-9°.

Output `parans.json` (in the per-chart cache, next to `acg.json`):

```json
{"schema_version": "acg-parans-1",
 "parans": [{"id": "sun-IC__neptune-ASC", "a": {"body": "sun", "angle": "IC"},
             "b": {"body": "neptune", "angle": "ASC"}, "lat": 38.466,
             "crossing_lon": 12.34}]}
```

`crossing_lon` is the map longitude where the two lines meet, for drawing a marker. Sort by `lat`.

The map layer is `acg_parans.geojson`: one `LineString` per paran along its latitude (−180…180, split at the
antimeridian), `properties: {kind: "paran", id, planets: [a, b], angles: [α, β]}`, plus a `Point` at `crossing_lon`.
The UI draws them dashed, labelled with the two planet glyphs at the edges, like professional maps.

## 4. Locate (additions to spec 02 / 07 §4)

For a place at latitude φ_p, every paran with |φ_p − lat| ≤ **1.0°** is "near". The distance is
`dlat_km = |φ_p − lat| × 111.2`.

- Keep at most **2 parans per place**, the closest first.
- Add them to `locate.json` as `parans_near` and to the UI block as `parans_display`:
  `{planets_en: ["Sun","Neptune"], planets_tr: ["Güneş","Neptün"], north_south: "north|south",
  distance_km_rounded, label_en: "Latitude crossing", label_tr: "Enlem kesişimi"}`.

## 5. Corpus and goal tags

- The paran records already exist (`acg_scope: paran`, `about: {type: acg_paran, planets: [p1, p2]}`).
  **Include scope `paran` in `tag_goals_acg.py`** (07 §5) and re-run it. It's idempotent; only the new records get model calls.
- Paran records become **eligible for v1 retrieval** (update the spec 03 eligibility list).
- Coverage will be thin (the source discusses parans for a minority of pairs), hence the fallback in §6.

## 6. Scoring (addition to spec 08)

**Paran affinity** for a planet pair {A, B} and goal g:

```
if paran-specific records for {A,B} have volume ≥ 2:
    Apar(A,B,g) = affinity computed from those records (the same formula as 08 §2)
else:
    Apar(A,B,g) = 0.5 · ( Ā(A,g) + Ā(B,g) )     where Ā(p,g) = mean of A(p,a,g) over the 4 angles
```

Store it in `acg_goal_affinity.json` under `parans`, with contributors. In the fallback case, the contributors are
the contributors of both planets' cells.

**Contribution to a place score:**

```
w_par(Δφ) = W_PARAN · (1 − |Δφ| / 1.0)       |Δφ| ≤ 1.0°,  W_PARAN = 0.4
contribution = w_par · Apar(A,B,g)             added into P / N / S exactly like a line (08 §3)
```

- Parans count toward the `dominant_line` choice in 09 only if no real line contributes more. Their key for the
  diversity rule is `paran:<A>-<B>`.
- **Recalibration:** adding parans shifts the score distributions, so re-run the band calibration gate (08 §4) after this lands.
  Only thresholds may move.

## 7. Reading (additions to spec 04 / 07 §6)

A new city section after `lines_here`:

| key | TR title | EN title | Source | Length (TR words) | Omit when |
|---|---|---|---|---|---|
| `background_influences` | Arka Plan Etkileri | Background Influences | per near paran: paran records if present, else both planets' `planet_general` records + `acg-method-crossings` | 30–60 per paran | no parans near |

Prompt rules: describe it as a **combined, background** influence of the two planets across this latitude band, softer
than a line. No mention of latitude numbers, "paran" or angle names. Validator: AV12 extends to "the planets named
in `background_influences` ⊆ the near parans' planets". AV1 (no numbers) still applies.

Suitability cards and `positives`/`challenges` may trace paran contributors (they're in `goal_contributors`).

## 8. Acceptance (`test_acg_parans.py`)

| # | Check |
|---|---|
| PA1 | For every paran: set LST = RA_A + h_α(lat); then B's hour angle = h_β(lat, δ_B) within 1e-6°. |
| PA2 | For every paran: the longitudes of the A-α and B-β polylines in `acg.json`, interpolated at `lat`, differ by < 0.01°, and equal `crossing_lon`. |
| PA3 | No meridian × meridian combos; no nodes; every root lies within both bodies' valid latitude ranges. |
| PA4 | Determinism: byte-identical `parans.json` across runs. Count for the 1979-03-30 06:30 Sofia chart: 200–230 (the prototype found 216). |
| PA5 | A place at `lat + 0.5°` gets that paran in `parans_near` with weight 0.2 (= 0.4 × 0.5). A place at `lat + 1.01°` doesn't get it. |
| PA6 | At most 2 parans per place; the closest are kept. |
| PA7 | Scores: with W_PARAN = 0, all scores are identical to pre-paran scores (regression guard). |
| PA8 | Reading: a place with no near paran has no `background_influences` section; one with a paran has it, with traced ids from the paran or fallback contributors only. |
