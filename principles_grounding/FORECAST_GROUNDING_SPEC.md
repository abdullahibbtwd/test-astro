# FORECAST_GROUNDING_SPEC.md

Build spec for `ground_forecast.py` — the forecast analogue of `ground.py`. It is the step
the reading layer's input contract depends on and that the compute/reading specs both defer
to. It takes the deterministic forecast (events) plus the natal chart, and attaches to each
event the predictive principles that are verifiably about that event. Its output is the
`matched_principles` array the reading layer already consumes.

**Deterministic-first, no runtime LLM.** The backbone is exact structured matching against
`about`; a semantic residual (reusing the existing L2 retrieval infra) only fills the gaps.
This is the call we locked earlier: structure-to-structure first, embeddings for the
`other`/`unclassified` residual, model calls never.

---

## 0. Mirror `ground.py`, change only the subject

`ground.py` keeps a principle iff its subject is true of a **static chart**. Forecast
grounding keeps a principle iff its subject is true of a **transient event**. The
three-gate structure, the drop-logging, and the `GroundingResult` shape are all reused; the
only thing that changes is Gate B's reconciliation target.

| | `ground.py` (natal) | `ground_forecast.py` (this) |
|---|---|---|
| Subject reconciled | one natal chart | each forecast **event** |
| Gate A domain | `{natal}` / `{natal,basics}` | **`{predictive, timing}`** |
| Gate B subject | `about` vs chart placements | `about` vs the **event's** configuration |
| Gate C requires | satisfiable in chart | satisfiable in the **natal chart** (unchanged logic) |
| Result unit | kept-for-chart, bundled by factor | kept-per-event, injected as `matched_principles` |

**Reuse verbatim** from the existing module where the logic is subject-agnostic:
`grounding_schema.invariant_violation`, `grounding_vocab.DIGNITY_TO_CLASSIFICATION`, Gate A,
Gate C (`_requirement_satisfiable` / `_gate_c`), and the `DropLog` / report machinery. Add a
reading key: `_READING_DOMAINS["predictive"] = {"predictive", "timing"}`.

---

## 1. Inputs and outputs

**Inputs:** the forecast object (`compute_forecast()` output) and the natal chart object
(same chart the forecast was built on — needed for Gate C satisfiability and any natal-side
fact not already carried on the event).

**Primary output:** the forecast object, unchanged except each event gains
```jsonc
event["matched_principles"] = [
  { "principle_id": "...", "judgment": "<plain gloss the reading interprets from>",
    "topic_tags": [...], "tradition": "modern",
    "source_stage": "structural" | "embedding", "similarity": <float|null> }
]
```
`judgment` is copied straight from the grounded corpus record (the reading layer already
expects this field). Cap at **N per event** (suggest 6). **Modern-only:** only records
with `tradition == "modern"` are eligible (same rule as CAL D3). The predictive+timing slice
is *not* all modern — it holds 32 traditional `general`/`unclassified` records — so the
tradition gate is enforced in the index build and on Stage-2 hits, not assumed.

**Secondary output — coverage report** (the recall-visibility artifact I flagged): per-event
kept count, `drops_by_gate`, structural-vs-embedding split, and — critically —
`events_with_zero_matches` listed explicitly, so a grounding **recall gap** is never
confused with a genuinely **quiet** period. The reading's sparse path and eval both read
this.

---

## 2. Stage 1 — deterministic exact-match index (the backbone)

Build once per run, from the predictive-domain slice of the merged corpus
(`all_principles_grounded_with_predictive.json`, 1,589 predictive records):

- **Aspect index** — key `(source, target, type)` → records with
  `about.factor_type == "aspect"`. **Directed:** corpus aspect records are
  `source = transiting planet`, `target = natal point` (Hand, *Planets in Transit*).
- **House index** — key `(point, house, house_system)` → `planet_in_house` records; and key
  `(house, house_system)` → `house_domain` records.
- **Sign index** — key `point` → `sign_element` / `point_sign` records (for sign ingresses).

Then per event, Gate B is an index lookup, exact and deterministic:

| Event family | Reconciles against | Match key |
|---|---|---|
| `transit_aspect` (planet target) | aspect index | `(transiting, natal, aspect)` — directed |
| `transit_aspect` (angle target) | — (no planet-pair record) | route to Stage 2 + `ascendant`-tagged records |
| `ingress_house` | house index | `(transiting, house_placidus, "placidus")`, then `(house_placidus,"placidus")` for domain |
| `ingress_sign` | sign index | `transiting` (+ its sign/element) |
| `lunation` / `eclipse` | house index (domain) | `(house_placidus, "placidus")` where the syzygy falls |

**Direction discipline (lesson from the synastry direction/role inversion fix):** match the
**directed** key: `transiting Mars □ natal Venus` finds only the record whose source is Mars
and target is Venus, never the `transiting Venus □ natal Mars` record. The two texts
describe different experiences, and almost every directed key has a reverse twin in the
corpus (442 of 487), so an unordered match grounds most aspect events on the wrong text.
(An earlier version of this spec matched unordered. That was a bug: CAL F6.) Also
**preserve the event's transiting/natal roles unchanged** in the output, so the reading
phrases it correctly. Never let the match step overwrite which body is transiting.

