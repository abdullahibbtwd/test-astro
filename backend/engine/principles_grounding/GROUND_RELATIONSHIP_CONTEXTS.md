# GROUND_RELATIONSHIP_CONTEXTS.md — changes to `ground_relationship.py` for the reading-type fork

**Scope of change: minimal.** Under the design where `reading_type` filtering lives in S3 (ground once, filter at read time), grounding stays a **single, type-agnostic pass**. It does not learn about general/personal/professional, does not filter, and does not re-run per type. Verified against the actual source: every emit path (`_mk_overlay`, `_mk_aspect`, `_mk_reception`, the compatibility builder, and the `person_*` / `framing` appends) uses `{**rec, ...}`, and `RelResult.payload()` dumps the buckets verbatim — so `record["synastry"]["contexts"]` already flows end-to-end into `personal_relationship_principles.json` with no code change. Confirmed empirically: the tag survives `{**rec}` + JSON round-trip, and all 888 tagged records carry it.

There are three changes, and only two are code.

---

## 1. Point `--records` at the tagged corpus (config)

`main()` line ~850–851 defaults to `combined_relationship_principles.clean.json`. The fork requires the corpus to carry `synastry.contexts` on every record. Either:

- change the default to `combined_relationship_principles_tagged.json`, or
- replace the contents of the existing corpus file with the tagged version (same 888 records + the tag).

No other loader change. The tag is nested under each record's `synastry` block (`record["synastry"]["contexts"]`), which is exactly what the `{**rec}` emit preserves.

---

## 2. Add invariant E6 — fail fast on an untagged corpus (code)

The tag is the contract S3's filter depends on. If an untagged or partially tagged corpus is ever fed, grounding would emit records with no `contexts`, and S3 would silently mis-filter (personal records could surface in a professional reading). Guard it at load, in the spirit of the existing E-invariants.

Right after the corpus is loaded (line ~861–862, `records = json.load(fh)`), before grounding:

```python
_VALID_CONTEXTS = {"universal", "personal", "professional"}
for rec in records:
    ctx = (rec.get("synastry") or {}).get("contexts")
    if not (isinstance(ctx, list) and ctx and set(ctx) <= _VALID_CONTEXTS):
        raise RelInvariantViolation(
            f"{rec.get('principle_id','?')}: missing or invalid synastry.contexts "
            f"(got {ctx!r}); corpus must be tagged before grounding")
```

This is a corpus-level property, so check it once at load — not per emitted record. Zero tolerance, matching the E-discipline already in the file.

---

## 3. Add a per-context breakdown to `counts` (code, observability)

`RelResult.payload()` (line ~234–242) reports bucket sizes. Add the profile split so you can see, before S3 runs, how the grounded facts divide across contexts — useful for spotting a thin professional slice on a given pair.

Extend the `counts` dict:

```python
def _ctx_split(bucket):
    out = {"universal": 0, "personal": 0, "professional": 0}
    for rec in bucket:
        for c in (rec.get("synastry") or {}).get("contexts", []):
            if c in out:
                out[c] += 1
    return out

# inside payload()["counts"]:
"contexts": {
    "synastry":  _ctx_split(self.synastry),
    "person_a":  _ctx_split(self.person_a),
    "person_b":  _ctx_split(self.person_b),
},
```

A record tagged both `personal` and `professional` counts in both cells — that's fine; these are eligibility tallies, not partitions.

---

## What does NOT change

- **No `reading_type` argument, no filtering, no per-type grounding.** Grounding is single-pass and type-agnostic; the fork is entirely in S3 (`SYNASTRY_READING_PROFILES.md`).
- **No propagation code.** The `{**rec}` emit already carries `contexts` through. Do not add field-copying.
- **No change to reception, dedup, role-binding, or the E1–E5 invariants** — all verified clean and unaffected.

---

## If the filter is later moved to retrieval instead of S3

Even then, `ground_relationship.py` gains **no per-type logic** — it would simply receive a pre-filtered candidate set from retrieval and ground it as now. Changes 2 and 3 above still apply (validate the tag, report the split); change 1 becomes "retrieval passes only the eligible slice." So this spec holds either way; the decision only moves *where the filter runs*, not what grounding does.
