# CAL_04 §6 Best Days calibration

*10 real charts × 90 days from 2026-09-28 × 10 activities; C-factors disabled (Q4), so no hard gates. Only grade thresholds tuned; weights unchanged.*

## Spec thresholds

`{'excellent': 2.0, 'good': 1.0, 'avoid': -1.5}`

| activity | excellent | good | neutral | avoid | in target |
|---|---|---|---|---|---|
| love | 0.7% | 10.9% | 88.3% | 0.1% | ❌ |
| meetings | 2.6% | 12.9% | 82.1% | 2.4% | ❌ |
| business | 1.0% | 8.2% | 84.4% | 6.3% | ❌ |
| contract | 0.3% | 10.0% | 88.9% | 0.8% | ❌ |
| conversation | 1.2% | 11.0% | 87.7% | 0.1% | ❌ |
| travel | 0.3% | 8.3% | 91.0% | 0.3% | ❌ |
| shopping | 0.0% | 3.8% | 96.2% | 0.0% | ❌ |
| project_start | 0.1% | 5.1% | 87.9% | 6.9% | ❌ |
| interview | 1.3% | 6.4% | 84.8% | 7.4% | ❌ |
| moving | 0.2% | 6.9% | 92.1% | 0.8% | ❌ |

## Proposed thresholds (loss 0.194)

`{'excellent': 1.25, 'good': 0.55, 'avoid': -0.8}`

| activity | excellent | good | neutral | avoid | in target |
|---|---|---|---|---|---|
| love | 7.1% | 24.4% | 64.2% | 4.2% | ❌ |
| meetings | 11.3% | 19.7% | 56.2% | 12.8% | ❌ |
| business | 6.1% | 15.3% | 54.1% | 24.4% | ✅ |
| contract | 6.4% | 19.4% | 61.6% | 12.6% | ✅ |
| conversation | 8.7% | 21.2% | 63.8% | 6.3% | ❌ |
| travel | 5.4% | 18.2% | 66.7% | 9.7% | ❌ |
| shopping | 2.8% | 9.7% | 79.4% | 8.1% | ❌ |
| project_start | 2.6% | 11.1% | 58.3% | 28.0% | ❌ |
| interview | 5.1% | 13.3% | 55.6% | 26.0% | ❌ |
| moving | 3.6% | 15.0% | 72.9% | 8.6% | ❌ |

Targets: excellent 3–10%, good 10–25%, avoid 10–25%.
