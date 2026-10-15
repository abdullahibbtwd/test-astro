# CAL_02 §7 calibration

*10 real charts (runs/, distinct birth dates) × 12 months from 2026-09-28, each in its birth tz. Only thresholds are tuned: one factor λ scales every spec threshold.*

Charts: 1990-07-13 (Europe/Sofia), 1985-05-12 (Europe/Sofia), 1989-12-23 (Europe/Sofia), 1989-04-09 (Europe/Sofia), 1996-02-22 (Europe/Sofia), 1979-03-30 (Europe/Sofia), 1994-10-26 (Europe/Sofia), 1988-07-07 (Europe/Sofia), 1988-08-26 (Europe/Sofia), 1998-07-25 (Europe/Sofia)

## Spec thresholds (λ = 1)

`{'quiet': 0.15, 'mixed_min': 0.3, 'mixed_ratio': 0.5, 'strong': 0.8, 'normal': 0.3}`

| goal | favorable | challenging | mixed | quiet | strong | periods/quarter | in target |
|---|---|---|---|---|---|---|---|
| love | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0 | ❌ |
| career | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0 | ❌ |
| business | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0 | ❌ |
| money | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0 | ❌ |
| family | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0 | ❌ |
| education | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0 | ❌ |
| creativity | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0 | ❌ |
| spirituality | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0 | ❌ |
| rest | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0 | ❌ |
| travel | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0 | ❌ |
| relocation | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0 | ❌ |

## Proposed: λ = 0.04

`{'quiet': 0.006, 'mixed_min': 0.012, 'mixed_ratio': 0.5, 'strong': 0.032, 'normal': 0.012}`  (loss 1.094)

| goal | favorable | challenging | mixed | quiet | strong | periods/quarter | in target |
|---|---|---|---|---|---|---|---|
| love | 15.9% | 28.0% | 9.1% | 47.0% | 19.9% | 2.6 | ❌ |
| career | 13.9% | 21.7% | 5.6% | 58.8% | 11.3% | 2.1 | ✅ |
| business | 18.9% | 2.8% | 1.4% | 76.9% | 2.2% | 1.4 | ❌ |
| money | 7.2% | 17.4% | 1.5% | 74.0% | 5.7% | 1.4 | ❌ |
| family | 15.3% | 21.0% | 2.9% | 60.9% | 18.9% | 1.4 | ✅ |
| education | 29.4% | 1.0% | 0.0% | 69.5% | 8.7% | 0.9 | ❌ |
| creativity | 24.9% | 0.6% | 1.1% | 73.3% | 8.2% | 1.4 | ❌ |
| spirituality | 35.4% | 10.6% | 4.1% | 49.9% | 22.2% | 0.9 | ❌ |
| rest | 1.6% | 47.2% | 1.5% | 49.7% | 26.5% | 1.4 | ❌ |
| travel | 11.6% | 0.9% | 0.1% | 87.3% | 2.2% | 1.1 | ❌ |
| relocation | 2.1% | 0.0% | 0.0% | 97.9% | 0.0% | 0.0 | ❌ |

## Sweep

| λ | loss |
|---|---|
| 0.02 | 1.838 |
| 0.04 | 1.094 |
| 0.06 | 1.130 |
| 0.08 | 1.273 |
| 0.1 | 1.468 |
| 0.12 | 1.705 |
| 0.14 | 1.929 |
| 0.16 | 2.119 |
| 0.18 | 2.267 |
| 0.2 | 2.425 |
| 0.22 | 2.551 |
| 0.24 | 2.623 |
| 0.26 | 2.677 |
| 0.28 | 2.710 |
| 0.3 | 2.726 |
| 0.32 | 2.733 |
| 0.34 | 2.737 |
| 0.36 | 2.742 |
| 0.38 | 2.744 |
| 0.4 | 2.747 |
| 0.42 | 2.747 |
| 0.44 | 2.748 |
| 0.46 | 2.750 |
| 0.48 | 2.750 |
| 0.5 | 2.750 |
| 0.52 | 2.750 |
| 0.54 | 2.750 |
| 0.56 | 2.750 |
| 0.58 | 2.750 |
| 0.6 | 2.750 |

Targets: favorable 10–25%, challenging 10–25%, quiet ≥ 40%, 1–4 periods per goal per quarter.
Goals that stay outside the targets at the best λ are sparse in the corpus. Fix that in tagging or corpus, not in per-goal thresholds (the spec allows one threshold set).
