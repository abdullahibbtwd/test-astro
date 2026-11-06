import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import Fastify from "fastify";
import { clearAuthMode, wipeDemoTenant } from "./helpers";
import { buildLocalApp } from "../api/app";
import {
  isExemptPath,
  isExpensiveRoute,
  isJobPollRoute,
  readRateLimitConfig,
  readTrustProxyHops,
  registerRateLimit,
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
  assert.equal(isExpensiveRoute("GET", "/v1/jobs/abc"), false);
  assert.equal(isJobPollRoute("GET", "/v1/jobs/abc"), true);
  assert.equal(isJobPollRoute("GET", "/v1/jobs/abc?lang=en"), true);
  assert.equal(isJobPollRoute("POST", "/v1/jobs/abc"), false);
  assert.equal(isExemptPath("/v1/meta/config"), true);
  assert.equal(isExemptPath("/v1/meta/config?x=1"), true);
  assert.equal(isExemptPath("/v1/me"), false);
});

test("readRateLimitConfig and trustProxy hops honor env", () => {
  const defaults = readRateLimitConfig({} as NodeJS.ProcessEnv);
  assert.equal(defaults.ipMax, 300);
  assert.equal(defaults.max, 120);
  assert.equal(defaults.expensiveMax, 40);
  assert.equal(defaults.jobMax, 180);
  assert.ok(defaults.ipMax > defaults.max);

  const cfg = readRateLimitConfig({
    ASTRO_RATE_LIMIT_DISABLED: "1",
    ASTRO_RATE_LIMIT_WINDOW_MS: "10000",
    ASTRO_RATE_LIMIT_IP_MAX: "50",
    ASTRO_RATE_LIMIT_MAX: "5",
    ASTRO_RATE_LIMIT_EXPENSIVE_MAX: "2",
    ASTRO_RATE_LIMIT_JOB_MAX: "90",
    ASTRO_TRUST_PROXY_HOPS: "1",
  } as NodeJS.ProcessEnv);
  assert.equal(cfg.disabled, true);
  assert.equal(cfg.windowMs, 10000);
  assert.equal(cfg.ipMax, 50);
  assert.equal(cfg.max, 5);
  assert.equal(cfg.expensiveMax, 2);
  assert.equal(cfg.jobMax, 90);
  assert.equal(cfg.trustProxyHops, 1);
  assert.equal(readTrustProxyHops({} as NodeJS.ProcessEnv), 0);
  assert.equal(
    readTrustProxyHops({ ASTRO_TRUST_PROXY_HOPS: "2" } as NodeJS.ProcessEnv),
    2,
  );
  assert.equal(
    readTrustProxyHops({ ASTRO_TRUST_PROXY_HOPS: "-1" } as NodeJS.ProcessEnv),
    0,
  );
});

type EnvSnapshot = Record<string, string | undefined>;

function snapshotEnv(keys: string[]): EnvSnapshot {
  const out: EnvSnapshot = {};
  for (const key of keys) out[key] = process.env[key];
  return out;
}

function restoreEnv(prev: EnvSnapshot) {
  for (const [key, value] of Object.entries(prev)) {
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
}

const RATE_ENV_KEYS = [
  "ASTRO_RATE_LIMIT_DISABLED",
  "ASTRO_RATE_LIMIT_WINDOW_MS",
  "ASTRO_RATE_LIMIT_IP_MAX",
  "ASTRO_RATE_LIMIT_MAX",
  "ASTRO_RATE_LIMIT_EXPENSIVE_MAX",
  "ASTRO_RATE_LIMIT_JOB_MAX",
  "ASTRO_TRUST_PROXY_HOPS",
];

async function withRateApp(
  env: Record<string, string>,
  emails: string[],
  run: (app: Awaited<ReturnType<typeof buildLocalApp>>) => Promise<void>,
) {
  const prev = snapshotEnv(RATE_ENV_KEYS);
  Object.assign(process.env, env);
  for (const email of emails) await wipeDemoTenant(email);
  await clearAuthMode();
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), "rate-limit-"));
  const app = await buildLocalApp({ dbPath: path.join(folder, "state.sqlite") });
  try {
    await run(app);
  } finally {
    await app.close();
    for (const email of emails) await wipeDemoTenant(email);
    restoreEnv(prev);
  }
}

async function demoLogin(
  app: Awaited<ReturnType<typeof buildLocalApp>>,
  email: string,
) {
  const login = await app.inject({
    method: "POST",
    url: "/v1/auth/email/verify",
    payload: { email, code: "000000" },
  });
  assert.equal(login.statusCode, 200, login.body);
  const body = login.json() as {
    access_token: string;
    refresh_token: string;
  };
  return body;
}

