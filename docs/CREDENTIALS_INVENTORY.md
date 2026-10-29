# Credentials & environment inventory

Report only. No values. Searched: `backend/`, `frontend/`, `Dockerfile`, `docker-compose.yml`, `docker-compose.dev.yml`, `.env.docker.example`, `frontend/.env.example`, `frontend/eas.json`, `frontend/app.json`, `frontend/app.config.js`, `scripts/` (repo + `frontend/scripts/`, `backend/scripts/`), `.github/workflows/`.

**Coolify:** not referenced anywhere in-repo. Vars marked **Coolify** are the Docker/`docker-compose.yml` surface a Coolify (or similar) host would inject at runtime.

**EAS:** `frontend/eas.json` defines build profiles only — no `env` block. App secrets/public config for native builds must be supplied via EAS project env / local `.env` / CI; the app reads them at Metro/EAS bundle time.

**Defaults below** are what the code uses when the variable is unset (not what any local `.env` may contain).

---

## AI providers by generation feature

Provider is inferred from the model id in `backend/engine/llm_client.py` (`gemini-*` → Google, `gpt-*`/`o*` → OpenAI, `claude-*` → Anthropic). App bridges use `llm_client.DEFAULT_MODEL` / `DEFAULT_CHEAP_MODEL` unless noted.

| Feature | What runs | Default model(s) | Provider called (with project defaults) | Keys / flags required |
| --- | --- | --- | --- | --- |
| **natal** | Monolithic L4 (`reading_bridge` → `l4_interpret` / `LLMGenerator`) or progressive sections (`reading_section_bridge`) | Section/synthesis: `ASTRO_LLM_MODEL` → `gemini-3.5-flash-lite`. Translation/detox: `ASTRO_CHEAP_MODEL` → same as `DEFAULT_MODEL` | **Google (Gemini)** for prose; translation also **Gemini** unless `ASTRO_CHEAP_MODEL` is set to an OpenAI/Anthropic id | `ASTRO_ALLOW_PAID=1`; `GEMINI_API_KEY` or `GOOGLE_API_KEY` (or `~/.gemini_key`). If cheap model is `gpt-*`, also `OPENAI_API_KEY` |
| **forecast** | `forecast_bridge` → `run_reading` + `translate_reading` | Prose: `DEFAULT_MODEL`. EN translation: `DEFAULT_CHEAP_MODEL` | **Google (Gemini)** (+ same caveat for cheap model) | Same as natal |
| **map** | `map_reading_bridge` → `ar_generate` / area / recommend | `DEFAULT_MODEL` + `DEFAULT_TRANSLATION_MODEL` (= cheap) | **Google (Gemini)** (+ cheap-model caveat) | Same as natal |
| **compatibility** | `compatibility_bridge` → `read_relationship` | Section/synthesis: `DEFAULT_MODEL`. Statements + translation: `DEFAULT_CHEAP_MODEL` | **Google (Gemini)** (+ cheap-model caveat) | Same as natal |
| **guest** | Guest onboarding → `ProgressiveReadings` → same section bridge as progressive natal | Same as natal progressive | **Google (Gemini)** (+ cheap-model caveat) | `ASTRO_GUEST_ONBOARDING=1` **and** `ASTRO_ALLOW_PAID=1`, plus Gemini key |
| **ask** | `ask_bridge` → PA planner/composer (`pa_constants.PA_MODEL`) | Hardcoded `gpt-6-luna` (not `ASTRO_LLM_MODEL`) | **OpenAI** | `ASTRO_ALLOW_PAID=1`, `ASTRO_ASK_ENABLED=1`, `ASTRO_PA_ROOT` with PA tree, `OPENAI_API_KEY` (or `~/.openai_key`) |
| **translation** | EN (and detox) stages inside natal / forecast / map / compatibility / guest | `DEFAULT_CHEAP_MODEL` (default = `DEFAULT_MODEL` = Gemini Flash-Lite) | **Google (Gemini)** by default; set `ASTRO_CHEAP_MODEL=gpt-6-luna` to use **OpenAI** (documented prior path) | Provider key for whichever cheap model id resolves to |

Paid generation is also blocked by the budget guard (`backend/api/budget.py`) unless `DATABASE_URL` works, the model is in the verified `RATES` table, and `ASTRO_BUDGET_LIMIT` is respected. Setting `OPENAI_BASE_URL` away from the public OpenAI API or `GOOGLE_GENAI_USE_VERTEXAI=1` aborts paid calls.

Offline key files (backend only, never ship in the app): `~/.gemini_key`, `~/.openai_key`, `~/.anthropic_key`.

---

## Backend / Coolify (API process & Docker)

