# PREDICTIVE_ORCHESTRATION_SPEC.md

Build spec for `run_predictive.py` — the top-level orchestrator of the predictive pipeline.
It turns one user request into a persisted run: resolve input → natal chart → forecast →
grounding → reading(s), owning the run folder and the run manifest. It mirrors the natal
`run.py` contract (compute stays pure; the orchestrator owns all I/O and sequencing).

Depends on: `compute_chart.py` (built), `compute_forecast.py` (built),
`ground_forecast.py` (spec: FORECAST_GROUNDING_SPEC.md — build first), and the reading
layer's `read_forecast.py` generate function (built). Confirm the real `run.py` /
`read_forecast.py` signatures before wiring and mirror them.

---

## 0. Role and shape

Single entry point `run_predictive(request) -> RunResult`, plus a CLI. Pure-ish: stage
functions are called in sequence; a single writer persists every artifact into one run
folder. The orchestrator never interprets or computes astrology itself — it sequences,
handles failure, and records.

---

## 1. Pipeline stages and the profile/horizon asymmetry

```
request
  │
  ├─0  resolve input         location → coords (geocode), validate, default target_date="today"
  ├─1  compute_chart         BirthData → natal chart object            [deterministic, cacheable]
  ├─2  compute_forecast      (natal, target_date, horizon) → forecast  [deterministic; horizon-specific]
  ├─3  ground_forecast       (forecast, natal) → forecast+matched + coverage report  [deterministic]
  ├─4  reading   (×profiles) grounded forecast → sectioned Turkish reading  [LLM; per profile]
  └─5  persist + manifest    write all artifacts + run_manifest.json
```

**The asymmetry that drives batching (state it, implement it):**
- **Profile is a read-time lens** — stages 1–3 are profile-agnostic. So for a multi-profile
  request, run 1–3 **once** and loop stage 4 over the requested profiles, reusing the same
  grounded forecast. Never recompute compute/forecast/grounding per profile.
- **Horizon changes the event window** — stages 2–3 are horizon-specific. A multi-horizon
  request re-runs 2–3 per horizon (stage 1 natal is still shared).

Default request = one horizon + one profile. Optional `profiles: [...]` and `horizons: [...]`
enable batching with the sharing above.

---

## 2. Request object

