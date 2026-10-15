# ACG 08: goal scoring (deterministic)

*No LLM. Used by city cards (07 §6.2), the country/region view (07 §6.3), the map heat layer (§6)
and the recommender (ACG_09). Module: `Astrocartography/acg_goals.py`. All constants live in
`acg_constants.py`.*

## 1. Goal taxonomy (closed enum)

These definitions are **normative**. The tagging pass (07 §5) uses them verbatim in its prompt.

| goal | TR | EN | Definition (what a record must directly concern) |
|---|---|---|---|
| `love` | Aşk | Love | romance, attraction, dating, intimate partnership, marriage |
| `career` | Kariyer | Career | vocation, profession, public role, reputation, recognition, promotion, authority at work |
| `business` | İş ve Ticaret | Business | enterprise, commerce, deals, negotiation, clients, business partners, entrepreneurship |
| `money` | Para | Money | income, wealth, financial gain or loss, material comfort, spending |
| `family` | Aile | Family | home life, household, parents, children, roots, domestic security |
| `education` | Eğitim | Education | study, learning, teaching, writing, publishing, intellectual development |
| `creativity` | Yaratıcılık | Creativity | arts, performance, self-expression, creative work, play |
| `spirituality` | Ruhsal Gelişim | Spiritual Growth | meaning, faith, inner work, retreat, transcendence, ideals |
| `rest` | Dinlenme | Rest | ease, relaxation, calm, recuperation, low pressure |
| `travel` | Seyahat | Travel | visiting, short stays, exploration, movement, experiences as a visitor |
| `relocation` | Kalıcı Taşınma | Permanent Relocation | long-term residence, settling, belonging, putting down roots, making a place home |

## 2. Affinity table (built once per corpus version)

`build_affinity.py` → `principles_grounding/acg_goal_affinity.json` (+ `.sha256`).

For every planet `p` (10) × angle `a` (4) × goal `g` (11):

```
s = Σ w_r · cit_r   over records r with goal_effects[g] == "supportive"
c = Σ w_r · cit_r   over records r with goal_effects[g] == "challenging"
m = Σ w_r · cit_r   over records r with goal_effects[g] == "mixed"
      where the records r are:  A1 line records for (p, a)        w_r = 1.0
                                A2 planet_general records for p   w_r = 0.5
      cit_r = max(1, citation_count_r)

s' = s + 0.5·m          c' = c + 0.5·m
volume = s' + c'
net    = (s' − c') / (s' + c' + K)          K = 2.0   (smoothing: thin evidence shrinks toward 0)
A(p,a,g) = net · min(1, volume / V0)        V0 = 5.0
```

- A ∈ [−1, 1]. Store per cell: `{A, s, c, m, volume, contributors: [record ids]}`.
- Angle frames (A3) and fallback planet-in-house records (A4) **don't** enter the affinity table. They carry no goal polarity evidence specific to the planet × angle pair.
- Cells with `volume < 2` are flagged `low_evidence: true`.
- **Review gate (Radul):** the build writes `acg_goal_affinity_review.md`, a 40 × 11 grid of A values with
  flags. Sanity expectations, **not** hard-coded: Venus DSC/ASC positive for love; Jupiter MC positive for
  career/business; Saturn MC mixed or positive for career and negative for rest; Mars ASC negative for rest;
  Neptune positive for spirituality/creativity and negative or mixed for money. If a sanity expectation
  fails, the fix is in tagging or corpus, **never** a manual override of A.

## 3. Place score

For a point (city, grid point or manual lat/lon), consider every read line (10 planets × 4 angles) with
perpendicular distance `d ≤ 1000 km` (spec 02 §3 distance).

Distance weight:

```
w(d) = 1.0                              d ≤ 150
     = 1.0 − 0.5·(d − 150)/250          150 < d ≤ 400     (→ 0.5)
     = 0.5 − 0.5·(d − 400)/600          400 < d ≤ 1000    (→ 0)
```

For each goal `g`:

