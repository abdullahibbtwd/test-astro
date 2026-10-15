# PRINCIPLE_GROUNDING_SPEC.md

> **REVISION 3 (current — supersedes the §2 architecture below).** The rev-2 re-run
> regressed badly: natal `unclassified` jumped 47 → 223, with ~177 of those being
> *recoverable* subjects the pipeline abandoned (62 dignity, 45 aspect, 41 house, 21
> element, 8 plain planet-in-sign). Root cause: the backfill used `manual`/`unclassified`
> as an **unconstrained discard channel** — 1,361 records were tagged `manual` with no
> human ever reviewing them, and `unclassified` (which has no required fields) trivially
> satisfied the new invariant, so the pipeline took the cheap path on every hard record.
> 20 of 121 *deterministically obvious* records (clean IDs like `*-element-*`, `*-domain`)
> ended up unclassified — records that should never have touched a model or a discard
> bucket.
>
> Measured fix basis: deterministic extraction covers **39% of natal / 14% of corpus**;
> the rest genuinely needs semantic reading. So the LLM stays — it does necessary work —
> but it is **demoted behind a mandatory deterministic tier and the discard channel is
> sealed.** Rev 3 mandates a three-tier architecture (§2): deterministic-first with the
> captured records *locked*, LLM for the genuine residual only, and `unclassified` as an
> *earned* verdict with per-category build floors set to the deterministic counts (so they
> are always achievable without the LLM and the LLM can only add, never subtract).
> **Input is `all_principles_clean.json`** (the rev-2 grounded output was overwritten and
> is not a valid base). Where §2 below conflicts with this banner, this banner governs.

> **REVISION 2.** The v1 pipeline was implemented and run end-to-end
> (`backfill.py` → `all_principles_grounded.json` + `backfill_report.json`;
> `ground.py` → `grounding_report.json`). The run validated the core design — gate A
> removed all 1,685 non-natal records; gate B caught every keystone failure with
> correct logged reasons (false Scorpio ascendant, all wrong-house nodes). But it
> exposed one systematic defect: **~47 genuinely-applicable principles per reading were
> silently dropped at gate B because they were mistyped with a `factor_type` whose
> reconciliation field was null** ("element mismatch: about None vs chart fire",
> "chart has no None sector for Sun", "house-ruler mismatch: about None"). 54 of 468
> natal records were affected. This revision fixes the typing model so those records are
> either correctly reconciled or fail loudly at backfill time — never silently at the
> gate. The defect breaks into three patterns (general significations, chart-relative
> rulership, and incomplete extractions); §1, §3, §4 are revised to address each.
>
> The run also surfaced a separate, expected signal: a handful of records had *non-null
> but wrong* values (e.g. `moon-element-instinct-security` extracted `fire`; the Moon is
> in water). The gate correctly drops these. They are LLM extraction errors, not typing
> bugs, and they are the reason §2.2's error-rate measurement is mandatory.

Spec for making Layer 2 (retrieval) emit **only grounded principles** — records whose
actual subject is verifiably true of the chart, and whose data dependencies the chart
can satisfy. This is the exit contract of Layer 2. Layer 3 trusts its input absolutely
and performs no reconciliation.

Three coupled deliverables, built in order:

1. **Content schema** — structured `about` factor fields on every principle, plus
   `conditions` normalization.
2. **Backfill** — populate those fields across all 2,153 records via a confidence-tiered
   cascade ending in an LLM extraction pass.
3. **Grounding gate** — the deterministic Layer 2 exit filter: domain pre-filter →
   subject reconciliation → dependency satisfiability.

---

## 0. Why this exists (the failure it fixes)

Semantic retrieval returns value-mismatched neighbors. Observed on a live chart
(North Node in whole-sign house 5):

- `north-node-7th-women`, `north-node-2nd-wealth`, `north-node-8th-life-strength`
  retrieved — principles about the node in the **7th / 2nd / 8th**, not the 5th.
- `asc-scorpio-mars-primary-ruler` retrieved by the true fact "Pluto in Scorpio",
  asserting a **Scorpio ascendant** — the ascendant is **Libra**.
- Non-natal records (horary "prisoner" technique, mundane "rain" omen, 8 predictive
  transits) retrieved into a natal reading.

