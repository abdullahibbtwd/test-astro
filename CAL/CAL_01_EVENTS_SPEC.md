# CAL 01: events engine (collective + personal)

*Deterministic. Swiss Ephemeris, with the same flags and ephemeris files as L1. All internal times are UTC (JD UT). Local dates are
derived only at output time, using the user's current-location IANA timezone (CAL_00 D1).*

## 1. Bodies, aspects, points

- Transiting bodies: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto.
  **The Moon is used only for Best Days (CAL_04) and VOC; it is not a calendar transit.**
- Natal points: the 10 planets + ASC + MC (from the natal `chart.json`). Nodes are excluded in v1.
- Aspects: conjunction 0, sextile 60, square 90, trine 120, opposition 180.
- Orbs (`cal_constants.TRANSIT_ORB`): **reuse `compute_forecast`'s orbs if they exist** (Phase 0 item 1). Otherwise
  use Sun/Mercury/Venus/Mars 1.5°, Jupiter/Saturn 2.0°, Uranus/Neptune/Pluto 1.5°, the same for all aspects.

## 2. Collective events (global; built per calendar year, cached in `cal_run/_collective/<year>.json`)

| Event | Definition | Fields |
|---|---|---|
| `new_moon`, `full_moon` | exact Sun–Moon conjunction / opposition in ecliptic longitude (root-find to 1 s) | `t_utc`, `sign`, `degree` (0–30), `eclipse_id` or null |
| `solar_eclipse`, `lunar_eclipse` | `swe.sol_eclipse_when_glob` / `swe.lun_eclipse_when` (maximum) | `t_utc`, `kind` (total / annular / hybrid / partial / penumbral), `sign`, `degree`, `lunation_id` |
| `station_retrograde`, `station_direct` | root of longitude speed = 0, for Mercury…Pluto | `t_utc`, `body`, `sign`, `degree` |
| `retrograde_period` | from station R to the next station D | `body`, `start_utc`, `end_utc`, `sign_start`, `sign_end` |
| `ingress` | a body's longitude crossing a multiple of 30°, for Sun…Pluto; retrograde re-entries included, flagged `retro: true` | `t_utc`, `body`, `sign` |
| `moon_ingress` | the Moon entering a sign | `t_utc`, `sign` |
| `voc_moon` | **modern definition:** from the Moon's last exact major aspect (the 5 above) to any of Sun…Pluto until the Moon's next sign ingress | `start_utc`, `end_utc`, `last_aspect: {body, aspect}` |
| `moon_phase_daily` | not an event: a helper returning the Sun–Moon elongation at any t (0–360; waxing < 180) | — |

Build years 2026–2031 on first run; afterwards extend by 1 year when the horizon needs it.

## 3. Personal events (per user; rolling 12 months from "today" in the current tz; cached per chart)

### 3.1 Transits to natal points

For each (transiting body T ≠ Moon, aspect a, natal point N):
- The **window** starts when |sep − a| first ≤ orb and ends when it next exceeds orb. Find the **exact times** inside it
  (root-find to 1 min).
- **Episodes:** windows of the same (T, a, N) whose gap is < 60 days are merged into one episode, with `exacts: [t1, t2, t3]`
  (the retrograde triple pass). `start` = the first window start, `end` = the last window end.
- `phase` per day (for texts): `approaching` before the first exact, `exact_window` within ±1 day of any exact (±3 days for Jupiter–Pluto),
  `separating` after the last exact.
- **Importance** (deterministic):

```
w_T  = {Pluto:5, Neptune:5, Uranus:5, Saturn:4, Jupiter:3, Mars:2, Venus:1, Mercury:1, Sun:1}
w_N  = {Sun:1.5, Moon:1.5, ASC:1.5, MC:1.5, Mercury:1, Venus:1, Mars:1, Jupiter:0.7, Saturn:0.7, Uranus:0.5, Neptune:0.5, Pluto:0.5}
w_a  = {conj:1.2, opp:1.0, square:1.0, trine:0.8, sextile:0.6}
I = w_T · w_N · w_a      major ≥ 4.0   moderate ≥ 2.0   minor otherwise
```

