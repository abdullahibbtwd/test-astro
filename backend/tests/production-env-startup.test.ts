/**
 * Startup with exactly the documented Coolify required production env list
 * (payments off). Names only in assertions — no secret values printed.
 */
import test from "node:test";
import assert from "node:assert/strict";
import os from "node:os";
import {
  checkConfig,
  REQUIRED_PRODUCTION_ENV_NAMES,
  paymentsEnabled,
  isProductionLike,
} from "../api/config-check";

/** Minimal values that satisfy refuse rules — fixtures only, not production. */
function minimalProductionEnv(): NodeJS.ProcessEnv {
  return {
    NODE_ENV: "production",
    DATABASE_URL: "postgres://app:strong-pass@db.internal:5432/astrology",
    AUTH_ENABLED: "1",
    SUPABASE_URL: "https://abcdefghijklmnopqrst.supabase.co",
    SUPABASE_SECRET_KEY: "sb_secret_test_fixture_only",
    ASTRO_DEMO_AUTH: "0",
    ASTRO_ALLOW_PAID: "0",
  };
}

test("production-like is NODE_ENV=production or ASTRO_PRODUCTION_LIKE=1", () => {
  assert.equal(isProductionLike({ NODE_ENV: "production" }), true);
  assert.equal(isProductionLike({ ASTRO_PRODUCTION_LIKE: "1" }), true);
  assert.equal(isProductionLike({ NODE_ENV: "development" }), false);
});

test("paymentsEnabled only when ASTRO_PAYMENT_PROVIDER is set", () => {
  assert.equal(paymentsEnabled({}), false);
  assert.equal(paymentsEnabled({ ASTRO_PAYMENT_PROVIDER: "unset" }), false);
  assert.equal(paymentsEnabled({ ASTRO_PAYMENT_PROVIDER: "fake" }), true);
  assert.equal(paymentsEnabled({ ASTRO_PAYMENT_PROVIDER: "revenuecat" }), true);
});

test("REQUIRED_PRODUCTION_ENV_NAMES matches Coolify minimal list", () => {
  assert.deepEqual([...REQUIRED_PRODUCTION_ENV_NAMES].sort(), [
    "ASTRO_DEMO_AUTH",
    "AUTH_ENABLED",
    "DATABASE_URL",
    "NODE_ENV",
    "SUPABASE_SECRET_KEY",
    "SUPABASE_URL",
  ]);
});

test("config:check passes with exactly the required production env set (payments off)", () => {
  const env = minimalProductionEnv();
  for (const name of REQUIRED_PRODUCTION_ENV_NAMES) {
    assert.ok(env[name] != null && env[name] !== "", name);
  }
  // No payment provider → webhook secret not required
  assert.equal(paymentsEnabled(env), false);
  const result = checkConfig(env, os.tmpdir());
  assert.equal(
    result.findings.filter((f) => f.level === "refuse").length,
    0,
    result.findings.map((f) => f.message).join("; "),
  );
  assert.equal(result.ok, true);
});

test("emergency rate-limit loosening uses MAX env vars, not DISABLED", () => {
  // Documented emergency path — raising caps must not trip refuse.
  const env = {
    ...minimalProductionEnv(),
    ASTRO_RATE_LIMIT_IP_MAX: "2000",
    ASTRO_RATE_LIMIT_MAX: "800",
    ASTRO_RATE_LIMIT_EXPENSIVE_MAX: "200",
    ASTRO_RATE_LIMIT_JOB_MAX: "600",
  };
  assert.equal(checkConfig(env, os.tmpdir()).ok, true);
  assert.equal(
    checkConfig(
      { ...minimalProductionEnv(), ASTRO_RATE_LIMIT_DISABLED: "1" },
      os.tmpdir(),
    ).ok,
    false,
  );
});