The `triggered_by` field does **not** catch these: it records what retrieval *thought*
connected principle to chart, which for the failures above is a literally-true chart
fact attached to a principle about something else. Grounding must reconcile the
**principle's own subject** against the chart, which requires structured subject data
the dataset does not currently carry.

### Why existing fields can't drive the gate (verified against `all_principles_clean.json`)

- `conditions` is polytyped (1844 list / 140 str / 169 dict) and its entries are
  **dependency templates, not resolved facts**: "Sun sign", "element of Mars sign",
  "aspects to the planet". Of ~3,832 entries, only 137 name a concrete sign/house.
  `conditions` tells you *what variables a principle depends on*, never *what value
  triggers it*. Useful for dependency-satisfiability (gate C), useless for subject
  reconciliation (gate B).
- `principle_id` encodes the subject only partially: of 468 natal records, 84 match a
  clean `planet-sign-SIGN` pattern, 162 carry a house marker. IDs are also sometimes
  *labels not subjects* (`asc-scorpio-mars-primary-ruler` is about the ascendant/ruler,
  not "Scorpio").
- `topic_tags` is singleton-dominated and unreliable as established previously.

Conclusion: no existing field reliably encodes a resolved subject. Hence the backfill.

---

## 1. Content schema (`about` block)

Add one structured object, `about`, to every principle record. It declares the
principle's **subject** (what chart configuration it interprets) in resolved,
foreign-key terms — the thing gate B reconciles against the chart.

```json
"about": {
  "factor_type": "planet_in_house",
  "point": "North Node",
  "house": 5,
  "house_system": "whole_sign",
  "sign": null,
  "aspect": null,
  "element": null,
  "dignity": null,
  "ascendant_sign": null,
  "extraction_confidence": "high",
  "extraction_source": "deterministic"
}
```

### `factor_type` enum (closed set — covers the observed natal archetypes)

| factor_type | subject | key fields used |
|---|---|---|
| `planet_in_sign` | a point in a sign | `point`, `sign` |
| `planet_in_house` | a point in a house | `point`, `house`, `house_system` |
| `planet_in_sign_and_house` | both | `point`, `sign`, `house`, `house_system` |
| `aspect` | a relation between two points | `aspect` `{source,target,type}` |
| `dignity` | a point's essential dignity state | `point`, `dignity` |
| `element` | a point's sign element | `point`, `element` |
| `node` | N/S node in sign or house | `point`, `sign`/`house`, `house_system` |
| `ascendant` | the rising sign | `ascendant_sign` |
| `house_ruler` | the ruler of a house, named by a concrete planet, & its placement | `house`, `house_system`, `point` (the ruler) |
| `house_domain` | what a **point's houses signify in general** — no specific placement (e.g. "the Sun governs vitality through its house"); or what a **house signifies in general** ("third-house significations") | `point` *or* `house`+`house_system`, **never both a specific occupancy** |
| `house_lord_relative` | a **chart-relative** rulership statement whose ruling planet is not named in the text but must be resolved from the chart (e.g. "lord of the ascendant in the 11th") | `subject_house`, `subject_house_system`, `placement_house`, `placement_house_system` — see §3.1 |
| `general` | non-configurational principle (basics-style, applies always) | none |

Any natal record that does not fit one of these → `factor_type: "general"` **only if**
it genuinely applies unconditionally; otherwise it is `unclassified` and handled per §3.

### CRITICAL — `factor_type` ⇒ required-field invariant (the v1 defect)

The v1 backfill assigned reconcilable types (`planet_in_house`, `element`, `house_ruler`,
`ascendant`) to records that lacked the field needed to reconcile them, leaving the field
null. Gate B then compared a real chart value against `None` and logged a "mismatch",
silently dropping a true principle. **This must never happen.** The rule:

> A record's `factor_type` is valid **only if every reconciliation field that type
> requires is non-null**. If the correct subject genuinely has no specific value (a
> planet's house-significations in general, a house's general meaning), the type is
> `house_domain` (which requires no specific occupancy), **not** `planet_in_house` with
> a null house. If the ruling planet is chart-relative and unnamed, the type is
> `house_lord_relative`, **not** `house_ruler` with a null `point`.

Backfill enforces this as a hard validation (§2.2); the gate treats a violation as a
fatal data error, not a drop.

### Field rules

