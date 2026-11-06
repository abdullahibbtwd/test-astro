import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { clearAuthMode, wipeDemoTenant } from "./helpers";
import { buildLocalApp } from "../api/app";
import {
  isExpensiveRoute,
  readRateLimitConfig,
} from "../api/rate-limit";

test("expensive route classifier covers generation surfaces", () => {
  assert.equal(isExpensiveRoute("POST", "/v1/compatibility"), true);
  assert.equal(
    isExpensiveRoute("POST", "/v1/ask/threads/abc/messages"),
    true,
  );
  assert.equal(
    isExpensiveRoute("GET", "/v1/profiles/x/natal-reading"),
    true,
  );
  assert.equal(isExpensiveRoute("GET", "/v1/meta/config"), false);
  assert.equal(isExpensiveRoute("GET", "/v1/me"), false);
});

test("readRateLimitConfig honors env overrides", () => {
  const cfg = readRateLimitConfig({
    ASTRO_RATE_LIMIT_DISABLED: "1",
    ASTRO_RATE_LIMIT_WINDOW_MS: "10000",
    ASTRO_RATE_LIMIT_MAX: "5",
    ASTRO_RATE_LIMIT_EXPENSIVE_MAX: "2",
  } as NodeJS.ProcessEnv);
  assert.equal(cfg.disabled, true);
  assert.equal(cfg.windowMs, 10000);
  assert.equal(cfg.max, 5);
  assert.equal(cfg.expensiveMax, 2);
});

test("expensive endpoints return 429 when expensive max is exceeded", async () => {
  const prev = {
    disabled: process.env.ASTRO_RATE_LIMIT_DISABLED,
    max: process.env.ASTRO_RATE_LIMIT_MAX,
    expensive: process.env.ASTRO_RATE_LIMIT_EXPENSIVE_MAX,
    window: process.env.ASTRO_RATE_LIMIT_WINDOW_MS,
  };
  process.env.ASTRO_RATE_LIMIT_DISABLED = "0";
  process.env.ASTRO_RATE_LIMIT_MAX = "100";
  process.env.ASTRO_RATE_LIMIT_EXPENSIVE_MAX = "2";
  process.env.ASTRO_RATE_LIMIT_WINDOW_MS = "60000";

  await wipeDemoTenant("rate-limit@example.com");
  await clearAuthMode();
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), "rate-limit-"));
  const app = await buildLocalApp({ dbPath: path.join(folder, "state.sqlite") });
  try {
    const login = await app.inject({
      method: "POST",
      url: "/v1/auth/email/verify",
      payload: { email: "rate-limit@example.com", code: "000000" },
    });
    assert.equal(login.statusCode, 200, login.body);
    const headers = {
      authorization: `Bearer ${login.json().access_token}`,
    };
    // meta/config is cheap — should not burn expensive budget
    assert.equal(
      (await app.inject({ url: "/v1/meta/config", headers })).statusCode,
      200,
    );

    const hit = () =>
      app.inject({
        method: "POST",
        url: "/v1/compatibility",
        headers: { ...headers, "idempotency-key": String(Math.random()) },
        payload: {
          profile_a_id: "a",
          profile_b_id: "b",
          type: "love",
        },
      });

    const first = await hit();
    const second = await hit();
    const third = await hit();
    // First two may be 400/404 (missing profiles) but must not be 429.
    assert.notEqual(first.statusCode, 429, first.body);
    assert.notEqual(second.statusCode, 429, second.body);
    assert.equal(third.statusCode, 429, third.body);
    assert.equal(third.json().code, "rate_limited");
    assert.ok(Number(third.headers["retry-after"] ?? 0) >= 1);
  } finally {
    await app.close();
    await wipeDemoTenant("rate-limit@example.com");
    for (const [key, value] of Object.entries(prev)) {
      const envKey =
        key === "disabled"
          ? "ASTRO_RATE_LIMIT_DISABLED"
          : key === "max"
            ? "ASTRO_RATE_LIMIT_MAX"
            : key === "expensive"
              ? "ASTRO_RATE_LIMIT_EXPENSIVE_MAX"
              : "ASTRO_RATE_LIMIT_WINDOW_MS";
      if (value === undefined) delete process.env[envKey];
      else process.env[envKey] = value;
    }
  }
});
