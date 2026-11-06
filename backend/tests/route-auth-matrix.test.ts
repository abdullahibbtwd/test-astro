/**
 * Route authorization matrix: every route vs token variants.
 * Expected results: see EXPECTED_AUTH_RESULTS in route-auth-matrix.ts
 * and docs/ROUTE_AUTH_MATRIX.md.
 */
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import {
  generateKeyPair,
  exportJWK,
  SignJWT,
  createLocalJWKSet,
} from "jose";
import { JwtAuth } from "../api/jwt-auth";
import { buildLocalApp } from "../api/app";
import { prisma } from "../api/db";
import {
  ROUTE_AUTH_MATRIX,
  concretePath,
  EXPECTED_AUTH_RESULTS,
} from "../api/route-auth-matrix";
import { FakeProvider } from "../api/payments";
import { clearAuthMode, tempDataDir } from "./helpers";

const PROJECT = "https://abcdefghijklmnopqrst.supabase.co";
const ISSUER = PROJECT + "/auth/v1";
const SUB = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";

async function jwtFixture() {
  const { privateKey, publicKey } = await generateKeyPair("ES256");
  const jwk = await exportJWK(publicKey);
  jwk.alg = "ES256";
  jwk.use = "sig";
  jwk.kid = "test";
  const getKey = createLocalJWKSet({ keys: [jwk] });
  const jwt = new JwtAuth(PROJECT, undefined, getKey);
  const sign = async (
    opts?: { exp?: number | string; aud?: string; iss?: string },
  ) => {
    let builder = new SignJWT({ email: "matrix@example.com" })
      .setProtectedHeader({ alg: "ES256", kid: "test" })
      .setSubject(SUB)
      .setIssuer(opts?.iss ?? ISSUER)
      .setAudience(opts?.aud ?? "authenticated");
    if (opts?.exp !== undefined) builder = builder.setExpirationTime(opts.exp);
    else builder = builder.setExpirationTime("1h");
    return builder.sign(privateKey);
  };
  return { jwt, sign };
}

type TokenKind =
  | "none"
  | "malformed"
  | "expired"
  | "wrongAud"
  | "wrongIss"
  | "valid";

async function tokens(sign: Awaited<ReturnType<typeof jwtFixture>>["sign"]) {
  return {
    none: undefined as string | undefined,
    malformed: "not.a.jwt",
    expired: await sign({ exp: Math.floor(Date.now() / 1000) - 120 }),
    wrongAud: await sign({ aud: "anon" }),
    wrongIss: await sign({ iss: "https://evil.example/auth/v1" }),
    valid: await sign(),
  } satisfies Record<TokenKind, string | undefined>;
}

function authHeader(token: string | undefined): Record<string, string> {
  return token ? { authorization: "Bearer " + token } : {};
}

/** Sample minimal bodies so schema validation is not the failure mode for auth. */
function sampleBody(method: string, routePath: string): object | undefined {
  if (method === "GET" || method === "DELETE") return undefined;
  if (routePath.includes("/auth/email/start")) return { email: "a@example.com" };
  if (routePath.includes("/auth/email/verify"))
    return { email: "a@example.com", code: "000000" };
  if (routePath.includes("/auth/refresh") || routePath.includes("/auth/logout"))
    return { refresh_token: "x".repeat(64) };
  if (routePath.includes("/auth/apple") || routePath.includes("/auth/google"))
    return { id_token: "x" };
  if (routePath.includes("/auth/browser/start")) return { email: "a@example.com" };
  if (routePath.includes("/auth/browser/poll") || routePath.includes("/auth/browser/cancel"))
    return { poll_token: "a".repeat(64) };
  if (routePath.endsWith("/me") && method === "PATCH")
    return { display_name: "Test" };
  if (routePath.includes("/profiles") && method === "POST")
    return {
      label: "Self",
      relation: "self",
      birth: {
        date: "1990-01-15",
        time: "12:00",
        place_id: "place-test-1",
      },
    };
  if (routePath.includes("/compatibility") && method === "POST")
    return { profile_a_id: "x", profile_b_id: "y" };
  if (routePath.includes("/ask/threads") && method === "POST" && !routePath.includes("messages"))
    return { profile_id: "x" };
  if (routePath.includes("/messages") && method === "POST")
    return { text: "hello" };
  if (routePath.includes("/feedback/reading"))
    return { profile_id: "x", rating: 5 };
  if (routePath.includes("/feedback"))
    return { message_id: "x", helpful: true };
  if (routePath.includes("/natal-reading/progress"))
    return { section_key: "sun", completed: true };
  if (routePath.includes("/acg/recommendations"))
    return { goal: "love", limit: 3 };
  if (routePath.includes("/me/onboarding/claim"))
    return { guest_token: "a".repeat(64) };
  return {};
}

test("ROUTE_AUTH_MATRIX has no admin routes and covers user+public+webhook", () => {
  assert.equal(
    ROUTE_AUTH_MATRIX.filter((r) => r.auth === "admin").length,
    0,
    EXPECTED_AUTH_RESULTS.admin,
  );
  assert.ok(ROUTE_AUTH_MATRIX.some((r) => r.auth === "public"));
  assert.ok(ROUTE_AUTH_MATRIX.some((r) => r.auth === "user"));
  assert.ok(ROUTE_AUTH_MATRIX.some((r) => r.auth === "webhook"));
});

