# ACG 09: "Where Should I Go?" recommender

*The ranking is deterministic (ACG_08 scores). The LLM only writes grounded explanations.
Module: `acg_reading/ar_recommend.py` (explanations) + `Astrocartography/acg_recommend.py` (ranking).*

## 1. Input

| Field | Values | Notes |
|---|---|---|
| `goal` | one of the 11 goals (08 §1) | required |
| `scope` | `world` (default), `TR`, or any ISO-2 code | the country filter |
| `query_text` | optional free text, e.g. "Kariyer için en iyi yer neresi?" | mapped to `goal` by §2 when `goal` is absent |

## 2. Free-text → goal (optional path)

A single cheap-model call with a **closed enum** output: `{goal: <enum> | null, confidence: 0–1}`.
The prompt holds the 08 §1 table. If the result is `null` or `confidence < 0.6`, return `status: "needs_goal"` with
the 11 options (TR/EN labels) so the UI can ask. **Never guess.** Unit-test it with 22 fixed phrases
(2 per goal, TR + EN) plus 5 off-topic phrases that must return `needs_goal`.

## 3. Ranking (`acg_recommend.py`, deterministic)

Inputs: `goal_scan.npz` (08 §6), `gazetteer.json`, `countries.json`, `regions.json`.

### 3.1 Cities

1. Candidates: gazetteer cities in `scope` with band ∈ {`strongly_supportive`, `supportive`} for `goal`.
2. Sort by `S` descending; break ties by lower `N`, then population descending.
3. **Diversity** (greedy, in sorted order):
   - Each city's **dominant line** = the line with the largest positive contribution.
   - At most **2 cities per dominant line**.
   - At most **3 cities per country** (world scope only).
   - Cities less than **150 km** from an already chosen city are skipped (it avoids listing Istanbul's suburbs).
4. Take up to **10**. **Don't pad**: if fewer than 3 qualify, return what there is plus `thin_result: true`.

### 3.2 Regions

Admin-1 regions in `scope`, scored by 08 §5. Keep those with an eligible band, sort by `S_agg`, apply the same
dominant-line rule (max 2 per line) and max 2 per country. Take up to **5**.

### 3.3 Countries

Only for `scope = world`. Countries scored by 08 §5 with an eligible band, sorted by `S_agg`. Take up to **5**. Each
country carries its `best_cities(goal)` (top 3) and its best region.

### 3.4 Turkey block (always)

For `scope = world`, also run §3.1–3.2 with `scope = TR` and return it as a separate `turkey` block (up
to 5 cities and 3 regions). It is shown even when Turkey has no eligible places: in that case it holds an empty
list plus the single best TR city by `S`, marked `band` as-is (honest), with its explanation.

### 3.5 Honesty fields

For every recommended item, store: `band`, `S`, `P`, `N`, `dominant_line`, `supporting_lines`
(contribution > 0.05), `challenging_lines` (contribution < −0.05), and `contributors` (record ids).
If `N ≥ 0.25`, set `has_tradeoff: true`. The explanation must then mention the demanding side.

## 4. Explanations (LLM, grounded)

Reuse the reading pipeline (TR draft → EN translation → detox → validate).

| Unit | Length (TR words) | Grounding |
|---|---|---|
| `intro` (1 per result) | 50–80 | `acg-method-ambivalence`, `acg-method-natal-modifies-response`, `acg-method-orb-distance` + the goal definition |
| each city | 40–70 | the item's `contributors` for `goal` + the A3 frame of the dominant line |
| each region | 30–50 | same, from the region's top-k points |
| each country | 40–70 | same + a mention of its best region/city by name |
| `turkey` block intro | 30–50 | as for city; if there are no eligible TR places, say so plainly (trace `acg-method-no-influence`) |

Prompt rules: the reading rules from spec 04 §4 (no numbers, distances, angle jargon or house numbers; no
directives; sensitivity rule 8), plus:
- Explain **why** through the planet's theme and where it shows up. For example: "Jüpiter'in zirve çizgisi
  burada görünürlük ve mesleki büyüme temasını öne çıkarır…"
- If `has_tradeoff`, one sentence names the demanding side.
- Name the place with `name_tr` (TR) / `name` (EN).
- The explanation may not assert a band different from the item's band (AV9 logic: start with the band label).

The validator applies AV1–AV12, plus:

| # | Rule |
|---|---|
| RV1 | Every explanation's trace ⊆ that item's `contributors` ∪ the frame/method ids listed above. |
| RV2 | Every item with `has_tradeoff: true` has ≥ 1 traced record with polarity challenging or mixed. |
| RV3 | Item order and membership in the output = the deterministic ranking (the model never reorders or drops). |
| RV4 | No superlatives that imply certainty: TR `en iyi yer kesinlikle`, `garantili`; EN `the best place for sure`, `guaranteed`. |

## 5. Output `recommend_<goal>_<scope>.json`

```json
{
  "schema_version": "acg-recommend-1",
  "goal": "career", "goal_label_tr": "Kariyer", "scope": "world",
  "status": "ok | needs_goal | thin_result",
  "intro": {"tr": "...", "en": "...", "trace": []},
  "cities":    [{"id": "gn-2643743", "name": "London", "name_tr": "Londra", "country": "GB",
                 "band": "strongly_supportive", "band_label_tr": "Güçlü şekilde destekleyici",
                 "dominant_line": {"body": "jupiter", "angle": "MC", "distance_km_rounded": 60},
                 "has_tradeoff": false, "text_tr": "...", "text_en": "...", "trace": []}],
  "regions":   ["..."],
  "countries": ["..."],
  "turkey":    {"intro": {}, "cities": [], "regions": []},
  "footer":    {"tr": "...", "en": "..."}
}
```

`dominant_line.distance_km_rounded` is UI data (07 §4 rules). The footer is the fixed spec 04 §6 text.

## 6. Acceptance (`test_acg_recommend.py`)

| # | Check |
|---|---|
| W1 | Ranking is deterministic and identical over two runs (no LLM involved in §3). |
| W2 | Diversity: no dominant line appears more than twice among the cities; no country more than 3 times (world); no two cities are within 150 km. |
| W3 | Only eligible bands are recommended; a fixture chart where nothing qualifies → `thin_result`, with no padding. |
| W4 | The Turkey block is always present for world scope, including the "none eligible" fixture. |
| W5 | `--scope DE` returns only German cities and regions and no `countries` list. |
| W6 | Free-text classification: 22/22 on-topic phrases correct, 5/5 off-topic → `needs_goal`. |
| W7 | RV1–RV4 each have a unit test (one positive, one negative). |
| W8 | `--dry-run` produces the ranking and the prompts with zero model calls. |
| Gate | Radul reviews 1 real chart × 4 goals (career, love, family, relocation) × world scope: does the ranking make sense against the affinity table, and is the text honest about tradeoffs? |
