# Local Astro agent connection

Updated 2026-10-06.

## Status

The working Android frontend is connected to the local agent at `D:\Dev\astrology-app\astrologist` through the existing authenticated Ask API. The emulator is running on the conversation screen. No Google Drive imports are required at runtime.

Source tools and PA specifications were copied from `G:\My Drive\Tech\Astrology app`. The missing planner, composer, validator, engine, root JSONL bridge and private CLI were implemented locally. The Drive source was not overwritten.

## What works

- Eleven deterministic tools reuse the chart, calendar, Best Days, map, compatibility and cached reading layers.
- Strict structured planning, saved-person handles, contextual tool calls and deterministic date resolution.
- Evidence-linked answers, validation before streaming, one repair attempt and a safe fallback.
- Scope templates, Turkish/English responses, deterministic cards and navigation links.
- Existing frontend authentication, thread history, feedback, cancellation, daily quota and shared $20 spending cap.
- Safe audit diagnostics; birth details and user text are excluded from model planner inputs and audits respectively. The model receives selected chart evidence and the question, not raw birth inputs.
- Local CLI supports saved Subject JSON or explicit birth coordinates, interactive questions, plan-only, dry-run, fake replies and deterministic prewarm.

## Verification

- Full agent suite: 75 passed before the final three regression cases were added.
- Final planner/validator/engine regression suite plus shared LLM-client suite: 76 passed (58 pipeline + 18 client).
- Frontend Ask contract tests: 6 passed.
- TypeScript and lint checks for changed frontend files: passed.
- Live model checks: English Sun sign, Turkish rising sign, scope decline, calendar/day, London/place and Turkish natal interpretation all reached a validated final answer after identified issues were fixed.
- Android end-to-end: created a conversation, sent a question through the real authenticated API and Python bridge, received a Cancer Sun answer/card, and opened the matching chart. Reopened the conversation after restarting the final API.
- Fixed a stray React Native text node and the input/Send overlap found during the emulator test. Final UI bounds confirm separate controls.

One initial Android question produced an unnecessary clarification. The planner now explicitly treats personal pronouns as referring to the selected subject; the follow-up completed successfully. This is not a claim that the full question-quality benchmark has passed.

## Screenshots

Saved under `FE/artifacts/pa-integration-2026-10-06/`:
1. `01-conversations.png`
2. `02-question.png`
3. `03-live-answer.png`
4. `04-chart-link.png`
5. `05-ready-to-test.png` (corrected composer layout)

The test conversation uses the existing **Fictional AI test** profile. Choose a different saved person from the conversation header to test your own details.

## Launch

From `D:\Dev\astrology-app\FE`:

```powershell
./scripts/Start-Android-Preview.ps1 -RealCharts -EnableReadings -EnableAstrologist -RestartApi
```

Wait for active generation to finish before restarting. Model calls share the existing durable spending guard, including the CLI and direct root bridge. OpenAI login remains outside the current scope.

## Remaining qualification work

The connection is ready for user testing; full PA production acceptance is not yet complete:

- The specified 80-question golden benchmark and separate adversarial evaluation have not run. Current live checks are targeted smoke tests.
- Turkish wording still needs native review, as specified in PA.
- Tool execution is serial to avoid races in shared calculation libraries and caches; parallel execution needs isolation before enabling it.
- Per-tool disk-cache telemetry is currently unknown (`cache_hit: null`) rather than fabricated. Full prewarm cache-hit reporting and the feedback-export evaluator remain to be added.
- The CLI intentionally uses the configured model; optional per-stage model overrides and text-based geocoding flags are not yet exposed.
- The supplied decline templates contain words that the general generated-answer forbidden-word checks prohibit (for example, declining to predict illness). They are trusted fixed templates, not run through those generated-answer checks; reconcile the PA_03 PV14 wording during acceptance.

These qualification gaps do not disable the working frontend conversation path.

## Spending

Shared recorded budget at report time: **$1.228581 of $20**. This includes earlier reading tests. This integration work began at $1.217258; private smoke artifacts are in ignored `ask_run/integration-2026-10-06/`.
