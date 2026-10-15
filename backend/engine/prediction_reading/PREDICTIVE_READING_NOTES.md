# PREDICTIVE_READING_NOTES.md

Implementation notes for the predictive **reading layer** (built to `predictive_reading.md`).
This is the L4-analogue and the ONLY LLM stage in the predictive pipeline.

## Files
| File | Role |
|---|---|
| `pr_profiles.py` | The reframe-lens: general/personal/professional lead sets, lens lines, focus domain (§3, §7.7). |
| `pr_events.py` | Deterministic event → plain-line serialization, profile emphasis order, segment split, sparse count (§5, §7.2, §9). |
| `pr_prompts.py` | The literal §7 prompt blocks + the two-tier banned vocab shared with the lint (§5). |
| `pr_generate.py` | The LLM runner: cached system prefix, parallel beats + synthesis, day single-call, §8 re-ask (§2). |
| `pr_validate.py` | The §11 lint: keyset, Tier-A/B mask, word-count ±15%, focus-on-domain, planet/date leak, sparse floor. |
| `read_forecast.py` | Orchestrator: call graph per horizon, re-ask loop, validate, persist into the run folder (§10) + CLI. |
| `test_forecast_reading.py` | Offline tests (fake generator, no API key) covering every §11 invariant + the sparse path. |

## How to run
```
# offline tests (no API key):
../.venv/Scripts/python.exe test_forecast_reading.py
../.venv/Scripts/python.exe -m pytest test_forecast_reading.py -q

# dry run: build & print the event blocks, no model calls:
python read_forecast.py --input <grounded_forecast.json> --profile personal --dry-run

# real generation (needs the key for the model's provider: ANTHROPIC_API_KEY for claude-*, GEMINI_API_KEY for gemini-*):
python read_forecast.py --input <grounded_forecast.json> --profile professional
```

## Input contract — the "grounded forecast" (IMPORTANT: upstream step not yet built)
This layer consumes a **grounded forecast object**: a `compute_forecast()` object
(`Forecast_compute/compute_forecast.py`) whose every event additionally carries the
principles the forecast-grounding step matched to it:

```jsonc
event["matched_principles"] = [
  { "principle_id": "transit-aspect-...", "judgment": "<plain, tradition-masked gloss>", ... }
]
```

`judgment` is the already-plain, corpus-masked text the reading interprets FROM (§4). The
`judgment` field name and record shape come straight from the grounded corpus
(`all_principles.grounded.json`: `principle_id / rule / judgment / topic_tags / requires`).

**The forecast-grounding step that produces `matched_principles` is a separate module and
is NOT part of this delivery** (the compute spec calls it downstream; the reading spec
assumes it as input). Events with an empty/absent `matched_principles` are treated as
non-material and are dropped from the reading — the model interprets only from given texts.

## Call graph (§2)
- **day** → 1 call → `{reading}`. No synthesis.
- **month** → 3 beat calls (`early/mid/late`, parallel, each sees only its segment) → 1
  synthesis (sees full list + the 3 beats) → `overview` + `focus`.
- **year** → 4 beat calls (`q1..q4`) → 1 synthesis → `overview` + `focus`.

Segment membership is read from the compute layer's `segment` field — never recomputed.
The shared §7.1 system block is sent once with `cache_control` (prompt caching).

## Astrological detail in the text — `astro_detail` (DEVIATION from spec §5)
The spec's §5 mask hides ALL astrological machinery and speaks purely in psychological
language. For an astrology-literate audience that removes the flavour they want, so the
reading now takes an `astro_detail` control (`run_reading(..., astro_detail=…)`,
`read_forecast.py --astro-detail`, `run_predictive.py --astro-detail` / interactive menu,
recorded in `meta.astro_detail`). Three levels, each un-banning one more vocabulary bucket:

| level | may name in the text | still hidden |
|---|---|---|
| `plain` | nothing — pure psychological language (original §5 behaviour) | everything |
| `modern` *(default)* | planets, aspects (conjunction/square/trine/sextile/opposition), signs, transits, retrogrades, new/full moons & eclipses | house **numbers**, applying/separating/perfecting, cycle-stage, Placidus/whole-sign, orb, and all classical terms |
| `technical` | + house numbers, phase/cycle-stage language, and classical terms where the grounded principle supports them | (nothing) |

How it works: for `modern`/`technical` the event serializer prints the real configuration in
`[brackets]` (`[Neptune square natal Saturn in Aries]`, `technical` adds `separating stage 3`),
and the prompt instructs the model to name the driver **then** give its lived meaning — but
only what appears in the line. The lint (`pr_validate`) enforces the matching bucket set, and
the §11.5 planet leak-check still fires in every mode, so the model can only name planets that
are actually in the event list (no fabrication). Classical (TIER-A) terms stay build-blocking
below `technical`. The three vocabulary buckets live in `pr_prompts.py`
(`TIER_A_* / MODERN_* / TECH_*`), shared with the lint so prompt and enforcement never drift.

## Decisions worth knowing
- **Aspect names never surface.** The lint's Tier-B bans the geometry words in output;
  the event serializer translates them to motion-words (`pressure building`,
  `support coming to a head now`, `a fresh start settling`) via the §5 guide.
- **`ay` (Moon) is excluded from the planet-leak scan** — it is also the Turkish word for
  "month", so scanning it would false-positive constantly. The prompt still forbids naming
  mechanics; the English "Moon" and all other planet words are scanned. When a
  lunation/eclipse is in the forecast, `Moon`/`Sun` are added to the allow-list so the
  permitted sky hooks ("dolunay/full moon", "eclipse") don't trip §11.5.
- **Two-tier mask, S3-style.** Unambiguous classical/technique terms are hard-banned;
  words that are ordinary in plain Turkish/English (`bound`, `term`, `square` as a shape,
  `transit` as a visa) are caught only in their technical phrasing, so the lint doesn't
  false-fail real prose. A **Tier-A** hit is build-blocking (`is_build_blocking`), a
  **Tier-B** hit is a violation to fix — both stop the reading from shipping.
- **Word-count re-ask (§8)** rewrites only the offending section, once, before final
  validation. Sparse periods (§9) relax the floor to 60% of the word minimum.
- **Persistence (§10):** the reading is written next to its forecast as
  `reading_{horizon}_{profile}_{target_date}.json`. A rejected draft (with its errors)
  is dumped to `…rejected.json` and never shipped.

## Deferred / not built here
- The forecast-grounding step (produces `matched_principles`) — its own module.
- The eval distiller adapter (§10 says the reading is the distiller's source; the
  human-score readback stays deferred, as in natal). The reading object is self-contained
  and ready for it.
- No profection/releasing text, no numeric score, no per-event mini-readings (§12).