- **Every value field is a foreign key.** `point`, `sign`, `aspect.type`,
  `element`, `dignity`, `ascendant_sign` use the exact vocabulary/casing of the chart
  (`"Venus"`, `"Taurus"`, `"trine"`, `"fire"`, `"domicile"`, `"Libra"`). FK discipline
  applies — do not localize, lowercase, or abbreviate.
- **Unused fields are structurally omitted, not nulled** — consistent with the chart
  engine's absent-field rule. (The example above shows nulls for illustration; in
  practice emit only the fields the `factor_type` uses, plus the two `extraction_*`
  fields, which are always present.)
- **`house_system` is mandatory whenever `house` is present.** A house number is
  meaningless without its system. Most classical material is whole-sign; record what
  the source actually used. If unknown, see §3 confidence rules.
- `extraction_confidence` ∈ `high | medium | low`. `extraction_source` ∈
  `deterministic | llm | manual` — `manual` requires `reviewer` + `reviewed_at` and is
  never auto-assigned. `unclassified` requires `unclassified_reason` (closed enum, §2.1).

### `conditions` normalization (dependency declaration)

Normalize the polytyped `conditions` into a single consistent shape: a list of
**dependency tokens**, each naming a chart variable the principle requires. This does
not resolve values — it declares needs, for gate C.

```json
"requires": [
  {"kind": "point_sign", "point": "Mars"},
  {"kind": "native_gender"}
]
```

`kind` enum: `point_sign`, `point_house`, `point_aspects`, `point_dignity`,
`sign_element`, `ascendant`, `house_ruler`, `native_gender`, `birth_time`, `other`.
The 4 records depending on `native_gender` and any depending on data the chart does not
carry are precisely what gate C will exclude. Preserve the original `conditions` field
unchanged for provenance; `requires` is the normalized projection.

---

## 2. Backfill — deterministic-first, LLM-for-residual, no discard channel

**Input: `all_principles_clean.json`.** Output: a grounded dataset + `backfill_report.json`
+ `validation_report.json`. Process every record (all domains) for internal consistency.

Architecture rationale (measured on the clean input): deterministic extraction covers
**39% of natal / 14% of corpus**; the remainder genuinely needs semantic reading. Both
prior runs failed not on the genuinely-ambiguous residual but on records that were
deterministically obvious yet got handed to a model or a discard bucket. Rev 3 therefore
runs three tiers in strict order, and **a record captured by an earlier tier is LOCKED —
no later tier and no discard verdict may overwrite it.**

### Tier 1 — deterministic capture (mandatory, exhaustive, LOCKED)

Run before anything else. Capture every record matching a high-precision signal and freeze
its `about`. The LLM (Tier 2) and the `unclassified` verdict are **forbidden** from
touching a Tier-1-captured record. Signals (each → `extraction_source: deterministic`,
confidence `high`):

| Signal | → factor_type |
|---|---|
| ID `PLANET-sign-SIGN` (84 natal) | `planet_in_sign` |
| ID ends `-domain` / contains `significations` (22 natal) | `house_domain` |
| ID `*-element-*` or rule "element of {planet}('s sign)" (14 natal) | `element` |
| ID/rule "lord of the {house} in the {house}" (12 natal) | `house_lord_relative` |
| rule/ID dignity keyword "{planet} … domicile/exaltation/detriment/fall/own bound/own triplicity/own face" (55 natal) | `dignity` |
| `conditions` contains a resolved `PLANET in SIGN` / `PLANET in house N` | `planet_in_sign` / `planet_in_house` |

These signals are templates, not heuristics — they either match exactly or they don't.
A record that matches is typed and locked; do not send it to Tier 2.

### Tier 2 — LLM extraction (the genuine residual ONLY)

Only records that survived Tier 1 unmatched (~281 natal, ~1,850 corpus) reach the LLM.
This is the work the LLM is actually needed for: subjects encoded in prose.

- **Task framing:** schema-constrained extraction, NOT generation. The model reads
  `rule` + `judgment` + `principle_id` and emits the `about` object only.
- **Output schema-constrained:** value fields restricted to the closed FK vocabularies
  (provide sign/planet/aspect/element/dignity enums in the prompt). Off-vocabulary →
  reject and retry.
- **`extraction_source: llm`, confidence capped at `medium`.** Never `high`.
- **`unclassified` from the LLM is an EARNED verdict, not a fallback** — see §2.1.
- The gate (§4) is the correctness safeguard for any wrong-but-plausible LLM subject;
  this pass only needs to maximize honest coverage of the residual.

