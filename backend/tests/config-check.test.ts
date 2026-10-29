import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {
  checkConfig,
  formatConfigCheck,
  geminiKeyPresent,
} from "../api/config-check";

const base = (): NodeJS.ProcessEnv => ({
  AUTH_ENABLED: "0",
  ASTRO_ALLOW_PAID: "0",
  ASTRO_DEMO_AUTH: "0",
});

const refuses = (env: NodeJS.ProcessEnv, home?: string) => {
  const result = checkConfig(env, home ?? os.tmpdir());
  assert.equal(result.ok, false);
  return result.findings.filter((f) => f.level === "refuse");
};

const warns = (env: NodeJS.ProcessEnv, home?: string) => {
  const result = checkConfig(env, home ?? os.tmpdir());
  return result.findings.filter((f) => f.level === "warn");
};

test("clean non-production env passes with no findings", () => {
  const result = checkConfig(base(), os.tmpdir());
  assert.equal(result.ok, true);
  assert.deepEqual(result.findings, []);
});

test("REFUSE: NODE_ENV=production with ASTRO_DEMO_AUTH=1", () => {
  const bad = refuses({
    ...base(),
    NODE_ENV: "production",
    ASTRO_DEMO_AUTH: "1",
    DATABASE_URL: "postgres://prod:secret@db.internal:5432/astrology",
  });
  assert.ok(bad.some((f) => f.names.includes("ASTRO_DEMO_AUTH")));
  assert.match(formatConfigCheck({ ok: false, findings: bad }), /REFUSE/);
});

test("REFUSE: AUTH_ENABLED on but SUPABASE_URL missing", () => {
  const bad = refuses({
    ...base(),
    AUTH_ENABLED: "1",
  });
  assert.ok(
    bad.some(
      (f) =>
        f.names.includes("AUTH_ENABLED") && f.names.includes("SUPABASE_URL"),
    ),
  );
  // Unset AUTH_ENABLED is also "on" (matches server.ts).
  const unset = refuses({ ...base(), AUTH_ENABLED: undefined });
  assert.ok(unset.some((f) => f.names.includes("SUPABASE_URL")));
});

test("REFUSE: ASTRO_ALLOW_PAID=1 without Gemini key", () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "cfg-nokey-"));
  const bad = refuses(
    {
      ...base(),
      ASTRO_ALLOW_PAID: "1",
    },
    home,
  );
  assert.ok(bad.some((f) => f.names.includes("ASTRO_ALLOW_PAID")));
  assert.equal(geminiKeyPresent({ ...base(), ASTRO_ALLOW_PAID: "1" }, home), false);
});

test("ASTRO_ALLOW_PAID=1 passes when ~/.gemini_key exists (no value printed)", () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "cfg-key-"));
  fs.writeFileSync(path.join(home, ".gemini_key"), "x".repeat(20));
  const result = checkConfig({ ...base(), ASTRO_ALLOW_PAID: "1" }, home);
  assert.equal(result.ok, true);
  assert.equal(geminiKeyPresent({}, home), true);
  assert.doesNotMatch(formatConfigCheck(result), /xxxxx|GEMINI_API_KEY=/);
});

test("REFUSE: OPENAI_BASE_URL is set", () => {
  const bad = refuses({
    ...base(),
    OPENAI_BASE_URL: "https://api.openai.com/v1",
  });
  assert.ok(bad.some((f) => f.names.includes("OPENAI_BASE_URL")));
});

test("REFUSE: GOOGLE_GENAI_USE_VERTEXAI is set", () => {
  const bad = refuses({
    ...base(),
    GOOGLE_GENAI_USE_VERTEXAI: "1",
  });
  assert.ok(bad.some((f) => f.names.includes("GOOGLE_GENAI_USE_VERTEXAI")));
});

test("REFUSE: production DATABASE_URL with default astrology/astrology credentials", () => {
  const bad = refuses({
    ...base(),
    NODE_ENV: "production",
    DATABASE_URL: "postgres://astrology:astrology@db:5432/astrology",
  });
  assert.ok(bad.some((f) => f.message.includes("default astrology/astrology")));
});

test("REFUSE: production DATABASE_URL with host 127.0.0.1", () => {
  const bad = refuses({
    ...base(),
    NODE_ENV: "production",
    DATABASE_URL: "postgres://app:secret@127.0.0.1:5432/astrology",
  });
  assert.ok(bad.some((f) => f.message.includes("127.0.0.1")));
});

test("production with non-default remote DATABASE_URL passes refuse rules", () => {
  const result = checkConfig(
    {
      ...base(),
      NODE_ENV: "production",
      DATABASE_URL: "postgres://app:secret@db.internal:5432/astrology",
    },
    os.tmpdir(),
  );
  assert.equal(
    result.findings.filter((f) => f.level === "refuse").length,
    0,
  );
  assert.equal(result.ok, true);
});

test("WARN: AUTH_OWNER_EMAIL is set", () => {
  const w = warns({
    ...base(),
    AUTH_ENABLED: "1",
    SUPABASE_URL: "https://proj.supabase.co",
    SUPABASE_SECRET_KEY: "secret",
    AUTH_OWNER_EMAIL: "owner@example.com",
  });
  assert.ok(w.some((f) => f.names.includes("AUTH_OWNER_EMAIL")));
  // Format must not include the email value.
  assert.doesNotMatch(
    formatConfigCheck({ ok: true, findings: w }),
    /owner@example\.com/,
  );
});

test("WARN: ASTRO_BUDGET_LIMIT or ASTRO_BUDGET_USER is set", () => {
  const limit = warns({ ...base(), ASTRO_BUDGET_LIMIT: "5" });
  assert.ok(limit.some((f) => f.names.includes("ASTRO_BUDGET_LIMIT")));
  const user = warns({ ...base(), ASTRO_BUDGET_USER: "alice" });
  assert.ok(user.some((f) => f.names.includes("ASTRO_BUDGET_USER")));
  assert.doesNotMatch(
    formatConfigCheck({ ok: true, findings: user }),
    /\balice\b/,
  );
});

test("WARN: SUPABASE_SECRET_KEY missing when auth URL is configured", () => {
  const w = warns({
    ...base(),
    AUTH_ENABLED: "1",
    SUPABASE_URL: "https://proj.supabase.co",
  });
  assert.ok(w.some((f) => f.names.includes("SUPABASE_SECRET_KEY")));
});

test("WARN: SUPABASE_JWKS_URL host differs from SUPABASE_URL", () => {
  const w = warns({
    ...base(),
    AUTH_ENABLED: "1",
    SUPABASE_URL: "https://proj.supabase.co",
    SUPABASE_SECRET_KEY: "secret",
    SUPABASE_JWKS_URL: "https://other.example.com/jwks",
  });
  assert.ok(
    w.some(
      (f) =>
        f.names.includes("SUPABASE_JWKS_URL") &&
        f.names.includes("SUPABASE_URL"),
    ),
  );
  assert.doesNotMatch(
    formatConfigCheck({ ok: true, findings: w }),
    /other\.example\.com|proj\.supabase/,
  );
});

test("same-host SUPABASE_JWKS_URL does not warn", () => {
  const w = warns({
    ...base(),
    AUTH_ENABLED: "1",
    SUPABASE_URL: "https://proj.supabase.co",
    SUPABASE_SECRET_KEY: "secret",
    SUPABASE_JWKS_URL:
      "https://proj.supabase.co/auth/v1/.well-known/jwks.json",
  });
  assert.ok(!w.some((f) => f.names.includes("SUPABASE_JWKS_URL")));
});
