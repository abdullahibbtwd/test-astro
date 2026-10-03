import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { buildLocalApp } from "../local-api/app";
import { SupabaseAuth } from "../local-api/supabase-auth";
import { validate } from "../src/api/zod";
test("Real auth blocks demo tokens, binds the verified owner, rotates and revokes sessions", async () => {
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), "astro-auth-"));
  const dbPath = path.join(folder, "app.sqlite");
  let app = buildLocalApp({ dbPath });
  const demo = (
    await app.inject({
      method: "POST",
      url: "/v1/auth/email/verify",
      payload: { email: "demo@example.com", code: "000000" },
    })
  ).json();
  const oldMe = (
    await app.inject({
      url: "/v1/me",
      headers: { authorization: "Bearer " + demo.access_token },
    })
  ).json();
  await app.close();
  let uid = "11111111-1111-4111-8111-111111111111";
  let count = 0;
  const auth = new SupabaseAuth(
    {
      url: "https://abcdefghijklmnopqrst.supabase.co",
      publishableKey: "sb_publishable_test",
      ownerEmail: "owner@example.com",
    },
    async (url) => {
      if (String(url).endsWith("/user"))
        return Response.json({
          id: uid,
          email: "owner@example.com",
          email_confirmed_at: "2026-10-03T00:00:00Z",
        });
      if (String(url).includes("/logout"))
        return new Response(null, { status: 204 });
      count++;
      return Response.json({
        access_token: "access" + count,
        refresh_token: "refresh" + count,
        expires_in: 3600,
      });
    },
  );
  app = buildLocalApp({ dbPath, auth });
  try {
    const post = (url: string, payload: Record<string, string>, headers = {}) =>
      app.inject({ method: "POST", url: "/v1/auth/" + url, payload, headers });
    assert.equal(
      (
        await app.inject({
          url: "/v1/me",
          headers: { authorization: "Bearer " + demo.access_token },
        })
      ).statusCode,
      401,
    );
    assert.equal(
      (await post("refresh", { refresh_token: demo.refresh_token })).statusCode,
      401,
    );
    assert.equal(
      (
        await post("email/verify", {
          email: "demo@example.com",
          code: "000000",
        })
      ).statusCode,
      403,
    );
    let response = await post("email/verify", {
      email: "owner@example.com",
      code: "123456",
    });
    assert.equal(response.statusCode, 200, response.body);
    let session = response.json();
    validate("Session", session);
    assert.equal(session.me.user_id, oldMe.user_id);
    const headers = { authorization: "Bearer " + session.access_token };
    assert.equal(
      (await app.inject({ url: "/v1/me", headers })).statusCode,
      200,
    );
    response = await post("refresh", { refresh_token: session.refresh_token });
    assert.equal(response.statusCode, 200, response.body);
    assert.equal(
      (await post("refresh", { refresh_token: session.refresh_token }))
        .statusCode,
      401,
    );
    assert.equal(
      (await app.inject({ url: "/v1/me", headers })).statusCode,
      401,
    );
    session = response.json();
    assert.equal(
      (
        await post(
          "logout",
          { refresh_token: session.refresh_token },
          { authorization: "Bearer " + session.access_token },
        )
      ).statusCode,
      204,
    );
    assert.equal(
      (await post("refresh", { refresh_token: session.refresh_token }))
        .statusCode,
      401,
    );
    uid = "22222222-2222-4222-8222-222222222222";
    assert.equal(
      (
        await post("email/verify", {
          email: "owner@example.com",
          code: "123456",
        })
      ).statusCode,
      403,
    );
  } finally {
    await app.close();
  }
  assert.throws(
    () => buildLocalApp({ dbPath }),
    /Real authentication is required/,
  );
  fs.rmSync(folder, { recursive: true, force: true });
});
