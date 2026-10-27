import test from "node:test";
import { clearAuthMode, dataDbPath, tempDataDir } from "./helpers";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { SupabaseAuth } from "../api/supabase-auth";
import { buildLocalApp } from "../api/app";
test("browser auth endpoints reject cross-origin claims, preserve one account, and return a token-free callback", async () => {
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), "astro-browser-auth-"));
  await clearAuthMode();
  const auth = new SupabaseAuth(
    {
      url: "https://abcdefghijklmnopqrst.supabase.co",
      publishableKey: "sb_publishable_test",
      ownerEmail: "owner@example.com",
    },
    async (url) =>
      String(url).endsWith("/user")
        ? Response.json({
            id: "11111111-1111-4111-8111-111111111111",
            email: "owner@example.com",
            email_confirmed_at: "2026-10-03T00:00:00Z",
          })
        : Response.json({
            access_token: "private-access",
            refresh_token: "private-refresh",
            expires_in: 3600,
          }),
  );
  const app = await buildLocalApp({
    dbPath: path.join(folder, "app.sqlite"),
    auth,
  });
  try {
    const post = (
      endpoint: string,
      payload: Record<string, string>,
      headers = {},
    ) =>
      app.inject({
        method: "POST",
        url: "/v1/auth/browser/" + endpoint,
        payload,
        headers,
      });
    assert.equal((await post("start", { provider: "apple" })).statusCode, 400);
    assert.equal(
      (await post("start", { provider: "email", email: "other@example.com" }))
        .statusCode,
      403,
    );
    assert.equal(
      (
        await post(
          "start",
          { provider: "google" },
          { origin: "https://evil.example" },
        )
      ).statusCode,
      403,
    );
    const start = await post("start", {
      provider: "email",
      email: "owner@example.com",
    });
    assert.equal(start.statusCode, 200, start.body);
    assert.equal(start.headers["cache-control"], "no-store");
    const ticket = start.json();
    assert.equal(
      (await post("poll", { poll_token: ticket.flow_id })).statusCode,
      401,
    );
    const page = await app.inject({
      url:
        "/v1/auth/browser/callback/" +
        ticket.flow_id +
        "?code=22222222-2222-4222-8222-222222222222",
    });
    assert.equal(page.statusCode, 200, page.body);
    assert.ok(!page.body.includes("private-access"));
    assert.ok(page.headers["content-security-policy"]);
    const ready = await post("poll", { poll_token: ticket.poll_token });
    assert.equal(ready.json().status, "complete");
    assert.equal(
      (
        await app.inject({
          url: "/v1/me",
          headers: {
            authorization: "Bearer " + ready.json().session.access_token,
          },
        })
      ).statusCode,
      200,
    );
    await post("cancel", { poll_token: ticket.poll_token });
    assert.equal(
      (await post("poll", { poll_token: ticket.poll_token })).statusCode,
      401,
    );
  } finally {
    await app.close();
    await clearAuthMode();
    fs.rmSync(folder, { recursive: true, force: true });
  }
});