| Name | Side | Public / secret | Required / optional | Default if unset | Feature that stops without it |
| --- | --- | --- | --- | --- | --- |
| `DATABASE_URL` | backend; Coolify/compose | secret | **Required** in practice (server sets a local default) | `postgres://astrology:astrology@127.0.0.1:5432/astrology` (`server.ts`); compose hardcodes `…@db:5432/astrology` | Entire API persistence, Prisma migrate, auth sessions, jobs, budget tables |
| `HOST` | backend; Coolify/compose | public | optional | `127.0.0.1` (compose/Dockerfile: `0.0.0.0`) | Bind address only; wrong value = unreachable API |
| `PORT` | backend; Coolify/compose | public | optional | `4020` (mock API: `4010`) | Listen port |
| `NODE_ENV` | backend; Coolify/Dockerfile | public | optional | unset locally; Dockerfile `production` | With `ASTRO_DEMO_AUTH=1` in production, process refuses to start |
| `PYTHON` | backend; Coolify/compose | public | optional | `python` (compose/Dockerfile: `/opt/venv/bin/python`) | Chart/calendar/reading/ask Python bridges fail to spawn |
| `DATA_DIR` | backend; Coolify/compose | public | optional | `backend/.local-data` (compose: `/app/backend/.local-data`) | Map product cache, dossiers, `auth-config.json`, budget sqlite path side effects |
| `ASTRO_PA_ROOT` | backend; Coolify/compose | public | optional for API; **required** for Ask | `./engine` via npm script; compose `/app/backend/engine`; Ask code defaults toward engine tree | Ask / PA if tree missing; other bridges use their own paths |
| `ASTRO_ALLOW_PAID` | backend; Coolify/compose | public (flag) | optional | `0` (compose) | All paid LLM prose: natal, forecast, map, compatibility, guest, ask |
| `ASTRO_PROGRESSIVE_READING` | backend; Coolify/compose | public (flag) | optional | `0` | Progressive (section-by-section) natal for signed-in users |
| `ASTRO_GUEST_ONBOARDING` | backend; Coolify/compose | public (flag) | optional | `0` (example often `1`) | Guest preview reading + claim (`/v1/onboarding/*`) |
| `ASTRO_ASK_ENABLED` | backend; Coolify/compose | public (flag) | optional | `0` | Ask Astrology (also needs paid + PA files + OpenAI) |
| `ASTRO_DEMO_AUTH` | backend; Coolify/compose | public (flag) | optional | `0` (npm `local-api:dev`); tests force `1` | Demo login (any email / `000000`); forbidden when `NODE_ENV=production` |
| `ASTRO_LLM_MODEL` | backend; Coolify/compose | public | optional | `gemini-3.5-flash-lite` | Overrides main generation model for natal/forecast/map/compat/guest |
| `ASTRO_CHEAP_MODEL` | backend; Coolify/compose | public | optional | same as `ASTRO_LLM_MODEL` | Overrides translation / statements / detox model |
| `GEMINI_THINKING_LEVEL` | backend; Coolify/compose | public | optional | `minimal` | Gemini thinking budget (cost/latency), not a hard feature kill |
| `GEMINI_API_KEY` | backend; Coolify/compose | **secret** | required for default Gemini features (or file/`GOOGLE_API_KEY`) | unset | Natal, forecast, map, compatibility, guest, translation (default models) |
| `GOOGLE_API_KEY` | backend; Coolify/compose | **secret** | alternate to `GEMINI_API_KEY` | unset | Same as `GEMINI_API_KEY` |
| `OPENAI_API_KEY` | backend; Coolify/compose | **secret** | required for Ask; optional for cheap-model OpenAI path | unset | **Ask**; also translation/statements if `ASTRO_CHEAP_MODEL` is OpenAI |
| `ANTHROPIC_API_KEY` | backend; Coolify/compose | **secret** | optional | unset | Only if model ids are `claude-*` / offline corpus tools; not used by default app bridges |
| `OPENAI_REASONING_EFFORT` | backend | public | optional | `low` | OpenAI call parameter when OpenAI models are used |
| `GEMINI_MAX_CONCURRENCY` | backend | public | optional | `8` | Throughput under Gemini rate limits |
| `GEMINI_429_MAX_WAITS` | backend | public | optional | `6` | Gemini 429/503 retry depth |
| `GEMINI_RETRY_BASE_S` | backend | public | optional | `1` | Gemini retry backoff base |
| `GEMINI_RETRY_MAX_WAIT_S` | backend | public | optional | `60` | Cap per Gemini retry sleep |
| `ASTRO_BUDGET_LIMIT` | backend | public | optional | `20` (USD) | Paid LLM under budget guard; invalid/over-cap rejects spend |
| `ASTRO_BUDGET_USER` | backend | public | optional | `shared` (limits.ts falls back to request user id when set for metering) | Budget ledger partitioning / per-user caps |
| `ASTRO_BUDGET_LOG` | backend | public (path) | optional | unset (off) | Ops retry/spend ledger file only |
| `ASTRO_BUDGET_RESERVATION_TTL_S` | backend | public | optional | code default TTL | Stale budget reservations expiry |
| `OPENAI_BASE_URL` | backend | public | optional | `https://api.openai.com/v1` | Non-default → paid guard refuses (“unverified endpoint”) |
| `GOOGLE_GENAI_USE_VERTEXAI` | backend | public | optional | unset/false | If `1`/`true` → paid guard refuses |
| `ASTRO_DAILY_NATAL_LIMIT` | backend | public | optional | `3` | Daily natal generation quota (not provider auth) |
| `ASTRO_DAILY_MAP_LIMIT` | backend | public | optional | `5` | Daily map generation quota |
| `ASTRO_DAILY_FORECAST_LIMIT` | backend | public | optional | `5` | Daily forecast generation quota |
| `ASTRO_DAILY_COMPAT_LIMIT` | backend | public | optional | `3` | Daily compatibility generation quota |
| `AUTH_ENABLED` | backend; Coolify/compose | public (flag) | optional | `1` in compose; treated as on unless `0` | Real Supabase auth path; `0` disables JWT/admin/auth client wiring even if URL set |
| `SUPABASE_URL` | backend; Coolify/compose | public (project URL) | required for real auth | unset | Supabase JWT verify, browser OTP helpers, admin delete; without it + demo off → no usable login |
| `SUPABASE_PUBLISHABLE_KEY` | backend; Coolify/compose | public (publishable) | required with URL for `SupabaseAuth` / email OTP server helpers | unset | Server-side Supabase Auth client config (env path); JWT can still verify with URL alone |
| `SUPABASE_SECRET_KEY` | backend; Coolify/compose | **secret** | optional | unset | Account deletion against Supabase Admin API; without it, local wipe only |
| `SUPABASE_JWKS_URL` | backend; Coolify/compose | public | optional | `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` | JWT verification; must stay on same project host |
| `AUTH_OWNER_EMAIL` | backend; Coolify/compose | secret-ish (PII) | optional | unset → multi-user | If set, pins single owner; other emails get 403 |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Coolify/compose **db** service only | secret (password) | required for compose Postgres image | hardcoded `astrology` / `astrology` / `astrology` in compose files | Postgres container bootstrap (app uses `DATABASE_URL`, not these names) |
| `MOCK_HOST` | backend mock server | public | optional | `127.0.0.1` | Mock API bind host |
| `MOCK_JOB_SECONDS` | backend mock | public | optional | `6` | Simulated job duration only |
| `CI` | GitHub Actions / scripts | public | optional | unset; workflow sets `1` for bundle | Frontend bundle step behavior; Android preview script clears it |
| `ACG_LIVE` | backend engine tests only | public | optional | unset | Enables live ACG model pytest; not production |

