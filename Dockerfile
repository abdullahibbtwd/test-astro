# Astrology local API: Node Fastify + Python chart/reading bridges.
FROM node:22-bookworm AS node-deps
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

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
RUN apt-get update \
  && apt-get install -y --no-install-recommends python3 libstdc++6 \
  && rm -rf /var/lib/apt/lists/*

COPY --from=python-deps /opt/venv /opt/venv
COPY --from=node-deps /app/frontend/node_modules ./frontend/node_modules

# Full engine tree (bridges import across module folders).
COPY . .

ENV PATH="/opt/venv/bin:/usr/local/bin:$PATH"
ENV PYTHON=/opt/venv/bin/python
ENV ASTRO_PA_ROOT=/app
ENV HOST=0.0.0.0
ENV PORT=4020
ENV NODE_ENV=production

WORKDIR /app/frontend
EXPOSE 4020
CMD ["npx", "tsx", "local-api/server.ts"]
