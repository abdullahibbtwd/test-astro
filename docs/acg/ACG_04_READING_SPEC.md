# ACG 04: place reading (`acg_reading/`)

*Mirrors `prediction_reading/` and `Interpretation_layer/`. **Reuse** `llm_client`, the
translation pass, the detox rewrite and the validator framework; only add ACG sections,
prompts and rules. Phase 0 item 8 gives the concrete functions to extend.*

## 1. Pipeline

```
acg_principles.json ─► ar_routing (deterministic bundles → sections)
                     ─► TR draft per section (parallel, llm_client)
                     ─► TR synthesis per section (other drafts as context)
                     ─► EN translation per section
                     ─► detox rewrite if a rule fires
                     ─► ar_validate (refuses to ship on any violation)
                     ─► ar_render (reading.md + JSON)
```

Default models are the same as for predictive (Turkish drafts/synthesis: the synthesis model;
translation: the cheap model with fallback). The same CLI flags apply (spec 05).

## 2. Sections

| key | TR title | EN title | Source bundles | Length (TR words) | Omit when |
|---|---|---|---|---|---|
| `place_overview` | Bu Yere Genel Bakış | This Place at a Glance | `method` + one-line gist of each other section (from drafts) | 90–140 | never (status ok) |
| `lines_here` | Buradaki Gezegen Çizgileri | Planetary Lines Here | `line:*` bundles | 70–120 **per line**, one paragraph each | no line bundles |
| `life_areas_here` | Burada Öne Çıkan Yaşam Alanları | Life Areas That Shift Here | `house:*` bundles | 100–200 total | no house bundles |

Section order in the output: `place_overview`, `lines_here`, `life_areas_here`.
`place_overview` is drafted **last**, with the other drafts as context, in the synthesis stage.
Empty sections are omitted, never emitted blank (the project rule).

## 3. Routing and profile lens (`ar_routing.py`)

- Each `line:*` bundle → one paragraph slot in `lines_here`. Each `house:*` bundle → a slot in `life_areas_here`.
- **Tier to wording** (deterministic label passed to the prompt, never a number):
  `tight` → TR "belirgin biçimde" / EN "strongly"; `strong` → TR "hissedilir biçimde" / EN "noticeably";
  `wide` (only ever the single nearest line, spec 03 §3) → TR "hafif ve arka planda" / EN "faintly, in the background".
- **House → life-area name:** use the reader-facing house names from `PROJECT_OVERVIEW` §3 (e.g. 10
  → "Toplumsal Statü ve Meslek" / "Social Status and Vocation"). House numbers never reach
  the prompt as numbers.
- **Profile lens** reorders line paragraphs and adds a single emphasis instruction. It never filters:

| profile | Paragraph order in `lines_here` | Emphasis instruction |
|---|---|---|
| general | by distance | balanced |
| personal | DSC, IC, ASC, MC, then by distance | foreground relationships, home and emotional life within each principle |
| professional | MC, ASC, DSC, IC, then by distance | foreground work, visibility and collaboration within each principle |

## 4. Prompt requirements (`ar_prompts.py`)

Build on the existing prompt builder. ACG-specific content for the system prompt:

1. You are describing how **this place** brings certain themes of the person's birth chart
   forward. Write in Turkish, in second person, in the project's established register.
2. Use **only** the supplied principles. Each paragraph ends with its principle-id trace in
   the existing trace format.
3. A line paragraph combines the **angle frame** (A3: where the theme shows up), the
   **planet-on-angle principles** (A1, the core, in the given order), and the **planet synopsis**
   (A2, for colour). Fallback records (A4, planet-in-house) describe the planet's expression:
   present them as what this place emphasises, **not** as "your planet is in house N".
   Records flagged `sensitivity: high` follow rule 8.
4. Use the tier wording label as given. Never state distances, degrees, coordinates, house
   numbers or angle abbreviations.
5. Always convey ambivalence (`acg-method-ambivalence`): themes come in easier and more
   demanding forms. The overview also carries `acg-method-natal-modifies-response` (how the person
   meets the theme depends on their whole chart) and `acg-method-degree-of-expression` (the themes
   show up at the scale of an ordinary life, not as dramatic events).
