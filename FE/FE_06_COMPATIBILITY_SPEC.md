# FE 06: Compatibility (Match tab)

*Brief §9. API: FE_02 §7.6. Backend: synastry pipeline S1–S3 with reading types `personal` (love) and
`professional` (work); family is NEW (O4, fallback `general`). No numeric score in v1 (O1).*

## 1. Match home (`match/index`)

- Title: "Who fits me?" / "Kim bana uygun?" (chrome) and a primary **New compatibility** button.
- History: `GET /compatibility` as cards: two round avatars (sun-sign glyphs), "Ayşe & Mehmet", type chip
  (Love / Family / Work), status (ready / preparing / failed), date. Tap → report. Swipe → delete.
- Empty state: one line + the button.

## 2. New compatibility (`match/new`)

### 2.1 People
- Two slots, **Person A** (default: You) and **Person B**. Each opens a sheet listing My Charts (FE_03 §7.1) with
  **Add a new person** at the top (the FE_03 §7.2 flow inline; the new person is saved to My Charts, since the API
  works on saved profiles and the brief reuses them).
- A ≠ B is enforced. A swap button exchanges the slots (the backend attributes text per person, so order is kept
  as chosen).
- Entry from a profile's **Compare with you** (FE_03 §7.2) preselects both.

### 2.2 Type
Three cards (chrome copy, native review):

| Type | TR | EN | Covers (brief §9) |
|---|---|---|---|
| `love` | Aşk | Love | attraction, emotional compatibility, romance, chemistry, communication, trust, long-term potential, main conflicts, what connects you |
| `family` | Aile | Family | parent–child, siblings, other family ties: emotional bond, communication, understanding, conflicts, family dynamics, how to improve the relationship |
| `work` | İş | Work / Business | working compatibility, communication, decision-making, leadership, financial partnership, trust, conflict areas, strengths as a team, the best division of roles |

- Choosing **Family** shows a sub-choice: Parent–child · Siblings · Other (`family_relation`). Hidden when flag
  `familyCompatibility` is off.
- Preselect from Person B's relation: partner → love; colleague, business_partner → work; child, parent, family →
  family (+ parent_child / other); friend, other → none.

### 2.3 Create
`POST /compatibility` with an `Idempotency-Key` → navigate to `match/[id]`. The same pair + type returns the
existing report instantly (idempotent).

## 3. Report (`match/[id]`)

| Order | Block | Content |
|---|---|---|
| 1 | Header | both avatars, "Ayşe & Mehmet", type chip (+ family relation), creation date |
| 2 | Big three, side by side | ☉ ☽ AC signs for each person (from `people.*.big_three`); tap → that person's chart |
| 3 | Type switcher | segmented Love · Family · Work. Switching creates / opens the report of that type for the same pair (`POST`, idempotent). |
| 4 | Score *(flag `compatibilityScore`, default off)* | only if `score` is non-null: `value` / 100 in a quiet ring + `label`, placed **after** the first section (the analysis leads, brief §9) |
| 5 | Sections | `reading.sections` in API order with API titles as `ReadingSection`s; the first expanded. `what_each_brings` holds one paragraph per person; render paragraphs as they come. |
| 6 | Actions | **Ask about this relationship** (Ask with `context.other_profile_id`), **Download PDF**, **Share** |
| 7 | Footer | the general disclaimer (FE_01 C6) |

- The app treats section keys as opaque (they differ by type; FE_02 §7.6). No hard-coded section list, no
  client-side mapping of brief items to sections.
- Pending: header, big three and switcher render at once; sections show `JobProgress` (the backend's first
  compatibility run grounds both charts; switching type later reuses the grounding and is faster).
- Failed: ErrorState + Retry (`GET /compatibility/{id}?retry=true`).

### 3.1 PDF
A4: title (`reading.title`), both names and big threes, the two wheels side by side (canonical `renderChart`, light
theme, vector), all sections, disclaimer, wordmark. Same pipeline and font rules as FE_05 §6. File name
`{labelA}-{labelB}-uyum.pdf` / `-compatibility.pdf` (ASCII-folded).

## 4. Score decision (O1)
The brief allows an optional 0–100 % score; the synastry spec forbids a numeric score (S3 §6). v1 shows none:
`score` is `null` and flag `compatibilityScore` is off. The block exists only so that a later backend decision
needs no app release beyond the flag.

## 5. Acceptance

| # | Check |
|---|---|
| CP1 | Create love, work and family (flag on) reports for two fixture profiles; each renders the fixture's sections in order with the API titles in TR and EN. |
| CP2 | Creating the same pair + type twice returns the same `compatibility_id`; the type switcher reuses existing reports. |
| CP3 | With `familyCompatibility` off, the Family card and switcher segment are hidden. |
| CP4 | No score block renders with the flag off or with `score: null`. |
| CP5 | Adding a new person inside the flow saves it to My Charts and returns to the flow with Person B filled. |
| CP6 | Pending state keeps the header interactive; leaving and returning shows progress, not a restart; the ready toast deep-links to the report. |
| CP7 | The PDF contains both vector wheels and every section with correct Turkish glyphs. |