### 3.2 Lunations and eclipses in the chart

For each collective `new_moon` / `full_moon` / eclipse in the horizon:
- `natal_house`: the Placidus house of the lunation degree (for a full moon, the **Moon's** degree).
- `hits`: natal points within **3°** (lunations) or **5°** (eclipses) by conjunction or opposition.
- Importance: `major` if a hit is on Sun/Moon/ASC/MC, or if it's an eclipse with any hit. `moderate` if it's an eclipse without a hit,
  or a lunation hitting another planet. Otherwise `minor`.

### 3.3 Stations on natal points

A collective station within **2°** of a natal point (conj/opp/square) → a personal event `station_on_point`. Importance `major`
for Mercury/Venus/Mars stations on the luminaries or angles, and for every Jupiter–Pluto station within 1°.

### 3.4 Output `personal_events.json`

```json
{"schema_version": "cal-events-1", "chart_key": "…", "tz": "Europe/Istanbul",
 "horizon": {"from_local": "2026-09-28", "to_local": "2027-09-27"},
 "events": [
   {"id": "tr:saturn:square:sun:2027a", "kind": "transit", "t_body": "saturn", "aspect": "square",
    "n_point": "sun", "start_utc": "…", "end_utc": "…", "exacts_utc": ["…"],
    "start_local": "2027-01-03", "end_local": "2027-03-20", "exacts_local": ["2027-02-10"],
    "importance": "major", "I": 6.0},
   {"id": "lun:2026-10-10:new", "kind": "new_moon", "t_utc": "…", "local_date": "2026-10-10",
    "sign": "libra", "natal_house": 10, "hits": [{"point": "mc", "aspect": "conj", "orb": 1.2}],
    "importance": "major"}
 ]}
```

Collective events are **referenced by id** in the personal file (not copied), with their local dates computed for the user's tz.

## 4. Local-time rules

- The local date of an instant = its date in the user tz (DST-aware, `zoneinfo`).
- Multi-day spans use local dates, inclusive.
- If the current location changes, recompute all local fields (the UTC data stays). The cache key includes the tz.

## 5. Acceptance (`test_cal_events.py`)

| # | Check |
|---|---|
| E1 | Eclipses 2026–2027 (UT dates): solar 2026-02-17 (annular), 2026-08-12 (total), 2027-02-06 (annular), 2027-08-02 (total); lunar 2026-03-03 (total), 2026-08-28 (partial), 2027-02-20, 2027-07-18, 2027-08-17 (penumbral). Exact dates match; kinds match. |
| E2 | Mercury stations 2026 (UT date, ±1 day): R 02-26, D 03-21, R 06-29, D 07-24, R 10-24, D 11-13. |
| E3 | Every lunation `t_utc`: Sun–Moon separation 0°/180° within 1e-4°. Every station: |speed| < 1e-5 °/day. |
| E4 | VOC: at `start_utc` a Moon major aspect to the named body is exact (1e-3°). No Moon major aspect to Sun…Pluto perfects inside (start, end). `end_utc` = the next Moon ingress (1 s). |
| E5 | Transits: at every `exacts_utc` the separation = the aspect angle within 1e-4°; windows respect the orb; the retrograde triple pass is merged into one episode (fixture: a Saturn station within 1° of a natal point). |
| E6 | Local dates: an event at 2026-10-10T22:30Z is local 2026-10-11 in Europe/Istanbul and 2026-10-10 in Europe/London. |
| E7 | Determinism: byte-identical JSON across runs; collective files identical for every user. |
| E8 | Importance fixtures: Pluto conj Sun → major; Sun sextile Neptune → minor; a new moon conj MC within 1.2° → major. |
