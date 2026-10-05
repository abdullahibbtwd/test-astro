# Personal Astrologist: spec index

*Spec set v1, 2026-10-05. Backend only. This is the backend behind the **Ask Astrology** screen (FE_09). It implements
the FE_09 / FE_02 §7.10 contract **unchanged**: same endpoints, same stream events, same cards. Read this file first,
then the specs in order.*

## 1. What gets built

A chat engine that answers a user's questions about **one person's chart**, using only that person's grounded
principles and computed data from every existing layer: natal, forecasts, calendar, Best Days, astrocartography and
compatibility. It explains computed results. It never computes positions, never invents them, and never says anything
astrological that it can't trace to a record or a computed fact (brief §13).

```
question + context ids
   │
   ▼
PLANNER (gpt-6-luna, JSON, closed enums) ──► plan: intent + ≤ 4 tool calls        PA_02
   │
   ▼
EXECUTOR (deterministic, no model) ──► evidence packs: facts, grounded records,     PA_01
   │                                    already-validated texts, items, cards, links
   ▼
COMPOSER (answer model, JSON segments with traces) ──► VALIDATOR ──► repair once    PA_03
   │                                                       │
   │                                    fails twice ──► segment drop or fallback
   ▼
ENGINE ──► status · delta · card · link · final  (FE_09 §4.2 via the API layer)      PA_04
```

**"All grounded rules for the person"** is the **personal dossier** (PA_01 §2): a per-chart cache holding every natal
principle kept for that chart, its masked chart facts and an index from topics to records. Time, place and
relationship grounding depends on the question, so the tools ground it on demand by reusing each layer's own grounding
(they never re-implement it). The model sees only what the tools return for this turn, never the whole corpus.

## 2. Files

| # | File | Scope |
|---|---|---|
| 0 | `PA_00_INDEX.md` | decisions, layout, phases, open decisions, Phase 0 report |
| 1 | `PA_01_DOSSIER_TOOLS_SPEC.md` | personal dossier, evidence pack, the 11 tools, context → forced calls, cards and links, caching |
| 2 | `PA_02_PLANNER_SPEC.md` | intents, plan schema, enums, dates, goals, places, people, scope policy, history window |
| 3 | `PA_03_ANSWER_VALIDATOR_SPEC.md` | composer prompt, answer JSON, lengths, voice, validator PV1–PV14, repair, fallback, fixed templates |
| 4 | `PA_04_ENGINE_SPEC.md` | engine interface, event stream, persistence and audit, CLI, bridge, prewarm, cost, privacy, eval harness (**partial**: wired after Phase 0) |

## 3. Locked decisions

### 3.1 Radul, 2026-10-05

| # | Decision |
|---|---|
| P1 | Personal Astrologist **is the backend of Ask Astrology** (FE_09). The FE contract stays as it is. A user-facing rename is a chrome string only (O1). |
| P2 | **Memory is per thread only.** The engine sees the current thread's recent messages; nothing about the user is stored across threads. |
| P3 | **Scope v1 = everything:** natal, forecasts, calendar, Best Days, ACG places and recommender, compatibility. |
| P4 | **Voice:** a neutral, warm, professional astrologer. No name, no character. |
| P5 | **Model, for now: OpenAI's cheapest and fastest, `gpt-6-luna`**, for every PA model call (planner, composer, repair), for all users. Reasoning effort `none`; Structured Outputs with the PA_02 §2 and PA_03 §5.1 JSON Schemas (strict). The model id and effort are config in `pa_constants.py` (`PA_MODEL`, `PA_PLANNER_EFFORT`, `PA_COMPOSER_EFFORT`), so switching later is a config change. This applies to PA only; the other layers keep their models. List price at the time of writing: US$0.10 input, US$0.01 cached input, US$0.50 output per 1M tokens. |

### 3.2 Domain and architecture decisions (this set)

