# SYNASTRY_READING_PROFILES.md — reading-type fork (general / personal / professional)

**Layers on:** `SYNASTRY_READING_SPEC.md` (S3). This document **supersedes §3 (section structure) and §4 (routing/floor)** of that spec and parameterizes them by `reading_type`. Everything else in the base spec — generation architecture (§5), no-score output (§6), attribution (§7), tradition mask (§8), asymmetry/precision (§9), invariants (§10), artifacts (§11) — applies unchanged to all three profiles.

**Corpus dependency:** `combined_relationship_principles_tagged.json` — every record now carries `synastry.contexts`, a list drawn from `{universal, personal, professional}`. Distribution: universal 514, personal 295, professional 61, both 18.

**Key principle:** a profile is **not** just a filter. Universal records enter every profile and are **reinterpreted through the profile's lens** — the same contact means different things romantically vs professionally. Filtering only removes the strictly off-context records; reframing does the real work.

---

## 1. Entry: ask the user

The pipeline entry point (orchestrator / CLI / UI) prompts for reading type before S3 runs:

```
Which relationship reading?
  [1] General             — the connection as a whole
  [2] Personal focus      — romantic / life partnership
  [3] Professional focus  — business / working partnership
```

Pass the choice as `reading_type ∈ {general, personal, professional}` to S3. **Default: `general`** (current pipeline behaviour). Record it in `run_meta.json` (`reading_type`) and stamp it into `relationship_reading_routing.json`.

One grounded file (`personal_relationship_principles.json`) serves all three — S1 and `ground_relationship.py` do **not** change and do **not** re-run per type. Only S3 forks. The user can switch type without re-grounding.

---

## 2. Context filter (which records a profile admits)

Applied via each record's `synastry.contexts`:

| reading_type | admits |
|---|---|
| general | **all** records (no filter) |
| personal | `contexts ∩ {universal, personal} ≠ ∅` — excludes professional-only |
| professional | `contexts ∩ {universal, professional} ≠ ∅` — excludes personal-only |

Admitted counts (test corpus): general 888, personal 827, professional 593. Apply this filter first, then the base-spec §4 noise floor (drop face receptions, sub-salience aspects), then route to sections.

`framing` / stance records (interaction `general`, tagged `universal`) are never rendered as content — they feed the S3 `_CONTRACT` block only, per base-spec §2, in all three profiles.

---

## 3. The reframing rule (the load-bearing part)

Universal records carry no fixed relational valence. S3's per-profile stance (in the cached `_CONTRACT`) tells the section calls how to read them. The same fact flips meaning:

| contact | personal lens | professional lens | general lens |
|---|---|---|---|
| Sun–Saturn hard | one partner feels controlled, judged, aged — a strain | structure, accountability, mentorship, seniority — usually an asset | one person grounds and limits the other |
| Moon contacts | emotional intimacy, feeling "at home" | instinctive rapport; read with caution, feelings can cloud a call | instinctive attunement |
| 8th-house overlay | sexual / psychological intimacy, merging | joint finances, shared investment, entanglement | pooled resources, depth |
| Venus–Mars | desire, romantic spark (core) | personal chemistry that may help or complicate the work (minor) | attraction of energies |
| 5th-house overlay | romance, play, children | creative collaboration, speculation, shared risk | shared creativity |
| Saturn reception | commitment, an enduring bond | durability of the venture, dependable structure | one holds and commits to the other |

The section prompt carries an explicit lens instruction for the chosen type. A universal record's `bound_statement` is a starting fact, not final copy — the section renders it in the profile's terms. **The lens reframes; it never invents** a fact not in the `bound_statement`, and the mask (base-spec §8) still binds.

---

## 4. Per-profile configuration

Each profile = {significator emphasis, section structure, stance}. Emphasis reweights routing/floor ordering — emphasized points lead, de-emphasized points sink (not dropped unless below the base floor).

