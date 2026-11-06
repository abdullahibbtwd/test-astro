# Account data inventory and deletion

How `DELETE /v1/me` maps to each place user data can live.

## Proven by tests

- `backend/tests/local-account.test.ts` — export scrub, local wipe, map cache
- `backend/tests/deletion-idp.test.ts` — mocked Supabase admin + IdP retry after tombstone
- `backend/tests/prisma-phase2.test.ts` — subscriptions / payment_events cleared

## Database (Postgres)

| Store | On DELETE /me | Notes |
| --- | --- | --- |
| `users` | deleted | Cascades to sessions, profiles, charts, readings, jobs, records, usage_counters, subscriptions |
| `sessions` | deleted | Explicit + cascade |
| `records` (tenant KV) | cascade | profiles, charts, readings, ask threads, reports, jobs, forecasts, map, compat, idem |
| `subscriptions` | deleted | Explicit |
| `payment_events` | deleted | Explicit (no FK) |
| `usage_counters` | deleted | Explicit |
| `budget_settings` | deleted | Explicit |
| `budget_calls` | anonymized `user_id → shared` | Spend ledger retained without identity |
| `guest_sessions` (claimed) | deleted | Claimed rows held birth JSON |
| `deleted_users` | upserted tombstone | Kept forever to block re-creation |
| `guest_rate_limits` | untouched | IP hashes only, no user id |
| `system_config` | auth-mode may be re-written | Shared place cache has no PII |

## Files / caches

| Location | On DELETE /me |
| --- | --- |
| `DATA_DIR/map-products/<userId>/` | wiped |
| `DATA_DIR/dossier/<chart_key>/` | released when last profile ref drops (`progressive.releaseProfile`) |
| In-memory rate-limit maps | expire naturally (keyed by user id / IP) |
| Browser sign-in PKCE flows | expire ≤10 min; not user-indexed |

## Queues / jobs

| Location | On DELETE /me |
| --- | --- |
| Prisma `jobs` | cascade with user |
| Record `job:*` | cascade with records |
| In-flight Ask streams for this tenant | aborted via `ask.closeTenant()` |

## Logs / Sentry

| Location | On DELETE /me |
| --- | --- |
| App logs | Fastify `logger:false`; no token/PII logging by design |
| `ASTRO_BUDGET_LOG` | model/spend only — no prompts |
| Sentry | no `setUser`; scrubbers drop email/tokens/bodies. Nothing to delete server-side |

## Client device

| Location | Cleared by client after 202 |
| --- | --- |
| Session / Supabase auth files | `clearSession` / sign-out |
| Encrypted MMKV query cache (Android) | cleared |
| SecureStore guest token | **not** cleared today (guest capability only) |

## IdP (Supabase Auth)

| Step | Behavior |
| --- | --- |
| Admin `DELETE /auth/v1/admin/users/{id}` | Called after local wipe |
| Failure | 503; JWT may retry `DELETE /me` (tombstone path retries IdP only) |
| Missing secret key | Local wipe only; config-check **warns** |

## Backups (owner retention)

| System | Retention | Owner action |
| --- | --- | --- |
| Coolify / volume snapshots | Operator-defined | Purge or rotate per policy after deletion requests |
| Supabase PITR / daily backups | Supabase plan default | Confirm project backup window; deleted Auth users remain in backup until expiry |
| Postgres logical dumps | If any | Exclude or re-dump after deletions |
| EAS / Sentry | N/A for account rows | Confirm no PII in release artifacts |

**BLOCKED for owner:** document exact Coolify snapshot TTL and Supabase backup retention in the production runbook; code cannot prove backup erasure.
