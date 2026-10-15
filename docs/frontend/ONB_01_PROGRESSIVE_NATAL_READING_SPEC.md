# ONB_01 — Progressive natal reading for onboarding (backend)

**For:** the backend coding agent (Python pipeline + `frontend/local-api` + contract) · **Owner:** Radul · **Domain decisions:** Claude
**Supersedes:** `FE_ONB_onboarding_free_reading_auth_paywall.md` §12 items 1–2 (the separate "essence" call and the theme grouping). Those are no longer needed.
**Status:** ready for Phase 0.
**Depends on:** `ONB_02_PROFILE_DOSSIER_SPEC.md`. The chart, the natal grounding and the Plan come from the profile dossier and are never recomputed here.

---

## 0. What Radul asked for

1. A short reading at onboarding that follows the **rules and principles of the long reading** (L4).
2. The text is generated **as the user keeps reading** (scrolling down). The full reading is generated only if they actually keep reading, so we never pay for text nobody reads.
3. A **"Seni doğru okuduk mu?"** ("Did we read you right?") button. Tapping it records the answer and takes the user to the email (sign-in) step.

## 1. The core decision: the onboarding reading *is* the L4 reading, delivered progressively

We do not build a second, shorter reading product. The onboarding reading is the canonical L4 reading, generated **section by section, in render order, only when the reader gets there.**

- **Chapter 1 is `core_identity`:** Sun and Moon by sign, Ascendant and chart ruler(s). It's about 450 words, roughly a 2–3 minute read.
- **The onboarding reading is Part One, "BİRİNCİ BÖLÜM — Kim Olduğun"** ("Who you are"): `core_identity` → `sun_house` → `moon_house` → `inner_drives` → `chart_shape`.
- **Part Two** (the 12 house sections) continues the same document after sign-in.

Why this design:

| Benefit | How |
| --- | --- |
| Every L4 rule applies unchanged | Same `ground()`, same `route()`, same `_CONTRACT` system prompt, same section prompt, same validator, same forbidden-token detox. |
| Nothing is paid twice | The sections an anonymous user reads become their saved reading after sign-in. There's no "teaser" text to throw away. |
| Pay per section read | Generation follows reading depth (§5). Real numbers are in §8. |
| One pipeline | My Charts profiles and the existing `GET /natal-reading` also move onto it (§6.4). |

**Exact birth time stays required** (FE_00 F9; L4 §7.7 is exact-only). The FE_ONB proposal to accept approximate or unknown times is **withdrawn** until L4 supports precision tiers.

**No user name in generated text.** L4 never uses the name, so cached sections can be shared across identical charts (§4.4). The app may greet by name in UI chrome, outside generated text.

## 2. The one architectural change: progressive synthesis

Batch L4 does `section_all()` (17 parallel drafts), then `synthesize()`: one call per section, each receiving **all other drafts** as context for dedup, callbacks and contradiction. A progressive reader can't wait for all drafts. Two inputs replace "all other drafts". Everything else in L4 §5 stays.

### 2.1 Ownership map (deterministic, from routing reasons)

`route(kept, chart)` routes one principle to several sections; overlap is intended. Each `RoutedPrinciple` records **why** it was placed (`reasons`). Two kinds of reason exist:

- **Primary** — the factor-type rule (L4 §3.1), e.g. `"planet_in_sign -> point home"`, `"planet_in_house -> domain h9"`, `"general(tags: Venus) -> point home"`.
- **Cross-route** — the §3.0 occupancy/rulership copies, emitted by `_emit_point_domains` with reasons containing `" occupancy: "` or `" rulership: "` (e.g. `"chart occupancy: Venus occupies domain"`, `"general(tags: Pluto) rulership: Pluto rules h8 domain"`).

**Ownership uses primary reasons only:**

```
primary(p) = [k in SECTION_ORDER where p sits in k with ≥1 primary reason]
ft         = p.about.factor_type
house_fact = ft in {planet_in_house, planet_in_sign_and_house, house_ruler, house_lord_relative}
             or (ft in {house_domain, node} and some primary(p) section is Movement 2)
m2         = [k in primary(p) if MOVEMENT[k] == 2]
if house_fact and m2:  owner[p] = m2[0]                    # domain wins (L4 §5.2)
else:                  owner[p] = first k in primary(p) not in {sun_house, moon_house}
                                  (else primary(p)[0])     # sign/character facts live in Part One
```