### 4.1 general
- **Emphasis:** none — weight by raw salience. Holistic, sphere-agnostic.
- **Sections:** 0 What each brings · 1 Overall rapport, how you meet · 2 Emotional dynamics · 3 Communication & mind · 4 Friction & tension · 5 Values & shared ground · 6 Support, reliability & trust · 7 Shared direction
- **Stance:** interpret each contact at face value for the bond as a whole; assume neither romance nor business. This is the current reading, now one option of three.

### 4.2 personal focus
- **Emphasis:** Venus, Mars, Moon, Sun; houses 5, 7, 8, 4. De-emphasize 6, 10.
- **Sections** (as base-spec §3): 0 What each brings to a partnership · 1 Attraction & chemistry · 2 Emotional needs & security · 3 Communication & meeting of minds · 4 Friction & challenge · 5 Values, money & shared life · 6 Commitment & long-term viability · 7 Shared purpose & growth
- **Stance:** romantic-first, the two as intimate life partners. Reframe universal contacts toward closeness, desire, security, and long-term bonding.

### 4.3 professional focus
- **Emphasis:** Mars, Saturn, Mercury, Venus, Moon (the corpus's own business set, `syn-rule-business-mars-saturn-mercury-venus-moon`); houses 10, 6, 2, 11, 7. Venus/Moon/2nd carry financial-value compatibility. De-emphasize 5 and 8-as-intimacy (keep 8 as shared resources), and Venus–Mars desire.
- **Sections:** 0 What each brings to a working partnership · 1 Working rapport & trust · 2 Roles, leadership & division of labour · 3 Communication & decision-making · 4 Reliability & follow-through · 5 Money, resources & shared value · 6 Conflict & friction style · 7 Shared goals & venture longevity
- **Stance:** the two as collaborators / co-founders / colleagues. Reframe universal contacts toward competence, dependability, authority, decision-making, and venture durability. Personal chemistry, if strong, is noted only as something that may support or complicate the work — never the point.

---

## 5. The classical layer carries across profiles

Reception and the 7th house survive the fork intact, protecting the differentiator:

- The 7th house is classically the house of **partners, spouses, and business associates / contracts alike** — so 7th-lord reception and 7th overlays route into both personal (commitment) and professional (working partnership), reframed by lens.
- Reception (mutual accommodation — who defers to whom, who provides for whom) reads for a working partnership as naturally as for a marriage. A Saturn-receives reception is romantic commitment in personal, dependable structural deference in professional.

No separate classical corpus is needed for the fork; the tag plus the lens handle it.

---

## 6. Known thin spots (top-up candidates, not blockers)

- **Professional per-person opener:** only ~29 `natal_relational` records survive the professional filter (most partnering-capacity records are marriage-specific → tagged personal). "What each brings to a working partnership" will be lean — candidate for a small authored top-up (each person's Saturn / Mercury / 10th work-capacity), same method as the reception slice.
- **100 romantically-worded "universal" records were tagged `personal`** to keep them out of professional readings, costing professional some geometry. Neutralizing their wording later (a rewrite pass) would let them re-tag `universal` and rejoin professional. Deferred; not needed for v1.

---

## 7. Invariants (added to the base S3 set)

1. **Eligibility respected.** No `personal`-only record appears in a professional reading, nor vice versa. Stance/framing records never appear as content in any reading.
2. **Lens applied, not invented.** Every universal record surfaced in personal/professional is framed in-context but asserts nothing beyond its `bound_statement`.
3. **Type stamped and consistent.** `reading_type` is in `run_meta.json` and the routing report, and the reading's framing matches it (a professional reading contains no romance/attraction claims; a personal one contains no venture/contract framing).
4. All base-spec S3 invariants (attribution from `bound` only, tradition mask, no numeric score, floor applied, traceable statements) continue to hold per reading type.

---

## 8. Out of scope

- No fourth type (friendship/familial) in v1 — those records sit in `universal`/`personal` and surface, reframed, under whichever focus is chosen.
- No change to compute or grounding — the fork is entirely S3: user prompt → context filter → section structure → emphasis → lens.
- Optional later: an LLM re-tag pass to promote safely-defaulted `universal` records into `personal`/`professional` where a sharper split helps; the deterministic tagging is sufficient to ship all three.
