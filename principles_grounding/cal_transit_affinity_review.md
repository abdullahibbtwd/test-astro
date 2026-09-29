# CAL transit affinity: review (CAL_02 §3 gate)

*schema cal-affinity-1; corpus sha 5a69fae208ab; tags sha 49f005734a0b.*

A ∈ [−1, 1] per (transiting T, aspect, natal N, goal). Record weight = 1/n per cell, so the book counts once.
With one source book, volume ≤ 1 < V0 = 5.0, so **|A| ≤ 0.067 by construction**. The day-score band thresholds are calibrated to that scale (CAL_02 §7); only the sign and relative size matter.

## 1. Expectation checks

| T | aspect | N | goal | expected | A | contributors | ok |
|---|---|---|---|---|---|---|---|
| jupiter | trine | sun | career | + | +0.0000 | — | ❌ |
| jupiter | trine | sun | money | + | +0.0200 | jupiter-trine-sun-transit | ✅ |
| saturn | square | moon | family | − | -0.0667 | saturn-square-moon, saturn-square-moon-transit | ✅ |
| saturn | square | moon | rest | − | +0.0000 | — | ❌ |
| venus | conjunction | venus | love | + | +0.0667 | venus-conjunct-venus-transit, venus-venus-conjunct | ✅ |
| saturn | opposition | venus | love | − | -0.0667 | saturn-opposition-venus, saturn-opposition-venus-transit | ✅ |
| jupiter | conjunction | mc | career | + | +0.0667 | jupiter-conjunct-midheaven-transit, jupiter-conjunct-midheaven-transit-2 | ✅ |
| saturn | square | mc | career | − | -0.0333 | saturn-square-mc-alienation, saturn-square-midheaven-transit | ✅ |
| neptune | square | sun | rest | − | -0.0667 | neptune-square-sun, neptune-square-sun-transit | ✅ |
| jupiter | trine | moon | family | + | +0.0667 | jupiter-moon-trine, jupiter-trine-moon-transit | ✅ |

8/10 expectations hold. A failure is fixed in the tagging, never the numbers.

## 2. Coverage

- cells: 535 (T = Sun…Pluto × 5 aspects × 12 natal points = 540 possible)
- cells with no goal at all: 41 (jupiter|conjunction|asc, jupiter|opposition|mars, jupiter|opposition|pluto, jupiter|square|asc, jupiter|square|sun, mars|conjunction|mars, mars|opposition|mars, mars|opposition|pluto, mars|sextile|asc, mars|sextile|uranus, mars|square|jupiter, mars|square|mars, mars|square|pluto, mars|trine|mars, mars|trine|uranus, mercury|opposition|moon, mercury|square|asc, mercury|trine|moon, neptune|conjunction|neptune, neptune|conjunction|pluto …)

| goal | cells + | cells − | cells mixed/0 |
|---|---|---|---|
| love | 72 | 84 | 37 |
| career | 60 | 46 | 21 |
| business | 52 | 23 | 8 |
| money | 34 | 37 | 11 |
| family | 32 | 32 | 3 |
| education | 83 | 4 | 17 |
| creativity | 68 | 3 | 1 |
| spirituality | 86 | 10 | 21 |
| rest | 23 | 107 | 4 |
| travel | 37 | 10 | 0 |
| relocation | 3 | 4 | 2 |

## 3. Strongest cells per goal

**love**: most supportive: venus trine venus +0.067; venus trine sun +0.067; venus trine saturn +0.067; venus trine pluto +0.067; venus trine moon +0.067; venus trine mercury +0.067

most challenging: jupiter opposition neptune -0.067; jupiter opposition saturn -0.067; mars opposition asc -0.067; mars opposition moon -0.067; mars opposition neptune -0.067; mars square asc -0.067

**career**: most supportive: venus trine mc +0.067; venus sextile sun +0.067; venus conjunction mc +0.067; uranus trine saturn +0.067; uranus trine mc +0.067; uranus sextile saturn +0.067

most challenging: jupiter square pluto -0.067; mars opposition mc -0.067; mars square mc -0.067; mercury square sun -0.067; neptune conjunction mc -0.067; neptune opposition mc -0.067

**business**: most supportive: venus trine saturn +0.067; venus trine mercury +0.067; venus sextile saturn +0.067; venus sextile mercury +0.067; venus conjunction mercury +0.067; sun trine mercury +0.067

most challenging: jupiter conjunction jupiter -0.067; mercury conjunction neptune -0.067; mercury opposition neptune -0.067; mercury square mercury -0.067; mercury square neptune -0.067; mercury square saturn -0.067

**money**: most supportive: venus trine jupiter +0.067; venus sextile mars +0.067; venus sextile jupiter +0.067; venus conjunction asc +0.067; uranus trine jupiter +0.067; sun trine venus +0.067

most challenging: jupiter opposition neptune -0.067; jupiter sextile neptune -0.067; jupiter square jupiter -0.067; jupiter square neptune -0.067; jupiter square saturn -0.067; jupiter trine neptune -0.067

**family**: most supportive: venus trine moon +0.067; venus trine asc +0.067; venus sextile moon +0.067; venus opposition mc +0.067; venus conjunction moon +0.067; uranus trine moon +0.067

most challenging: mars opposition mc -0.067; mars square mc -0.067; mars square mercury -0.067; mars square moon -0.067; neptune opposition mc -0.067; neptune opposition moon -0.067

**education**: most supportive: uranus trine mercury +0.067; uranus trine jupiter +0.067; uranus sextile mercury +0.067; uranus sextile jupiter +0.067; sun trine uranus +0.067; sun trine neptune +0.067

most challenging: neptune conjunction mercury -0.067; saturn square mercury -0.067; saturn opposition mercury -0.033; neptune opposition mercury -0.020

**creativity**: most supportive: venus trine venus +0.067; venus trine sun +0.067; venus trine pluto +0.067; venus trine neptune +0.067; venus trine mc +0.067; venus square neptune +0.067

most challenging: saturn square venus -0.067; venus opposition sun -0.033; saturn opposition venus -0.020

**spirituality**: most supportive: venus sextile pluto +0.067; uranus trine pluto +0.067; uranus trine neptune +0.067; uranus trine jupiter +0.067; uranus trine asc +0.067; uranus sextile uranus +0.067

most challenging: neptune opposition jupiter -0.067; neptune square jupiter -0.067; neptune square sun -0.067; saturn opposition neptune -0.067; saturn square neptune -0.067; uranus square uranus -0.067

**rest**: most supportive: venus trine sun +0.067; venus square sun +0.067; venus conjunction sun +0.067; sun trine venus +0.067; sun trine sun +0.067; sun trine asc +0.067

most challenging: jupiter conjunction mars -0.067; jupiter square saturn -0.067; mars conjunction neptune -0.067; mars conjunction saturn -0.067; mars opposition asc -0.067; mars opposition neptune -0.067

**travel**: most supportive: venus trine mercury +0.067; venus trine jupiter +0.067; uranus trine mercury +0.067; uranus sextile jupiter +0.067; sun trine mercury +0.067; sun trine jupiter +0.067

most challenging: mars conjunction mercury -0.067; mars opposition mercury -0.067; mars square mercury -0.067; mercury conjunction uranus -0.067; mercury opposition mars -0.067; mercury opposition mercury -0.067

**relocation**: most supportive: pluto sextile mc +0.067; pluto square mc +0.020; jupiter trine mc +0.020

most challenging: pluto opposition mc -0.067; saturn conjunction uranus -0.067; uranus square moon -0.020; saturn conjunction saturn -0.010