| # | Decision |
|---|---|
| D1 | **Deterministic first, model last.** Planning is the only model step before evidence exists; every tool is deterministic; the answer model only phrases evidence. |
| D2 | **Planner + executor, not native tool calling.** One planner call returns a JSON plan with closed-enum tools and arguments; the executor runs it. It works on any provider behind `llm_client` (OpenAI `gpt-6-luna` for now, P5), so the model can change without code changes, and it keeps each message to ≤ 4 model calls. |
| D3 | **Every astrological sentence is traced** to a record id, a computed fact id, a data item or an already-validated text from this turn's evidence (PA_03 PV2–PV4). Sentences without astrological content (greetings, coverage notes, clarifying questions) need no trace. |
| D4 | **The chat never starts another layer's paid generation.** It may run deterministic stages (chart, natal grounding, calendar events and scores, Best Days, ACG locate / goal scores / grounding, synastry compute and grounding). It reuses readings and texts that are already cached, and otherwise works from the grounded records directly. |
| D5 | **Tradition rules follow the layer the evidence comes from.** Natal: both traditions, modern primary, classical as enrichment, with the L4 2:1 modern:classical quota inside the evidence cap, all under the tradition mask. Calendar, forecasts, Best Days: modern only (CAL_00 D3). ACG: exactly what `ground_acg` keeps. Synastry: S2's kept records under the lens. Classical `time_lord` and every `out_of_scope` record stay excluded. |
| D6 | **Validate, then stream.** The answer is generated in full, validated, repaired once if needed, and only then streamed as `delta` events. Nothing unvalidated reaches the user. |
| D7 | **Fixed templates instead of model text** for declines, safety, small talk, clarifications and fallback (PA_03 §7). They cost nothing and can't drift. |
| D8 | **A thread is bound to one subject profile.** Other people enter only as saved profiles (My Charts) through compatibility. The engine never accepts birth data typed into the chat. |
| D9 | **Answers are in the request `lang`** (TR or EN), written directly in that language. No draft-then-translate step in chat. |
| D10 | **Horizons are the existing ones:** day questions today − 7 … today + 365 (FE_02 §7.3); periods and transits the 12 rolling calendar months; Best Days 90 days. Outside → a coverage note, never an extrapolation. |
| D11 | **Houses are natal Placidus** in all facts (CAL_00 D7). The model never sees house numbers, degrees, orbs or distances: facts reach it as labels with life-area names (PA_01 §3.2). Numbers live only in cards. |
| D12 | **Cards and links are built deterministically** from evidence in the FE_02 shapes. The model only picks which candidates to show; it can't create one. |

## 4. Target layout

```
astrologist/
    pa_constants.py         caps, budgets, horizons, history window, model roles, timeouts
    pa_dossier.py           PA_01 §2
    pa_tools.py             PA_01 §4 (executors)
    pa_cards.py             PA_01 §6 (AskCard + link builders, FE_02 mapping rules)
    pa_planner.py           PA_02
    pa_compose.py           PA_03 §2–4
    pa_validate.py          PA_03 §5
    pa_lexicon.py           PA_03 §5.1 (TR/EN astro lexicon, Turkish-aware matching)
    pa_templates.json       PA_03 §7 (TR/EN fixed texts)
    pa_engine.py            PA_04 §2
    pa_eval.py              PA_04 §9
    fixtures/               scripted plans and answers, golden questions, adversarial questions
    test_pa_dossier.py  test_pa_tools.py  test_pa_cards.py  test_pa_planner.py
    test_pa_compose.py  test_pa_validate.py  test_pa_engine.py
run_ask.py                  PA_04 §5 (CLI)
ask_bridge.py               PA_04 §6 (JSONL bridge for the API layer)
ask_run/                    run folders (gitignored)
```

The dossier cache goes under the existing per-chart cache root if Phase 0 finds one shared by the layers
(`…/_cache/<chart_key>/astrologist/`); otherwise `astrologist_cache/<chart_key>/` (gitignored). Propose it in the
report; don't decide silently.

## 5. Phases and gates

| Phase | Deliverable | Gate |
|---|---|---|
| **0: Exploration** | `astrologist/PA_EXPLORATION_REPORT.md` (§7), no code | Radul reviews it and the wiring table in PA_04 §10 |
| 1: Dossier + natal tools | PA_01 §2–3, tools `chart_facts`, `natal_topics`, `natal_section` | PA_01 tests D1–D6 on the 3 fixture charts |
| 2: Other tools + cards | the other 8 tools, `pa_cards.py`, link table | PA_01 tests T1–T13; every card validates against `openapi.yaml` |
| 3: Planner | PA_02 with a fake `llm_client`; then one live classification run | PA_02 tests; live run: intent ≥ 90%, adversarial 20/20 (cost estimate approved first) |
| 4: Composer + validator | PA_03, templates | PV unit tests (one positive and one negative per rule); repair and fallback paths tested with scripted answers |
| 5: Engine + CLI + bridge | PA_04 | end-to-end on the 1979-03-30 06:30 Sofia chart with a fake model; then one live golden-set run (cost estimate approved first); Radul reads the TR answers |

**No paid generation without approval.** Every test runs against a fake `llm_client` with scripted plans and answers.
A live run happens only at the Phase 3 and Phase 5 gates, after Radul approves a written cost estimate, and its spend is
recorded in the report.

Each phase ends with a short report: what was built, test counts, deviations, contract questions. **Don't adapt
silently.**

## 6. Open decisions for Radul (defaults apply until answered)