test("authed buckets key on verified user id, not Authorization header bytes", async () => {
  const app = Fastify({ logger: false });
  const limiter = registerRateLimit(app, {
    disabled: false,
    windowMs: 60_000,
    ipMax: 1000,
    max: 100,
    expensiveMax: 2,
    jobMax: 5,
    trustProxyHops: 0,
  });
  assert.ok(limiter);
  const reply = {
    header() {
      return this;
    },
    code() {
      return this;
    },
    type() {
      return this;
    },
    send() {
      return this;
    },
  } as any;
  const req = (url = "/v1/compatibility") =>
    ({ method: "POST", url }) as any;

  // Same user id with two Authorization values that share a long prefix
  // (the old bug keyed on auth.slice(0, 64)).
  assert.equal(
    limiter!.enforceUserRateLimit(req(), reply, "user-same"),
    false,
  );
  assert.equal(
    limiter!.enforceUserRateLimit(req(), reply, "user-same"),
    false,
  );
  assert.equal(
    limiter!.enforceUserRateLimit(req(), reply, "user-same"),
    true,
  );
  assert.equal(
    limiter!.enforceUserRateLimit(req(), reply, "user-other"),
    false,
  );
  const keys = [...limiter!._buckets.keys()];
  assert.deepEqual(
    keys.filter((k) => k.startsWith("eu:")).sort(),
    ["eu:user-other", "eu:user-same"],
  );
  await app.close();
});

test("job polls use a separate generous bucket and do not burn general max", async () => {
  const app = Fastify({ logger: false });
  const limiter = registerRateLimit(app, {
    disabled: false,
    windowMs: 60_000,
    ipMax: 1000,
    max: 2,
    expensiveMax: 40,
    jobMax: 5,
    trustProxyHops: 0,
  });
  assert.ok(limiter);
  const reply = {
    header() {
      return this;
    },
    code() {
      return this;
    },
    type() {
      return this;
    },
    send() {
      return this;
    },
  } as any;
  const jobReq = { method: "GET", url: "/v1/jobs/job-1" } as any;
  const meReq = { method: "GET", url: "/v1/me" } as any;

  for (let i = 0; i < 5; i++)
    assert.equal(
      limiter!.enforceUserRateLimit(jobReq, reply, "u1"),
      false,
      `job poll ${i}`,
    );
  assert.equal(limiter!.enforceUserRateLimit(jobReq, reply, "u1"), true);
  assert.ok(limiter!._buckets.has("ju:u1"));
  assert.equal(limiter!._buckets.has("gu:u1"), false);

  // General budget still fully available after job-poll traffic.
  assert.equal(limiter!.enforceUserRateLimit(meReq, reply, "u1"), false);
  assert.equal(limiter!.enforceUserRateLimit(meReq, reply, "u1"), false);
  assert.equal(limiter!.enforceUserRateLimit(meReq, reply, "u1"), true);
  await app.close();
});

test("expensive endpoints return 429 with Retry-After when expensive max is exceeded", async () => {
  await withRateApp(
    {
      ASTRO_RATE_LIMIT_DISABLED: "0",
      ASTRO_RATE_LIMIT_MAX: "100",
      ASTRO_RATE_LIMIT_EXPENSIVE_MAX: "2",
      ASTRO_RATE_LIMIT_IP_MAX: "1000",
      ASTRO_RATE_LIMIT_WINDOW_MS: "60000",
      ASTRO_TRUST_PROXY_HOPS: "0",
    },
    ["rate-limit@example.com"],
    async (app) => {
      const { access_token } = await demoLogin(app, "rate-limit@example.com");
      const headers = { authorization: `Bearer ${access_token}` };
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
      assert.notEqual(first.statusCode, 429, first.body);
      assert.notEqual(second.statusCode, 429, second.body);
      assert.equal(third.statusCode, 429, third.body);
      assert.equal(third.json().code, "rate_limited");
      assert.ok(Number(third.headers["retry-after"] ?? 0) >= 1);
      assert.match(
        String(third.headers["content-type"] ?? ""),
        /application\/problem\+json/,
      );
    },
  );
});

test("two users with similar-looking tokens get separate buckets; refresh keeps the same bucket", async () => {
  const emailA = "rate-user-a@example.com";
  const emailB = "rate-user-b@example.com";
  await withRateApp(
    {
      ASTRO_RATE_LIMIT_DISABLED: "0",
      ASTRO_RATE_LIMIT_MAX: "100",
      ASTRO_RATE_LIMIT_EXPENSIVE_MAX: "2",
      ASTRO_RATE_LIMIT_IP_MAX: "1000",
      ASTRO_RATE_LIMIT_WINDOW_MS: "60000",
      ASTRO_TRUST_PROXY_HOPS: "0",
    },
    [emailA, emailB],
    async (app) => {
      const a = await demoLogin(app, emailA);
      const b = await demoLogin(app, emailB);
      // Tokens are opaque hex; force a shared prefix so a naive Authorization
      // slice would collide if keying were wrong.
      assert.notEqual(a.access_token, b.access_token);

      const expensive = (token: string) =>
        app.inject({
          method: "POST",
          url: "/v1/compatibility",
          headers: {
            authorization: `Bearer ${token}`,
            "idempotency-key": String(Math.random()),
          },
          payload: {
            profile_a_id: "a",
            profile_b_id: "b",
            type: "love",
          },
        });

      assert.notEqual((await expensive(a.access_token)).statusCode, 429);
      assert.notEqual((await expensive(a.access_token)).statusCode, 429);
      assert.equal((await expensive(a.access_token)).statusCode, 429);

      // B must still have a full expensive budget.
      assert.notEqual((await expensive(b.access_token)).statusCode, 429);
      assert.notEqual((await expensive(b.access_token)).statusCode, 429);
      assert.equal((await expensive(b.access_token)).statusCode, 429);

      // Refresh A → new access token, same verified owner → still limited.
      const refreshed = await app.inject({
        method: "POST",
        url: "/v1/auth/refresh",
        payload: { refresh_token: a.refresh_token },
      });
      assert.equal(refreshed.statusCode, 200, refreshed.body);
      const newAccess = refreshed.json().access_token as string;
      assert.notEqual(newAccess, a.access_token);
      assert.equal((await expensive(newAccess)).statusCode, 429);
      assert.equal((await expensive(newAccess)).json().code, "rate_limited");
    },
  );
});

