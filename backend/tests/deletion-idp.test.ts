/**
 * DELETE /me IdP path with a mocked Supabase admin client.
 * Proves: admin delete is called; failed IdP can be retried after tombstone.
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
import { clearAuthMode, tempDataDir } from "./helpers";
import type { SupabaseAdmin } from "../api/supabase-admin";

const PROJECT = "https://abcdefghijklmnopqrst.supabase.co";
const ISSUER = PROJECT + "/auth/v1";
const SUB = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";

async function jwtFixture() {
  const { privateKey, publicKey } = await generateKeyPair("ES256");
  const jwk = await exportJWK(publicKey);
  jwk.alg = "ES256";
  jwk.use = "sig";
  jwk.kid = "test";
  const jwt = new JwtAuth(PROJECT, undefined, createLocalJWKSet({ keys: [jwk] }));
  const sign = () =>
    new SignJWT({ email: "delete-me@example.com" })
      .setProtectedHeader({ alg: "ES256", kid: "test" })
      .setSubject(SUB)
      .setIssuer(ISSUER)
      .setAudience("authenticated")
      .setExpirationTime("1h")
      .sign(privateKey);
  return { jwt, sign };
}

function mockAdmin(impl: {
  deleteUser: (id: string) => Promise<void>;
}): SupabaseAdmin {
  return { deleteUser: impl.deleteUser } as SupabaseAdmin;
}

async function wipeSub() {
  await prisma().record.deleteMany({ where: { tenantId: SUB } });
  await prisma().session.deleteMany({ where: { userId: SUB } });
  await prisma().guestSession.deleteMany({ where: { claimedById: SUB } });
  await prisma().subscription.deleteMany({ where: { userId: SUB } });
  await prisma().paymentEvent.deleteMany({ where: { userId: SUB } });
  await prisma().user.deleteMany({ where: { id: SUB } });
  await prisma().deletedUser.deleteMany({ where: { id: SUB } });
}

test("DELETE /me calls mocked Supabase admin and removes claimed guest sessions", async () => {
  process.env.ASTRO_DEMO_AUTH = "0";
  await clearAuthMode();
  await wipeSub();
  const folder = tempDataDir("del-idp-");
  const { jwt, sign } = await jwtFixture();
  const calls: string[] = [];
  const admin = mockAdmin({
    async deleteUser(id) {
      calls.push(id);
    },
  });

  await prisma().user.create({
    data: { id: SUB, email: "delete-me@example.com", displayName: "Del" },
  });
  await prisma().guestSession.create({
    data: {
      tokenHash: "a".repeat(64),
      fingerprint: "fp",
      profile: { label: "guest birth" },
      expiresAt: new Date(Date.now() + 86400000),
      claimedById: SUB,
    },
  });

  const app = await buildLocalApp({
    dbPath: path.join(folder, "app.sqlite"),
    jwt,
    admin,
  });
  try {
    const token = await sign();
    const res = await app.inject({
      method: "DELETE",
      url: "/v1/me",
      headers: { authorization: "Bearer " + token },
    });
    assert.equal(res.statusCode, 202, res.body);
    assert.deepEqual(calls, [SUB]);
    assert.equal(await prisma().user.findUnique({ where: { id: SUB } }), null);
    assert.ok(await prisma().deletedUser.findUnique({ where: { id: SUB } }));
    assert.equal(
      await prisma().guestSession.count({ where: { claimedById: SUB } }),
      0,
    );
  } finally {
    await app.close();
    await wipeSub();
    await clearAuthMode();
    fs.rmSync(folder, { recursive: true, force: true });
  }
});

test("DELETE /me retries IdP after tombstone when first admin delete failed", async () => {
  process.env.ASTRO_DEMO_AUTH = "0";
  await clearAuthMode();
  await wipeSub();
  const folder = tempDataDir("del-retry-");
  const { jwt, sign } = await jwtFixture();
  let failOnce = true;
  const calls: string[] = [];
  const admin = mockAdmin({
    async deleteUser(id) {
      calls.push(id);
      if (failOnce) {
        failOnce = false;
        throw Object.assign(new Error("Auth provider unavailable"), {
          statusCode: 503,
        });
      }
    },
  });

  const app = await buildLocalApp({
    dbPath: path.join(folder, "app.sqlite"),
    jwt,
    admin,
  });
  try {
    const token = await sign();
    const first = await app.inject({
      method: "DELETE",
      url: "/v1/me",
      headers: { authorization: "Bearer " + token },
    });
    assert.equal(first.statusCode, 503, first.body);
    assert.ok(await prisma().deletedUser.findUnique({ where: { id: SUB } }));
    assert.equal(await prisma().user.findUnique({ where: { id: SUB } }), null);

    // Other routes stay closed.
    assert.equal(
      (
        await app.inject({
          url: "/v1/me",
          headers: { authorization: "Bearer " + token },
        })
      ).statusCode,
      403,
    );

    const second = await app.inject({
      method: "DELETE",
      url: "/v1/me",
      headers: { authorization: "Bearer " + token },
    });
    assert.equal(second.statusCode, 202, second.body);
    assert.deepEqual(calls, [SUB, SUB]);
  } finally {
    await app.close();
    await wipeSub();
    await clearAuthMode();
    fs.rmSync(folder, { recursive: true, force: true });
  }
});
