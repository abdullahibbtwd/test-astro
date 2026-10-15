# ACG 11: viable destinations, line-first recommendations, user filters

*v2, 2026-09-28. Replaces v1 of this spec entirely. It fixes "the math picks places nobody would go"
(Magnitogorsk, Nuuk, Stanley). The astrology scoring (08, 10) is **unchanged**. This spec governs **which places
may be recommended** and **how they are presented**. City and country screening still work for any place.*

## 1. Principles

1. **Astrology ranks; viability decides eligibility.** Viability rules and user filters remove candidates. They
   never add to or subtract from the ACG score.
2. **Line-first.** Recommend the user's strongest lines for the goal, then the viable places along each line.
   Don't recommend the single best point on Earth.
3. **Sensible defaults.** Every filter has a default, so a user who sets nothing gets good results.
4. Viability data is **committed, reviewed data**, never fetched at runtime.

## 2. Candidate list: `destinations.json` (built by `build_destinations.py`, human-reviewed)

```json
{"id": "dst-valencia", "name": "Valencia", "name_tr": "Valensiya", "country": "ES",
 "admin1_id": "ESP-5815", "kind": "city | resort | region",
 "lat": 39.4699, "lon": -0.3763, "radius_km": 0,
 "population": 800000, "size": "big | mid | small",
 "coast_km": 3.1, "purposes": ["living", "travel"],
 "climate": "warm | mild | cold",
 "appeal": 1, "exclude": false, "exclude_reason": null,
 "geonameid": 2509954, "reviewed": true}
```

| Field | Rule |
|---|---|
| `size` | from GeoNames population (city proper): `big` ≥ 1,000,000; `mid` 200,000–999,999; `small` < 200,000. `region` entries take the size of their largest city. |
| `coast_km` | distance to the nearest sea coastline (Natural Earth coastline 1:10m), precomputed. |
| `climate` | precomputed from the WorldClim annual mean temperature (CC BY 4.0): `warm` ≥ 18 °C, `mild` 10–18 °C, `cold` < 10 °C. Only used if the user sets a climate filter. |
| `purposes` | ⊆ {living, travel}. |
| `appeal` | 1 iconic / 2 well known / 3 niche. **Tie-breaker only.** |
| `exclude` | conflict zones and "do not travel" advisories at review time. Re-review quarterly. |
| `reviewed` | only `true` entries are ever recommended. **No auto-approval.** |

**Seed sources:** national capitals; GeoNames cities ≥ 200,000; all 81 Turkish province centres; the main Turkish coastal and
heritage destinations; the diaspora list (spec 02 §6); and an LLM-drafted list of known travel destinations (cities,
resorts, regions), with every drafted row set to `reviewed: false`. De-duplicate by `geonameid`, or by < 25 km for regions.
The **viability policy (§3) is applied at build time**: a non-conforming entry is written with `exclude: true` and
`exclude_reason: "policy:<rule>"`, so the review sheet shows why it was dropped.

## 3. Viability policy `viable_world_v1` (product default; applies to all recommendations)

Rules are evaluated in order; the first matching rule decides.