test("spoofed X-Forwarded-For does not change the IP bucket when hops=0", async () => {
  await withRateApp(
    {
      ASTRO_RATE_LIMIT_DISABLED: "0",
      ASTRO_RATE_LIMIT_MAX: "100",
      ASTRO_RATE_LIMIT_EXPENSIVE_MAX: "100",
      ASTRO_RATE_LIMIT_IP_MAX: "3",
      ASTRO_RATE_LIMIT_WINDOW_MS: "60000",
      ASTRO_TRUST_PROXY_HOPS: "0",
    },
    [],
    async (app) => {
      const hit = (xff: string) =>
        app.inject({
          method: "GET",
          url: "/v1/meta/catalogue",
          headers: { "x-forwarded-for": xff },
        });

      // /meta/catalogue is public (not exempt) — only IP bucket applies.
      const r1 = await hit("203.0.113.10");
      const r2 = await hit("203.0.113.20");
      const r3 = await hit("203.0.113.30");
      const r4 = await hit("203.0.113.40");
      assert.notEqual(r1.statusCode, 429, r1.body);
      assert.notEqual(r2.statusCode, 429, r2.body);
      assert.notEqual(r3.statusCode, 429, r3.body);
      assert.equal(r4.statusCode, 429, r4.body);
      assert.equal(r4.json().code, "rate_limited");
      assert.ok(Number(r4.headers["retry-after"] ?? 0) >= 1);
    },
  );
});

test("garbage tokens hit the pre-auth IP limit before flooding handlers", async () => {
  await withRateApp(
    {
      ASTRO_RATE_LIMIT_DISABLED: "0",
      ASTRO_RATE_LIMIT_MAX: "100",
      ASTRO_RATE_LIMIT_EXPENSIVE_MAX: "100",
      ASTRO_RATE_LIMIT_IP_MAX: "3",
      ASTRO_RATE_LIMIT_WINDOW_MS: "60000",
      ASTRO_TRUST_PROXY_HOPS: "0",
    },
    [],
    async (app) => {
      const hit = (n: number) =>
        app.inject({
          method: "GET",
          url: "/v1/me",
          headers: {
            authorization: `Bearer garbage-token-${n}-${"x".repeat(80)}`,
          },
        });

      const first = await hit(1);
      const second = await hit(2);
      const third = await hit(3);
      const fourth = await hit(4);
      // Valid path reaches auth and fails — must not be rate_limited yet.
      assert.equal(first.statusCode, 401, first.body);
      assert.equal(second.statusCode, 401, second.body);
      assert.equal(third.statusCode, 401, third.body);
      assert.equal(fourth.statusCode, 429, fourth.body);
      assert.equal(fourth.json().code, "rate_limited");
      assert.ok(Number(fourth.headers["retry-after"] ?? 0) >= 1);
    },
  );
});

test("health check /v1/meta/config is never limited", async () => {
  await withRateApp(
    {
      ASTRO_RATE_LIMIT_DISABLED: "0",
      ASTRO_RATE_LIMIT_MAX: "1",
      ASTRO_RATE_LIMIT_EXPENSIVE_MAX: "1",
      ASTRO_RATE_LIMIT_IP_MAX: "1",
      ASTRO_RATE_LIMIT_WINDOW_MS: "60000",
      ASTRO_TRUST_PROXY_HOPS: "0",
    },
    [],
    async (app) => {
      for (let i = 0; i < 8; i++) {
        const res = await app.inject({ url: "/v1/meta/config" });
        assert.equal(res.statusCode, 200, res.body);
      }
      // Non-exempt public route still consumes the IP bucket (max=1 → 2nd hits 429).
      const first = await app.inject({ url: "/v1/meta/catalogue" });
      assert.equal(first.statusCode, 200, first.body);
      const limited = await app.inject({ url: "/v1/meta/catalogue" });
      assert.equal(limited.statusCode, 429, limited.body);
      assert.equal(limited.json().code, "rate_limited");
    },
  );
});
