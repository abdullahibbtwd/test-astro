# PA 04: engine, stream, CLI, bridge (`pa_engine.py`, `run_ask.py`, `ask_bridge.py`)

*Status: **partial**. The interface, event order, audit, CLI and acceptance are fixed. Calls into the existing layers
are wired to the **real signatures from the Phase 0 report** (§10), not assumed ones.*

## 1. Responsibilities

| PA engine (this spec) | API layer (outside PA; context for whoever builds it) |
|---|---|
| One turn: plan → tools → compose → validate → stream events → final message + audit | Threads and messages store (FE_02 §7.10), thread title = the first question cut to 60 characters at a word boundary |
| Prewarm per profile | Daily quota (`me.ask_quota`), counted when the engine returns `final` (PA_00 O5) |
| Reports usage and cost per model call | Assigns `message_id`, emits FE `done` with the quota, stores the audit next to the message |
| Never stores user data itself (except CLI run folders) | Rejects a second concurrent turn in the same thread with `409 busy` (FX1.2); Stop aborts the turn; feedback storage; erasure on thread or account delete |

## 2. Engine interface

```python
def answer_turn(req: TurnRequest, cancel: CancelToken) -> Iterator[Event]: ...
def prewarm(subject: Subject) -> PrewarmReport: ...
```

```json
{
  "thread_id": "uuid",
  "subject":  {"profile_id": "…", "label": "…", "relation": "self", "is_self": true,
               "birth": {"date": "1979-03-30", "time": "06:30", "place": {"name": "Sofia", "lat": 42.70, "lon": 23.32, "tz": "Europe/Sofia"}},
               "effective_tz": "Europe/Sofia"},
  "profiles": [{"profile_id": "…", "label": "Ayşe", "relation": "partner", "birth": {"…": "…"}}],
  "compatibilities": [{"compatibility_id": "…", "profile_a_id": "…", "profile_b_id": "…", "type": "love", "family_relation": null}],
  "text": "…",
  "context": {"date": "2026-10-12"},
  "lang": "tr",
  "today": "2026-10-05",
  "history": [{"role": "user", "text": "…"}, {"role": "assistant", "text": "…", "calls": [{"tool": "span", "args": {}}]}],
  "llm_route": {}
}
```

- `profiles` = the user's other saved profiles, including the self profile when the subject is someone else; the engine
  assigns handles `p1…pN` in the given order (PA_02 §1).
- `history` = the last 8 messages as stored; assistant `calls` come from the stored audits.
- `llm_route` is opaque to PA and passed to `llm_client` as is (which OpenAI key to use: the platform's, or the user's
  own for OpenAI sign-in users). The model itself is fixed by PA config (PA_00 P5).
- Birth data is used in memory to compute or find charts. PA never logs it and never writes it outside the layers'
  existing per-chart caches.

### 2.1 Turn sequence

```
status(understanding)
plan (PA_02)  ── template intent ─────────────────────────────► deltas ─► links ─► final
   │
status(computing, sources)
tools (PA_01), forced calls first, independent calls in parallel
   │ ── needs_input / nothing usable ─────────────────────────► template deltas ─► links ─► final
status(writing, sources)
compose → validate → [repair → validate] → [drop | fallback] (PA_03)
deltas ─► cards ─► links ─► final
```

The cancel token is checked between stages and between delta chunks. On cancel the engine stops emitting; the API marks
the message `interrupted` (FE_09 §2.2). The audit records the stage reached.

## 3. Events

The engine yields these; the API layer forwards `status`, `delta`, `card`, `link`, `error` to the SSE stream verbatim and
turns `final` into the stored message plus the FE `done` event.

| Event | Data | Notes |
|---|---|---|
| `status` | `{phase, sources: [{kind, label}]}` | `kind` ⊆ FE_09 `AskSourceKind`; distinct kinds of the plan's calls; `astro_basics` adds none |
| `delta` | `{text}` | the validated text in chunks of about 8 words; segments and paragraph breaks preserved exactly |
| `card` | `AskCard` | FE_09 §4.3 shape (PA_01 §6) |
| `link` | `{label, route}` | PA_01 §6 table |
| `final` | `{message: {text, cards, links, status: "complete", answer_kind: "composed" \| "template" \| "fallback", lang}, audit}` | `text` = the concatenated deltas |
| `error` | FE_02 `Problem` | `upstream_unavailable` (provider down after `llm_client` retries), `generation_failed` (turn timeout), `internal` |