6. Never advise moving, staying or avoiding a place. Never promise outcomes.
7. Name the place with `name_tr` (TR) / `name` (EN).
8. **Sensitive records** (`sensitivity_high_ids`) may only be rendered as inner or experiential
   themes (intensity, pressure, risk-taking, feeling unanchored, deep change), never as events
   that will happen (death, accident, attack, illness, crime, addiction). If a sensitive record
   can't be rendered that way, leave it out rather than soften it into a new claim.

## 5. Validator additions (`ar_validate.py`, on top of the existing checks)

| # | Rule | Applies to |
|---|---|---|
| AV1 | No technical leakage. Reject a digit adjacent to `km`, `°`, `derece`, `kilometre`, `mil`; also reject the tokens `boylam`, `enlem`, `longitude`, `latitude`, `orb`, `ASC`, `MC`, `DSC`, `IC`, `yükselen çizgi`, `tepe noktası`, `hour angle`, and house-number patterns (`\b\d{1,2}\.\s?ev`, `\b\d{1,2}(st|nd|rd|th) house`). Match abbreviations case-sensitively on word boundaries (`\bMC\b`); match words case-insensitively with Turkish-aware casefolding. | TR + EN |
| AV2 | No directive or fatalistic language. ACG forbidden list, added to the detox list: TR `taşınmalısın`, `taşınmalısınız`, `taşının`, `kaçının`, `uzak durun`, `kesinlikle`, `garanti`, `asla yaşama`; EN `you should move`, `must move`, `avoid living`, `stay away`, `guarantee`, `definitely will`. If one fires → detox rewrite → re-validate once → refuse on a second failure. | TR + EN |
| AV3 | Planet coverage. The set of planets named in `lines_here` = the set of bodies in the line bundles. No node, unselected or unbundled planet is named. | TR + EN |
| AV4 | Every paragraph carries a trace, and every traced id exists in `acg_principles.json`. | TR |
| AV5 | `place_overview` names the place (`name_tr` in TR, `name` in EN). | TR + EN |
| AV6 | Lengths are within the §2 ranges ±20%. | TR |
| AV7 | Omitted sections are absent from the JSON, not empty strings. | JSON |
| AV8 | No event-prediction language for sensitive themes. Reject TR `ölüm`, `öleceksin`, `kaza geçir`, `saldırıya uğra`, `hastalanacak`, `suça karış`, `suç işle`, `bağımlı ol` and EN `death`, `die`, `accident`, `attacked`, `will fall ill`, `crime`, `addiction` in any section. On a hit: detox rewrite → re-validate once → refuse. | TR + EN |

## 6. Fixed footer (deterministic, not model-written, no trace needed)

- TR: "Bu okuma sembolik bir yansımadır; nerede yaşayacağınıza dair bir tavsiye değildir."
- EN: "This reading is a symbolic reflection, not advice on where to live."

`ar_render` appends it to `reading.md` and to both JSONs as `footer`.

## 7. Outputs (in the run folder)

`reading_tr.json`, `reading_en.json` (the same section shape as the predictive reading JSON plus
`place` and `footer`), `reading.md`, and `validation_report.json`.

## 8. Acceptance (`test_acg_reading.py` + manual gate)

| # | Check |
|---|---|
| AR1 | Routing is deterministic: the same `acg_principles.json` + profile → the same section plan (unit test, no LLM). |
| AR2 | Profile lens: the personal/professional ordering follows §3; the paragraph count is identical across profiles. |
| AR3 | Zero-line fixture → no `lines_here`; the overview traces `acg-method-no-influence`. Wide-only fixture → exactly one `lines_here` paragraph, with the faint wording label. |
| AR4 | Validator unit tests: one positive and one negative case for each of AV1–AV8. |
| AR5 | `--dry-run` produces the section plan and prompts with no model calls. |
| Gate | 1 real chart × 3 cities (one with ≥ 2 tight lines, one with only house shifts, one with nothing) × 3 profiles → all pass the validator; Radul reads the TR output. |