### Non-env credential files (backend)

| Credential | Side | Public / secret | Required / optional | Default | Without it |
| --- | --- | --- | --- | --- | --- |
| `~/.gemini_key` | backend | **secret** | alternate to env | none | Same as missing `GEMINI_API_KEY` when env unset |
| `~/.openai_key` | backend | **secret** | alternate to env | none | Ask / OpenAI models fail |
| `~/.anthropic_key` | backend | **secret** | alternate to env | none | Claude models / offline extract tools fail |
| `$DATA_DIR/auth-config.json` | backend | **secret** (URL + publishable key ± owner) | optional fallback if Supabase env unset | none | Falls back to demo auth or no auth |

---

## App build / EAS (Expo / Metro / native)

`eas.json` and `app.json` do not declare env values. `app.config.js` reads `GOOGLE_IOS_URL_SCHEME` at config time. `EXPO_PUBLIC_*` are baked into the JS bundle.

| Name | Side | Public / secret | Required / optional | Default if unset | Feature that stops without it |
| --- | --- | --- | --- | --- | --- |
| `EXPO_PUBLIC_API_URL` | app build / EAS; `dev-phone.sh` | public | effectively required for non-mock | `http://127.0.0.1:4010/v1` | All live API calls (wrong host = network errors) |
| `EXPO_PUBLIC_BACKEND_MODE` | app build / EAS | public | optional | unset (code checks `local` / `demo`) | `local` enables local export UX; `demo` affects auth UI assumptions |
| `EXPO_PUBLIC_AUTH_MODE` | app build / EAS | public | optional | unset → Supabase if keys configured | `demo` forces demo auth UI; `supabase` requires Supabase public keys |
| `EXPO_PUBLIC_SUPABASE_URL` | app build / EAS | public | required for real mobile auth | `""` | Supabase client / OTP / session |
| `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | app build / EAS | public (publishable) | required for real mobile auth | `""` | Same |
| `EXPO_PUBLIC_DEMO_LOGIN_HINT` | app build | public | optional | unset/off | Dev-only demo email hint; does not enable demo auth alone |
| `EXPO_PUBLIC_SHARE_URL` | app build / EAS | public | optional | unset | Share URL display on export screen only |
| `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` | app build / EAS | public (OAuth client id) | required for Google native sign-in | unset | Google Sign-In throws `ProviderUnavailable` |
| `EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID` | app build / EAS | public | optional (iOS) | unset | iOS Google Sign-In client; web id alone may be insufficient on iOS |
| `GOOGLE_IOS_URL_SCHEME` | app build / EAS (`app.config.js`) | public | optional | unset → Google Sign-In plugin omitted | Native Google Sign-In iOS URL scheme / plugin wiring |
| `EXPO_PUBLIC_SENTRY_DSN` | app build / EAS | public-ish (DSN) | optional | unset → telemetry init no-ops | Crash/error reporting to Sentry |
| `EXPO_PUBLIC_STRICT_CONTRACT` | app build | public | optional | unset; strict also on in `__DEV__` | Forces Zod contract throws in production builds |
| `EXPO_PUBLIC_FX_AUDIT` | app build | public | optional | unset | FX audit gallery outside `__DEV__` |
| `NODE_ENV` | app build / tooling | public | set by bundlers | — | Contract validation / telemetry in-memory diagnostics |

**Not present in code (despite older FE specs):** `MAP_STYLE_URL` / EAS profile `env` blocks — map style is local/static in `frontend/src/features/map/style.ts`.

---

## Scripts & workflows

| Name | Where | Notes |
| --- | --- | --- |
| Loads root `.env` into process | `backend/package.json` `local-api:dev` / `test` | Sources `../.env` then applies defaults for `DATABASE_URL`, `HOST`, `PORT`, `ASTRO_PA_ROOT`, `DATA_DIR`, `PYTHON`, `ASTRO_DEMO_AUTH` |
| `EXPO_PUBLIC_API_URL` | `dev-phone.sh`, `frontend/scripts/Start-Android-Preview.ps1` | Sets Metro-facing API URL |
| `EXPO_PUBLIC_BACKEND_MODE`, `EXPO_PUBLIC_AUTH_MODE`, `ASTRO_*`, `DATA_DIR`, `JAVA_HOME`, `ANDROID_HOME`, `ANDROID_AVD_HOME`, `NODE_OPTIONS`, `ADB` | `Start-Android-Preview.ps1` / `dev-phone.sh` | Local preview tooling; Android SDK paths are machine env, not product secrets |
| `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `EXPO_PUBLIC_API_URL` | `backend/scripts/e2e-supabase-otp.mjs` | Interactive OTP smoke; requires Supabase vars |
| `DATABASE_URL` | `backend/scripts/prisma-smoke.ts`, Prisma `prisma.config.ts`, Dockerfile generate stage | Migrate/generate |
| `CI=1` | `.github/workflows/frontend-contract.yml` (bundle step) | Only workflow env; **no GitHub Actions secrets** referenced |
| `eas.json` | EAS profiles `development` / `preview` / `production` | No credential or env entries |