- **For section S:** `own(S)` = routed ids whose owner is S. **Exception (L4 §5.2):** `sun_house` and `moon_house` treat every routed id as own; they are never trimmed to a callback.
- `elsewhere(S)` = every other id routed to S. Each carries its owner's display title, `l4_render.section_title(owner, 'tr', house)`.

**Evidence — Radul's chart (166 kept principles, all 17 sections non-empty):**
- With this rule, Part One keeps its portraits. `core_identity` owns 26 of 32 ids, `inner_drives` 12 of 37, `chart_shape` 47 of 76. `sun_house` and `moon_house` own all of theirs.
- House sections own their house facts. The rest of their routed ids are cross-route copies, which they use for the house angle only (§3.2).
- **Do not use the naive rule** "Movement 2 always wins over all routed sections". On the same chart it left `core_identity` owning 5 of 32 and `inner_drives` 0 of 37: Part One would collapse into callbacks.

This is the deterministic version of L4 §5.2 together with the existing section briefs: Part One briefs already say "point forward in one clause"; house briefs already say "do not restate the Part-one sign portraits".

### 2.2 Written-so-far context

The finalize call for S receives the **finalized Turkish text** of sections already written for this chart:

- `core_identity` (always, once it exists) — the voice anchor;
- the **nearest preceding** finalized section in render order, if different;
- capped at ~6k tokens.

This replaces the "all other drafts" context.

### 2.3 The per-section pipeline

```
draft    = build_section_prompt(S, routed[S], chart)                ← UNCHANGED (l4_prompts.py)
final_tr = build_progressive_finalize_prompt(
              S, draft, written_context, own(S), elsewhere(S),
              chart, low_salience_ids)                              ← NEW (§3)
validate(single-section output, routed_ids, langs=('tr',))          ← extended (§3.3)
detox if forbidden tokens                                           ← UNCHANGED
persist (immutable)
text_en  = translate(S, final_tr)   only when lang=en is requested  ← UNCHANGED prompt, lazy
```

**How the L4 §5 jobs carry over:**

| L4 §5 job | Progressive version |
| --- | --- |
| Voice unification | Same instruction + the `core_identity` anchor in context. |
| Cross-section dedup | `elsewhere(S)` facts are used only for S's own angle. Their portrait is not repeated; at most one clause points to the owner section by title. Backward callbacks ("as we saw above") are allowed for facts visible in the written context. |
| Texture balancing | Unchanged. |
| Contradiction | Named against the **written context**. A tension with a later section is named when that later section is written; it sees the earlier one. |
| `chart_shape` salience pruning | Unchanged; uses `routing.low_salience_ids()`. |
| Hard invariant: adds nothing | Unchanged. The only source is S's draft; the context is read-only. |

## 3. Code changes (Python, `Interpretation_layer/`)

### 3.1 New module `l4_progressive.py`

| Function | Behaviour |
| --- | --- |
| `prepare(chart, kept) -> Plan` | `route()` → `non_empty()` → ownership map (§2.1) → `section_houses(chart)` → titles (`l4_render.section_title`, both languages) → `low_salience_ids()`. Pure and deterministic, no LLM. **Plan:** `{chart_key, order: [key…], movement, house, titles, routed_ids: {key: [ids]}, own: {key: [ids]}, elsewhere: {key: [{id, owner, owner_title_tr}]}, low_salience_ids}`. |
| `generate_section(plan, key, chart, routed, written: list[{key, text_tr}], gen) -> SectionResult` | Draft call + finalize call + validate + detox. **SectionResult:** `{key, movement, house, text_tr, principle_ids, draft_tr, usage: {draft, finalize, detox}, prompt_version, context_keys}`. |
| `translate_section(key, text_tr, gen) -> text_en` | Wraps `LLMGenerator.translate` + detox. |
| `PROMPT_VERSION = "l4p.v1"` | Stored with every section. |

Reuse `LLMGenerator` (`l4_generate.py`) for all calls, so retries, auto-grow on truncation, the stall timeout, `usage` accounting and the provider routing via `llm_client` are inherited. Models stay unchanged: `DEFAULT_MODEL` (gemini-3.7-flash, thinking `low`) for draft and finalize; `DEFAULT_TRANSLATION_MODEL` (gpt-6-luna) for translation and detox.