| # | Question | Default |
|---|---|---|
| O1 | Rename the screen to "Personal Astrologist / Kişisel Astrolog"? | Chrome rename only, through the FE team; the flag stays `askAstrology`. No contract change. |
| O2 | Turkish register. Readings and calendar texts use **siz** ("haritanızdaki"); the FE_09 disclaimer uses **sen** ("senin hesaplanmış haritana"). | Answers and templates use **siz**, matching the readings. Recommend aligning the FE_09 disclaimer. Native review either way. |
| O3 | Retrieval vs the whole natal set in every prompt. | **Retrieval** (PA_01 §2.3). Revisit if Phase 0 shows a chart's kept natal set is under ~25k tokens. |
| O4 | Crisis template contact. | It names **112** (emergency number in Turkey and the EU) and suggests talking to someone trusted or a professional. No helpline numbers until Radul supplies vetted ones. |
| O5 | Does a template answer (decline, small talk, clarification) count against the daily quota? | Yes: every completed message counts (the API decides; PA reports `answer_kind`). |
| O6 | Questions about the past beyond 7 days ("why was last year hard?"). | Out of scope in v1, with a template. A past-transit tool is a fast-follow. |
| O7 | ~~Models~~ | **Answered 2026-10-05:** see P5. If the Phase 5 gate shows a first-pass validator rate below 85%, the first lever is `PA_COMPOSER_EFFORT = low` (still `gpt-6-luna`); a model change is Radul's call. |
| O8 | History window. | The last **8** messages of the thread (PA_02 §6). |

## 7. Phase 0: exploration report

Answer with file:line references and short excerpts. No feature code.

1. **Natal grounding per chart.** The producer of `personal_principles.json`: function, signature, output path, and the
   schema (paste 3 full bundles with their records). Confirm it runs **without any model call** and report its
   runtime. Record counts per factor type and per tradition for the 3 fixture charts, and the token size of each
   chart's full kept set rendered as the L4 prompt renders it (for O3).
2. **L4 routing.** The module and function that assign factor bundles to the 17 section keys (FE_02 `NatalSection.key`),
   the function that renders a record into prompt text, and where the 2:1 modern:classical quota is applied.
3. `l4_output.json`: confirm `sections[].key`, `text_tr`, `text_en`, `principle_ids`.
4. **Calendar.** Loaders for the per-chart caches (`personal_events.json`, `periods.json`, `day_scores.json`,
   `best_days.json`, `texts_<lang>.json`, collective `<year>.json`); the CAL_03 function that selects the allowed
   record set for a text unit, and whether it can be called without generating text; the label catalogue API; the
   CAL_02 goal tags on transit records; the `best_days_factors.json` grounding lists.
5. **Predictive.** Whether a cached `reading_<horizon>_<lens>_<date>.json` can be found by (chart_key, tz, date, lens),
   and the `ground_forecast` output for a transit episode (keys, `about` type).
6. **ACG.** Entry points for: gazetteer search by text (TR names, fuzzy matching, the "Instanbul" case), locate + goal
   scores + `ground_acg` for one place **without** the reading stage, the per-goal `contributors` (ACG_08 §3), the
   recommender's `--dry-run` ranking. Cold and warm runtimes.
7. **Synastry.** S1–S2 entry points without S3, output file names, how the lens is applied, runtime.
8. **`llm_client`.** Whether it can call OpenAI with model `gpt-6-luna`, `reasoning_effort`, and Structured Outputs
   (strict JSON Schema); how a caller picks the provider and model; how the OpenAI key is chosen (platform key vs a
   user's own key for OpenAI sign-in users); usage reporting including cached input tokens; timeouts and retries; how
   tests fake it. If OpenAI or Structured Outputs support is missing, propose the smallest addition to `llm_client`
   (not a separate client inside PA).
9. **Validator framework.** Where the AV2, AV8, RV4 and CV2 lists live, the detox rewrite function, and any existing
   mask-term list (FE_00 F7, FE_02 AC3) in the backend.
10. **Catalogue.** The Python source of TR/EN labels for bodies, signs, aspects, life-area (house) names, goals,
    activities, bands, grades, tones, transit phases, ACG tiers.
11. **API integration (read-only, if Radul provides the FE repo).** How `local-api/` invokes the Python bridges
    (`*_bridge.py`): process model, stdin/stdout protocol, cancellation, timeouts; the `budget.py` spending-ledger
    contract; and a copy of `openapi.yaml` for card validation. Don't modify anything there.
12. Run-folder and manifest helpers (names), and the per-chart cache root if there is a shared one.
13. Anything in these specs that contradicts the code. **Flag it; don't adapt silently.**