---

## Compose / Dockerfile baked defaults (not host secrets)

Set inside images/compose rather than read from the developer’s shell (except `${VAR:-}` interpolation on the compose API service):

- Dockerfile: `DATABASE_URL` dummy at **build** for `prisma generate`; runtime `PYTHON`, `ASTRO_PA_ROOT`, `DATA_DIR`, `HOST`, `PORT`, `NODE_ENV=production`.
- `docker-compose.yml` `api.environment`: passes through Coolify/host values for paid flags, models, Supabase, and LLM keys (see table above).

---

## Minimal production matrix (no values)

| Concern | Must supply |
| --- | --- |
| API up + DB | `DATABASE_URL`, `HOST`/`PORT` as needed |
| Real auth (multi-user) | `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `AUTH_ENABLED≠0`; app: matching `EXPO_PUBLIC_SUPABASE_*` + `EXPO_PUBLIC_AUTH_MODE=supabase`; JWT via URL (± `SUPABASE_JWKS_URL`) |
| Soft-delete IdP user | `SUPABASE_SECRET_KEY` |
| Paid Gemini readings | `ASTRO_ALLOW_PAID=1`, `GEMINI_API_KEY` (or `GOOGLE_API_KEY` / `~/.gemini_key`) |
| Guest preview | + `ASTRO_GUEST_ONBOARDING=1` |
| Ask | + `ASTRO_ASK_ENABLED=1`, `OPENAI_API_KEY`, complete `ASTRO_PA_ROOT` |
| Google native login | `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` (+ iOS client/scheme as needed) |
| Demo-only local | `ASTRO_DEMO_AUTH=1` (never with `NODE_ENV=production`) |

---

*Generated as an uncommitted report. Do not paste live secret values into this file.*