### `extraction_source` is a closed, meaningful enum

`deterministic | llm | manual`. **`manual` means a named human reviewed the record** and
carries `reviewer` + `reviewed_at`. It is **NOT** an auto-assignable label and **must
never** be used as a dump for un-extracted records. (Rev-2 tagged 1,361 records `manual`
with no reviewer — this is now a build-blocking violation: any `manual` record lacking
`reviewer`/`reviewed_at` fails validation.)

### 2.1 `unclassified` is earned, never a default

A record may be `unclassified` only if it carries `unclassified_reason` from this closed
enum:

`no_subject_in_text` · `multi_subject_unsplittable` · `dependency_unsatisfiable`
(e.g. native gender) · `non_configurational`

There is deliberately **no** `hard` / `unclear` / `declined` member. "The extractor found
it difficult" is not a valid reason. A Tier-1-eligible record can never be `unclassified`
(it was captured and locked). An LLM-residual record is `unclassified` only when the model
can state, in those enum terms, why no subject exists in the text.

### 2.2 Build floors & ceiling (hard, set to the DETERMINISTIC counts)

These are build-blocking assertions. The floors equal the Tier-1 deterministic counts, so
they are **always achievable without the LLM** — Tier 1 alone satisfies them, and Tier 2
can only add. This makes the lazy path structurally impossible: the LLM cannot reduce a
category below what determinism already guarantees.

| Natal category | Floor (≥) | Basis |
|---|---|---|
| `planet_in_sign` | 84 | Tier-1 deterministic |
| `dignity` | 55 | Tier-1 deterministic |
| `house_domain` | 22 | Tier-1 deterministic |
| `element` | 14 | Tier-1 deterministic |
| `house_lord_relative` | 12 | Tier-1 deterministic |

| Ceiling | Limit (≤) | Basis |
|---|---|---|
| natal `unclassified` | 50 | v1 baseline 47 + 3 genuine gender-unsatisfiables |

Any natal `unclassified` beyond the 3 documented gender records requires its own logged
`unclassified_reason`; the build fails if the ceiling is exceeded or any floor is missed.

### 2.3 Invariant validation (hard, blocks the build)

For each record, every field required by its `factor_type` (§1) must be non-null. A
reconcilable `factor_type` with a null required field is a **build-blocking error** —
the record is re-routed (`house_domain`/`house_lord_relative`/re-extract) or, only with a
valid `unclassified_reason`, `unclassified`. The accepted output must contain **zero**
reconcilable-with-null-field records. Emit `validation_report.json` listing every
violation and resolution.

### 2.4 Re-run stability (LLM non-determinism guard)

Because Tier 2 is an LLM pass, two runs over the same input will not agree on the residual.
Treat the accepted backfill as a **versioned artifact**. Every subsequent run emits a diff
against the last accepted version listing every record whose `factor_type` changed. **Any
net movement INTO `unclassified`, or any drop below a §2.2 floor, is a build-blocking
event** requiring per-record justification before acceptance. With Tier 1 locked, the diff
surface is only the ~281-record residual, not the whole corpus.

### 2.5 Human review (sampling, not exhaustive)

Review a stratified sample of Tier-2 output: all `unclassified`, all low-confidence, a
random N% of `medium`. Goal is to measure the LLM extraction error rate and record it as a
baseline artifact — not to hand-check the corpus. Genuine `manual` corrections happen here
and only here.

---

## 3. Edge cases & rules

- **House system ambiguity.** Classical node/house principles assume whole-sign; modern
  house principles often Placidus. When the source is classical (tradition
  `traditional`) and unmarked, default `house_system: "whole_sign"` at confidence
  `medium`. When modern and unmarked, default `placidus` at `medium`. Never default at
  `high`.
- **Generic house-significations are `house_domain`, never `planet_in_house`.** This is
  the v1 defect (Pattern 1). Records like `sun-house-vitality-domain`,
  `venus-house-pleasure-domain`, `third-house-significations` describe what a point or a
  house signifies *in general*, with no specific occupancy. They must be typed
  `house_domain` and reconcile on **existence only** (the point exists; the house exists
  — both always true), asserting no placement. The whole modern planet×house matrix
  lives here; mis-typing it as `planet_in_house` with a null house silently deletes the
  domain layer of every reading.
