import test from "node:test";
import assert from "node:assert/strict";
import { SupabaseAuth } from "../api/supabase-auth";
const config = {
  url: "https://abcdefghijklmnopqrst.supabase.co",
  publishableKey: "sb_publishable_test",
  ownerEmail: "owner@example.com",
};
const user = {
  id: "11111111-1111-4111-8111-111111111111",
  email: config.ownerEmail,
  email_confirmed_at: "2026-10-03T00:00:00Z",
};
test("Supabase authenticates the confirmed owner and never sends another address upstream", async () => {
  const calls: string[] = [];
  const auth = new SupabaseAuth(config, async (url, init) => {
    calls.push(String(url));
    assert.equal(
      new Headers(init?.headers).get("apikey"),
      config.publishableKey,
    );
    if (String(url).endsWith("/user")) return Response.json(user);
    return Response.json({
      access_token: "access",
      refresh_token: "refresh",
      expires_in: 3600,
    });
  });
  await assert.rejects(auth.startEmail("stranger@example.com"), {
    statusCode: 403,
  });
  assert.equal(calls.length, 0);
  await auth.startEmail(" OWNER@example.com ");
  const session = await auth.verify("owner@example.com", "123456");
  assert.equal(session.user.id, user.id);
  assert.ok(calls.some((url) => url.endsWith("/user")));
});
test("Supabase refuses unverified identities, malformed sessions and unavailable upstreams", async () => {
  for (const value of [
    { ...user, email_confirmed_at: null },
    { ...user, email: "stranger@example.com" },
  ]) {
    const auth = new SupabaseAuth(config, async () => Response.json(value));
    await assert.rejects(auth.user("access"), { statusCode: 403 });
  }
  const malformed = new SupabaseAuth(config, async () =>
    Response.json({ access_token: "access" }),
  );
  await assert.rejects(malformed.verify(config.ownerEmail, "123456"), {
    statusCode: 503,
  });
  const outage = new SupabaseAuth(config, async () => {
    throw new Error("private upstream details");
  });
  await assert.rejects(outage.startEmail(config.ownerEmail), {
    statusCode: 503,
    message: "Authentication unavailable",
  });
  assert.throws(() => new SupabaseAuth({ ...config, url: "http://localhost" }));
  assert.throws(
    () => new SupabaseAuth({ ...config, publishableKey: "sb_secret_invalid" }),
  );
});
test("multi-user mode allows any email through startEmail", async () => {
  const calls: string[] = [];
  const auth = new SupabaseAuth(
    {
      url: config.url,
      publishableKey: config.publishableKey,
    },
    async (url) => {
      calls.push(String(url));
      return new Response(null, { status: 204 });
    },
  );
  assert.equal(auth.multiUser, true);
  await auth.startEmail("stranger@example.com");
  assert.ok(calls.some((url) => url.includes("/otp")));
});