### 3.2 New prompt `build_progressive_finalize_prompt` (in `l4_prompts.py`)

- **System:** `_CONTRACT` + the five jobs, worded as in `build_section_synthesis_prompt`, with the context sentences replaced:
  - "You are finalizing ONE section that will be read **in order**. WRITTEN SO FAR are sections the reader has already read: keep the same voice, do not re-teach what they already covered (a brief backward reference is fine), and name a genuine tension with them as productive tension."
  - "OWN principles get the full treatment."
  - "OWNED ELSEWHERE lists principles whose portrait belongs to another section. Use them only for what they mean in THIS section's area of life — for example how a planet that sits in or rules this house acts here. Do not repeat the portrait their home section gives. If the reader needs it, refer to that section **by its title** in one clause."
  - The `sun_house` / `moon_house` and `chart_shape` instructions are kept verbatim.
- **User:** `SECTION`, `THEME`, `BRIEF` (`section_brief`); `THIS SECTION'S DRAFT`; `WRITTEN SO FAR` (JSON list of `{title, text_tr}`); `OWNED ELSEWHERE` (JSON list of `{principle_id, rule (≤160 chars), owner_title}`); `LOW-SALIENCE ids`; `CHART` (compact).
- **Output schema:** `SECTION_SCHEMA` `{key, text_tr}` (unchanged).

### 3.3 Extend `l4_validate.validate`

Add `langs: tuple[str, ...] = ("tr", "en")`. Only the listed languages must be non-empty and are scanned for forbidden tokens. The batch path keeps the default; the progressive path passes `("tr",)` and re-validates with `("en",)` after translation. A single-section output dict must validate: order is informative only, as today.

### 3.4 Batch path stays

`interpret()` and the CLI remain for evaluation and regression. App requests use the progressive path only.

## 4. State, storage, caching

### 4.1 Records (local-api `Store` key/value, same style as `reading:` / `reading-job:`)

| Key | Value |
| --- | --- |
| `dossier/{chart_key}/a0/natal_plan.json` | Plan (§3.1), written once as a dossier product (ONB_02 §6). Kept principles: `a0/natal_grounding.json`. |
| `reading-section:{chart_key}:{key}` | `{status, text_tr?, text_en?, principle_ids, house?, prompt_version, context_keys, usage, generated_at, job_id?, error?}`. **Immutable** once `ready`. |
| `reading-progress:{profile_id}` | `{opened: [key…], furthest_index, complete_requested_at?}` |
| `reading-feedback:{id}` | §7 |

**Section status:** `not_started` → `drafting` → `finalizing` → `ready` (TR); then `text_en` is added on demand. `failed` is retryable.

### 4.2 Immutability

A section the reader has seen **never changes**. No re-synthesis of a ready section, ever; a new `PROMPT_VERSION` applies only to sections not yet generated. This is why progressive synthesis looks only backwards.

### 4.3 Concurrency

- Per chart: at most **2** section generations at once (current + read-ahead); up to **3** in complete mode.
- The current `ReadingJobs` refuses any second job globally (`busyProblem`). Replace that with a per-chart limit, plus a global cap from config (local default 3).

### 4.4 Shared cache

Plan and sections are keyed by `chart_key` (same birth data → same chart → same text). Two users with identical charts share sections; access is still checked per profile.

## 5. Generation policy — pay only for what is read