- **Multi-house enumerations** (one record listing effects across all twelve houses):
  template/reference records, not single-subject. Prefer **splitting into per-house
  records** when the text cleanly separates per house (improves precision and lets each
  reconcile); otherwise `factor_type: general` + `low`. (Owner decision recorded: split
  when clean, else `general`.)
- **Aspect direction.** Store `aspect` as `{source, target, type}` but the gate must
  treat source/target as unordered (chart relations are symmetric for matching).
- **Outer-planet / generational** principles: `factor_type` per their actual subject
  (`planet_in_sign` for "Uranus in Capricorn"), but flag `generational: true` so Layer 3
  can down-weight them as non-personal. (Optional field; additive.)

### 3.1 Chart-relative rulership — `house_lord_relative` (Pattern 2)

The classical corpus is dense with statements of the form **"the lord of the Xth in the
Yth"** (`lord-asc-in-11th-natal`, and many Sahl/Māshā'allāh house-lord rules). The ruling
planet is **not named in the text** — it depends on the chart — so v1 typed these
`house_ruler` with a null `point` and the gate dropped them. The correct model names the
*relationship*, not the planet, and resolves the planet from the chart at gate time.

**Schema (`about` for `house_lord_relative`):**

```json
"about": {
  "factor_type": "house_lord_relative",
  "subject_house": 1,            "subject_house_system": "whole_sign",
  "placement_house": 11,         "placement_house_system": "whole_sign",
  "extraction_confidence": "...", "extraction_source": "..."
}
```

`subject_house` is the house whose lord the principle is about ("the ascendant" = house
1); `placement_house` is where that lord is said to sit. No `point` field — by design,
because the planet is chart-derived.

**Reconciliation (full, the recommended path — uses `sector_rulers`):**

1. Resolve the lord: `ruler = chart.sector_rulers[subject_house_system][subject_house].ruler`.
2. Find the lord's actual placement:
   `actual = chart.points[ruler].sector[placement_house_system]`.
3. **Keep iff** `actual == placement_house`; else drop with reason
   `house-lord-relative mismatch: lord of {subject_house} is {ruler}, in {actual} not {placement_house}`.

This is why `CHART_SECTOR_RULERS_SPEC.md` exists. It recovers the classical house-lord
layer *correctly* — "lord of the ascendant in the 11th" is kept only for a native whose
ascendant-ruler is genuinely in the 11th — rather than passing it through unverified.
Passthrough (keep all house-lord principles without checking placement) was considered and
**rejected**: it would let a "lord of the asc in the 11th" reading attach to a chart whose
asc-lord is in the 8th, which is exactly the value-mismatch failure this whole spec exists
to prevent.

Where a house-lord principle names **only** the subject house with no placement claim
(general "the lord of the 7th matters for marriage"), type it `house_domain` keyed on the
house, not `house_lord_relative`.

---

## 4. Grounding gate — Layer 2 exit contract

A deterministic function `ground(records, chart) -> kept[]` applied AFTER semantic
retrieval, BEFORE returning to Layer 3. Three sequential gates:

### Gate A — domain pre-filter (cheapest, runs first)
Keep only records whose `domain` is in the reader's allowed set. For the natal reader:
`domain == "natal"` (optionally `basics` if the owner wants general framing material;
default natal-only). On the observed data this alone removes 11/34 leaked records and,
corpus-wide, removes the 1,685 non-natal records.

### Gate B — subject reconciliation (the core fix)
For each surviving record, verify its `about` subject is **true of this chart**, using
the chart's own precomputed facts (points, sectors in both systems, axes, relations,
`sector_rulers`, dignities/classifications, derived element).

**Precondition — invariant check (runs before reconciliation).** If a record's
`factor_type` requires a field (per §1) that is null, this is a **fatal data error**, not
a drop: the gate raises/flags it as `INVARIANT_VIOLATION` rather than logging a spurious
"mismatch against None". This is the v1 defect's tripwire — `planet_in_house` with null
house, `element` with null element, `house_ruler` with null point must surface as data
errors to be fixed in backfill, never as silent gate-B drops.

- `planet_in_sign`: `chart.points[point].sign == about.sign`
- `planet_in_house`: `chart.points[point].sector[about.house_system] == about.house`
- `planet_in_sign_and_house`: both of the above
- `aspect`: a chart relation exists matching `{source,target}` (unordered) and `type`,
  in the matching scheme (whole-sign aspects vs modern — honor the tradition-routing
  already in `RETRIEVAL_CONTRACT.md`)
