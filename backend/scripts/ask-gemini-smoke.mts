/**
 * Approved paid Ask smoke: astrology_test, fake data, fresh US$1 cap,
 * three questions of different length. Reports cost per answer (no secrets).
 *
 * Usage (from backend/): npx tsx scripts/ask-gemini-smoke.mts
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const allow = new Set([
  "GEMINI_API_KEY",
  "GOOGLE_API_KEY",
  "ASTRO_LLM_MODEL",
  "ASTRO_CHEAP_MODEL",
  "ASTRO_ASK_MODEL",
  "GEMINI_THINKING_LEVEL",
]);
for (const line of fs.readFileSync(path.join(root, ".env"), "utf8").split("\n")) {
  const match = /^([A-Z0-9_]+)=(.*)$/.exec(line.trim());
  if (!match || !allow.has(match[1])) continue;
  let value = match[2].trim();
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  )
    value = value.slice(1, -1);
  if (value) process.env[match[1]] = value;
}

const keyNames = ["GEMINI_API_KEY", "GOOGLE_API_KEY"].filter(
  (n) => process.env[n],
);
if (!keyNames.length) {
  console.log(JSON.stringify({ fatal: "no_gemini_key_var" }));
  process.exit(1);
}

const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), "ask-gemini-smoke-"));
const logPath = path.join(dataDir, "budget.jsonl");
const budgetUser = `ask-smoke-${Date.now()}`;

process.env.DATABASE_URL =
  "postgres://astrology:astrology@127.0.0.1:5432/astrology_test";
process.env.ASTRO_ALLOW_PAID = "1";
process.env.ASTRO_ASK_ENABLED = "1";
process.env.ASTRO_DEMO_AUTH = "1";
process.env.ASTRO_GUEST_ONBOARDING = "0";
process.env.ASTRO_PROGRESSIVE_READING = "0";
process.env.ASTRO_BUDGET_LIMIT = "1";
process.env.ASTRO_BUDGET_USER = budgetUser;
process.env.ASTRO_BUDGET_LOG = logPath;
process.env.PYTHON = path.join(root, ".venv/bin/python");
process.env.DATA_DIR = dataDir;
process.env.ASTRO_PA_ROOT = path.join(root, "backend/engine");
process.env.AUTH_ENABLED = "0";
delete process.env.SUPABASE_URL;
delete process.env.SUPABASE_SECRET_KEY;
delete process.env.SUPABASE_PUBLISHABLE_KEY;
delete process.env.SUPABASE_JWKS_URL;
delete process.env.OPENAI_API_KEY;
delete process.env.OPENAI_BASE_URL;
delete process.env.GOOGLE_GENAI_USE_VERTEXAI;
delete process.env.ANTHROPIC_API_KEY;
if (!process.env.ASTRO_ASK_MODEL)
  process.env.ASTRO_ASK_MODEL =
    process.env.ASTRO_LLM_MODEL || "gemini-3.5-flash-lite";

const { buildLocalApp } = await import("../api/app.ts");
const { prisma } = await import("../api/db.ts");
const { clearAuthMode, clearUsageCounters } = await import(
  "../tests/helpers.ts"
);
const { fixture } = await import("../mock/fixtures.ts");

function readLog() {
  if (!fs.existsSync(logPath)) return [];
  return fs
    .readFileSync(logPath, "utf8")
    .split("\n")
    .filter(Boolean)
    .map((l) => JSON.parse(l));
}
function summarize(rows: any[]) {
  const settled = rows.filter(
    (r) => !r.retry && !r.void && !r.error && typeof r.usd === "number",
  );
  return {
    settled_calls: settled.length,
    models: [...new Set(settled.map((r) => r.model))],
    input_tokens: settled.reduce((s, r) => s + (r.input_tokens || 0), 0),
    output_tokens: settled.reduce((s, r) => s + (r.output_tokens || 0), 0),
    usd: Number(settled.reduce((s, r) => s + r.usd, 0).toFixed(6)),
  };
}

await clearAuthMode();
await prisma().$executeRawUnsafe(
  `DELETE FROM budget_calls WHERE user_id = $1`,
  budgetUser,
);
await prisma().$executeRawUnsafe(
  `DELETE FROM budget_settings WHERE user_id = $1`,
  budgetUser,
);

const app = await buildLocalApp({
  dbPath: path.join(dataDir, "app.sqlite"),
  allowPaid: true,
  progressiveReadings: false,
  guestOnboarding: false,
});

const questions = [
  { label: "short", text: "What is my Sun sign?" },
  {
    label: "medium",
    text: "Briefly, what stands out about my career and work themes this season?",
  },
  {
    label: "long",
    text:
      "Using only my birth chart, explain how my Sun, Moon, and Ascendant work together " +
      "in everyday life, and mention one practical caution for the next month without predicting events.",
  },
];

const reports: any[] = [];
try {
  console.log(
    JSON.stringify({
      setup: true,
      db: "astrology_test",
      budget_user: budgetUser,
      cap_usd: 1,
      ask_model: process.env.ASTRO_ASK_MODEL,
      key_vars: keyNames,
    }),
  );

  const login = await app.inject({
    method: "POST",
    url: "/v1/auth/email/verify",
    payload: { email: "ask-smoke@example.com", code: "000000" },
  });
  if (login.statusCode !== 200) {
    throw new Error(`login_${login.statusCode}`);
  }
  const headers = { authorization: `Bearer ${login.json().access_token}` };
  const tenantId = login.json().me.user_id as string;
  await clearUsageCounters(tenantId);

  const profile = {
    ...fixture("profile.0.en"),
    label: "Smoke Chart",
    birth: {
      ...fixture("profile.0.en").birth,
      date: "1991-06-15",
      time: "09:30",
    },
  };
  const { openStore } = await import("../tests/helpers.ts");
  const store = await openStore();
  await store.runAsAsync(tenantId, async () => {
    await store.put("profile:" + profile.profile_id, profile);
  });
  await store.close();

  const thread = await app.inject({
    method: "POST",
    url: "/v1/ask/threads",
    headers,
    payload: { profile_id: profile.profile_id },
  });
  console.log(JSON.stringify({ thread: thread.statusCode }));
  if (thread.statusCode !== 200) {
    throw new Error(`thread_${thread.statusCode}:${String(thread.body).slice(0, 200)}`);
  }
  const threadId = thread.json().thread_id as string;

  for (const q of questions) {
    const before = readLog().length;
    const started = Date.now();
    const res = await app.inject({
      method: "POST",
      url: `/v1/ask/threads/${threadId}/messages?lang=en`,
      headers,
      payload: { text: q.text },
    });
    const ledger = summarize(readLog().slice(before));
    const done = /event: done/.test(res.body);
    const failed = /event: error/.test(res.body);
    const got = await app.inject({
      url: `/v1/ask/threads/${threadId}`,
      headers,
    });
    const messages = got.json()?.messages ?? [];
    const assistant = [...messages]
      .reverse()
      .find((m: any) => m.role === "assistant");
    const report = {
      question: q.label,
      chars: q.text.length,
      http: res.statusCode,
      ms: Date.now() - started,
      done,
      failed,
      assistant_status: assistant?.status ?? null,
      answer_chars:
        typeof assistant?.text === "string" ? assistant.text.length : 0,
      ledger,
    };
    reports.push(report);
    console.log(JSON.stringify({ report }));
    if (!done || failed || assistant?.status !== "complete") break;
  }
} catch (error: any) {
  console.log(
    JSON.stringify({
      fatal: String(error?.message ?? error).slice(0, 300),
    }),
  );
} finally {
  const rows = await prisma().$queryRawUnsafe<
    { state: string; calls: number; usd: number }[]
  >(
    `SELECT state, COUNT(*)::int AS calls, COALESCE(SUM(charged),0)::float8 / 1000000 AS usd
     FROM budget_calls WHERE user_id = $1 GROUP BY state ORDER BY state`,
    budgetUser,
  );
  const me = reports.length
    ? null
    : null;
  console.log(
    JSON.stringify({
      done: true,
      ask_model: process.env.ASTRO_ASK_MODEL,
      reports,
      log: summarize(readLog()),
      ledger: rows.map((r) => ({
        state: r.state,
        calls: Number(r.calls),
        usd: Number(r.usd),
      })),
      proposal_note:
        "Propose ASTRO_DAILY_ASK_LIMIT and per-user budget ceiling from these costs",
      me_unused: me,
    }),
  );
  await app.close();
}
