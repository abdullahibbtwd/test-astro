"""Durable LLM spending ledger on PostgreSQL (Prisma-owned budget_* tables)."""
import json
import math
import os
from contextlib import closing
from datetime import date


class BudgetExceeded(RuntimeError):
    pass


def _pg():
    import psycopg

    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required for the budget ledger")
    return psycopg.connect(url)


class Budget:
    def __init__(self, filename, limit=20, user_id="shared"):
        # filename retained for call-site compatibility; storage is Postgres only.
        del filename
        if not 0 < limit <= 20:
            raise ValueError("The user authorized at most US$20 total")
        self.user_id = user_id or "shared"
        cap = math.ceil(limit * 1000000)
        with closing(_pg()) as db:
            db.execute(
                "INSERT INTO budget_settings(user_id, cap) VALUES (%s,%s) "
                "ON CONFLICT (user_id) DO NOTHING",
                (self.user_id, cap),
            )
            row = db.execute(
                "SELECT cap FROM budget_settings WHERE user_id=%s",
                (self.user_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError("budget_settings row missing after insert")
            if int(row[0]) != cap:
                raise ValueError("Existing budget must not be changed silently")
            db.commit()

    def reserve(self, model, dollars):
        amount = math.ceil(dollars * 1000000)
        if amount <= 0:
            raise ValueError("Invalid reservation")
        with closing(_pg()) as db:
            with db.transaction():
                # Lock the settings row only — never FOR UPDATE on the SUM.
                cap_row = db.execute(
                    "SELECT cap FROM budget_settings WHERE user_id=%s FOR UPDATE",
                    (self.user_id,),
                ).fetchone()
                if cap_row is None:
                    raise RuntimeError("budget_settings missing for user")
                cap = int(cap_row[0])
                total = int(
                    db.execute(
                        "SELECT COALESCE(SUM(charged),0) FROM budget_calls WHERE user_id=%s",
                        (self.user_id,),
                    ).fetchone()[0]
                )
                if total + amount > cap:
                    raise BudgetExceeded("Integration testing budget exhausted")
                row = db.execute(
                    "INSERT INTO budget_calls(user_id,model,reserved,charged,state) "
                    "VALUES (%s,%s,%s,%s,%s) RETURNING id",
                    (self.user_id, model, amount, amount, "reserved"),
                ).fetchone()
                return int(row[0])

    def settle(self, call_id, dollars):
        amount = math.ceil(dollars * 1000000)
        with closing(_pg()) as db:
            with db.transaction():
                reserved_row = db.execute(
                    "SELECT reserved FROM budget_calls WHERE id=%s AND user_id=%s",
                    (call_id, self.user_id),
                ).fetchone()
                if reserved_row is None:
                    raise BudgetExceeded("Unknown budget reservation")
                reserved = int(reserved_row[0])
                if amount < 0 or amount > reserved:
                    raise BudgetExceeded(
                        "Provider usage exceeded reservation; stop and investigate"
                    )
                db.execute(
                    "UPDATE budget_calls SET charged=%s,state=%s WHERE id=%s",
                    (amount, "settled", call_id),
                )

    def total(self):
        with closing(_pg()) as db:
            return (
                int(
                    db.execute(
                        "SELECT COALESCE(SUM(charged),0) FROM budget_calls WHERE user_id=%s",
                        (self.user_id,),
                    ).fetchone()[0]
                )
                / 1000000
            )


# Standard text rates verified 2026-10-02 (Flash free-tier defaults added for
# local Gemini-key testing). Cached inputs deliberately charged as uncached.
RATES = {
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.7-flash": (0.75, 3.75),
    "gemini-3.8-flash": (0.75, 3.75),
    "gpt-6-luna": (0.125, 0.50),
}


def _budget_log(entry):
    """Optional per-call ledger. Never include prompts, chart data, or keys."""
    path = os.environ.get("ASTRO_BUDGET_LOG")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=True) + "\n")


def install_guard(client, filename):
    import json

    if os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip(
        "/"
    ) != "https://api.openai.com/v1":
        raise BudgetExceeded("Unverified OpenAI endpoint/pricing")
    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in ("1", "true"):
        raise BudgetExceeded("Vertex pricing has not been verified for these tests")
    raw_limit = os.environ.get("ASTRO_BUDGET_LIMIT", "20")
    try:
        limit = float(raw_limit)
    except ValueError as error:
        raise BudgetExceeded("Invalid spending cap") from error
    budget = Budget(
        filename,
        limit,
        user_id=os.environ.get("ASTRO_BUDGET_USER", "shared"),
    )

    def wrap(original):
        def bounded(model, system, user, **kwargs):
            if date.today() > date(2026, 11, 16):
                raise BudgetExceeded("Reverify pricing before further integration tests")
            if model not in RATES:
                raise BudgetExceeded("Model has no verified price")
            rates = RATES[model]
            size = (
                len(
                    json.dumps(
                        [system, user, kwargs.get("schema")], ensure_ascii=False
                    ).encode("utf-8")
                )
                + 4096
            )
            if size > 250000:
                raise BudgetExceeded("Prompt exceeds verified short-context pricing")
            output = kwargs["max_tokens"]
            if not 0 < output <= 64000:
                raise BudgetExceeded("Unbounded output request")
            reserved = 2 * (size * rates[0] + output * rates[1]) / 1000000
            try:
                reservation = budget.reserve(model, reserved)
            except BudgetExceeded:
                _budget_log({"model": model, "error": "BudgetExceeded", "reserved_usd": reserved})
                raise
            try:
                response = original(model, system, user, **kwargs)
            except Exception as error:
                _budget_log({"model": model, "error": type(error).__name__, "reserved_usd": reserved})
                raise
            usage = response.usage
            inputs = sum(
                usage.get(k, 0)
                for k in (
                    "input_tokens",
                    "cache_read_input_tokens",
                    "cache_creation_input_tokens",
                )
            )
            outputs = usage.get("output_tokens", 0)
            spent = (inputs * rates[0] + outputs * rates[1]) / 1000000 if inputs + outputs else 0
            if inputs + outputs:
                budget.settle(reservation, spent)
            _budget_log({
                "model": model,
                "input_tokens": inputs,
                "output_tokens": outputs,
                "usd": spent,
            })
            return response

        return bounded

    client.GEMINI_429_MAX_WAITS = 0
    client._PROVIDERS = {
        "gemini": (wrap(client._gemini_complete), client._gemini_transient),
        "openai": (wrap(client._openai_complete), client._openai_transient),
    }
    return budget