- `dignity`: `chart.points[point].classifications` confirms the named dignity state
- `element`: derived element of `chart.points[point].sign` == `about.element`
- `node`: as planet_in_sign / planet_in_house for North/South Node
- `ascendant`: `chart.axes.ascendant.sign == about.ascendant_sign`
- `house_ruler`: `chart.sector_rulers[about.house_system][about.house].ruler == point`
  (named-planet ruler; `point` is non-null by invariant)
- `house_domain`: **passes on existence** — the point and/or house named always exists in
  any chart, so there is nothing to falsify; asserts no placement. This is how the generic
  planet×house and house-signification matrix survives. (Reconciliation is a no-op beyond
  confirming the named point/house are valid chart entities.)
- `house_lord_relative`: resolve the lord from `sector_rulers`, then check its placement
  — full procedure in §3.1. Keep iff the resolved lord's actual house equals
  `placement_house`.
- `general`: passes (no subject to reconcile)
- `unclassified`: **fails** (cannot be verified → not trusted)

Mismatch → drop. This is what removes `north-node-7th-women` (about house 7, node is in
5), `asc-scorpio-mars-primary-ruler` (asserts Scorpio asc, chart is Libra), etc.

**Note on wrong-but-non-null values.** A record with a non-null value that is simply
*wrong for this chart* (e.g. `element: "fire"` when the point is in water — an LLM
extraction error) is a legitimate drop, not an invariant violation. The gate cannot tell
a wrong extraction from a genuinely-inapplicable principle, nor should it — both are
correctly excluded. These drops are the observable signal of extraction error rate;
§2.2's sampling review is what attributes them.

### Gate C — dependency satisfiability
For each record passing B, verify every `requires` token is satisfiable from this chart.
Drop records requiring data the chart does not carry (e.g. `native_gender`,
`birth_time` when time is unknown — relevant when the precision-tier extension lands).
On current exact-time charts this mainly removes the 4 gender-dependent records.

### Logging (diagnostic-first)
Every drop is logged: `{principle_id, gate, reason, about, relevant_chart_fact}`. This
is non-optional — it is how retrieval gets tuned. Silent dropping masks retrieval error;
the log surfaces it. Emit a per-chart grounding report alongside the kept set.

---

## 5. What Layer 2 returns to Layer 3 (the contract)

After grounding, Layer 2 hands Layer 3:

- the kept principle records (full content: `rule`, `judgment`, `tradition`, `about`),
  **bundled and keyed by the chart factor that grounded them** (the bundling already
  agreed for L3 input), and
- the full chart object.

Guarantee to Layer 3: **every principle is true of this chart and its dependencies are
satisfied.** Layer 3 performs no reconciliation and may treat all received principles as
grounded fact.

---

## 6. Types & schema

### TypedDict (additions)

```python
from typing import TypedDict, Literal, List, Optional

FactorType = Literal[
  "planet_in_sign","planet_in_house","planet_in_sign_and_house","aspect",
  "dignity","element","node","ascendant","house_ruler",
  "house_domain","house_lord_relative",          # added in rev 2
  "general","unclassified"]

class AspectSubject(TypedDict):
    source: str
    target: str
    type: str

class About(TypedDict, total=False):
    factor_type: FactorType            # required
    point: str
    sign: str
    house: int
    house_system: Literal["placidus","whole_sign"]
    aspect: AspectSubject
    element: str
    dignity: str
    ascendant_sign: str
    # house_lord_relative fields (rev 2): planet is chart-derived, never stored
    subject_house: int
    subject_house_system: Literal["placidus","whole_sign"]
    placement_house: int
    placement_house_system: Literal["placidus","whole_sign"]
    generational: bool
    extraction_confidence: Literal["high","medium","low"]  # required
    extraction_source: Literal["deterministic","llm","manual"]  # required
    # required IFF factor_type == "unclassified"; closed enum, no "hard"/"unclear"
    unclassified_reason: Literal["no_subject_in_text","multi_subject_unsplittable",
                                 "dependency_unsatisfiable","non_configurational"]
    # required IFF extraction_source == "manual"
    reviewer: str
    reviewed_at: str

class Requirement(TypedDict, total=False):
    kind: Literal["point_sign","point_house","point_aspects","point_dignity",
                  "sign_element","ascendant","house_ruler","native_gender",
                  "birth_time","other"]   # required
    point: str
```

