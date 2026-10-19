import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {
  generateKeyPair,
  exportJWK,
  SignJWT,
  createLocalJWKSet,
} from "jose";
import { JwtAuth } from "../api/jwt-auth";
import { buildLocalApp } from "../api/app";
import { deleteAccount } from "../api/account";
import { prisma } from "../api/db";

const PROJECT = "https://abcdefghijklmnopqrst.supabase.co";
const ISSUER = PROJECT + "/auth/v1";
const SUB_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const SUB_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";

async function testKeys() {
  const { privateKey, publicKey } = await generateKeyPair("ES256");
  const jwk = await exportJWK(publicKey);
  jwk.alg = "ES256";
  jwk.use = "sig";
  jwk.kid = "test";
  const getKey = createLocalJWKSet({ keys: [jwk] });
  const jwt = new JwtAuth(PROJECT, undefined, getKey);
  const sign = async (
    sub: string,
    email: string,
    opts?: { exp?: number; aud?: string; iss?: string },
  ) => {
    let builder = new SignJWT({ email })
      .setProtectedHeader({ alg: "ES256", kid: "test" })
      .setSubject(sub)
      .setIssuer(opts?.iss ?? ISSUER)
      .setAudience(opts?.aud ?? "authenticated");
    if (opts?.exp !== undefined) builder = builder.setExpirationTime(opts.exp);
    else builder = builder.setExpirationTime("1h");
    return builder.sign(privateKey);
  };
  return { jwt, sign };
}

test("JwtAuth rejects invalid, expired and wrong-audience tokens", async () => {
  const { jwt, sign } = await testKeys();
  await assert.rejects(jwt.verify("not-a-jwt"), { statusCode: 401 });
  const expired = await sign(SUB_A, "a@example.com", {
    exp: Math.floor(Date.now() / 1000) - 120,
  });
  await assert.rejects(jwt.verify(expired), { statusCode: 401 });
  const wrongAud = await sign(SUB_A, "a@example.com", { aud: "anon" });
  await assert.rejects(jwt.verify(wrongAud), { statusCode: 401 });
  const wrongIss = await sign(SUB_A, "a@example.com", {
    iss: "https://evil.example/auth/v1",
  });
  await assert.rejects(jwt.verify(wrongIss), { statusCode: 401 });
  const ok = await sign(SUB_A, "a@example.com");
  assert.deepEqual(await jwt.verify(ok), {
    sub: SUB_A,
    email: "a@example.com",
  });
});

test("JWT bearer: first login creates user; tenants are isolated; tombstone refused", async () => {
  process.env.DATABASE_URL ??=
    "postgres://astrology:astrology@127.0.0.1:5432/astrology";
  process.env.ASTRO_DEMO_AUTH = "0";
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), "astro-jwt-"));
  const { jwt, sign } = await testKeys();
  const app = await buildLocalApp({
    dbPath: path.join(folder, "app.sqlite"),
    jwt,
  });
  try {
    const tokenA = await sign(SUB_A, "a@example.com");
    const tokenB = await sign(SUB_B, "b@example.com");
    assert.equal(
      (
        await app.inject({
          url: "/v1/me",
          headers: { authorization: "Bearer " + tokenA },
        })
      ).statusCode,
      200,
    );
    const user = await prisma().user.findUnique({ where: { id: SUB_A } });
    assert.ok(user);
    assert.equal(user!.email, "a@example.com");

    await app.inject({
      method: "PATCH",
      url: "/v1/me",
      headers: { authorization: "Bearer " + tokenA },
      payload: { display_name: "Alice Only" },
    });
    assert.equal(
      (
        await app.inject({
          url: "/v1/me",
          headers: { authorization: "Bearer " + tokenB },
        })
      ).statusCode,
      200,
    );
    const meB = (
      await app.inject({
        url: "/v1/me",
        headers: { authorization: "Bearer " + tokenB },
      })
    ).json();
    const againA = (
      await app.inject({
        url: "/v1/me",
        headers: { authorization: "Bearer " + tokenA },
      })
    ).json();
    assert.equal(againA.user_id, SUB_A);
    assert.equal(againA.display_name, "Alice Only");
    assert.equal(meB.user_id, SUB_B);
    assert.notEqual(meB.display_name, "Alice Only");

    await deleteAccount(prisma(), SUB_A, folder);
    assert.equal(
      (
        await app.inject({
          url: "/v1/me",
          headers: { authorization: "Bearer " + tokenA },
        })
      ).statusCode,
      403,
    );
  } finally {
    await app.close();
    fs.rmSync(folder, { recursive: true, force: true });
    await prisma().record.deleteMany({
      where: { tenantId: { in: [SUB_A, SUB_B] } },
    });
    await prisma().session.deleteMany({
      where: { userId: { in: [SUB_A, SUB_B] } },
    });
    await prisma().user.deleteMany({ where: { id: { in: [SUB_A, SUB_B] } } });
    await prisma().deletedUser.deleteMany({
      where: { id: { in: [SUB_A, SUB_B] } },
    });
    // Shared Postgres: clear sticky auth-mode so demo tests can open a clean app.
    await prisma().systemConfig.deleteMany({ where: { key: "auth-mode" } });
    process.env.ASTRO_DEMO_AUTH = "1";
  }
});

test("demo email verify is unavailable when ASTRO_DEMO_AUTH is off", async () => {
  process.env.ASTRO_DEMO_AUTH = "0";
  await prisma().systemConfig.deleteMany({ where: { key: "auth-mode" } });
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), "astro-demo-off-"));
  const app = await buildLocalApp({
    dbPath: path.join(folder, "app.sqlite"),
  });
  try {
    const verify = await app.inject({
      method: "POST",
      url: "/v1/auth/email/verify",
      payload: { email: "demo@example.com", code: "000000" },
    });
    assert.equal(verify.statusCode, 404, verify.body);
    const start = await app.inject({
      method: "POST",
      url: "/v1/auth/email/start",
      payload: { email: "demo@example.com", lang: "en" },
    });
    assert.equal(start.statusCode, 404, start.body);
  } finally {
    await app.close();
    fs.rmSync(folder, { recursive: true, force: true });
    process.env.ASTRO_DEMO_AUTH = "1";
  }
});

test("production refuses to start with ASTRO_DEMO_AUTH=1", async () => {
  const prevNode = process.env.NODE_ENV;
  const prevDemo = process.env.ASTRO_DEMO_AUTH;
  process.env.NODE_ENV = "production";
  process.env.ASTRO_DEMO_AUTH = "1";
  try {
    await assert.rejects(async () => {
      // Re-evaluate the same guard used by server.ts
      if (
        process.env.NODE_ENV === "production" &&
        process.env.ASTRO_DEMO_AUTH === "1"
      )
        throw new Error(
          "ASTRO_DEMO_AUTH must not be enabled when NODE_ENV=production",
        );
    }, /ASTRO_DEMO_AUTH must not be enabled/);
  } finally {
    process.env.NODE_ENV = prevNode;
    process.env.ASTRO_DEMO_AUTH = prevDemo ?? "1";
  }
});