Source labels (the app may override them with chrome, FE_09 §2.2):

| kind | TR | EN |
|---|---|---|
| chart | Haritanıza bakılıyor… | Looking at your chart… |
| natal_reading | Doğum haritası yorumunuz okunuyor… | Reading your birth chart report… |
| forecast | Öngörünüz kontrol ediliyor… | Checking your forecast… |
| calendar | Takviminiz kontrol ediliyor… | Checking your calendar… |
| best_days | En iyi günleriniz kontrol ediliyor… | Checking your best days… |
| acg | Haritanızın dünya üzerindeki izlerine bakılıyor… | Looking at your map… |
| compatibility | Uyumunuz inceleniyor… | Looking at your compatibility… |

An invalid composer answer is **never** an `error`: it goes to repair, drop or fallback (PA_03 §6).

## 4. Audit (`pa-audit-1`, one per assistant message; internal, never returned to the app)

```json
{
  "schema_version": "pa-audit-1",
  "chart_key": "…", "other_chart_keys": [],
  "lang": "tr", "today": "2026-10-05", "tz": "Europe/Sofia",
  "plan": {}, "plan_drops": [],
  "calls": [{"call_id": "c1", "tool": "span", "args_resolved": {}, "forced": false, "status": "ok", "cache_hit": true, "ms": 120}],
  "evidence_ids": {"facts": [], "records": [], "items": [], "prose": []},
  "answer_kind": "composed", "template_id": null,
  "validation": [{"attempt": 1, "violations": [{"rule": "PV4", "segment": 2, "span": "…"}]}, {"attempt": 2, "violations": []}],
  "repair": true, "dropped_segments": [], "fallback": false, "notes": [],
  "models": {"planner": "…", "composer": "…"},
  "usage": [{"step": "planner", "input_tokens": 0, "cached_tokens": 0, "output_tokens": 0, "cost_usd_est": 0.0}],
  "latency_ms": {"plan": 0, "tools": 0, "compose": 0, "validate": 0, "first_delta": 0, "total": 0},
  "versions": {"dossier": "pa-dossier-1", "prompt_v": "…", "lexicon_v": "…", "templates_v": "…", "corpus_sha256": "…"}
}
```

No question text, no answer text (both are in the message), no birth data, no labels of people. Staff can see audits
only through the FE_02 §6.4 debug flag.

## 5. CLI (`run_ask.py`)

```
python run_ask.py [birth flags as run.py] [--current-location TEXT] [--label TEXT] [--relation REL]
                  [--others-json FILE]          # other profiles: [{label, relation, birth flags}]
                  [--lang tr|en] [--today YYYY-MM-DD] [--context JSON]
                  [--question TEXT]             # one turn; omitted → interactive
                  [--plan-only]                 # planner call only: prints the validated plan and resolved dates
                  [--dry-run --plan-json FILE]  # scripted plan, tools run, composer prompt written; zero model calls
                  [--fake-llm FIXTURE]          # scripted planner and composer replies
                  [--prewarm]
                  [--planner-model M] [--model M]
```

- Interactive commands: `/context {json}`, `/new` (new thread), `/audit` (print the last audit), `/quit`.
- Output: the answer text, the cards (pretty-printed), the links.
- Run folder `ask_run/YYYYMMDD-HHMMSS_<3char>/` with the existing helper: `transcript.jsonl` (events per turn),
  `audit_<n>.json`, `dry_run_prompt_<n>.json` when applicable, `manifest.json` (`layer: "astrologist"`). Add `ask_run/`
  to `.gitignore` in the same commit (it holds real birth data and questions).

## 6. Bridge (`ask_bridge.py`)

For the API layer's process bridge (the `*_bridge.py` pattern; Phase 0 item 11 aligns the details with the existing
bridges, and their conventions win if they differ).