test("every user route: no/malformed/expired/wrong-aud/wrong-iss → 401; valid → not 401", async () => {
  process.env.ASTRO_DEMO_AUTH = "0";
  process.env.ASTRO_GUEST_ONBOARDING = "0";
  process.env.ASTRO_PAYMENT_PROVIDER = "fake";
  await clearAuthMode();
  await prisma().deletedUser.deleteMany({ where: { id: SUB } }).catch(() => undefined);
  await prisma().user.deleteMany({ where: { id: SUB } }).catch(() => undefined);

  const folder = tempDataDir("astro-matrix-");
  const { jwt, sign } = await jwtFixture();
  const t = await tokens(sign);
  const app = await buildLocalApp({
    dbPath: path.join(folder, "app.sqlite"),
    jwt,
  });

  const userRoutes = ROUTE_AUTH_MATRIX.filter((r) => r.auth === "user");
  // Skip browser/guest-only routes that are not registered without auth/guest flags.
  const skip = new Set([
    "/v1/me/onboarding/claim", // needs guest onboarding registration
  ]);

  try {
    const failures: string[] = [];
    for (const route of userRoutes) {
      if (skip.has(route.path)) continue;
      const url = concretePath(route.path);
      const payload = sampleBody(route.method, route.path);
      const cases: [TokenKind, number | "non-401"][] = [
        ["none", 401],
        ["malformed", 401],
        ["expired", 401],
        ["wrongAud", 401],
        ["wrongIss", 401],
        ["valid", "non-401"],
      ];
      for (const [kind, expected] of cases) {
        const res = await app.inject({
          method: route.method,
          url,
          headers: {
            "content-type": "application/json",
            ...authHeader(t[kind]),
          },
          payload,
        });
        const ok =
          expected === "non-401"
            ? res.statusCode !== 401
            : res.statusCode === expected;
        if (!ok) {
          failures.push(
            `${route.method} ${route.path} [${kind}]: got ${res.statusCode}, want ${expected}`,
          );
        }
      }
    }
    assert.deepEqual(failures, [], failures.join("\n"));
  } finally {
    await app.close();
    fs.rmSync(folder, { recursive: true, force: true });
    await clearAuthMode();
  }
});

test("public routes do not require Bearer (no token is not 401-from-auth)", async () => {
  process.env.ASTRO_DEMO_AUTH = "0";
  await clearAuthMode();
  const folder = tempDataDir("astro-pub-");
  const { jwt } = await jwtFixture();
  const app = await buildLocalApp({
    dbPath: path.join(folder, "app.sqlite"),
    jwt,
  });
  try {
    const publicRoutes = ROUTE_AUTH_MATRIX.filter(
      (r) =>
        r.auth === "public" &&
        !r.path.startsWith("/v1/auth/browser"), // browser routes need auth client
    );
    const failures: string[] = [];
    for (const route of publicRoutes) {
      const res = await app.inject({
        method: route.method,
        url: concretePath(route.path),
        headers: { "content-type": "application/json" },
        payload: sampleBody(route.method, route.path),
      });
      // Public routes may 400/404/503 for bad body or missing features,
      // but must not gate on missing Bearer.
      if (res.statusCode === 401) {
        failures.push(
          `${route.method} ${route.path}: unexpected 401 without token`,
        );
      }
    }
    assert.deepEqual(failures, [], failures.join("\n"));
  } finally {
    await app.close();
    fs.rmSync(folder, { recursive: true, force: true });
    await clearAuthMode();
  }
});

test("webhook route: bad signature 401; valid signature not 401", async () => {
  process.env.ASTRO_PAYMENT_PROVIDER = "fake";
  process.env.ASTRO_DEMO_AUTH = "0";
  await clearAuthMode();
  const folder = tempDataDir("astro-wh-");
  const { jwt } = await jwtFixture();
  const app = await buildLocalApp({
    dbPath: path.join(folder, "app.sqlite"),
    jwt,
  });
  try {
    const body = JSON.stringify({
      event_id: "matrix-evt-1",
      type: "purchase",
      user_id: SUB,
      plan_id: "premium",
      product_id: "fake.premium",
      original_transaction_id: "mtx-1",
      status: "active",
      expires_at: "2027-01-01T00:00:00.000Z",
      occurred_at: new Date().toISOString(),
    });
    const bad = await app.inject({
      method: "POST",
      url: "/v1/webhooks/payments",
      headers: {
        "content-type": "application/json",
        "x-fake-signature": "00",
      },
      payload: body,
    });
    assert.equal(bad.statusCode, 401);

    const sig = new FakeProvider().sign(body);
    const good = await app.inject({
      method: "POST",
      url: "/v1/webhooks/payments",
      headers: {
        "content-type": "application/json",
        "x-fake-signature": sig,
      },
      payload: body,
    });
    // 200 applied or applied:false (missing user) — never 401
    assert.notEqual(good.statusCode, 401);
    assert.ok([200, 400].includes(good.statusCode));
  } finally {
    await app.close();
    fs.rmSync(folder, { recursive: true, force: true });
    await clearAuthMode();
  }
});
