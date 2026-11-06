#!/usr/bin/env bash
# Readiness check for paid AI / Ask enablement.
# NEVER sets ASTRO_ALLOW_PAID=1, never calls LLM providers, never prints secret values.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="$ROOT/backend"
cd "$BACKEND"

# Load .env for presence checks only (do not export blindly into a live API).
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

pass=0
warn=0
fail=0

ok() { echo "OK   $*"; pass=$((pass + 1)); }
note() { echo "WARN $*"; warn=$((warn + 1)); }
bad() { echo "FAIL $*"; fail=$((fail + 1)); }

mask_present() {
  local name="$1"
  if [[ -n "${!name:-}" ]]; then
    ok "$name is set (value hidden)"
  else
    bad "$name is missing"
  fi
}

echo "=== Paid / Ask enablement readiness (no side effects) ==="
echo "ASTRO_ALLOW_PAID=${ASTRO_ALLOW_PAID:-unset} (expected 0 for dry check)"
echo "ASTRO_ASK_ENABLED=${ASTRO_ASK_ENABLED:-unset}"
echo "ASTRO_GUEST_ONBOARDING=${ASTRO_GUEST_ONBOARDING:-unset}"
echo "ASTRO_PROGRESSIVE_READING=${ASTRO_PROGRESSIVE_READING:-unset}"
echo "ASTRO_BUDGET_LIMIT=${ASTRO_BUDGET_LIMIT:-unset→code default 20}"
echo "ASTRO_BUDGET_USER=${ASTRO_BUDGET_USER:-unset→shared}"
echo

if [[ "${ASTRO_ALLOW_PAID:-0}" == "1" ]]; then
  note "ASTRO_ALLOW_PAID is already 1 — this script still will not call models"
else
  ok "ASTRO_ALLOW_PAID is not enabled (safe default)"
fi

if [[ -n "${GEMINI_API_KEY:-}" || -n "${GOOGLE_API_KEY:-}" || -f "$HOME/.gemini_key" ]]; then
  ok "Gemini key material appears present (env or ~/.gemini_key)"
else
  bad "No Gemini key (GEMINI_API_KEY / GOOGLE_API_KEY / ~/.gemini_key) — required before ASTRO_ALLOW_PAID=1"
fi

if [[ -n "${OPENAI_BASE_URL:-}" ]]; then
  bad "OPENAI_BASE_URL is set — config:check / paid guard refuse; leave unset"
else
  ok "OPENAI_BASE_URL unset"
fi

if [[ -n "${GOOGLE_GENAI_USE_VERTEXAI:-}" ]]; then
  bad "GOOGLE_GENAI_USE_VERTEXAI is set — leave unset"
else
  ok "GOOGLE_GENAI_USE_VERTEXAI unset"
fi

if [[ "${ASTRO_ASK_ENABLED:-0}" == "1" ]]; then
  note "ASTRO_ASK_ENABLED=1 — Ask also needs paid + PA tree + usually OPENAI_API_KEY"
  if [[ -n "${OPENAI_API_KEY:-}" || -f "$HOME/.openai_key" ]]; then
    ok "OpenAI key material appears present for Ask"
  else
    bad "Ask enabled but no OPENAI_API_KEY / ~/.openai_key"
  fi
else
  ok "ASTRO_ASK_ENABLED is off"
fi

PA_ROOT="${ASTRO_PA_ROOT:-$BACKEND/engine}"
if [[ -d "$PA_ROOT" ]]; then
  ok "ASTRO_PA_ROOT / engine tree exists at $PA_ROOT"
else
  bad "Engine/PA root missing: $PA_ROOT"
fi

if [[ -n "${DATABASE_URL:-}" ]]; then
  ok "DATABASE_URL is set (value hidden)"
else
  note "DATABASE_URL unset — API defaults to local postgres URL"
fi

echo
echo "=== config:check (current process env; does not enable paid) ==="
if npm run config:check >/tmp/astro-config-check.out 2>&1; then
  ok "config:check exited 0"
  # Print non-secret summary lines only
  grep -E '^(OK|WARN|REFUSE|config:)' /tmp/astro-config-check.out || true
else
  bad "config:check failed — see /tmp/astro-config-check.out"
  grep -E '^(OK|WARN|REFUSE|config:|Error)' /tmp/astro-config-check.out || tail -20 /tmp/astro-config-check.out || true
fi

echo
echo "=== Summary: pass=$pass warn=$warn fail=$fail ==="
echo "Next: follow docs/AI_ASK_ENABLEMENT_RUNBOOK.md Stage 1+ only with spend approval."
echo "This script did not enable flags and did not call LLMs."

if [[ "$fail" -gt 0 ]]; then
  echo "RESULT=NOT_READY"
  exit 1
fi
echo "RESULT=READY_FOR_MANUAL_ENABLE"
exit 0
