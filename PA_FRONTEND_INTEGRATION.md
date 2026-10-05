# Personal Astrologist frontend integration — 2026-10-05

Status: frontend/API adapter implemented and tested; live PA answers blocked by incomplete supplied backend.

## Source inspected

- Backend: G:\My Drive\Tech\Astrology app\astrologist
- Specifications: G:\My Drive\Tech\Astrology app\PA
- Frontend working copy: D:\Dev\astrology-app\FE

The supplied folder currently contains dossier, catalogue, context, tools, cards, constants and their tests. It does not contain pa_planner.py, pa_compose.py, pa_validate.py or pa_engine.py. The backend root has no ask_bridge.py. These are required by PA_02–04 to turn a question into a validated answer. No substitute readings or new model implementation were added.

## Implemented

- Authenticated thread create/list/read/delete and assistant feedback routes using the existing private SQLite store.
- PA_04 request mapping: thread subject and effective timezone, other saved profiles, compatibility handles, context IDs, language, local date and last eight messages with assistant tool-call history.
- JSONL subprocess reader with a 90-second timeout, output size limit and cancellation. Operational stderr is drained without logging personal data.
- SSE status/delta/card/link forwarding; final is validated against the emitted content, persisted, and converted into the frontend done event.
- Concurrent turns in one thread return 409 busy. Streaming releases the API mutation lock so Stop/deletion can work.
- Daily quota (default 20; UTC reset displayed in local time) counts only successfully completed turns. Active turns reserve available slots. Failed/interrupted answers do not consume quota.
- Deleting a thread cancels active generation and erases its messages, saved audits and feedback. Account export includes conversations/feedback; account deletion cancels chat before clearing records. Deleted-subject conversations remain readable but cannot accept questions.
- HTTP problem codes now reach the existing frontend error UI instead of every error becoming upstream_unavailable.
- Local Python launcher installs the existing shared $20 budget guard before invoking the supplied PA bridge. It does not create an independent spending allowance.

## Backend handoff

The source backend should supply its PA_04 bridge at <backend root>/ask_bridge.py and engine at <backend root>/astrologist/pa_engine.py, plus planner/composer/validator and supporting dependencies. It must read one stdin object {op:'turn', request:...}, emit flushed JSONL {event,data}, and terminate after final/error. Its final message text/cards/links must equal the emitted deltas/cards/links.

The FE adapter defaults to D:\Dev\astrology-app as backend root. ASTRO_PA_ROOT can select another complete backend root. Prefer synchronizing the completed backend and its changed shared dependencies to D: before testing, as requested by the user; the incomplete G: backend was not copied over the existing approved D: layers.

Ask additionally requires ASTRO_ASK_ENABLED=1 and ASTRO_ALLOW_PAID=1. Both must remain off until the missing backend is delivered and its integration verified. Existing startup scripts do not automatically enable Ask. The wrapper keeps the current shared budget/pricing guard; no pricing or model choices were changed.

Still required after backend delivery:
1. Compare and synchronize the completed PA files and changed shared dependencies, including llm_client/run_calendar, into D: without overwriting unrelated changes.
2. Verify a no-cost scripted bridge round trip against the actual PA implementation, complete audit compatibility and deterministic prewarm support (prewarm is not wired yet).
3. Confirm the shared budget guard works with the backend's provider interface. Backend audit price constants differ from the frontend guard; the existing guard remains authoritative for the cap.
4. Run a real question through Android, verify cancellation, cards, navigation, saved messages, EN/TR responses, and save screenshots. Follow the PA live-run cost-estimate gate before paid evaluation.

## Verification

- Full existing TypeScript/API regression suite: 102 passed (included the first four new PA tests).
- Final focused suite: six PA tests passed, including bounded history, persistence, authentication, feedback/deletion, disabled backend, malformed final, same-thread concurrency, quota/reset, foreign context, deleted subject and actual HTTP disconnect.
- Existing real-profile API test re-run after the final API changes: passed.
- TypeScript typecheck and ESLint for all changed TypeScript files: passed.
- Python launcher with generation disabled: returned the expected safe JSONL error; no model calls.
- No live PA answers, Android PA screenshots, or full PA bridge success were claimed: the required backend implementation is absent.

No paid LLM calls were made for this work. Unrelated PHASE_1_REPORT.md, USER_TEST_GUIDE.md, ANDROID_ACCEPTANCE_REPORT.md and Claude outputs were left intact.
