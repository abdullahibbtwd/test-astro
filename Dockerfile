# Astrology local API: Node Fastify + Python chart/reading bridges.
FROM node:22-bookworm AS frontend-deps
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM node:22-bookworm AS backend-deps
WORKDIR /app/backend
COPY backend/package.json backend/package-lock.json ./
COPY backend/prisma ./prisma
COPY backend/prisma.config.ts ./
RUN npm ci && npx prisma generate

FROM python:3.11-slim-bookworm AS python-deps
WORKDIR /app
RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential \
  && rm -rf /var/lib/apt/lists/*
COPY requirements-handoff.txt ./
RUN python -m venv /opt/venv \
  && /opt/venv/bin/pip install --no-cache-dir -r requirements-handoff.txt \
  && /opt/venv/bin/pip install --no-cache-dir "psycopg[binary]==3.2.9"

FROM node:22-bookworm-slim
WORKDIR /app
# Native wheels (e.g. swisseph) need C++ runtime libs from the slim base.
RUN apt-get update \
  && apt-get install -y --no-install-recommends libstdc++6 \
  && rm -rf /var/lib/apt/lists/*

# The venv's python symlink targets /usr/local/bin/python from the python image.
# Copy that interpreter (and site libs) or places/charts spawn fails with ENOENT → 500.
COPY --from=python-deps /usr/local /usr/local
COPY --from=python-deps /opt/venv /opt/venv
COPY --from=frontend-deps /app/frontend/node_modules ./frontend/node_modules
COPY --from=backend-deps /app/backend/node_modules ./backend/node_modules

# Full engine tree (bridges import across module folders).
COPY . .

ENV PATH="/opt/venv/bin:/usr/local/bin:$PATH"
ENV PYTHON=/opt/venv/bin/python
ENV ASTRO_PA_ROOT=/app/backend/engine
ENV DATA_DIR=/app/backend/.local-data
ENV HOST=0.0.0.0
ENV PORT=4020
ENV NODE_ENV=production

WORKDIR /app/backend
EXPOSE 4020
# migrateDeploy() also runs inside api/server.ts; keep an explicit step for clarity.
CMD ["sh", "-c", "npx prisma migrate deploy && npx tsx api/server.ts"]
