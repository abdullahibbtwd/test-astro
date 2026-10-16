# Astrology app

Start with the [frontend team handoff](docs/frontend/FRONTEND_TEAM_HANDOFF.md), dated 6 October 2026.

This repository contains the Expo/React Native app, its private preview API, deterministic astrology calculations, reading layers and Personal Astrologist. The Android development preview works with real calculations/readings; it is not a production release.

Remaining priorities: payment policy and implementation, UX/UI refinement in the current design direction, and native iOS completion. The handoff also records hosting, multiuser and release dependencies.

- [New-developer setup](docs/handoff/SETUP.md)
- [Workstreams and decisions](docs/handoff/REMAINING_WORK.md)
- [Verification and acceptance](docs/handoff/ACCEPTANCE.md)
- [Current design direction](docs/handoff/DESIGN_DIRECTION.md)

Use the complete repository, not just `frontend/`. The private fixture ZIP is included at `fixtures/frontend-demo-fixtures.zip`; extract it as described in the setup guide before starting either API. Obtain the original design kit from Radul. Credentials, live account data and SDK installations are intentionally not shipped.

## Docker (API + PostgreSQL)

**Full stack** (API image + Postgres) — rebuild when the Dockerfile or deps change:

```bash
cp .env.docker.example .env   # optional
docker compose up --build
```

API listens on `http://localhost:4020/v1`. Without Supabase env, sign in with any email and code `000000` (each email is an isolated account). Set `AUTH_ENABLED=1` plus Supabase URL/key for real multi-user auth; omit `AUTH_OWNER_EMAIL` so every confirmed user gets their own tenant.

**Dev (Postgres only)** — API runs on the host so TypeScript/Python edits apply without rebuilding:

```bash
# Stop the full stack if it is running: docker compose down
docker compose -f docker-compose.dev.yml up -d

cd backend
export DATABASE_URL=postgres://astrology:astrology@127.0.0.1:5432/astrology
export PYTHON="${PYTHON:-$(cd .. && pwd)/.venv/bin/python}"
export ASTRO_PA_ROOT="$(pwd)/engine"
export DATA_DIR="$(pwd)/.local-data"
# Load LLM flags/keys from repo-root .env as needed, e.g. set -a; source ../.env; set +a
npm run local-api
```

Same API URL: `http://localhost:4020/v1`. Dev Postgres uses volume `pgdata-dev` (separate from the full-stack `pgdata`).