- **stdin:** one JSON object: `{"op": "turn", "request": TurnRequest}` or `{"op": "prewarm", "subject": Subject}`.
- **stdout:** JSON lines only: `{"event": "<name>", "data": {…}}` for each §3 event (prewarm: one
  `{"event": "prewarm", "data": PrewarmReport}`). Flush after each line.
- **stderr:** operational logs without birth data, labels, question or answer text.
- **Exit:** 0 after `final`, `error` or `prewarm`. SIGTERM = cancel: stop at the next check, no `final`, exit 130.

## 7. Prewarm

`prewarm(subject)`: build the dossier (PA_01 §2) and make sure the calendar (events, scores, periods), Best Days and
ACG map caches exist for the subject's chart and effective timezone. Deterministic, no model calls, idempotent.
Recommended triggers for the API: creating a self profile, and `POST /ask/threads` for a profile. The report gives
per-step `cache_hit` and timings.

## 8. Models, limits, cost

| Item | Value |
|---|---|
| Model calls per turn | planner 1 (+1 retry on invalid JSON), composer 1, repair 1 → **≤ 4**; template turns use the planner only |
| Model | `gpt-6-luna` for planner, composer and repair (PA_00 P5); reasoning effort `none` for all three by default; Structured Outputs (strict) with the PA_02 §2 and PA_03 §5.1 schemas. Put the stable system rules first in every prompt so OpenAI's automatic prompt caching applies (cached input is a tenth of the input price). |
| Prompt budgets | planner ≤ 3k tokens; composer ≤ 14k tokens (rules ≤ 2k, stable for provider caching; evidence ≤ 9k; history ≤ 2k) |
| Timeouts | tool 45 s (PA_01 §7); model call per `llm_client` defaults; whole turn `PA_TURN_TIMEOUT_S = 90` |
| Question length | 1–1,000 characters (the API validates; the engine cuts defensively) |
| Cost target | ≤ US$0.003 per composed answer with `gpt-6-luna` (estimate: planner ≈ US$0.0004, composer ≈ US$0.0015, a repair when needed ≈ US$0.0015), measured at the Phase 5 gate |
| Spending | every call's usage goes into the audit and into the platform's spending ledger under feature `ask` (Phase 0 item 11) |

Tests use the fake `llm_client` only. Live runs need Radul's approval of a written estimate (PA_00 §5).

## 9. Evaluation

**`pa_eval.py`** `--golden fixtures/golden_questions.json [--fake-llm FIXTURE | --live] --today YYYY-MM-DD` →
`eval/<run_id>/eval_report.md` + `results.jsonl`. Per question: intent, calls and statuses, answer kind, violations per
attempt, repair, drop, fallback, latency, usage, cost. Summary: the targets below.

**Golden set** (reference chart 1979-03-30 06:30 Sofia, current location Sofia; `--today` set inside the fixture cache
horizons): 60 TR + 20 EN questions. It includes the 6 FE_09 starter prompts in both languages, ≥ 4 questions per astro
intent, 3 follow-up chains of 3 turns, the other profiles 1988-12-28 (partner) and 1984-06-12 (colleague), the places
İzmir, London, Berlin, Antwerp and "Instanbul", and 20 adversarial questions (prompt injection, degrees and techniques
requested, a death prediction, a medical question, a celebrity, typed birth data, lottery numbers, a crisis message).

**Gate targets (live run):**

| Metric | Target |
|---|---|
| Validator pass at the first attempt | ≥ 85% of composed answers |
| Fallback | ≤ 3% of composed answers |
| Shipped text violating PV4 or PV8 | 0 (by construction; the eval re-validates shipped text to prove it) |
| Adversarial routing | 20/20 in the right class; crisis and harm exact |
| Time to first delta, warm caches | p50 ≤ 10 s, p95 ≤ 25 s |
| Mean cost per composed answer | ≤ US$0.003 |
| Radul's reading | every TR answer read; comments go back as prompt or lexicon changes, not code workarounds |

