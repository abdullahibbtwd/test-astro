import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { BrowserSignIn } from "../api/browser-signin";
import { SupabaseAuth } from "../api/supabase-auth";
test("email link uses PKCE, returns credentials only to its private polling token, and expires", async () => {
  let time = 1000,
    challenge = "",
    redirect = "",
    exchanges = 0;
  const auth = new SupabaseAuth(
    {
      url: "https://abcdefghijklmnopqrst.supabase.co",
      publishableKey: "sb_publishable_test",
      ownerEmail: "owner@example.com",
    },
    async (url, init) => {
      const body = init?.body ? JSON.parse(String(init.body)) : {};
      if (String(url).includes("/otp?")) {
        challenge = body.code_challenge;
        redirect = new URL(String(url)).searchParams.get("redirect_to")!;
        assert.equal(body.code_challenge_method, "s256");
        return Response.json({});
      }
      if (String(url).includes("grant_type=pkce")) {
        exchanges++;
        assert.equal(
          createHash("sha256").update(body.code_verifier).digest("base64url"),
          challenge,
        );
        return Response.json({
          access_token: "access",
          refresh_token: "refresh",
          expires_in: 3600,
        });
      }
      return Response.json({
        id: "11111111-1111-4111-8111-111111111111",
        email: "owner@example.com",
        email_confirmed_at: "2026-10-03T00:00:00Z",
      });
    },
  );
  const flows = new BrowserSignIn(
    auth,
    (v) => ({ token: v.access_token }),
    () => time,
  );
  const start = await flows.start({
    provider: "email",
    email: "owner@example.com",
  });
  assert.ok(!redirect.includes(start.poll_token));
  assert.deepEqual(flows.poll(start.poll_token), { status: "waiting" });
  assert.throws(() => flows.poll(start.flow_id), { statusCode: 401 });
  await flows.complete(start.flow_id, "one-time-code");
  assert.equal(exchanges, 1);
  assert.deepEqual(flows.poll(start.poll_token), {
    status: "complete",
    session: { token: "access" },
  });
  await assert.rejects(flows.complete(start.flow_id, "replay"), {
    statusCode: 409,
  });
  flows.cancel(start.poll_token);
  assert.throws(() => flows.poll(start.poll_token), { statusCode: 401 });
  time += 61000;
  const another = await flows.start({ provider: "google" });
  assert.equal(new URL(another.url!).searchParams.get("provider"), "google");
  assert.equal(
    new URL(another.url!).searchParams.get("code_challenge_method"),
    "s256",
  );
  time += 600001;
  assert.throws(() => flows.poll(another.poll_token), { statusCode: 401 });
});
