# CAL 03: calendar texts (grounded, cached)

*Reuses the predictive reading machinery (`prediction_reading/pr_*`): a TR draft, then an EN translation, then detox, then the validator.
Modern records only (CAL_00 D3). Texts are generated **lazily** (on first view) and **prewarmed nightly for the next 14 days**.*

## 1. Text units

| Unit | Scope | Length (TR words) | Grounding | Cache key |
|---|---|---|---|---|
| `collective_event` | new/full moon by sign, eclipse by sign and kind, retrograde period by body, slow-planet ingress (Jupiter–Pluto) | 50–80 | modern records for that event kind (Phase 0 audit) | `(event_id, lang, corpus_sha, prompt_v)`, **global, shared by all users** |
| `personal_transit` | transit episode, importance major | 70–110 | Hand transit records for (T,a,N) + the phase label | `(chart_key, event_id, lang, corpus_sha, prompt_v)` |
| | importance moderate | 30–50 | same | same |
| | importance minor | **no text**, label only | — | — |
| `personal_lunation` | lunation or eclipse, importance ≥ moderate | 40–70 | lunation/eclipse records + the `house_domain` record for `natal_house` (modern) | per chart |
| `period` | periods with importance major or strength strong | 40–80 | the drivers' records restricted to those tagged with the period's goal | per chart |
| `day_note` | "today" card, on request | 40–60 | the day's top drivers (≤ 3) + active collective events | per chart and date |

**No grounding, no text.** If a unit has no eligible record (e.g. a collective event kind that is missing from the corpus), return only
the deterministic label (§2) and add the unit to `gaps` in the manifest. Never write around a gap.

## 2. Deterministic labels (always present, no LLM)

These come from a label catalogue (TR/EN), e.g.:
- "Yeni Ay – Terazi" / "New Moon in Libra"
- "Merkür retrosu" / "Mercury retrograde"
- "Satürn, Güneş'inize kare" / "Saturn square your Sun"
- "Tam güneş tutulması – Aslan" / "Total solar eclipse in Leo"

Date ranges are UI data, not prose.

## 3. Prompt rules (on top of the predictive layer's rules)

- Second person, reflective register, present/near-future tense.
- `personal_transit`: frame by `phase` ("building", "at its peak", "easing") using the phase label, never dates or degrees.
- `period`: name the life area and whether it is supportive or demanding. Use only the records tagged for that goal.
- No directives ("you must", "sign now"), no guarantees, no fatalism.
- Sensitive themes (health, accidents, death, loss) follow the ACG_04 AV8 rules: experiential framing only, never predicted events.

## 4. Validator additions

| # | Rule |
|---|---|
| CV1 | Trace ⊆ the unit's allowed records; every paragraph is traced. |
| CV2 | No numbers in prose: dates, degrees, orbs, percentages, house numbers. |
| CV3 | ACG_04 AV2 (no directive language) and AV8 (no event-prediction words) lists apply unchanged. |
| CV4 | A `period` text for `kind = challenging` must trace ≥ 1 driver record with polarity `mixed` or `supportive` for that goal, so it can offer a constructive angle. If no such record exists, only the label is shown. |
| CV5 | Lengths within ±20%. |

## 5. Output

- `texts_tr.json` / `texts_en.json`: `{unit_id: {text, trace, unit_type, ref}}`.
- Collective texts live in `cal_run/_collective/texts_<lang>.json`.

## 6. Acceptance (`test_cal_reading.py`)

| # | Check |
|---|---|
| T1 | A collective text is generated once and reused for 2 different charts (the call counter proves it). |
| T2 | A minor transit gets no model call and has a label only. |
| T3 | A unit with no eligible records → label only + a `gaps` entry, no model call. |
| T4 | CV1–CV5: one positive and one negative unit test each. |
| T5 | Nightly prewarm generates exactly the units whose dates fall in the next 14 days and aren't cached. |
| Gate | Radul reads 1 real chart × 3 months of texts (TR). |
