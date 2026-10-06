"""pa_constants.py - every tunable of the Personal Astrologist (PA_00..04) in one place."""

from __future__ import annotations

import os

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ASK_RUN = os.path.join(ROOT, "ask_run")
CACHE_ROOT = os.path.join(ASK_RUN, "_cache")          # per chart: <chart_key>/ (Phase 0 §12)

# --- models (PA_00 P5): config, so switching later is a one-line change ----------------------
PA_MODEL = "gpt-6-luna"
PA_PLANNER_EFFORT = "none"
PA_COMPOSER_EFFORT = "none"
PA_PLANNER_MAX_TOKENS = 1200
PA_COMPOSER_MAX_TOKENS = 2400
# list price per 1M tokens (USD) for the cost estimate in the audit
PRICE = {"gpt-6-luna": {"input": 0.10, "cached": 0.01, "output": 0.50}}

# --- turn limits (PA_04 §8) ---------------------------------------------------------------------
MAX_CALLS = 4
PA_HISTORY_MESSAGES = 8
PA_HISTORY_ASSISTANT_CHARS = 400
PA_TOOL_TIMEOUT_S = 45
PA_TURN_TIMEOUT_S = 90
QUESTION_MAX_CHARS = 1000
DELTA_WORDS = 8

# --- evidence caps (PA_01 §2.3, §3.4) ----------------------------------------------------------------
NATAL_CAP_ONE = 24
NATAL_CAP_MANY = 32
NATAL_CAP_MORE = 40
CLASSICAL_MAX_SHARE = 1 / 3                    # the 2:1 modern:classical quota
CAP_RECORDS = 40
CAP_PROSE = 3
CAP_PROSE_WORDS = 250
CAP_ITEMS = 30
MIN_RECORDS_PER_CALL = 4

# --- horizons (PA_00 D10) -------------------------------------------------------------------------------
DAY_PAST_DAYS = 7
DAY_FUTURE_DAYS = 365
CAL_MONTHS = 12
BEST_DAYS_DAYS = 90
BEST_DAYS_DEFAULT_DAYS = 30
SPAN_DEFAULT_DAYS = 90

# --- versions (cache invalidation) ------------------------------------------------------------------------
DOSSIER_SCHEMA = "pa-dossier-1"
PACK_SCHEMA = "pa-pack-1"
AUDIT_SCHEMA = "pa-audit-1"
PROMPT_VERSION = "pa-prompt-1"