Gate A and Gate C wrap this exactly as in `ground.py`: drop if domain ∉ `{predictive,timing}`
(Gate A); drop if `tradition != "modern"` (tradition gate, logged as `TRADITION`); drop if any `requires` token is unsatisfiable in the **natal chart** (Gate C —
reused unchanged; the aspect records are almost all `requires:[other]`, so Gate C mostly
passes and Gate B does the real work).

---

## 3. Gate B reconciliation rules (the overrides)

Dispatch by `about.factor_type`, reconciling against the **event**, not the chart:

- **`aspect`** → keep iff `(transiting, natal, aspect_type)` equals the record's
  `(source, target, type)`.
  Do **not** consult `chart.relations` (those are natal-natal aspects, irrelevant to a
  transit).
- **`planet_in_house`** → keep iff record `(point, house, house_system)` equals the ingress
  event's transiting body + `house_placidus` (+ `"placidus"`). Whole-sign is texture, not a
  match key.
- **`house_domain`** → keep iff the record's house equals the event's `house_placidus`
  (ingress or lunation). Passes on existence, like `ground.py`.
- **`sign_element` / `point_sign`** → keep for a sign-ingress event of that point/sign.
- **`general`** and **`unclassified`** → **never** pass structural Gate B (a general record
  has no subject; attaching it to every event would flood the reading). Reachable **only**
  through Stage 2 with a similarity floor. This is the deliberate divergence from
  `ground.py`, which keeps `general` — per-event grounding cannot, or every event drowns in
  domain-neutral text.
- **angle-target aspects** → no planet-pair record exists; route to Stage 2, plus any record
  whose `topic_tags`/`requires.kind` is `ascendant` (for Ascendant contacts only).

---

## 4. Stage 2 — embedding residual (reuse existing L2 retrieval)

Only for: events with too few structural matches (below a per-family floor), angle contacts,
lunation/eclipse texture, and to reach `general`/`unclassified` records that carry no
structured subject.

Reuse the **existing L2 semantic retrieval infrastructure** (the same embedding index/model
natal retrieval already uses over `all_principles_grounded*.json`) — do not stand up a second
embedding space. Predictive-domain pre-filter on the candidate set. Per event:
1. Build the query from the event's `grounding.topic_tags` + a compact plain gloss of the
   configuration (already produced by compute).
2. Semantic top-K over predictive candidates.
3. Keep only those with `similarity ≥ floor` (tunable; suggest 0.35 as a starting default —
   validate empirically).
4. Dedupe against Stage-1 structural matches; cap the event's combined list at N (§1),
   structural matches ranked ahead of embedding matches.

If no embedding infra is available yet, ship Stage 1 alone (the structural backbone grounds
the aspect + ingress spine, which is most events) and gate Stage 2 behind a flag — but
`general`/`unclassified`/angle coverage will be thin until it's wired.

---

## 5. Determinism

Stage 1 is fully deterministic (exact index lookup; ties broken by `principle_id` sort).
Stage 2 is deterministic given a fixed index and model, with `principle_id` as the final
tiebreak on equal similarity. No randomness, no LLM anywhere. Same (forecast, natal, corpus,
index) → identical `matched_principles`.

---

## 6. Invariants (tests)

1. Every matched principle has `domain ∈ {predictive, timing}` (Gate A held).
2. For a `transit_aspect` event, every **structural** match has `source == transiting`,
   `target == natal` and the event's aspect type (no cross-pair or reverse-direction
   leakage). Every match has `tradition == "modern"`.
3. The event's transiting/natal roles are byte-identical before and after grounding (no
   direction inversion).
4. No `general`/`unclassified` record appears as a `structural` match; if present at all it
   is `embedding` with `similarity ≥ floor`.
5. Every matched `principle_id` exists in the merged corpus predictive slice.
6. Gate C reuse: no kept record has a `requires` token unsatisfiable in the natal chart
   (e.g. a `birth_time`/`ascendant` requirement kept on a timeless natal → fail).
7. `events_with_zero_matches` is present in the report and equals the count of events whose
   `matched_principles` is empty (recall visibility).
8. Per-event cap N respected; structural ranked ahead of embedding.
9. Determinism: two runs on the same inputs produce identical output (hash the injected
   forecast).

---

## 7. Non-goals / deferred

- No LLM (this is the deterministic gate; the reading layer downstream is the only LLM stage).
- No ZR/profection records — excluded by domain and by the compute-side module flags; if
  those modules switch on later, their events flow through this same gate unchanged.
- No classical predictive records — coverage is near-zero and they are out of the
  `{predictive,timing}` domain set anyway.
- No corpus re-grounding — that is `backfill.py`'s job (clean→grounded enrichment); this step
  only *reads* the already-grounded corpus.
- Point the corpus loader at the **merged** file (3,263 records, predictive slice = 1,589),
  never the pre-merge 2,153.