Add `about: About` and `requires: List[Requirement]` to the principle record type.
`extraction_confidence`, `extraction_source`, and `about.factor_type` are always present;
all other `about` fields are omitted when unused.

**Schema must encode the required-field invariant per `factor_type`** (§1, §2.3): use
JSON Schema conditional subschemas (`allOf`/`if`/`then`) so that, e.g.,
`factor_type: "planet_in_house"` *requires* non-null `point`, `house`, `house_system`;
`house_domain` requires `point` OR (`house` + `house_system`) and forbids a specific
occupancy claim; `house_lord_relative` requires the four `subject_*`/`placement_*` fields
and forbids `point`. A null required field must fail schema validation — this is the
structural enforcement of §2.3, not just a runtime check.

### JSON Schema
Mirror the above as Draft 2020-12 with `additionalProperties: false`, value fields
constrained by `enum` to the canonical FK vocabularies (signs, planets, aspect types,
elements, dignities). Off-vocabulary values must fail validation — this is what enforces
FK discipline on LLM output.

---

## 7. Validation (adversarial — verify drops, not just keeps)

Use the live failures as fixtures. Against the working chart (Libra asc, NN whole-sign 5):

1. **Domain leak:** the 8 predictive + 2 horary + 1 mundane records → all dropped by
   gate A. Assert 0 non-natal records survive.
2. **Wrong-house node:** `north-node-7th-women`, `-2nd-wealth`, `-8th-life-strength`
   → dropped by gate B (about house ≠ 5). Assert dropped, with log reason naming the
   house mismatch.
3. **False ascendant:** `asc-scorpio-mars-primary-ruler` → dropped by gate B
   (about ascendant Scorpio ≠ Libra). This is the keystone test.
4. **True-positive survival:** `mars-sign-aries-delineation`, `moon-sign-pisces-delineation`,
   and a correctly-housed record (e.g. `venus-in-whole_sign-house-8` if present) → kept.
   Assert the genuinely-correct delineations are NOT over-filtered.
5. **Dependency drop:** a gender-dependent record → dropped by gate C with reason
   `unsatisfiable: native_gender`.
6. **Unclassified safety:** an `unclassified` record → dropped by gate B. Assert no
   `unclassified` ever reaches Layer 3.
7. **FK casing on extraction:** an LLM output with `"sign": "taurus"` (lowercase) →
   rejected at schema validation, not silently accepted.
8. **House-system correctness:** a node principle marked `whole_sign` must reconcile
   against the whole-sign sector, not Placidus. Construct a fixture where the node's
   placidus and whole-sign houses differ and confirm the correct system is used.
9. **`house_domain` survival (rev 2 — the regression this revision prevents):**
   `sun-house-vitality-domain`, `venus-house-pleasure-domain`, the planet×house matrix,
   `third-house-significations` → typed `house_domain` and **kept** (pass on existence,
   assert no placement). Assert these are NOT dropped. Guard test: the same records typed
   `planet_in_house` with null `house` must raise `INVARIANT_VIOLATION`, never a silent
   drop.
10. **`house_lord_relative` reconciliation (rev 2):** on the working chart, lord of the
    ascendant (whole-sign h1 = Libra) is Venus, in whole-sign h8. A principle "lord of the
    1st in the 8th" → **kept**; "lord of the 1st in the 11th" → **dropped** with reason
    naming the resolved lord and its actual house. Confirms the `sector_rulers`-based
    resolution path works in both directions.
11. **Invariant tripwire (rev 2):** seed a record `factor_type: "element"` with
    `element: null`. Assert §2.3 validation flags it as build-blocking, and that gate B —
    if it ever sees one — raises `INVARIANT_VIOLATION` rather than logging
    "element mismatch: about None vs chart fire". This is the exact v1 failure; it must be
    impossible to reproduce silently.

A passing run on the observed 34-record retrieval output must keep the genuinely-grounded
natal delineations (including `house_domain` and correctly-reconciled `house_lord_relative`
records) and drop exactly the domain leaks, wrong-house nodes, and false ascendant —
turning the unsafe 34 into a trustworthy set. **Corpus-wide, the count of
reconcilable-`factor_type`-with-null-required-field records must be zero.**

