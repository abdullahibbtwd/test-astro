# CAL 04: Best Days (electional scoring, 90 days)

*Deterministic scoring per local day and activity. Modern only. **Every scoring factor must be grounded in ≥ 1 modern corpus record, or it is
disabled** (grounding gate, §3). The weights below are initial domain values, tunable only at the calibration gate (§6).*

## 1. Activities (closed enum)

| key | TR | EN |
|---|---|---|
| `love` | Aşk | Love |
| `meetings` | Görüşmeler ve Randevular | Meetings & Appointments |
| `business` | İş | Business |
| `contract` | Sözleşme İmzalama | Signing a Contract |
| `conversation` | Önemli Konuşma | Important Conversation |
| `travel` | Seyahat | Travel |
| `shopping` | Alışveriş | Shopping |
| `project_start` | Proje Başlatma | Starting a Project |
| `interview` | İş Görüşmesi | Job Interview |
| `moving` | Taşınma | Moving House |

## 2. The day

A local day in the user's **current tz**. The "active window" is **08:00–22:00 local**. The Moon's position is taken at **local 12:00**.
Houses are natal Placidus (CAL_00 D7). DSC = ASC + 180° and IC = MC + 180° are added as natal points for this spec only.

## 3. Factor catalogue (`best_days_factors.json`)

Each factor has `{id, kind: collective|personal, weights: {activity: w}, cap, grounding: [record ids], enabled}`.

### 3.1 Collective factors (same for everyone in the same tz)

| id | Value on day d | Weights (activity: w) |
|---|---|---|
| C1 `voc_fraction` | f = the share of the active window with a VOC Moon (0–1) | contract −2, project_start −2, business −2, interview −2, shopping −2, moving −2, meetings −1, conversation −1, travel −1, love −0.5 (× f) |
| C2 `mercury_rx` | 1 if Mercury is retrograde at local noon | contract −1.5, conversation −1, interview −1, shopping −1, travel −1, meetings −1, business −1, project_start −0.5, moving −0.5 |
| C3 `venus_rx` | 1 if Venus is retrograde | love −1.5, shopping −1, business −0.5 |
| C4 `mars_rx` | 1 if Mars is retrograde | project_start −1, moving −1, business −0.5 |
| C5 `eclipse_window` | 1 if within ±3 days of an eclipse | project_start −1.5, contract −1.5, moving −1.5, business −1, interview −1, love −0.5 |
| C6 `waxing_moon` | 1 if the elongation is in 12°–168° (a waxing Moon, not the dark or full days) | project_start +0.5, business +0.5, contract +0.5, moving +0.5, interview +0.5 |
| C7 `moon_benefic_aspects` | the count of exact Moon conj/sext/trine to Venus or Jupiter within the active window (cap 2) | all activities +0.5 each |
| C8 `moon_malefic_aspects` | the count of exact Moon conj/square/opp to Mars or Saturn within the active window (cap 2) | all activities −0.5 each |

### 3.2 Personal factors

Key points and houses per activity:

| activity | key natal points | houses (transiting Moon) |
|---|---|---|
| love | Venus, Moon, DSC | 5, 7 |
| meetings | Mercury, Sun, ASC | 3, 7, 11 |
| business | Jupiter, Sun, Mercury, MC | 2, 7, 10 |
| contract | Mercury, Jupiter, Saturn | 3, 7 |
| conversation | Mercury, Moon | 3, 7 |
| travel | Jupiter, Mercury | 3, 9 |
| shopping | Venus, Jupiter | 2 |
| project_start | Sun, Mars, Jupiter, MC | 1, 5, 10 |
| interview | Sun, Mercury, Jupiter, MC | 6, 10 |
| moving | Moon, Venus, IC | 4 |

