# SYNASTRY_GROUNDING_FIXES.md

**Target:** the relationship grounding script that produces `personal_relationship_principles.json`
**Inputs it reads:** `combined_relationship_principles_clean.json` (865 records, all `domain: relationship`) + two `chart.json` files (A, B)
**Verified against:** test pair `chart_1979-03-30.json` (A) × `chart_r_1988-12-28.json` (B)
**Scope:** four fixes (A–D) + exit invariants (E). Reception is explicitly **out of scope** (see §Reception).

Grounding *correctness* is already good — in the test run, 23/23 house overlays and 65/65 aspects match real facts. These fixes are about **person-attribution, deduplication, routing, and auditability**, not about the geometry.

---

## Corpus reference (real field names — do not invent)

Each record: `principle_id, domain, topic_tags, rule, conditions, judgment, tradition, notes, synastry{…}`.
The `synastry` block varies by `interaction`:

| interaction | count | block fields |
|---|---|---|
| aspect | 475 | `person_a_point`, `person_b_point`*, `aspect`, `polarity` (*15 records omit `person_b_point`) |
| house_overlay | 139 | `person_a_point`, `overlay_house` |
| natal_relational | 101 | `point/sign/dignity/…`, `applies_to`, `relational_role`, `source_domain` (per-person; 55 of these are the only `traditional` records) |
| planet_role | 72 | `person_a_point` |
| general | 46 | `interaction` only |
| compatibility | 32 | `factors` |

Grounded output buckets today: `person_a` (29), `person_b` (29), `synastry` (88), `framing` (150), `dropped` (593).
Direction is computed at match time and written to `matched[].direction ∈ {"A>B","B>A"}`, where **`A>B` = A's planet into B's houses / A-owned point listed first**, and `B>A` is the reverse.

---

## FIX A — Role binding (highest priority; correctness bug)

**Problem.** The corpus rule text and the `person_a_point` / `person_b_point` labels are written with literal "person A / person B", but any record can ground in **either** direction. On a `B>A` match the literal A/B is inverted. Verified: `syn-mercury-in-10th-house-overlay` — rule text says *"person A's Mercury falls in person B's 10th house"*, but the matched fact is `B>A` = **B's Mercury in A's 10th** (B's Mercury 291.98° sits in A's Placidus H10, 277.2–299.0). Read literally, S3 tells the couple the wrong person's Mercury shapes the other's career, on ~half of all records.

**Rule.** From `matched.direction`, assign real persons to corpus roles, then emit a bound fact and a pre-substituted statement. S3 must consume only the bound output — never the raw `rule` and never `person_a_point`'s "a".

Role mapping:
- **house_overlay:** corpus `person_a_point` is the *mover* (the planet), `overlay_house` belongs to the *home* person.
  `A>B` ⇒ mover=A, home=B. `B>A` ⇒ mover=B, home=A.
- **aspect:** the first-named point belongs to the person on the left of `direction`, the second to the right. `B>A` ⇒ `person_a_point` is **B's**, `person_b_point` is **A's**.

Emit on every grounded synastry record:
```json
"bound": {                         // house_overlay
  "mover_person": "B", "mover_point": "Mercury",
  "home_person": "A", "home_house": 10, "house_system": "placidus"
}
"bound": {                         // aspect
  "p1_person": "B", "p1_point": "Sun",
  "aspect": "conjunction",
  "p2_person": "A", "p2_point": "Saturn"
}
"bound_statement": "<rule text with 'person A'/'person B' replaced by the resolved person labels per the role mapping>"
```

**Acceptance (test pair).** `syn-mercury-in-10th-house-overlay` emits `mover_person:"B", home_person:"A"` and a `bound_statement` reading "B's Mercury falls in A's 10th house…". Any record whose `bound` disagrees with the two charts is a halt (see E).

---

## FIX B — Deduplicate by fact-key

**Problem.** Multiple corpus records ground to the *same physical fact*. In the test run three fact pairs doubled: Sun-in-9th (`syn-ninth-house-overlay-general` + `syn-sun-in-9th-house`), Sun-in-12th, Mercury-in-10th. Root cause: the `*-overlay-general` records carry a **spurious specific** `person_a_point` (e.g. `syn-ninth-house-overlay-general` has `person_a_point: "Sun"`, identical to the specific record). S3 will state each fact twice.

