# RECEPTION_BUILD.md

**Target file:** `ground_relationship.py` (the same script that computes overlays/aspects/compatibility and grounds them — there is no separate compute module).
**Corpus addition:** `syn_reception_slice.json` (23 records, `interaction: reception`) merged into `combined_relationship_principles_clean.json`.
**Depends on:** Pass 1 + Pass 2 grounding fixes already landed (role binding, dedup, re-derivation guard).
**Verified against:** `chart_1979-03-30.json` (A) × `chart_r_1988-12-28.json` (B).

Reception is the same three-part pattern you already run for overlays — **compute the fact → match a principle → bind persons** — with a new interaction type. Add all three parts below.

---

## Part A — compute `cross_reception` facts

Add a reception-fact pass to the fact-computation section of `ground_relationship.py`, alongside the overlay/aspect/compatibility passes.

### A.1 Significators (per person)

Resolve, per chart, the set of significator **planets**, tagging each with the role(s) that qualified it:

- `Sun, Moon, Venus, Mars` → role `personal` (Sun/Moon also `luminary`)
- `Mercury` → role `personal` (secondary)
- domicile ruler of the Ascendant sign → role `ascendant_ruler`
- domicile ruler of the Descendant sign (7th) → role `seventh_ruler`

Dedup to unique planet names; a planet may carry several roles (e.g. Aries rising ⇒ Mars is both `personal` and `ascendant_ruler`). Store `{planet: [roles]}` per person.

### A.2 Dignity lords of a sign

Reuse the tables already locked in `SYNASTRY_COMPUTE_SPEC.md` §9 (domicile, exaltation, Dorothean triplicity, Egyptian bounds, Chaldean faces). **Import bounds/faces from the L1 dignity module** — do not re-type them.

Triplicity is sect-sensitive: use the `is_diurnal` flag of **the chart the sign sits in** (i.e. the *received* person's chart, since the sign belongs to their planet).

### A.3 Fact generation

For each ordered pair of persons (received = X, receiver = Y), for each of X's significators `P` in sign `S`:

```
for grade in [domicile, exaltation, triplicity, bound, face]:
    L = lord_of(S, grade, X.is_diurnal)
    if L in Y.significators:
        emit reception fact (receiver = Y's L, received = X's P, grade)
```

Run both directions (X=A,Y=B and X=B,Y=A).

### A.4 Collapse to strongest grade per pair

A single received planet can qualify at several grades under the same receiver (e.g. A's Sun in Aries is received by B's Sun at both exaltation and triplicity). **Keep only the highest-weight grade per `(receiver_point, received_point, direction)`.** Weights: domicile 1.0, exaltation 0.9, triplicity 0.6, bound 0.4, face 0.2. This prevents the triple-counting that plagued the pre-fix overlays.

### A.5 Mutual flag

Set `mutual: true` on a fact when the reverse-direction fact also exists for the **same significator pair at domicile or exaltation** (strict mutual reception). Add `+0.2` to weight, capped at 1.0. Lesser-grade mutuals are not flagged in v1.

### A.6 Debilitation flag

Set `receiver_debilitated: true` when the receiving planet is in its own detriment or fall **in the receiver's chart** (available from that chart's `classifications`). This feeds `syn-reception-receiver-debilitated`.

### A.7 Fact schema

```json
{
  "kind": "reception",
  "receiver_person": "B", "receiver_point": "Mars", "receiver_roles": ["personal","ascendant_ruler"],
  "received_person": "A", "received_point": "Sun", "received_roles": ["personal","luminary"],
  "received_sign": "Aries",
  "grade": "domicile",
  "weight": 1.2,            // pre-cap; store capped 1.0
  "mutual": true,
  "receiver_debilitated": false
}
```

Reception facts also enter the ranked contact inventory (`SYNASTRY_COMPUTE_SPEC.md` §7) with `kind: "reception"` at their weight.

### A.8 Expected facts for the test pair (acceptance target)

After A.4 collapse, `B receives A` and `A receives B` should include (highest grade per receiver→received shown):

- **B's Mars receives A's Sun — domicile.** A's Sun receives B's Mars — exaltation. ⇒ **mutual (Sun–Mars)**, and note these two are also conjunct in Aries.
- B's Venus receives A's Moon (domicile), A's Mercury / A's Venus / A's Mars (exaltation).
- B's Moon receives A's Moon (exaltation).
- A's Mercury receives B's Moon (domicile).
- A's Venus receives B's Sun / B's Mercury (triplicity); A's Sun receives B's Venus (triplicity).

At minimum, the run must produce the Sun–Mars mutual reception and B's-Venus-receives-multiple-A-planets cluster.