| Rule | Default (config) | Behaviour |
| --- | --- | --- |
| Start | — | When the self profile is created (birth place confirmed): dossier tier A0 (chart, natal grounding, `prepare()` → Plan) runs synchronously (ONB_02 §4), and generation of **`core_identity`** starts at once. Dossier A1 + B build in the background. Measured on Radul's chart: corpus load 0.16 s, `ground` + `route` < 0.01 s. |
| Read-ahead | `read_ahead = 1` | When the client reports `opened` for section *i*, the server ensures section *i+1* (next non-empty in order) is generating. Never more than 1 ahead outside complete mode. |
| Order guard (anonymous) | — | A section *k* (index in the outline) may start only if *k* ≤ `furthest_index + read_ahead`, where `furthest_index` is the highest opened index (−1 before anything is opened); otherwise `409 read_ahead_limit`. `core_identity` is always allowed. Signed-in users may jump via contents. A jump generates the target with whatever written context exists (`core_identity` is always generated first). |
| Complete | `complete_after_opened = 3` | When the reader opens their 3rd section, **or** calls `POST …/complete` (read all, export, PDF), every remaining allowed section is generated in render order, 3 in parallel, each with `core_identity` + nearest preceding ready section as context. |
| Anonymous ceiling | `anon_max_movement = 1` | Anonymous users can generate Part One only. A Movement-2 section returns `403 account_required`. **Decision for Radul:** `0` = `core_identity` only; `1` = Part One (recommended). |
| Language | — | TR is always generated; EN only when an EN request arrives (translation is lazy). |
| Limits | 1 self profile per anonymous user; 3 anonymous onboardings per install per 24 h; per-IP cap | `429 rate_limited` with `retry_after`. Supabase's default anonymous IP limit (30/h) also applies; add Turnstile or attestation before public launch. |
| Budget | existing `install_guard` | Every call goes through the shared guard (§10). |

**Latency targets** (measured in Phase 3):
- `core_identity` ready **≤ 30 s p50 / 45 s p90** from profile creation. The FE fills this time with the chart reveal and the Big Three (deterministic, instant).
- Section *i+1* ready before the reader finishes section *i*: p90 draft + finalize ≤ 45 s, against 1.5–3 min of reading per section.

## 6. API (extends FE_02 §7.2 and the §4 job pattern; add to `openapi.yaml`, zod, mock)

### 6.1 Anonymous session (Supabase)

- Use **Supabase anonymous sign-in**. The JWT carries `is_anonymous = true`, and the same auth middleware and RLS apply.
- Converting the account keeps the **same user id**: email via `updateUser({ email })` with verification, Google via `linkIdentity()`, Apple later.
- **If the email already belongs to an account:** sign in to it and call `POST /me/claim-anonymous` (§6.3). That reassigns the anonymous profile, progress and feedback. If the self profile has the same `chart_key`, keep the existing one and drop the duplicate.
- The current private-preview restriction (owner email only) stays on the local server. Anonymous mode goes behind config `allow_anonymous`.

### 6.2 Endpoints

```text
POST /v1/profiles                          (anonymous allowed: self profile only, max 1)
     → 201 BirthProfile  + starts core_identity (§5)

GET  /v1/profiles/{id}/natal-reading/outline?lang=tr|en
     → 200 ReadingOutline                  (deterministic; from reading-plan)

GET  /v1/profiles/{id}/natal-reading/sections/{key}?lang=
     → 200 NatalSection | 202 { job } | 403 account_required | 409 read_ahead_limit | 404
       (first GET starts generation, FE_02 §4.1; repeated GETs join the same job;
        ?retry=true restarts a failed one)

POST /v1/profiles/{id}/natal-reading/progress   { key, event: "opened" | "finished" }
     → 204                                 (drives read-ahead and complete, §5)

POST /v1/profiles/{id}/natal-reading/complete
     → 202 { job }                         (explicit read-all / export)

GET  /v1/profiles/{id}/natal-reading?lang=  (existing contract unchanged)
     → 200 NatalReading when every allowed section is ready, else 202 { job }
       (the job = complete mode)

POST /v1/feedback/reading                   (§7)
POST /v1/me/claim-anonymous                 { anonymous_access_token } → 200 { moved: {...} }
```

```ts
interface ReadingOutline {
  profile_id: string; chart_key: string; lang: Lang;
  title: string;                                   // l4_render._DOC_TITLE
  parts: { movement: 1 | 2; title: string }[];     // MOVEMENT_TITLES
  sections: {
    key: NatalSection['key']; movement: 1 | 2; house: number | null;
    title: string;                                 // l4_render.section_title
    status: 'not_started' | 'generating' | 'ready' | 'failed';
    access: 'open' | 'account_required';
  }[];                                             // non-empty sections only, render order
  big_three: { sun: Sign; moon: Sign; rising: Sign };   // from the chart, no LLM
  accuracy: { score: number; n: number } | null;
}
```

`NatalSection` is unchanged (FE_02 §7.2). `principle_ids`, `draft_tr`, `usage` and `context_keys` are **never** returned to the app.

### 6.5 Personal Astrologist