```
contribution_L = w(d_L) · A(p_L, a_L, g)
P = Σ max(0, contribution_L)        N = Σ max(0, −contribution_L)        S = P − N
contributors(g) = ∪ over lines L with |contribution_L| ≥ 0.05 of the affinity cell's contributor ids
```

Keep `P`, `N`, `S` and the per-line contributions (these are used by explanations and the recommender).

## 4. Bands (evaluated in this order)

| Band | Condition | TR label | EN label |
|---|---|---|---|
| `no_emphasis` | `P + N < 0.20` | Belirgin bir vurgu yok | No clear emphasis |
| `mixed` | `max(P,N) ≥ 0.35` and `min(P,N) ≥ 0.5·max(P,N)` | Karışık: hem fırsat hem zorluk | Mixed: opportunity and challenge |
| `strongly_supportive` | `S ≥ 1.00` | Güçlü şekilde destekleyici | Strongly supportive |
| `supportive` | `S ≥ 0.35` | Destekleyici | Supportive |
| `challenging` | `S ≤ −0.35` | Zorlayıcı | Challenging |
| `no_emphasis` | otherwise | Belirgin bir vurgu yok | No clear emphasis |

The thresholds (`0.20, 0.35, 0.5, 1.00`) are the **initial** constants.

**Calibration gate:** on 20 real charts × the full gazetteer, report the share of each band per goal.
Target: `strongly_supportive` 2–8% of cities per goal, `no_emphasis` 40–75%. Adjust **only the band
thresholds** (never A) and record the final values with a date in `acg_constants.py`.

## 5. Aggregates (country and region)

Score every `geo_grid` point inside the polygon, plus the gazetteer cities inside it.

```
k = max(3, ceil(0.05 · n_points))     for countries
k = max(1, ceil(0.10 · n_points))     for regions
S_agg(g) = mean of the top-k point scores S for goal g
```

The band is computed from `P_agg` and `N_agg`, the means over the same top-k points (§4).
`varies_by_region` is defined in 07 §6.3. `best_cities(g)` = the top 3 gazetteer cities in the polygon by S
(ties broken by population, descending).

## 6. Goal scan and heat layer (map mode)

`goal_scan.npz`: for every gazetteer city and every grid point, `S`, `P` and `N` for the 11 goals (float32),
plus the index arrays. **Performance target:** < 10 s per chart on the dev machine, single process,
numpy-vectorised.
- Tip: MC/IC distance is closed-form. For ASC/DSC, precompute each line's longitude per 0.25° latitude
  and use a local perpendicular search, pre-filtered to points within ±15° of latitude.

`goal_heat_<goal>.geojson`: grid points whose band ≠ `no_emphasis`, with properties `{band, S}`,
coordinates rounded to 2 decimals. It's for the UI heat or colour layer on the world map.

## 7. Acceptance (`test_acg_goals.py`)

| # | Invariant |
|---|---|
| S1 | Affinity: a synthetic corpus with 5 supportive citations and 0 challenging for (venus, DSC, love) → A = (5/7)·1 = 0.714 ± 1e-9. |
| S2 | w(d) is continuous and monotonically non-increasing: w(150)=1, w(400)=0.5, w(1000)=0, and w(1000.1) is excluded. |
| S3 | Bands: hand-built (P, N) pairs hit each band, including the order precedence (a point satisfying both `mixed` and `S ≥ 1` → `mixed`). |
| S4 | Traceability: every id in `contributors(g)` exists in the corpus and belongs to an affinity cell of a line within 1,000 km of the point. |
| S5 | Determinism: identical `goal_scan.npz` bytes over two runs. |
| S6 | Consistency: a city's score from `goal_scan.npz` equals its score from the city path (`locate` → §3) within 1e-6. |
| S7 | A point with no lines within 1,000 km → every goal `no_emphasis`, P = N = 0. |
| S8 | Performance: the goal scan completes in < 10 s on the reference chart (a warning if exceeded, not a failure). |
