# Coolify setup checklist

Placeholders only — never paste live secrets into this file. Variable **names** only below.

The production compose file is `docker-compose.yml`. Local convenience Postgres (published `5432`, simple password) stays in `docker-compose.dev.yml` only.

---

## Postgres password vs existing volume

Postgres stores the bootstrap password **inside the data volume** on first init.

If you change `POSTGRES_PASSWORD` (or the password embedded in `DATABASE_URL`) after `pgdata` already exists, the **old password remains in the volume**. New env values do **not** rewrite `pg_authid`. Symptoms: API auth failures to Postgres / `password authentication failed`.

**Safe options:**

1. **Fresh volume (recommended for first production cut):** remove the Coolify/compose Postgres volume (destroys data), set the new password, redeploy so initdb runs once.
2. **Keep data:** connect with the *old* password and `ALTER USER … PASSWORD …`, then update Coolify env to match. Do not only change the env.

---

## Variables to SET

Marking **secret** vs **public**. Use placeholders; supply real values in Coolify.

### Required for a working API + DB

| Name | Kind | Placeholder / notes |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | **secret** | Strong URL-safe secret. Required by compose (`${POSTGRES_PASSWORD:?…}`). |
| `POSTGRES_USER` | public | e.g. `astrology` (default in compose) |
| `POSTGRES_DB` | public | e.g. `astrology` (default in compose) |
| `DATABASE_URL` | **secret** | If using **compose `db` service**: compose builds this from `POSTGRES_*`. If using a **separate Coolify Postgres resource**: set explicitly, e.g. `postgres://USER:PASSWORD@HOST:5432/DB` (no `127.0.0.1`, no default `astrology`/`astrology` password). |
| `HOST` | public | Compose sets `0.0.0.0` |
| `PORT` | public | Compose sets `4020` |
| `NODE_ENV` | public | Compose sets `production` |

### Auth (real users)

| Name | Kind | Placeholder / notes |
| --- | --- | --- |
| `AUTH_ENABLED` | public | `1` |
| `SUPABASE_URL` | public | `https://YOUR_PROJECT_REF.supabase.co` |
| `SUPABASE_PUBLISHABLE_KEY` | public | `sb_publishable_…` |
| `SUPABASE_SECRET_KEY` | **secret** | `sb_secret_…` — needed so account deletion removes the IdP user |
| `SUPABASE_JWKS_URL` | public | optional; default `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` (same host) |
| `AUTH_OWNER_EMAIL` | secret-ish (PII) | **Omit** for multi-user. If set, only that email can sign in (`config:check` warns). |

### Paid Gemini readings (optional until you enable)

| Name | Kind | Placeholder / notes |
| --- | --- | --- |
| `ASTRO_ALLOW_PAID` | public | `0` until ready; then `1` |
| `GEMINI_API_KEY` | **secret** | or `GOOGLE_API_KEY` |
| `ASTRO_LLM_MODEL` | public | default `gemini-3.5-flash-lite` |
| `ASTRO_CHEAP_MODEL` | public | default same as LLM model |
| `GEMINI_THINKING_LEVEL` | public | default `minimal` |

### Feature flags (compose defaults)

| Name | Kind | Default in compose |
| --- | --- | --- |
| `ASTRO_PROGRESSIVE_READING` | public | `0` |
| `ASTRO_GUEST_ONBOARDING` | public | `0` (example often `1`) |
| `ASTRO_ASK_ENABLED` | public | `0` — leave off until Ask works with your chosen model |
| `ASTRO_DEMO_AUTH` | public | `0` — **must** stay `0` in production |

### Optional tuning (set on the Coolify service when needed; omit rather than empty-string)

| Name | Kind | Notes |
| --- | --- | --- |
| `ASTRO_BUDGET_LIMIT` | public | USD cap (code default `20`; `config:check` warns when set) |
| `ASTRO_BUDGET_USER` | public | ledger partition (warns when set) |
| `ASTRO_BUDGET_LOG` | public | path for JSONL spend/retry log |
| `ASTRO_BUDGET_RESERVATION_TTL_S` | public | reservation TTL |
| `ASTRO_DAILY_NATAL_LIMIT` / `MAP` / `FORECAST` / `COMPAT` / `ASK` | public | per-user UTC daily generation caps |
| `ASTRO_ASK_MODEL` | public | Ask model id (Gemini schemas currently rejected by provider — keep Ask off) |
| `OPENAI_API_KEY` | **secret** | only if Ask uses an OpenAI model id |
| `ANTHROPIC_API_KEY` | **secret** | only if using Claude model ids |
| `OPENAI_REASONING_EFFORT` | public | OpenAI only |
| `GEMINI_MAX_CONCURRENCY` / `GEMINI_429_MAX_WAITS` / `GEMINI_RETRY_*` | public | Gemini client tuning |