```jsonc
{
  "birth": { "year","month","day","hour","minute", "location": "<string>",
             "time_precision": "exact" | "approximate" | "unknown" },
  "target_date": "YYYY-MM-DD" | null,      // null → "today" in birth-location tz
  "horizon": "day" | "month" | "year",     // or "horizons": [...]
  "profile": "general" | "personal" | "professional",   // or "profiles": [...]
  "config": { "enable_profections": false, "enable_lots_targets": false,
              "surface_planets": true }
}
```
Stage 0 validates, geocodes `location` → `(latitude, longitude)` (geopy/Nominatim; **cache by
location string**, since it's a network call and not deterministic), and resolves
`target_date`. Coordinates are held by the orchestrator and passed to BOTH `compute_chart`
and `compute_forecast` (the latter needs them for the day/hour ruler; the natal object does
not carry them).

---

## 3. Run folder layout

One folder per run, `runs/<run_id>/` with `run_id = YYYYMMDD-HHMMSS_<3char>` (same scheme as
natal/synastry). The orchestrator **mints the run_id and owns the folder**; every stage
writes into it — including the reading stage, which must be called with this folder rather
than minting its own.

```
runs/<run_id>/
  input.json                                   # the resolved request (coords included)
  natal_chart.json                             # stage 1
  forecast_<horizon>.json                      # stage 2  (one per horizon)
  forecast_grounded_<horizon>.json             # stage 3
  grounding_report_<horizon>.json              # stage 3 coverage (events_with_zero_matches)
  reading_<horizon>_<profile>_<target>.json    # stage 4 (one per horizon×profile)
  reading_<...>.rejected.json                  # stage 4, only if a draft failed validation
  run_manifest.json                            # stage 5
```

---

## 4. Stage contracts

Each stage is a typed function; the orchestrator wires them and the writer persists. On any
stage raising, the orchestrator records the failure in the manifest, writes whatever
artifacts already completed, and stops (no partial reading ships).

| Stage | Function (mirror real sig) | Output artifact | Deterministic |
|---|---|---|---|
| 0 resolve | `resolve_input(request)` | `input.json` | geocode cached, else yes |
| 1 natal | `compute_chart(BirthData)` | `natal_chart.json` | yes |
| 2 forecast | `compute_forecast(natal, target, horizon, lat, lon, config)` | `forecast_<h>.json` | yes |
| 3 grounding | `ground_forecast(forecast, natal)` | `forecast_grounded_<h>.json` + report | yes |
| 4 reading | `generate_reading(grounded, profile, folder, config)` | `reading_<h>_<p>_<t>.json` | no (LLM) |
| 5 manifest | writer | `run_manifest.json` | yes |

---

## 5. Failure handling and run status

The manifest carries a `status`:
- **ok** — all stages passed; reading validated and shipped.
- **degraded** — shipped, but with a caveat worth surfacing: `meta.sparse=true`, or
  `grounding_report.events_with_zero_matches` above a threshold (recall-thin), or a birth
  time so imprecise the forecast came back `degraded`. Degraded runs still ship a reading;
  the status flags that it rests on thin material.
- **failed** — a deterministic stage errored, or the reading could not pass validation after
  its bounded re-ask. The failed reading is written to `…rejected.json` and NOT shipped;
  `status=failed` with the offending stage + errors recorded.

Coverage-driven degradation is the concrete payoff of the recall-visibility work: the
orchestrator reads `events_with_zero_matches` from stage 3 and, if the grounded material is
thin, marks the run degraded rather than letting a starved reading pass silently as if the
period were genuinely quiet.

---

## 6. Run manifest

`run_manifest.json` makes every run auditable and the deterministic stages reproducible:
```jsonc
{
  "run_id", "status", "created_at",
  "request_hash",                     // hash of the resolved input
  "natal_ref",                        // sha256 of the natal object (matches forecast.meta)
  "corpus_version": { "file": "all_principles_grounded_with_predictive.json",
                      "record_count": 3263, "hash": "<sha256>" },
  "stages": [ { "name","status","artifact","duration_ms","error": null } ],
  "params": { "grounding": { "cap": 6, "similarity_floor": 0.35, "stage2_enabled": true },
              "reading":   { "model", "temperature", "surface_planets" },
              "config":    { "enable_profections": false, "enable_lots_targets": false } },
  "outputs": { "horizons": [...], "profiles": [...], "readings": [ "<path>", ... ] }
}
```
The corpus hash + record count pin which corpus a run grounded against — so a later corpus
change is visible in the run history.

---

## 7. Natal reuse / caching (optional, off by default)

The same natal chart serves many forecasts (dates, horizons, profiles). Support an optional
natal cache keyed by the **birth-data hash** (birth fields + resolved coords + precision):
on hit, load `natal_chart.json` from the cache instead of recomputing. Default: recompute
each run (simplest, fully correct). Always record `natal_ref` so dedup/caching can be turned
on later without changing artifacts. This is a performance switch, Radul's call.

---

## 8. Determinism boundaries

Stages 0–3 and 5 are deterministic and reproducible; stage 4 (reading) is not (LLM). The
manifest records enough to reproduce the deterministic spine exactly (inputs, corpus hash,
params) and to characterize the reading (model, params). A re-run of the same request mints
a new run folder; the deterministic artifacts will be byte-identical, only the reading prose
varies.

---

## 9. CLI

```
python run_predictive.py --location "Istanbul, TR" --date 1990-06-15 --time 14:30 \
    --precision exact --target today --horizon month --profile personal
# batching:
python run_predictive.py ... --horizon month --profiles general,personal,professional
python run_predictive.py ... --profile personal --horizons day,month,year
python run_predictive.py --request request.json          # full request object
python run_predictive.py --request request.json --dry-run  # stages 0–3 only, no LLM
```
`--dry-run` executes the deterministic spine and stops before the reading — useful for
inspecting the grounded forecast and coverage without spending model calls.

---

## 10. Invariants (tests)

1. Stages 1–3 run exactly once for a multi-profile, single-horizon request (assert no
   duplicate compute/forecast/grounding calls); stage 4 runs once per profile.
2. For a multi-horizon request, stages 2–3 run once per horizon; stage 1 once total.
3. The run folder contains every expected artifact for the requested horizon×profile matrix,
   and nothing from a non-requested combination.
4. A stage exception yields `status=failed`, the completed artifacts on disk, the offending
   stage recorded, and NO shipped reading (only `…rejected.json` if the reading itself failed).
5. `status=degraded` iff (reading sparse) OR (events_with_zero_matches ≥ threshold) OR
   (forecast degraded) — and a reading still shipped.
6. `run_manifest.json` pins `corpus_version.hash` and `natal_ref`; the natal_ref equals
   `forecast.meta.natal_ref`.
7. `--dry-run` writes stages 0–3 artifacts and no reading; makes zero model calls.
8. Determinism: two non-dry runs of one request produce byte-identical stage 1–3 artifacts
   (reading may differ).

---

## 11. Non-goals / deferred

- No profection/ZR stages — those modules ship off upstream; if enabled later they enter via
  stages 2–3 unchanged, and the orchestrator needs no change.
- No web/API surface — this is the batch/CLI orchestrator; a request-serving layer is
  separate.
- No cross-run deduplication beyond the optional natal cache.
- The orchestrator does not re-ground the corpus or retrain embeddings — it consumes the
  already-built corpus and index.