**`pa_feedback_report.py`** (staff tool): joins thumbs-down feedback (FE_09 §2.2 reasons) with the audits from an API
store export and lists, per item, the reason, plan, evidence ids and validation history. Input format confirmed with
the API layer.

## 10. ⏳ Wiring table (fill from the Phase 0 report before implementing)

| Need | Existing call | Real signature |
|---|---|---|
| chart | `compute_chart(...)` | ⏳ |
| natal grounding per chart | producer of `personal_principles.json` | ⏳ |
| L4 routing + record renderer + 2:1 quota | `Interpretation_layer` routing / prompt builder | ⏳ |
| natal reading lookup | `l4_output.json` path for a chart_key | ⏳ |
| calendar caches + views | `run_calendar.py` stages / loaders | ⏳ |
| CAL_03 unit record sets | calendar text unit selector | ⏳ |
| Best Days + factor grounding | `best_days.py`, `best_days_factors.json` | ⏳ |
| predictive reading lookup | `reading_<horizon>_<lens>_<date>.json` locator | ⏳ |
| ACG gazetteer search | gazetteer / destinations search | ⏳ |
| ACG locate + goal scores + `ground_acg` (no reading) | `run_acg.py` stages | ⏳ |
| ACG recommender ranking | `acg_recommend.py` dry-run path | ⏳ |
| synastry S1–S2 | `synastry_run.py` stages | ⏳ |
| model calls | `llm_client` JSON call, roles, routing, usage | ⏳ |
| forbidden lists, detox, mask list | validator framework | ⏳ |
| labels | TR/EN catalogue | ⏳ |
| run folder + manifest | helpers | ⏳ |
| spending ledger | `budget.py` contract | ⏳ |
| bridge conventions | existing `*_bridge.py` | ⏳ |

The coding agent fills this table in a short note and sends it to Radul **before** writing `pa_engine.py`.

## 11. Privacy and security

- No birth data, people's labels, question or answer text in any log or in the audit. The CLI run folder is the only
  place PA writes them, and it is gitignored.
- Thread data (messages and audits) is deleted with the thread or the account (FE_02 §7.1 KVKK/GDPR); PA keeps no copy.
- The question is data: it reaches the models only inside delimited blocks; plans are schema-validated; tools take only
  enums, structured time expressions, handles and a place string that goes to the gazetteer search. No URL fetching,
  no shell, no free-form queries.
- Per-thread memory only (PA_00 P2): nothing derived from a thread is reused in another thread.

## 12. Acceptance (`test_pa_engine.py` + gate)

| # | Check |
|---|---|
| E1 | Event order for a composed answer: `status(understanding)` → `status(computing)` → `status(writing)` → `delta`+ → `card`* → `link`* → `final`. Template turns skip `computing` and `writing`. |
| E2 | Nothing is streamed before validation passes: with a scripted invalid-then-valid composer reply, no delta carries text from the invalid reply. |
| E3 | `final.message.text` equals the concatenated deltas; `final` cards and links equal the emitted ones. |
| E4 | Cancel during tools → no delta, no `final`, the audit names the stage. Cancel during deltas → emission stops. |
| E5 | A provider error after retries → one `error` event (`upstream_unavailable`), no `final`. A turn over 90 s → `generation_failed`. |
| E6 | Model calls per turn ≤ 4; a template turn makes exactly 1 (the planner). |
| E7 | `--dry-run` makes zero model calls; `--fake-llm` gives a byte-identical transcript over two runs. |
| E8 | Bridge: stdin → JSONL round trip for `turn` and `prewarm`; stdout holds only event lines; SIGTERM → exit 130 without `final`. |
| E9 | Privacy: a turn run with DEBUG logging; a search of logs and the audit for the birth date, time, place name, people's labels and the question text finds nothing. |
| E10 | `prewarm` is idempotent: the second call is all cache hits and makes zero model calls. |
| E11 | Every `card` validates against `AskCard` in `openapi.yaml`; every `status.sources[].kind` ∈ `AskSourceKind`. |
| E12 | The existing test suites still pass, plus all PA tests. |
| Gate | The live golden run meets §9's targets; Radul reads the TR answers. |
