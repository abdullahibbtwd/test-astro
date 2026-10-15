# RECLASSIFY_SPEC.md

A **deterministic, count-free, idempotent** post-pass that re-routes `unclassified`
records produced by the backfill (`PRINCIPLE_GROUNDING_SPEC.md` §2) into their honest
homes. It runs **after** backfill and **before** the build's floor/ceiling checks. It makes
**no LLM calls.**

---

## 0. Why this exists

The backfill's LLM tier honestly declined to type a large `unclassified` pile. Inspection
showed that pile is not homogeneous "failures" — it contains four distinct populations,
three of which have honest non-`unclassified` homes:

- **Re-capturable:** records whose true subject is deterministically derivable but whose ID
  shape escaped Tier-1's patterns (e.g. `planet-sign-function-sun` = "the sign of the Sun
  signifies…", which is `house_domain`, **not** `planet_in_sign` — there is no specific
  sign).
- **Configuration rules / chart-level rules:** apply to any chart, no single subject
  (`asc-ruler-sign-position`, "any planet within 6° of the Ascendant…",
  `element-emphasis-chart-interpretation`) → honest `general`.
- **Classical procedures:** multi-step techniques (hīlāj/alcocoden, triplicity-survival
  ladder) → preserved as `out_of_scope: true`, not discarded.
- **Genuinely unclassifiable / dependency-blocked:** gender-dependent, truly subjectless →
  stay `unclassified` with their existing reason.

Leaving all four as `unclassified` both understates the dataset and (for the re-capturable
ones) silently drops real delineations.

---

## 1. Hard design constraints

1. **No counts, no targets, no distribution assumptions.** The script never asserts "≤ N
   unclassified", never expects a split. Each record is routed on its own signals; totals
   fall out wherever they fall. This is what keeps it correct as the dataset grows or rules
   are added.
2. **Idempotent & order-independent.** Running it twice, or on a fresh backfill, or on a
   dataset with new records, yields the same per-record result. Achieved by: rule-over-
   fields only, no global state, no randomness, deterministic precedence.
3. **Only touches `unclassified` records.** Records already typed by the backfill
   (deterministic or LLM) are left **byte-identical**. The script is purely additive
   routing of the failure pile.
4. **Conservative re-capture.** A record is re-captured to a reconcilable type **only** on
   an unambiguous template match (§3, route 1). Anything debatable stays put. Over-eager
   re-capture reintroduces the false-subject risk the grounding model exists to prevent;
   when in doubt, do not re-capture.
5. **No LLM.** Every decision is a rule over fields already present (`principle_id`, `rule`,
   `judgment`, existing `unclassified_reason`).

---

## 2. Routing — five outcomes, strict precedence

For each record with `factor_type == "unclassified"`, evaluate routes in order and apply
the **first** that matches. Precedence matters: a genuine subject beats any passthrough; a
hard dependency beats a procedure tag; a procedure beats general.

| # | Route | Condition (deterministic) | Result |
|---|---|---|---|
| 1 | **Re-capture** | matches a clean Tier-1-style template (§3) | assign the real reconcilable type; `extraction_source: deterministic` |
| 2 | **Stay (dependency)** | `unclassified_reason == "dependency_unsatisfiable"` OR text names a dependency the chart cannot carry (e.g. native gender) | remain `unclassified`, keep reason |
| 3 | **Out-of-scope** | matches a procedure signal (§4) | keep record but set `out_of_scope: true`, `scope_note: "classical_procedure"`; leave `factor_type` as-is (or `procedure` if that type is adopted) |
| 4 | **Widen to general** | matches a configuration-rule / chart-level signal (§5) | `factor_type: "general"`; clear `unclassified_reason` |
| 5 | **Stay (honest)** | none of the above | remain `unclassified` with reason `no_subject_in_text` |

Every record routed in 1/3/4 records a `reclassified_from: "unclassified"` and
`reclassify_rule: "<route id>"` for auditability. The script emits a
`reclassify_report.json` listing per-record routing — diagnostic only, **no count
assertions.**

---

## 3. Route 1 — conservative re-capture (templates only)

Re-capture **only** on unambiguous, closed templates. These are extensions of the Tier-1
patterns that a record's ID shape caused Tier-1 to miss. Each maps to a type whose required
fields are **fully derivable from the template itself** (no null fields, no inference):

| Template (ID and/or rule) | → factor_type | Notes |
|---|---|---|
| `planet-sign-function-{planet}` / "the (zodiac) sign of {planet} (describes/signifies)…" with **no specific sign named** | `house_domain` keyed on `point` | **NOT** `planet_in_sign` — there is no fixed sign; subject is "the point's sign-significations in general". This is the canonical re-capture case. |
| `{planet}-house-{domain-word}` / "the house of {planet} signifies…" with **no specific house named** | `house_domain` keyed on `point` | general planet-house significations |
| `{ordinal}-house-significations` with **no planet/specific occupancy** | `house_domain` keyed on `house`+`house_system` | general house meaning |

**Forbidden in re-capture:** assigning `planet_in_sign`, `planet_in_house`,
`planet_in_sign_and_house`, `dignity`, `aspect`, or any type that needs a *specific* value
(a particular sign/house/aspect) that is not literally and unambiguously present in the
text. If the specific value is not stated, the record is not re-capturable — route it
onward. (This is the rule that prevents recreating null-field invariant violations.)

The `house_domain` invariant still applies: it requires `point` **or**
`house`+`house_system`, and asserts **no specific occupancy**. Re-captured records must
satisfy it or they are not re-captured.