---

## Part B — reception matcher

Add a matcher branch for `interaction: reception`, parallel to the overlay/aspect matchers.

### B.1 New `synastry` block fields (in the slice)

```
received_point:  planet | null      // required received planet, or null = any
receiver_point:  planet | null      // required receiver planet, or null = any
receiver_class:  "benefic" | "malefic" | "luminary" | null
received_role:   "ascendant_ruler" | "seventh_ruler" | null
grade:           "domicile"|"exaltation"|"triplicity"|"bound"|"face"|"any"
mutual:          true | false | null   // null = don't care
receiver_debilitated: true | (absent) // present only on the debilitation record
```

Class expansions: `benefic = {Venus, Jupiter}`, `malefic = {Mars, Saturn}`, `luminary = {Sun, Moon}`.

### B.2 Match rule

A reception principle matches a reception fact when **all present constraints hold** (null / absent = wildcard):

- `received_point` equals fact's `received_point`
- `receiver_point` equals fact's `receiver_point`
- `receiver_class` — fact's `receiver_point` ∈ the class set
- `received_role` ∈ fact's `received_roles`
- `grade` equals fact's `grade` (or principle grade `"any"`)
- `mutual` equals fact's `mutual`
- `receiver_debilitated: true` — fact's `receiver_debilitated` is true

Multiple principles may match one fact (a domicile Venue-receives fact matches the general, the domicile-grade, the benefic-receiver, and the pair-specific records). That is intended — dedup handles surplus (§C).

### B.3 Role binding + `bound_statement`

The slice's rule text uses explicit tokens `{RECEIVER}` and `{RECEIVED}` (an improvement on the overlay records' baked-in "person A/B"). Bind them from the fact:

```
bound = {
  "kind": "reception",
  "receiver_person": fact.receiver_person, "receiver_point": fact.receiver_point,
  "received_person": fact.received_person, "received_point": fact.received_point,
  "grade": fact.grade, "mutual": fact.mutual
}
bound_statement = rule.replace("{RECEIVER}", label(receiver_person)).replace("{RECEIVED}", label(received_person))
```

where `label("A")` / `label("B")` are the person labels S3 uses. No reception `bound_statement` may contain a literal `{RECEIVER}` / `{RECEIVED}` token or a raw "person A/B" (invariant §C).

---

## Part C — dedup + invariants

### C.1 Fact-key dedup (extend Fix B)

Reception fact-key: `(interaction, receiver_point, received_point, grade, receiver_person)`. When several principles bind the same fact, keep one survivor by precedence: (1) most specific — pair-specific `received_point`+`receiver_point` beats class/role beats grade-only beats general; (2) higher extraction confidence; (3) longer rule. Collapse the rest into `superseded`.

**Mutual pairs emit once.** When a mutual fact and its reverse both exist, represent the pair with a single record carrying `mutual: true` (prefer a `mutual`-flagged principle, e.g. `syn-reception-mutual-domicile-exaltation` or `syn-reception-venus-mars-mutual`); suppress the two one-way records for that exact significator pair.

### C.2 Re-derivation guard (extend E1)

Add `kind: reception` to the exit invariant. Every emitted reception record must re-derive against the two charts: the `received_point` in the received person's chart occupies a sign whose lord **at the stated grade** (using the received chart's sect for triplicity) is the `receiver_point`. Any failure halts with the offending `principle_id`. This is the same guard that catches wrong-chart grounding automatically.

### C.3 Other invariants (unchanged, now covering reception)

- No two emitted reception records share a fact-key (post-C.1).
- Every reception record carries `bound` + a fully-substituted `bound_statement` (no residual tokens).
- Every drop carries a reason from the closed enum (add `reception_no_matching_fact`).

---

## Order

A (facts) → C.2 (guard, so A is self-checking) → B (matcher + binding) → C.1 (dedup). Re-run the test pair and confirm the Sun–Mars mutual reception surfaces as a single mutual record, the B's-Venus cluster grounds `syn-reception-receiver-benefic` + `syn-reception-grade-domicile`, and no reception `bound_statement` contains a residual `{RECEIVER}`/`{RECEIVED}` token.

---

## Not in this build

- Bounds/faces reception is computed and can ground the `grade-bound` / `grade-face` records, but treat these as minor (low weight) in the inventory — do not let a face-grade reception outrank a personal-planet aspect.
- Reception salience tuning in the contact inventory beyond the weights in A.4/A.5 is deferred to the inventory pass.
- No new significators beyond §A.1 in v1 (no Lot rulers — lots remain deferred to the predictive layer).
