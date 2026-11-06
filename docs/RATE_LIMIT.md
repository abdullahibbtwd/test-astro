# HTTP rate limits

In-process Fastify limits (not a gateway). See `backend/api/rate-limit.ts`.

## Storage

Buckets live in a **process-local `Map` only** (no Redis / DB). On API restart or
redeploy, **all counters reset** — every client gets a fresh window. That is
acceptable for abuse smoothing; do not treat these limits as durable quotas.

Expired buckets are also swept on a timer so memory cannot grow without bound
within a long-lived process.

## Proxy trust (`ASTRO_TRUST_PROXY_HOPS`)

Client IP for unauthenticated buckets comes from **`request.ip` only**. Never parse `X-Forwarded-For` in app code.

| Deployment | Set `ASTRO_TRUST_PROXY_HOPS` to |
| --- | --- |
| Local / direct TCP (no reverse proxy) | `0` (default) — IP is the socket peer; spoofed `X-Forwarded-For` is ignored |
| Coolify with Traefik in front of the API | `1` — Traefik is the one trusted hop |
| Cloudflare (or similar CDN) in front of Coolify/Traefik | `2` — CDN + Traefik (add one hop per extra trusted proxy) |

Wrong hop count either ignores the real client IP (too low → all clients share the proxy IP bucket) or allows header spoofing (too high).

## Buckets and hook order

1. **`onRequest` — coarse per-IP** (`ASTRO_RATE_LIMIT_IP_MAX`, default **300**/min). Separate from, and much higher than, per-user general. Runs before JWT verification so garbage `Authorization` values cannot flood verify.
2. **Route handler — `resolveTenant`** (verified `user_id` / demo owner).
3. **After auth — per-user**:
   - general (`ASTRO_RATE_LIMIT_MAX`, default 120)
   - expensive (`ASTRO_RATE_LIMIT_EXPENSIVE_MAX`, default 40)
   - job poll (`ASTRO_RATE_LIMIT_JOB_MAX`, default **180**) for `GET /v1/jobs/{id}` only — **does not** consume the general bucket

Unauthenticated routes only see the IP bucket. Authenticated keys are the verified tenant id, not any slice of the Bearer string (token refresh keeps the same bucket).

Exempt from all buckets: `GET /v1/meta/config` (health / mobile bootstrap).

429 responses use problem+json `code: rate_limited` and a `Retry-After` header (seconds).

## Env

| Variable | Default | Role |
| --- | --- | --- |
| `ASTRO_TRUST_PROXY_HOPS` | `0` | Fastify `trustProxy` hop count |
| `ASTRO_RATE_LIMIT_DISABLED` | unset | `1` disables all limits (CI) |
| `ASTRO_RATE_LIMIT_WINDOW_MS` | `60000` | Window length |
| `ASTRO_RATE_LIMIT_IP_MAX` | `300` | Pre-auth per IP (separate from user limits) |
| `ASTRO_RATE_LIMIT_MAX` | `120` | Per-user general |
| `ASTRO_RATE_LIMIT_EXPENSIVE_MAX` | `40` | Per-user expensive routes |
| `ASTRO_RATE_LIMIT_JOB_MAX` | `180` | Per-user `GET /jobs/{id}` |

## Mobile job polls — worst-case RPM

Source: `frontend/src/api/job-watcher-core.ts` + `job-policy.ts` (config mirrors in `backend/api/defaults/config.json`).

| Parameter | Value |
| --- | --- |
| Scheduler | **One** shared `JobWatcher` for the whole app |
| Concurrent HTTP job polls | **1** — `running` flag serializes; only one `GET /jobs/{id}` in flight |
| Global inter-poll floor | `lastStart + 1000` → **≥1s** between poll starts |
| Per-job backoff | `1000 → 2000 → 3000 → 4000` ms; after job age 2 min → 10s; after 20 min (`JOB_VERY_SLOW_MS`) → 30s |
| Backend generation busy | Per-feature single busy slot (`blocking_job_id`); many job *ids* can still be registered while older ones finish |

**Worst-case job polls for one user (foreground):** many pending jobs all due immediately still yield at most **~60 `GET /jobs/{id}` per minute** (1 Hz global floor). Steady state with a few young jobs is closer to **15–30/min** (4s interval once past the ramp).

Without a separate job bucket, ~60 polls/min would consume half of the general **120**/min budget and leave little room for navigation. Job polls therefore use **`ASTRO_RATE_LIMIT_JOB_MAX=180`** (3× client worst case) and do not count against general.

## Mobile fan-out vs expensive default

Screens that fire **multiple expensive** calls together:

| Surface | Expensive calls |
| --- | --- |
| Map tab (`MapScreen`) | `GET …/acg/lines` + `GET …/acg/heat/{goal}` → **2** |
| Recommend result | `GET …/acg/recommendations` + `GET …/acg/lines` → **2** |
| Ahead day / month / year | one of `forecast/day|month|year` → **1** |
| Chart reading (`InlineReading` when enabled) | `GET …/natal-reading` → **1** |
| New match / profile create / claim / export | matching `POST` surfaces → **1** each |

Cold session bootstrap (`/me`, `/meta/config`, profiles, catalogue, `/home`) is **not** in the expensive list.

A single normal user switching Map → Ahead → Chart reading in one minute is typically **≤5** expensive hits. Default expensive **40/min**.