---

## 4. Route 3 — procedure signals (out-of-scope, preserved)

Signals that mark a multi-step classical technique rather than a delineation. Match on
presence in `principle_id` + `rule` + `judgment` (case-insensitive). Indicative, not
exhaustive — **extensible** (see §6):

`hilaj`, `hyleg`, `hileg`, `alcocoden`, `kadukhudah`, `kadkhudah`, longevity /
"length of life" / "years of life", "infant survival" / "survive infancy",
"triplicity ladder" / triplicity-lord survival sequence, "sequential hierarchy of
testimony", "evaluate … in order" / step-wise assignment procedures.

Routed records are **preserved**: `out_of_scope: true`, `scope_note: "classical_procedure"`.
They stay queryable for a future predictive/timing layer; the natal gate excludes them.

---

## 5. Route 4 — configuration / chart-level rule signals (→ general)

Signals that a principle applies to **any** chart with no single subject. Match on
`principle_id` + `rule` + `judgment`:

- **Angle rules:** ascendant / rising / descendant / midheaven / MC / IC referenced as the
  thing being aspected or as a general indicator, where the *other* element is unfixed
  ("any planet within N degrees of the Ascendant", "the sign of the Ascendant-ruler",
  `asc-ruler-sign-position`, `asc-conjunction-modification`, `mc-aspect-…`).
- **Meta / weighting rules:** "gains in importance", "more important when", "weighting",
  "proportionally", "any aspect", "any planet", "overall chart", "strongly represented",
  "emphasis".
- **Chart-level elemental/modal balance:** `element-emphasis-chart-interpretation` and kin
  (these were already correctly typed `general` by Tier-1 when caught; this route catches
  the ones the LLM dumped).

These become `general` — they pass gate B on existence and reach L3 as framing/context.

> **Precedence note:** because angle/meta signals are broad, route 1 (re-capture) and route
> 3 (procedure) are checked **first**. A procedure that happens to mention the ascendant is
> a procedure, not a general angle-rule; a re-capturable significations record that mentions
> "house" is re-captured, not generalized.

---

## 6. Extensibility (you will run this again)

The signal lists in §4 and §5 and the templates in §3 are **data, not code** — keep them in
an editable table/config the script reads, so new procedures, new angle-rule phrasings, or
new clean templates can be added without touching logic. Re-running the script after adding
a rule must (a) re-route only records the new rule newly matches, (b) leave all others
byte-identical, (c) still make no LLM calls and assert no counts. Adding a rule is the
intended way to shrink the residual `unclassified` over time.

---

## 7. Interaction with the build gates

After this post-pass, the `PRINCIPLE_GROUNDING_SPEC.md` build checks run:
- **Floors** (§2.2 there) — re-capture can only *raise* reconcilable counts; never lowers a
  floor.
- **Invariant** (§2.3 there) — re-captured records must satisfy required-field non-nullness;
  the §3 template rules guarantee this by construction.
- **Ceiling** — `unclassified` is now only routes 2 and 5 (genuine dependency + genuine
  no-subject). The ceiling, if retained, should be re-derived from what genuinely remains
  rather than the prior arbitrary value; **but per project decision this script asserts no
  count** — the ceiling check lives in the build spec, and its number should be set from the
  post-reclass reality, not guessed. (Recommend: replace a hard ceiling with "every
  `unclassified` has a valid reason and no record matching a route-1/3/4 signal remains
  `unclassified`" — a structural check, not a count.)

---

## 8. Validation (adversarial, count-free)

1. **Idempotence:** run twice; second run produces byte-identical output and an empty
   reclassify diff.
2. **Non-destruction:** every record not `unclassified` before the pass is byte-identical
   after.
3. **Re-capture safety:** assert no re-captured record has a null required field; assert no
   record was re-captured to `planet_in_sign`/`planet_in_house`/`dignity`/`aspect` (specific
   types) — the canonical case `planet-sign-function-sun` must become `house_domain`, never
   `planet_in_sign`.
4. **Preservation:** procedure records carry `out_of_scope: true` and remain in the dataset
   (not deleted, not `unclassified`).
5. **Precedence:** a fixture matching both a procedure signal and an angle signal routes to
   out-of-scope (route 3 before route 4). A fixture matching both a re-capture template and a
   meta signal routes to re-capture (route 1 first).
6. **No-count guarantee:** grep the script for hardcoded thresholds on routing — there must
   be none. Routing depends only on per-record signals.
7. **Honest residual:** every remaining `unclassified` has a valid `unclassified_reason` and
   matches **no** route-1/3/4 signal (else it should have moved).

---

## 9. Acceptance checklist

- [ ] Runs after backfill, before build gates; makes no LLM calls.
- [ ] Only `unclassified` records altered; all others byte-identical.
- [ ] Five routes implemented with the §2 precedence.
- [ ] Re-capture is template-only and conservative; `planet-sign-function-*` →
      `house_domain` (never `planet_in_sign`); no null required fields introduced.
- [ ] Procedures preserved via `out_of_scope` + `scope_note`, queryable for later layers.
- [ ] Config/angle/meta rules → `general`.
- [ ] Signal lists & templates are editable config (extensible without code changes).
- [ ] `reclassify_report.json` emitted (diagnostic; no count assertions).
- [ ] Idempotent and order-independent; all §8 tests pass.
- [ ] No hardcoded counts/targets anywhere in routing.