| id | Value | Weight |
|---|---|---|
| P1 `benefic_transits` | Σ intensity (CAL_02 §4) of Sun/Venus/Jupiter conj/sext/trine transits to the activity key points | +1 × Σ, cap +2 |
| P2 `hard_transits` | Σ intensity of Mars/Saturn/Uranus/Neptune/Pluto conj/square/opp transits to the activity key points | −1 × Σ, cap −2 |
| P3 `moon_in_house` | 1 if the transiting Moon at local noon is in one of the activity houses | +0.75 |
| P4 `moon_to_key_points` | exact Moon aspects to the activity key points within the active window: sext/trine +0.5 each; square/opp −0.5 each | cap ±1 |

### 3.3 Grounding gate

- A factor is `enabled` only if `grounding` lists ≥ 1 **modern** corpus record whose meaning supports the factor
  (e.g. a VOC Moon record for C1, Mercury retrograde records for C2, Hand transit records for P1/P2, Hand transiting-Moon-in-house records for P3).
  The Phase 0 audit fills these lists; Radul approves them.
- Disabled factors have weight 0 and are listed in `factors_disabled` in every output.
- **Expected gap:** C1–C8 may have little or no modern grounding in the current corpus (it's natal and transit-oriented).
  Supplying a modern source on lunar timing / electional practice as a TXT file enables them through a corpus delta
  (the ACG_06 pattern; a later spec, CAL_06). P1–P4 should be groundable today via Hand.

## 4. Score, grades, gates

```
R_act(d) = Σ_factors w · value (with caps)
```

| Grade | Condition |
|---|---|
| `excellent` | R ≥ 2.0 and no hard gate |
| `good` | R ≥ 1.0 and no hard gate |
| `neutral` | −1.5 < R < 1.0 |
| `avoid` | R ≤ −1.5 **or** a hard gate |

Hard gates (applied only if the factor is enabled):
- contract / project_start / business / interview: `voc_fraction ≥ 0.6`
- contract / project_start / moving: within ±1 day of an eclipse
- contract: within ±1 day of a Mercury station

## 5. Outputs (`best_days.json`, one file per user covering all activities)

Per activity:
- `days`: all 90 days `{local_date, R, grade, factors: [{id, value, contribution}]}`.
- `top_days`: the up to 5 highest R with grade ≥ good, in date order.
- `windows`: runs of ≥ 2 consecutive days with grade ≥ good `{start, end, n}`. These feed the notification candidates (CAL_02 §6, `favorable_window`).
- `avoid_days`: all days graded `avoid`, with the triggering gate or factor.
- `reasons` per top day: the top 3 positive and the top 2 negative contributions as **deterministic labels** (TR/EN catalogue), e.g.
  "Büyüyen Ay / Waxing Moon", "Venüs, Venüs'ünüze üçgen / Venus trine your Venus",
  "Ay 7. evinizde (Ortaklıklar) / Moon in your Partnerships area".
- `text_tr` / `text_en` per top day (30–50 words, grounded in the enabled factors' records for that day, via the CAL_03 machinery).
  Other days have labels only.

Plus `factors_disabled` and `calibration_version`.

## 6. Calibration gate

On 10 charts × 90 days, report per activity the share of each grade. Targets: excellent 3–10%, good 10–25%, avoid 10–25%.
Adjust thresholds, and weights only with Radul's sign-off, and record the version.

## 7. Acceptance (`test_best_days.py`)

| # | Check |
|---|---|
| B1 | VOC fraction: a fixture day with a known VOC span gives the right fraction of 08:00–22:00 in two different tzs. |
| B2 | A disabled factor contributes 0 and appears in `factors_disabled`. |
| B3 | Hard gates override R (a fixture with R = 2.5 and voc_fraction 0.7 → contract `avoid`). |
| B4 | Windows: runs of ≥ 2 good+ days only; `favorable_window` candidates are produced for each. |
| B5 | Reasons are exactly the top contributions by magnitude, with the correct labels. |
| B6 | Determinism; a tz change shifts local days but the factor definitions stay the same. |
| Gate | Radul reviews 1 chart × 10 activities × 90 days (grades + reasons) for plausibility. |