### Rev-3 backfill-integrity tests (run on the dataset, not a chart)

12. **Deterministic lock:** every record matching a Tier-1 signal has
    `extraction_source: deterministic` and the expected `factor_type`. Assert none of the
    121 clean-ID records is `unclassified` (rev-2 had 20). The clean `element` templates
    ("element of Mars's sign") must be `element`, never `unclassified`.
13. **No `manual` dump:** every `extraction_source: manual` record has non-empty
    `reviewer` and `reviewed_at`. A `manual` record without them fails the build. (Rev-2's
    1,361 reviewer-less `manual` records would all fail here.)
14. **`unclassified` is earned:** every `unclassified` record has an `unclassified_reason`
    from the closed enum. Assert a record with `unclassified` and no reason, or reason
    `"hard"`/`"unclear"`, fails validation.
15. **Floors & ceiling:** natal counts meet every §2.2 floor (planet_in_sign ≥ 84,
    dignity ≥ 55, house_domain ≥ 22, element ≥ 14, house_lord_relative ≥ 12) and
    `unclassified` ≤ 50. Each is an independent build-blocking assertion.
16. **Re-run stability:** run the backfill twice; diff `factor_type` across runs. Assert
    no net movement into `unclassified` and no floor breached. Any record that changed
    type appears in the diff report with justification.

---

## 8. Acceptance checklist

- [ ] `about` + `requires` populated on all 2,153 records from `all_principles_clean.json`;
      `factor_type`, `extraction_confidence`, `extraction_source` always present.
- [ ] **Three-tier backfill: Tier-1 deterministic capture runs first and LOCKS its
      records; Tier-2 LLM sees only the unmatched residual; LLM capped at `medium`,
      off-vocabulary rejected.**
- [ ] **`extraction_source` ∈ {deterministic, llm, manual}; `manual` requires
      reviewer+reviewed_at and is never auto-assigned (no discard channel).**
- [ ] **`unclassified` requires `unclassified_reason` from the closed enum; no
      hard/unclear/declined; Tier-1-eligible records can never be unclassified.**
- [ ] **Build floors met (natal: planet_in_sign ≥ 84, dignity ≥ 55, house_domain ≥ 22,
      element ≥ 14, house_lord_relative ≥ 12) and ceiling held (unclassified ≤ 50);
      each build-blocking.**
- [ ] **Re-run stability: versioned diff emitted; net movement into unclassified or any
      floor breach blocks the build.**
- [ ] `factor_type` required-field invariant enforced in schema (conditional subschemas)
      AND in §2.3 validation; null required field is build-blocking; corpus count of
      reconcilable-with-null-field records is zero.
- [ ] `house_domain` and `house_lord_relative` implemented; `house_lord_relative` resolves
      the lord via `sector_rulers` then checks placement (full reconciliation, not
      passthrough).
- [ ] Sampling review run; LLM extraction error rate recorded as a baseline artifact.
- [ ] `ground()` implements gates A→B→C in order with the §4 reconciliation rules,
      including the invariant precondition (raises `INVARIANT_VIOLATION`, never a
      silent None-mismatch).
- [ ] Whole-sign vs Placidus handled correctly in gate B (uses `about.house_system`).
- [ ] Every drop logged with reason + relevant chart fact; per-chart grounding report
      emitted.
- [ ] All 16 adversarial tests pass (11 gate tests + 5 backfill-integrity tests).
- [ ] Layer 2 returns grounded records bundled-by-factor + full chart; Layer 3 does no
      reconciliation.
- [ ] No change to existing principle fields (`rule`/`judgment`/etc.); `about`/`requires`
      additive. Original `conditions` preserved for provenance.

---

## Addendum — house policy (2026-09-21)

The natal reading is **Placidus-only**. `ground()` takes `house_policy` (default
`"placidus"`): gate B verifies **every** house claim — `house_system`,
`subject_house_system`, `placement_house_system` — against the chart's Placidus sector
and Placidus rulers, whatever system the record declares. A whole-sign record therefore
survives only when its house is also the planet's Placidus house; the record's declared
system stays in `about` as provenance, and `kept_payload()["house_policy"]` /
`report()["house_policy"]` record the system actually used. Bundle labels name the
verified system ("Sun in placidus house 9"). `house_policy=None` restores per-record
verification (§4 as written above; the test at §7.8 exercises that mode).
