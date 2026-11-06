# Compatibility scoring

**Status: BLOCKED** — do not ship a numeric `score` until product + astrologer pick a formula and fill weights.

Related code:

- Weights config: `backend/engine/rules/compatibility_score_weights.json` (empty / awaiting)
- Adapter: `backend/api/compatibility-score.ts` (returns `null` until configured)
- API field: `Compatibility.score` (`null | { value, label }`)
- Client flag: `compatibilityScore` (default **off** in `backend/api/defaults/config.json`)
- Spec conflict: `docs/frontend/FE_06_COMPATIBILITY_SPEC.md` §4 (brief allows 0–100; synastry S3 §6 forbids a numeric score in v1)

## What exists today

| Piece | Behavior |
| --- | --- |
| `POST/GET /compatibility` | Sets `score: null` |
| Flag `compatibilityScore` | `false` — UI hides the score ring |
| Synastry aspect math | Exists for Match / Family aspect rows (separate from a 0–100 rollup) |

## Intended config shape (when unblocked)

`compatibility_score_weights.json` holds:

- `formula_id` — which option below was chosen
- `aspect_type_weights.weights` — per aspect type
- `planet_pair_weights.weights` — optional pair multipliers
- `relationship_type_multipliers` — love / work / family
- `scale.label_bands` — how `value` maps to `label`
- inclusions / exclusions lists

`computeCompatibilityScore()` must stay a pure function of aspect rows + this file. No LLM.

## BLOCKED — formula options (pick one; do not invent)

Until one option is approved, **keep `score: null`**.

### Option A — “No numeric score” (current v1 / S3 §6)

- Keep `score: null` forever (or until a major version).
- Flag stays off; remove or never enable the score ring.
- **Pros:** Matches synastry reading philosophy; no false precision.
- **Cons:** Brief’s optional % score unused.

### Option B — Aspect hit-rate (0–100)

- Count modern synastry hits (optionally orb-weighted).
- `value = round(100 * Σ(w_aspect × w_pair × orb_factor) / Σ(max_possible))` with caps.
- Requires: complete `aspect_type_weights`, orb curve, and whether applying/separating matters.
- **Pros:** Deterministic from existing aspect math.
- **Cons:** Easy to misread as “relationship quality”; needs astrologer-approved weights.

### Option C — Banded qualitative index mapped to 0–100

- Astrologer defines discrete bands (e.g. challenging / mixed / supportive) from selected aspects only.
- Map bands to fixed midpoints (25 / 50 / 75) or closed intervals; expose `label` from the band, not a fine-grained %.
- **Pros:** Closer to interpretive practice; less false precision than Option B.
- **Cons:** Still a number on the wire; band boundaries must be authored.

### Option D — Type-specific scores (love ≠ work ≠ family)

- Separate weight tables per `CompatType` / `family_relation`.
- Same engine, different `relationship_type_multipliers` + inclusion lists.
- **Pros:** Matches product types already in the API.
- **Cons:** 3× (or more) authoring work; family rules are themselves still empty.

## Unblock checklist

1. Choose **A / B / C / D** (or a documented hybrid) in this file’s decision log below.
2. Fill `compatibility_score_weights.json` (`formula_id` + non-empty weights).
3. Implement the chosen arithmetic inside `computeCompatibilityScore` (still no LLM).
4. Wire the result into `compatibility-jobs` render path.
5. Add fixture tests with known aspect rows → expected `{ value, label }`.
6. Only then consider flipping `compatibilityScore` for a staged release.

## Decision log

| Date | Decision | By |
| --- | --- | --- |
| _pending_ | _none — BLOCKED_ | |

## Non-goals

- Do not derive scores from LLM prose.
- Do not enable `compatibilityScore` while `formula_id` is null.
- Do not commit invented placeholder weights that look “real.”