**Rule.** After Fix A, collapse emitted synastry records sharing a fact-key:
- overlay key: `(interaction, bound.mover_point, bound.home_house, direction, house_system)`
- aspect key: `(interaction, frozenset{bound.p1_point, bound.p2_point}, aspect, frozenset{p1_person, p2_person})`

Keep one survivor, by precedence: (1) `principle_id` **not** ending `-general` beats one that does; (2) higher `about.extraction_confidence` (or `notes` confidence if that's where it lives); (3) longer `rule`. Record collapsed ids on the survivor as `"superseded": ["…"]`. Never silently discard — the superseded list is the audit trail.

**Acceptance.** No two emitted synastry records share a fact-key; the three known dup pairs collapse to one each. Flag separately for corpus cleanup (not this script): repair `*-overlay-general` records to carry no `person_a_point`, or delete them since specific versions exist.

---

## FIX C — Stop dumping ungrounded interactions into `framing`

**Problem.** `framing` (150) = `general` (46) + `compatibility` (32) + `planet_role` (72). `planet_role` and `compatibility` are being pass-through routed, ungrounded. Only `general` is genuine methodology, and even 46 is too many to inject into S3.

**Rule.**
- **planet_role (72):** ground to actual placements. Each names `person_a_point`; every chart has every planet, so bind the role to each person's real placement (like `natal_relational`) and route to `person_a`/`person_b`, or to `synastry` if the role is cross-chart. If it can't be bound to a concrete factor, **drop** with a reason — do not pass through to framing.
- **compatibility (32):** match the record's `factors` against the pair's actual element/modality balance from the two charts. Keep only those that fit; route to `synastry`. Drop the rest (with reason).
- **general (46):** genuine interpretive stance. Curate to a fixed **allowlist** (≤ ~12) of stance principles; these are the *only* records that belong in `framing`. Drop the remainder.

**Acceptance.** `framing` ≤ ~15 records, all `interaction: general` and on the allowlist. `planet_role` and `compatibility` appear only when bound to a real chart factor, in a person or synastry bucket.

---

## FIX D — Echo resolved points into `matched` (auditability)

**Problem.** `matched` omits the point. Overlay `matched` = `{direction, house_system, house}`; aspect `matched` = `{direction, scheme, orb, separation}`. Neither names the planet(s), so nothing downstream (or in QA) can re-derive the fact from `matched` alone.

**Rule.** Add the resolved point(s) with person labels:
- overlay: `{"direction","house_system","house","person","point"}`
- aspect: `{"direction","scheme","orb","separation","a":{"person","point"},"b":{"person","point"}}`

**Acceptance.** Every `matched` entry names its concrete point(s) and person(s); an external checker can re-derive the fact from `matched` + the two charts with no other fields.

---

## FIX E — Exit invariants (halt on violation; mirror L3 discipline)

1. **Re-derivation.** Every emitted synastry record's `bound` fact is true against the two charts — the named point actually falls in that house (overlay), or the two named points are within orb for that aspect. Any failure halts with the offending `principle_id`. (This is the guard that would have caught the natal chart-mismatch class of bug automatically.)
2. **No duplicates.** No two emitted synastry records share a fact-key (post-Fix-B).
3. **No literal A/B leaks.** Every synastry record carries `bound` + `bound_statement`; no `bound_statement` contains the literal strings "person A" / "person B".
4. **Framing bounded.** `framing` contains only allowlisted `general` records.
5. **Every drop has a reason.** `dropped` entries carry a reason from a closed enum (`no_matching_fact`, `unbindable_role`, `factors_mismatch`, `not_on_stance_allowlist`, `superseded_by_fact_key`). No silent drops — consistent with the "`unclassified` is an earned verdict" rule from the natal pipeline.

---

## Reception — explicitly NOT in this fix pass

The corpus has **0 reception records** across all 865 (the only classical content is the 55 `natal_relational` domicile/marriage indications, per-person). Reception cannot ground until a three-part chain exists, none of which is this script:
1. the synastry **compute** emits `cross_reception` facts (per `SYNASTRY_COMPUTE_SPEC.md` §6),
2. a `syn-reception-*` corpus slice is authored (owner: astrology domain — reframe of the classical reception technique, neutral language, no modern-book IP),
3. the grounder gains a `reception` matcher binding those principles to the compute's reception facts.

Do not add reception handling in this pass. Land A–E first; reception is the next track.

---

## Suggested order

A (role binding) → D (echo points, so A/B are checkable) → E1 (re-derivation guard) → B (dedup) → C (framing/routing). A and E1 together make every subsequent change self-verifying against the two charts.

---

# PASS 2 — compatibility + planet_role routing

Pass 1 (A–E) is verified landed on the test pair `chart_1979-03-30.json` × `chart_r_1988-12-28.json`: all 88 synastry `overlay`/`aspect` bound facts re-derive true against the two charts, role attribution is correct ("B's Mercury in A's 10th"), the 12 duplicates collapsed via `superseded`, points echo into `matched`, and `framing` dropped 150→12.

Two interaction types Fix C touched were **re-routed but not cleaned**. Pass 2 closes them. Thresholds below are locked domain decisions — do not let implementation choose them.

## Reference: pooled placements for the test pair

Counting the seven classical planets in each chart (14 total):

- elements: fire 3, earth 7, air 0, water 4
- modalities: cardinal 6, fixed 2, mutable 6
- Scorpio: **0 planets**; Sagittarius 1; Taurus 2; Virgo 2; Capricorn 3; Pisces 3

## FIX F — compatibility prominence threshold

**Problem.** The 12 `kind: compatibility` records grounded without checking the factor is actually present. `syn-scorpio-general-role` fired with **zero** Scorpio placements across both charts; Sagittarius (1), Taurus (2), Virgo (2) fired as "strong influence" on 1–2 placements.

**Rule (locked).** A compatibility record grounds only if its factor clears threshold in the **pooled** two-chart placement set (seven classical planets per chart; angles excluded):

- **sign factor:** ≥ 3 pooled placements in that sign.
- **element / modality factor:** pooled bucket ≥ 5 of 14, **or** the strict single-highest bucket with a ≥ 2 margin over the next.

Below threshold → drop with reason `factor_below_threshold`.

**Acceptance (test pair).** Scorpio (0), Sagittarius (1), Taurus (2), Virgo (2) all drop. earth (7) and Capricorn (3) and Pisces (3) survive; cardinal (6) and mutable (6) tie at ≥5 so both may survive.

## FIX G — extend the E1 re-derivation guard to compatibility

**Problem.** E1 only re-derives `overlay` and `aspect` facts, so a compatibility factor absent from both charts still passes. This is exactly why the Scorpio record slipped through.

**Rule.** Add `kind: compatibility` to the exit invariant: every emitted compatibility record's factor must be present at the Fix F threshold in the pooled charts, or halt with the offending `principle_id`. No compatibility factor reaches S3 unverified.

## FIX H — dedup compatibility by factor

**Problem.** No fact-key dedup covers compatibility, so the pooled Pisces factor produced three records (`syn-pisces-influence-general`, `syn-pisces-adverse-aspects-entanglement`, `syn-pisces-sign-compatibility-general`), Virgo two, Sagittarius two.

**Rule.** Extend the Fix B fact-key collapse with a compatibility key: `(interaction, frozenset(bound.factors))`. Keep one survivor by (1) higher extraction confidence, (2) longer rule; collapse the rest into `superseded`. One record per sign/element/modality factor.

**Acceptance.** At most one surviving record per factor; the Pisces triple and Virgo/Sagittarius pairs collapse.

## FIX I — deduplicate planet_role per (person, point)

**Problem.** Fix C bound all 72 `planet_role` records to each person's real placement and routed them into the person buckets, which ballooned `person_a`/`person_b` from 29 to **101** each. Because "planet X plays a role" binds trivially to every chart, nothing dropped — the framing bloat became person-bucket bloat (~5 near-identical role templates per planet: `syn-sun-planet-role-general`, `syn-sun-conjunction-general-role`, `syn-sun-square-general`, …).

**Rule.** `planet_role` records are generic scaffolding, not chart-specific delineations. Collapse them by `(person, bound.point)` — keep at most **one** role line per planet per person (survivor by longest rule / highest confidence), rest into `superseded`. The chart-specific per-person content remains the `natal_relational` slice.

**Acceptance.** `person_a` and `person_b` return to roughly their pre-Pass-1 size (~29) plus at most one role line per planet; no planet contributes more than one `planet_role` record to a person bucket.

## Pass 2 order

F (threshold) → G (extend guard, so F is enforced) → H (compatibility dedup) → I (planet_role dedup). Re-run the test pair and confirm: Scorpio/Sagittarius/Taurus/Virgo compatibility records gone, one record per surviving factor, and person buckets back near ~29 + one role per planet.