### Paths fixed by compose/image

| Name | Kind | Value in compose/image |
| --- | --- | --- |
| `PYTHON` | public | `/opt/venv/bin/python` |
| `ASTRO_PA_ROOT` | public | `/app/backend/engine` |
| `DATA_DIR` | public | `/app/backend/.local-data` — **must** be a persistent volume (`api-data` in compose) |

---

## Variables that must stay UNSET (and why)

| Name | Why |
| --- | --- |
| `OPENAI_BASE_URL` | Paid guard + `config:check` refuse non-default / any set value — leave unset for the public OpenAI endpoint |
| `GOOGLE_GENAI_USE_VERTEXAI` | Paid guard + `config:check` refuse Vertex pricing path |
| `ASTRO_DEMO_AUTH=1` | Process refuses to start when `NODE_ENV=production` |
| `MOCK_HOST` / `MOCK_JOB_SECONDS` | Mock API only — not the production API |
| `ACG_LIVE` | Engine test harness only |
| `CI` | Frontend CI bundle behavior — not the API container |

Do **not** put `SUPABASE_SECRET_KEY`, `GEMINI_API_KEY`, or `POSTGRES_PASSWORD` in the mobile app or EAS public env.

---

## Persistent volume for `DATA_DIR`

Compose mounts named volume `api-data` → `/app/backend/.local-data`.

Holds map product cache, dossiers, optional `auth-config.json`, and related local files. **Keep this volume** across deploys. Losing it does not drop Postgres rows but can drop cached chart products and any file-based auth fallback.

---

## Fresh deployment — compose stack (API + Postgres)

1. In Coolify, create an application from this repo using `docker-compose.yml` (not `docker-compose.dev.yml`).
2. Set `POSTGRES_PASSWORD` (and optional `POSTGRES_USER` / `POSTGRES_DB`) **before** the first successful Postgres start.
3. Set Supabase + Gemini vars from the tables above. Leave `ASTRO_DEMO_AUTH` unset/`0`, leave `OPENAI_BASE_URL` and `GOOGLE_GENAI_USE_VERTEXAI` unset.
4. Confirm volumes: `pgdata` (Postgres) and `api-data` (`DATA_DIR`).
5. Deploy. Postgres is **not** published on the host; only the API port (`4020`) is.
6. From the API container or a one-off exec: `npm run config:check` (or rely on startup `runConfigCheck`).
7. Hit `https://YOUR_API_HOST/v1/meta/config` for a health/config smoke.

### If you change the DB password later

See [Postgres password vs existing volume](#postgres-password-vs-existing-volume). Prefer a fresh `pgdata` only when you accept data loss.

---

## Fresh deployment — separate Coolify Postgres resource

1. Create a Coolify **PostgreSQL** resource. Note host, port, user, password, database (Coolify UI — do not commit values).
2. Enable automated backups on that resource (next section).
3. Create the API application (Dockerfile or compose **without** the in-compose `db` service, or override so the API does not start a second Postgres).
4. Set `DATABASE_URL=postgres://USER:PASSWORD@COOLIFY_PG_HOST:5432/DB` (URL-encode special characters in the password).
5. Do **not** use `127.0.0.1` or the default `astrology`/`astrology` pair in production (`config:check` refuses those).
6. Mount a persistent volume for `DATA_DIR=/app/backend/.local-data`.
7. Pass the same `SUPABASE_*` / `ASTRO_*` / `GEMINI_*` env as above.
8. Deploy; run `config:check`; smoke `/v1/meta/config`.

---

## Postgres backups to an S3-compatible target

Exact Coolify UI labels vary by version; the intent is:

1. Open the **Postgres** resource (compose `db` or standalone).
2. Enable **Backups**.
3. Choose **S3-compatible** storage.
4. Set: endpoint URL, bucket, region, access key, secret key (all secret except endpoint/bucket/region as appropriate).
5. Schedule (e.g. daily) and retention.
6. Run a **manual backup** once and confirm the object appears in the bucket.
7. Periodically restore into a **throwaway** database (never overwrite production first). Locally you can use `backend/scripts/backup-drill` against `astrology_test`.

---

## Reading logs

- Coolify application → **Logs** (API container stdout/stderr). Startup prints config refuse/warn lines by **variable name only**.
- Optional spend/retry file: set `ASTRO_BUDGET_LOG` to a path under `DATA_DIR` and `tail` that file from the volume.
- Do not expect prompts, birth data, or API keys in logs; bridges are written to avoid that.

---

## Related local commands

```bash
# From backend/
npm run config:check
npm run local-api:dev   # uses host .env + docker-compose.dev.yml Postgres — not Coolify

# Backup drill against astrology_test (see script header)
./scripts/backup-drill
```
