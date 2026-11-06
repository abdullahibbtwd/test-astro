# AI readings & Ask Astrology — safe enablement runbook

**Do not flip production flags from this document alone.** This runbook explains how to enable paid generation and Ask **when** ops explicitly approve spend. The companion script `backend/scripts/smoke-paid-enablement-check.sh` only **checks** readiness; it never sets `ASTRO_ALLOW_PAID=1` or calls models.

Related inventory: `docs/CREDENTIALS_INVENTORY.md`. Config gate: `npm run config:check` (`backend/api/config-check.ts`).

## Current safe defaults (leave these)

| Variable | Safe default | Effect when off |
| --- | --- | --- |
| `ASTRO_ALLOW_PAID` | `0` | Natal / forecast / map / compat / guest prose → `generation_paused` or bridge refuse |
| `ASTRO_ASK_ENABLED` | `0` | Ask create / stream → 503 / disabled |
| `ASTRO_GUEST_ONBOARDING` | often `0` in prod compose | Guest preview routes 503 |
| `ASTRO_PROGRESSIVE_READING` | `0` | Progressive natal sections off |
| `ASTRO_BUDGET_LIMIT` | unset → **US$20** cap in code | Hard ceiling for ledger |
| `ASTRO_BUDGET_USER` | unset → `"shared"` | One org-wide ledger (noisy neighbor risk) |

Client flag `askAstrology` is derived from Ask readiness (`allowPaid` + `ASTRO_ASK_ENABLED` + bridge files), not from a free-standing “on” in production config alone.

## Preconditions checklist (before any enable)

1. **Approval** — written spend cap (≤ US$20 unless product raises `ASTRO_BUDGET_LIMIT` carefully; code rejects >20 unless you change budget.py).  
2. **Secrets on Coolify only** — `GEMINI_API_KEY` or `GOOGLE_API_KEY` (or `~/.gemini_key` on host). Never commit.  
3. **Ask extras** — `OPENAI_API_KEY` (or `~/.openai_key`) if Ask path requires OpenAI; `ASTRO_PA_ROOT` pointing at `backend/engine`; PA files present.  
4. **Refuse list empty** — `OPENAI_BASE_URL` and `GOOGLE_GENAI_USE_VERTEXAI` must be **unset**.  
5. **Auth** — real Supabase (not `ASTRO_DEMO_AUTH=1` in production).  
6. **Daily caps** — confirm `ASTRO_DAILY_*` and `ASTRO_DAILY_ASK_LIMIT` (default Ask 20/day).  
7. **Sentry** — optional but recommended (`SENTRY_DSN`) before paid traffic.  
8. **Run** `backend/scripts/smoke-paid-enablement-check.sh` — expect `READY` or listed gaps; fix gaps first.

## Staged enable order (manual Coolify / host env)

Perform one stage at a time. Restart API after each change. **Watch budget ledger and Sentry.**

### Stage 0 — dry check only

```bash
cd backend && ./scripts/smoke-paid-enablement-check.sh
npm run config:check
```

Expect paid still `0`. No model calls.

### Stage 1 — paid prose, Ask still off

Set on the **API** service only:

```text
ASTRO_ALLOW_PAID=1
ASTRO_ASK_ENABLED=0
ASTRO_GUEST_ONBOARDING=0
ASTRO_PROGRESSIVE_READING=0
ASTRO_BUDGET_LIMIT=5          # optional lower cap for first day
# ASTRO_BUDGET_USER=shared   # or a test tenant id if isolating ledger
```

Smoke (authenticated, synthetic birth data only):

- `GET .../natal-reading` → pending job → ready (not `generation_paused`)  
- One forecast day reading  
- One map place reading **or** love compatibility  

Stop if any call errors with budget exceeded or unexpected 503.

### Stage 2 — optional guest / progressive

Only if product wants them:

```text
ASTRO_GUEST_ONBOARDING=1
ASTRO_PROGRESSIVE_READING=1
```

Guest path still requires paid. Re-test claim flow on a throwaway account.

### Stage 3 — Ask Astrology (staged rollout; do NOT enable live until stages pass)

Ask uses the **same** org `$` ledger (`ASTRO_BUDGET_LIMIT`) via `budget.install_guard`
and a **separate** daily ASK counter (`ASTRO_DAILY_ASK_LIMIT`, default 20). Messages
are capped at 1000 chars; prompt-injection / role-break attempts return 400
`abuse_rejected`. When Ask is off: create/send → **503** `upstream_unavailable`.

#### 3a — Owner only

```text
ASTRO_ALLOW_PAID=1
ASTRO_ASK_ENABLED=1
ASTRO_DAILY_ASK_LIMIT=5
ASTRO_BUDGET_LIMIT=<owner C ≤ 20>
```

Smoke as the owner account only: create thread, one short in-scope question,
confirm streaming + quota footer, Stop mid-stream, Retry after error. Confirm
input never stuck loading.

#### 3b — Five testers

Keep Ask on; invite five known accounts. Watch `ASTRO_BUDGET_LOG` and Sentry
`budget_alert:*`. Lower `ASTRO_DAILY_ASK_LIMIT=3` if spend climbs.

#### 3c — Everyone

Raise `ASTRO_DAILY_ASK_LIMIT` toward product default (≤20). Keep org cap `C`.
Announce rollback path below before opening broadly.

Existing paid Ask script (spends money — **do not run** without approval):

`backend/scripts/ask-gemini-smoke.mts`

## Rollback (immediate)

```text
ASTRO_ALLOW_PAID=0
ASTRO_ASK_ENABLED=0
ASTRO_GUEST_ONBOARDING=0
ASTRO_PROGRESSIVE_READING=0
```

Restart API. In-flight jobs may fail; new paid bridges refuse. Budget ledger rows remain (accounting).

## What this runbook deliberately does not do

- Does not change Coolify env for you  
- Does not commit secrets  
- Does not raise the US$20 hard ceiling in code  
- Does not enable flags in `defaults/config.json` repo defaults  

## Decision log

| Date | Action | Cap / flags | By |
| --- | --- | --- | --- |
| _pending_ | _not enabled_ | | |