| # | Area | Rule |
|---|---|---|
| P1 | North Korea, Mongolia | **exclude** |
| P2 | Russia | **allow only European Russia**: admin-1 regions in the Central, Northwestern, Southern, North Caucasian and Volga federal districts (west of the Urals). Everything in the Ural, Siberian and Far Eastern districts is **excluded** (e.g. Magnitogorsk, Yekaterinburg, Novosibirsk). |
| P3 | China (mainland) | **allow only** `size == big` **and** `coast_km ≤ 300` (e.g. Shanghai, Beijing, Guangzhou, Shenzhen, Tianjin, Hangzhou, Xiamen, Qingdao, Dalian). The interior is excluded (e.g. Chengdu, Chongqing, Xi'an, Ürümqi). Hong Kong, Macau and Taiwan follow the normal rules. |
| P4 | Africa | **exclude**, except **Mediterranean-coast places** in Morocco, Algeria, Tunisia, Libya and Egypt with `coast_km ≤ 100` measured to the **Mediterranean** (e.g. Tangier, Algiers, Tunis, Alexandria). Morocco's Atlantic side (Casablanca, Rabat, Marrakech) is excluded under this rule. Canary Islands, Ceuta, Melilla, Madeira: treated as Spain/Portugal (allowed). |
| P5 | Middle East | **allow** Turkey, Israel, Saudi Arabia, the UAE, Qatar, Azerbaijan. Also allow the Gulf hubs Bahrain, Kuwait and Oman (Muscat), because they're Gulf hubs. **Exclude** all other Middle East countries (e.g. Iran, Iraq, Syria, Lebanon, Jordan, Yemen). |
| P6 | Central Asia (KZ, UZ, KG, TJ, TM) | **allow only** capitals + Almaty + Samarkand + Bukhara. Everything else is excluded. *(Default chosen by Claude; Radul to confirm.)* |
| P7 | Everywhere else | allowed (Europe, the Caucasus, the Americas, South/Southeast/East Asia outside P3, Oceania), subject to `exclude` and `reviewed`. |

The Mediterranean test for P4 uses a Mediterranean-only coastline subset (Natural Earth marine polygon "Mediterranean Sea",
including the Alboran, Tyrrhenian, Ionian, Adriatic and Aegean seas).

The policy is stored as `viability_policy.json` (versioned). **Users can't widen it; user filters can only narrow it.**

## 4. User filters (all optional, all with defaults)

| Filter | Options | **Default** |
|---|---|---|
| `regions` | multi-select: `europe`, `turkey`, `mediterranean`, `middle_east_gulf`, `caucasus`, `americas`, `east_asia`, `south_southeast_asia`, `oceania`, `central_asia` | **all** (= the whole viable world) |
| `city_size` | multi-select: `big`, `mid`, `small` (small includes resorts) | **`big` + `mid`** |
| `max_distance_km` | distance from the user's current home city (or the birthplace if no home city is set) | **none** |
| `climate` | multi-select: `warm`, `mild`, `cold` | **none (not applied)**. Only applied when the user sets it. |
| `purpose` | `living` / `travel` / both | **derived from the goal** (table below) |

Goal → default purpose:

| Goals | Purpose |
|---|---|
| relocation, career, business, money, education, family | living |
| travel, rest | travel |
| love, creativity, spirituality | living + travel |

Region membership is a static mapping ISO-2 → region key(s) in `regions_map.json`. A country can belong to several
regions (e.g. Turkey ∈ turkey, europe, mediterranean, middle_east_gulf).

The API/CLI takes these as optional arguments; omitted means default. Every output echoes `filters_applied` with the resolved values.

## 5. Line-first recommender (replaces spec 09 §3.1)

Inputs: goal g, filters, `goal_scan` (08), `parans.json` (10), `destinations.json`, `viability_policy.json`.

1. **Candidates:** destinations with `reviewed && !exclude`, passing the policy (§3) and all active filters (§4).
2. **Strong lines for the goal:** every line (planet × angle) with affinity `A(p,a,g) ≥ A_MIN = 0.30`, plus every
   paran with `Apar ≥ 0.30`. Sort by affinity descending.
3. **Destinations along each line:** candidates within **400 km** of the line (lines) or within **±1°** latitude
   (parans). For each, compute the **full place score** S (all lines + parans, 08/10). Keep only those with band
   `supportive` or `strongly_supportive` for g. Order by S (tie-break: `appeal`, then lower N).
4. **Groups:** take up to **4 lines**. At least 3 must be real lines if available; parans fill the rest. Each line keeps
   up to **5 destinations**, with **max 2 per country per line** and no two within 150 km of each other.
5. **Lines with nothing viable:** strong lines with 0 eligible destinations go into `lines_without_destinations`
   (e.g. "your strongest career line crosses mostly ocean and Siberia"). This is shown to the user honestly and never padded.
6. **Flat top list** (backwards-compatible `cities`): the union of the group destinations, sorted by S, deduplicated, up to 10,
   max 3 per country.
7. **Turkey block:** the same procedure restricted to TR destinations. It always runs (unless the user's region filter
   excludes `turkey`), and it ignores the city-size default so that resorts like Bodrum can appear there.
   *(Radul to confirm.)*
8. **Countries/regions lists** (09 §3.2–3.3): only admin-1 regions and countries that contain ≥ 1 destination from step 4.

Grouping by purpose for display: `by_purpose: {living: [ids], travel: [ids]}` from each destination's `purposes` ∩ the
active purpose.

## 6. Explanations (updates spec 09 §4)

| Unit | Length (TR words) | Grounding |
|---|---|---|
| `intro` | 50–80 | as before |
| each **line group** | 60–90 | the line's affinity-cell contributors for g + the A3 angle frame (or the paran records / fallback) |
| each **destination** in a group | 20–40 | what's specific to that place: its other contributing lines/parans for g, and if `has_tradeoff`, the demanding side |
| `lines_without_destinations` | 1 fixed template sentence per line (no model call) | `acg-method-orb-distance` |

The validator rules RV1–RV4 still apply; each unit's trace ⊆ its contributors.

## 7. Output (`recommend_<goal>_<scope>.json`, additions)

```json
"filters_applied": {"regions": ["all"], "city_size": ["big","mid"], "max_distance_km": null,
                    "climate": null, "purpose": ["living"], "policy": "viable_world_v1"},
"by_line": [
  {"line": {"body": "jupiter", "angle": "MC"}, "kind": "line", "affinity": 0.71,
   "text_tr": "...", "text_en": "...", "trace": [],
   "destinations": [{"id": "dst-valencia", "name": "Valencia", "country": "ES", "size": "mid",
                     "distance_km_rounded": 60, "band": "supportive", "S": 0.82,
                     "has_tradeoff": false, "text_tr": "...", "text_en": "...", "trace": []}]}
],
"lines_without_destinations": [{"line": {"body": "venus", "angle": "IC"}, "text_tr": "...", "text_en": "..."}],
"by_purpose": {"living": [], "travel": []}
```

Existing fields (`cities`, `regions`, `countries`, `turkey`) stay for compatibility.

## 8. CLI additions (`run_acg.py`)

`--regions europe,turkey` · `--city-size big,mid,small` · `--max-distance-km 3000` · `--home-city "Istanbul"` ·
`--climate warm,mild` · `--purpose living|travel|both`. Omitted means the defaults in §4.

## 9. Acceptance (`test_acg_destinations.py`)

| # | Check |
|---|---|
| DV1 | Policy fixtures: Magnitogorsk, Novosibirsk, Ulaanbaatar, Pyongyang, Chengdu, Casablanca, Nairobi, Tehran → excluded, each with the correct `policy:<rule>`. Moscow, St Petersburg, Shanghai, Beijing, Tangier, Alexandria, Tel Aviv, Dubai, Riyadh, Jeddah, Baku, Las Palmas → allowed. |
| DV2 | Defaults: no filters → `city_size = big+mid`, `climate` not applied, `regions = all`, purpose derived from the goal; all echoed in `filters_applied`. |
| DV3 | The climate filter only changes results when set; setting `warm` removes every `cold`/`mild` destination. |
| DV4 | Line-first: every destination in `by_line[i]` is ≤ 400 km from that line (or within ±1° for parans) and has an eligible band; ≤ 5 per line; ≤ 2 per country per line; none within 150 km of each other. |
| DV5 | A strong line with no viable destinations appears in `lines_without_destinations` and nowhere else. |
| DV6 | Regression, 1985-03-14 chart, career/world: no destination from P1–P4-excluded areas appears anywhere in the output. |
| DV7 | The Turkey block includes `small` destinations (e.g. Bodrum) even under default filters; the world lists don't. |
| DV8 | Filters never change S for any destination (compare against a no-filter run). |
| Gate | Radul reviews the 1979-03-30 Sofia chart × {career, love, relocation, travel}: are the lines sensible, and are the places viable? |

## 10. Open confirmations for Radul

1. P6 Central Asia default (capitals + Almaty, Samarkand, Bukhara).
2. Bahrain, Kuwait and Oman included as Gulf hubs.
3. The Turkey block ignores the size default (so resorts show there).
4. Resorts and regions (Algarve, Bali, Bodrum) are `small` and therefore **hidden in world lists by default**. Consider
   defaulting `city_size` to include `small` for the **travel** and **rest** goals only.
