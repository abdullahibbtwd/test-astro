"""Durable, shared integration-test spending cap. No prompts or credentials stored."""
import math
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

class BudgetExceeded(RuntimeError):
    pass

class Budget:
    def __init__(self, filename, limit=20):
        if not 0 < limit <= 20:
            raise ValueError("The user authorized at most US$20 total")
        self.filename = filename
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(filename, timeout=30)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, cap INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS calls (id INTEGER PRIMARY KEY, model TEXT, reserved INTEGER, charged INTEGER, state TEXT)')
            db.execute('INSERT OR IGNORE INTO settings VALUES (1,?)', (math.ceil(limit*1000000),))
            if db.execute('SELECT cap FROM settings WHERE id=1').fetchone()[0] != math.ceil(limit*1000000):
                raise ValueError('Existing budget must not be changed silently')
    def reserve(self, model, dollars):
        amount = math.ceil(dollars * 1000000)
        if amount <= 0: raise ValueError('Invalid reservation')
        with closing(sqlite3.connect(self.filename, timeout=30)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            total = db.execute('SELECT COALESCE(SUM(charged),0) FROM calls').fetchone()[0]
            cap = db.execute('SELECT cap FROM settings WHERE id=1').fetchone()[0]
            if total + amount > cap: raise BudgetExceeded('Integration testing budget exhausted')
            return db.execute('INSERT INTO calls(model,reserved,charged,state) VALUES (?,?,?,?)', (model, amount, amount, 'reserved')).lastrowid
    def settle(self, call_id, dollars):
        amount = math.ceil(dollars * 1000000)
        with closing(sqlite3.connect(self.filename, timeout=30)) as db, db:
            reserved = db.execute('SELECT reserved FROM calls WHERE id=?', (call_id,)).fetchone()[0]
            if amount < 0 or amount > reserved:
                raise BudgetExceeded('Provider usage exceeded reservation; stop and investigate')
            db.execute('UPDATE calls SET charged=?,state=? WHERE id=?', (amount, 'settled', call_id))
    def total(self):
        with closing(sqlite3.connect(self.filename, timeout=30)) as db:
            return db.execute('SELECT COALESCE(SUM(charged),0) FROM calls').fetchone()[0] / 1000000

# Standard text rates verified 2026-10-02. Cached inputs deliberately charged as uncached.
# https://ai.google.dev/gemini-api/docs/pricing
# https://developers.openai.com/api/docs/models/gpt-6-luna
RATES = {'gemini-3.7-flash': (0.75, 3.75), 'gpt-6-luna': (0.125, 0.50)}

def install_guard(client, filename):
    import json
    import os
    if os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1').rstrip('/') != 'https://api.openai.com/v1':
        raise BudgetExceeded('Unverified OpenAI endpoint/pricing')
    if os.environ.get('GOOGLE_GENAI_USE_VERTEXAI', '').lower() in ('1','true'):
        raise BudgetExceeded('Vertex pricing has not been verified for these tests')
    budget = Budget(filename)
    def wrap(original):
        def bounded(model, system, user, **kwargs):
            if date.today() > date(2026, 10, 9):
                raise BudgetExceeded('Reverify pricing before further integration tests')
            if model not in RATES: raise BudgetExceeded('Model has no verified price')
            rates = RATES[model]
            # Text-only requests. Bytes overestimate token counts; reserve extra for protocol overhead.
            size = len(json.dumps([system, user, kwargs.get('schema')], ensure_ascii=False).encode('utf-8')) + 4096
            if size > 250000: raise BudgetExceeded('Prompt exceeds verified short-context pricing')
            output = kwargs['max_tokens']
            if not 0 < output <= 64000: raise BudgetExceeded('Unbounded output request')
            reservation = budget.reserve(model, 2 * (size * rates[0] + output * rates[1]) / 1000000)
            response = original(model, system, user, **kwargs)
            usage = response.usage
            inputs = sum(usage.get(k, 0) for k in ('input_tokens','cache_read_input_tokens','cache_creation_input_tokens'))
            outputs = usage.get('output_tokens', 0)
            if inputs + outputs:
                budget.settle(reservation, (inputs * rates[0] + outputs * rates[1]) / 1000000)
            # Failed/unknown-outcome calls retain their entire reservation.
            return response
        return bounded
    # Disable Gemini's inner retries. Pipeline retries are each separately reserved.
    client.GEMINI_429_MAX_WAITS = 0
    client._PROVIDERS = {
        'gemini': (wrap(client._gemini_complete), client._gemini_transient),
        'openai': (wrap(client._openai_complete), client._openai_transient),
    }
    return budget