- **Ready sections feed the PA.** Each section that becomes ready is added to the dossier `readings` index and to `pa_dossier.prose` (ONB_02 §5.1), so the PA can quote it (`natal_section`).
- **The PA never generates a section.** It never calls the section endpoint and never creates a section job (PA rule D4). A question about an unread section is answered from grounded records only.

### 6.3 Job stages

Section jobs reuse `Job`, with `kind: 'natal_section'` (new value) and stages `reading` (draft), `synthesis` (finalize), `validate`, and `translation` when EN. All already have FE labels (FE_02 §4.3).

### 6.4 Migration of existing routes

- `GET /natal-reading` for any profile (My Charts included) now runs complete mode on the progressive pipeline. Its response shape is unchanged.
- Existing `reading:{chart_key}` records from the batch path stay valid and are served as-is.

## 7. "Seni doğru okuduk mu?" — accuracy capture

**Request:** `POST /v1/feedback/reading`

```json
{
  "profile_id": "…",
  "target": { "type": "reading" | "section" | "big_three", "key": "core_identity" },
  "rating": "spot_on" | "partly" | "not_me",
  "comment": "optional, ≤ 500 chars"
}
```

**Response:** `200 { "accuracy": { "score": 0.84, "n": 5 } }`. The score is (2 × spot_on + 1 × partly) ÷ (2 × n).

**What's stored:** the rating, the chart_key, the sections the user had opened at that moment (from progress), and the **union of their `principle_ids`**. This makes every rating an evaluation signal tied to the grounded principles behind the text read. The predictive orchestrator dropped its eval stage, so this is the only real-user quality signal we will have.

Upsert per (profile, target): a user re-rating replaces their earlier answer. Comments are personal data: include them in `POST /me/export` and erase them on `DELETE /me`.

**FE behaviour (for the FE agent; backend only needs the endpoint):**
1. After the reader finishes `core_identity`, a sticky **"Seni doğru okuduk mu?"** / "Did we read you right?" button appears.
2. It opens a sheet with three choices — **Tam ben** / **Kısmen** / **Bana uymadı** — and an optional comment.
3. Submitting posts the feedback, then routes to the **email step**: "Okumanı kaydetmek ve kaldığın yerden devam etmek için e-postanı ekle" / "Add your email to save your reading and continue where you left off".
4. **"Şimdilik okumaya devam et"** / "Keep reading for now" returns to Part One.
5. At the end of Part One the same button gates Part Two (`account_required`).

## 8. Cost (measured, not estimated)

**Measured** from `frontend/.local-data/ai-budget.sqlite`: the first live full natal reading (calls 1–52).
- Gemini 3.7 Flash intro prices: $0.75 input / $3.75 output per 1M tokens.
- The guard charges cached input as uncached, so these are upper bounds.

| Stage (batch L4 today) | Calls | Cost |
| --- | --- | --- |
| Section drafts | 17 | $0.129 (≈ $0.0076 each) |
| Synthesis (each call carries all other drafts) | 17 | $0.171 (≈ $0.010 each) |
| EN translation (gpt-6-luna) | 18 | $0.006 |
| **Full reading** | 52 | **$0.306** |

**Progressive estimate:** a draft at ≈ $0.0076 plus a finalize at ≈ $0.006–0.009 (smaller context than batch synthesis) gives **≈ $0.014–0.017 per section**, Turkish only.

| What the reader does | Sections generated | Cost (2026 prices) | 2027 (Flash ×2) |
| --- | --- | --- | --- |
| Reads chapter 1 only, then leaves | `core_identity` + 1 read-ahead | ≈ $0.03 | ≈ $0.06 |
| Reads Part One (the onboarding reading) | 5 (two are short notes) | ≈ $0.06–0.08 | ≈ $0.12–0.16 |
| Reads everything | 17 | ≈ $0.24–0.29 | ≈ $0.48–0.58 |

So the full progressive reading costs no more than today's batch reading. Every reader who stops early saves the rest.

**Phase 3 experiment (flag `progressive_single_pass`, off by default):** merge draft and finalize into one call fed `own(S)` + `elsewhere(S)` + written context, which roughly halves cost. Ship it only if Radul and Claude judge 3 side-by-side charts as equal in quality.

## 9. Invariants and acceptance

L4 §7 invariants 1–7 hold unchanged. The progressive path adds 8–15:

| # | Check |
|---|---|
| P1 | `prepare()` is deterministic: same chart and corpus → byte-identical Plan (run twice, compare). |
| P2 | Every ready section passes `validate(…, langs=('tr',))`, and `('en',)` after translation: non-empty, no forbidden tokens, `principle_ids` ⊆ routed ids. |
| P3 | **Ownership:** for Radul's chart and the 3 fixture charts, every routed id has exactly one owner, chosen by §2.1 from primary reasons only. House-type facts are owned by their house section; sign and character facts by Part One. `sun_house` and `moon_house` have empty `elsewhere`. Regression on Radul's chart: `core_identity` owns ≥ 20 ids and `inner_drives` ≥ 10. |
| P4 | **Immutability:** a ready section's text is identical across 3 later reads, and after generating every other section. |
| P5 | **Pay-per-read:** with a fake generator, creating a profile then idling makes **exactly 2** generator calls (draft + finalize of `core_identity`). `opened(core_identity)` adds exactly 2 more (`sun_house`). |
| P6 | **Order guard:** anonymous `GET` of a section 3 positions ahead returns `409 read_ahead_limit`, and a Movement-2 section returns `403 account_required`. Neither creates a job or calls the generator. |
| P7 | **Complete mode:** opening the 3rd section generates all remaining allowed sections, each exactly once. Concurrent `GET`s join one job; no duplicates. |
| P8 | **Lazy EN:** TR-only usage makes zero translation calls. The first EN request translates only the requested section. |
| P9 | **Claim:** anonymous → email conversion keeps `profile_id`, sections, progress and feedback. Conversion to an existing account moves them, and a same-`chart_key` duplicate is not regenerated. |
| P10 | **No leaks:** the app API never returns `principle_ids`, drafts, usage or prompts. Logs contain no birth data or reading text, matching the existing bridge rule. |
| P11 | **Live (Phase 3):** 3 fixture charts (1988-12-28, 1984-06-12, 1979-03-30). Report: `core_identity` latency p50/p90; per-section cost from real `usage`; total for Part One and full; and the TR text of `core_identity` progressive vs batch side by side for review. |
| P12 | `npm run check` passes: contract, types, zod, fixtures, typecheck, lint, tests. The mock serves outline, sections with 202 → 200 transitions, the 403 and 409 cases, and feedback. |

## 10. Budget guard

`frontend/local-api/budget.py` blocks every call after **2026-10-09** ("Reverify pricing"), and its rates are:
- `gemini-3.7-flash`: (0.75, 3.75). Official, intro price until 31 Dec 2026.
- `gpt-6-luna`: (0.125, 0.50). The official model page now lists $0.10 input / $0.01 cached / $0.50 output, so the guard over-reserves, which is safe.

**Radul decides** whether to extend the date for Phase 3. Phase 3 must stay within the existing $20 cap; expected spend is under $2.

## 11. Phases and gates

| Phase | Scope | Gate |
|---|---|---|
| 0 | Read-only report `ONB_01_00_exploration.md` (may be combined with ONB_02's Phase 0): confirm the signatures used here (`route`, `RoutingResult`, `LLMGenerator`, `validate`, `section_title`, `Store`, `ReadingJobs`); Supabase anonymous sign-in availability in the project; how `chart_key` is derived; current reading cache records. List any mismatch with this spec. | **Stop** |
| 1 | `l4_progressive.py`, the new prompt, the `validate(langs=)` extension, unit tests with a fake generator (P1–P5, P8). No paid calls. | — |
| 2 | Bridge (`reading_section_bridge.py`: ops `prepare`, `section`, `translate`), local-api records, endpoints, policy (§5), contract + mock (P6, P7, P10, P12). | **Stop** |
| 3 | Bounded live run (P11) under the budget guard, plus the single-pass experiment on the same 3 charts. | **Stop**: Radul and Claude review the texts |
| 4 | Anonymous auth + conversion + claim (P9), behind `allow_anonymous`. | **Stop** |

## 12. Out of scope

- FE screens. The FE agent gets an updated FE_ONB after Phase 2: progressive scroll, the rating button, the email step, and dropping the theme picker and approximate time.
- Payments.
- Approximate or unknown birth time.
- Changes to the L4 section model, routing or grounding.
