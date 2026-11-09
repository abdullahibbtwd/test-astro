/**
 * IDOR sweep: user A's token against user B's resources.
 * Expect 404 (tenant-scoped store; never leak existence via 403).
 */
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import {
  clearAuthMode,
  clearUsageCounters,
  demoTenantId,
  openStore,
  tempDataDir,
  wipeDemoTenant,
} from "./helpers";
import { buildLocalApp } from "../api/app";
import { fixture } from "../mock/fixtures";
import { prisma } from "../api/db";

const emailA = "idor-a@example.com";
const emailB = "idor-b@example.com";

async function login(
  app: Awaited<ReturnType<typeof buildLocalApp>>,
  email: string,
) {
  const res = await app.inject({
    method: "POST",
    url: "/v1/auth/email/verify",
    payload: { email, code: "000000" },
  });
  assert.equal(res.statusCode, 200, res.body);
  return res.json() as { access_token: string; me: { user_id: string } };
}

test("IDOR: A cannot read/write/delete B profiles, jobs, threads, messages, reports, exports, compatibility, map, subscriptions", async () => {
  process.env.ASTRO_DEMO_AUTH = "1";
  process.env.ASTRO_ASK_ENABLED = "0";
  process.env.ASTRO_FREE_LAUNCH_ENTITLE_ALL = "0";
  await wipeDemoTenant(emailA);
  await wipeDemoTenant(emailB);
  await clearUsageCounters(demoTenantId(emailA));
  await clearUsageCounters(demoTenantId(emailB));
  await clearAuthMode();

  const folder = tempDataDir("idor-");
  const profile = {
    ...fixture("profile.1.en"),
    profile_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    is_self: true,
    relation: "self",
  };
  const otherProfile = {
    ...fixture("profile.2.en"),
    profile_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    is_self: false,
    relation: "friend",
  };
  const compatId = "compat-idor-b-1";
  const threadId = "thread-idor-b-1";
  const messageId = "msg-idor-b-1";
  const jobId = "job-idor-b-1";
  const reportId = `map-idorbhash-en`;
  const pid = profile.profile_id;

  const app = await buildLocalApp({
    dbPath: path.join(folder, "app.sqlite"),
    allowPaid: false,
  });

  try {
    const sessionB = await login(app, emailB);
    const sessionA = await login(app, emailA);
    const headersA = { authorization: `Bearer ${sessionA.access_token}` };
    const headersB = { authorization: `Bearer ${sessionB.access_token}` };
    const tenantB = sessionB.me.user_id;

    const store = await openStore();
    await store.runAsAsync(tenantB, async () => {
      await store.put("profile:" + profile.profile_id, profile);
      await store.put("profile:" + otherProfile.profile_id, otherProfile);
      await store.put("chart:" + profile.profile_id, fixture("chart.1"));
      await store.put("raw:" + profile.profile_id, { points: [] });
      await store.put("compat:" + compatId, {
        id: compatId,
        context: {
          profile_a_id: profile.profile_id,
          profile_b_id: otherProfile.profile_id,
        },
        created_at: new Date().toISOString(),
        readings: {},
      });
      await store.put("ask-thread:" + threadId, {
        id: threadId,
        profile_id: profile.profile_id,
        title: "secret",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        messages: [
          {
            id: messageId,
            role: "user",
            text: "private question",
            created_at: new Date().toISOString(),
          },
        ],
      });
      await store.put("job:" + jobId, {
        job_id: jobId,
        status: "ready",
        kind: "forecast",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      });
      await store.put("report:" + profile.profile_id + ":en", {
        report_id: reportId,
        type: "map",
        profile_id: profile.profile_id,
        lang: "en",
        created_at: new Date().toISOString(),
        title: "B map",
      });
      await store.put("map-report:" + reportId, {
        report_id: reportId,
        type: "map",
        profile_id: profile.profile_id,
        lang: "en",
        created_at: new Date().toISOString(),
        title: "B map",
      });
      await store.put("me", {
        ...(await store.get("me")),
        self_profile_id: profile.profile_id,
      });
    });
    await prisma().subscription.create({
      data: {
        userId: tenantB,
        planId: "premium",
        status: "active",
        expiresAt: new Date(Date.now() + 86400000),
        sourceStore: "fake",
        originalTransactionId: "idor-b-txn",
        productId: "fake.premium",
      },
    });
    await store.close();

    // Owner can still see their profile (sanity).
    assert.equal(
      (
        await app.inject({
          url: `/v1/profiles/${pid}`,
          headers: headersB,
        })
      ).statusCode,
      200,
    );

    const expect404 = async (
      label: string,
      opts: {
        method?: string;
        url: string;
        payload?: object;
      },
    ) => {
      const res = await app.inject({
        method: opts.method ?? "GET",
        url: opts.url,
        headers: {
          ...headersA,
          ...(opts.payload ? { "content-type": "application/json" } : {}),
        },
        payload: opts.payload,
      });
      assert.equal(
        res.statusCode,
        404,
        `${label}: got ${res.statusCode} ${res.body.slice(0, 200)}`,
      );
    };

    // Profiles (read / write / delete)
    await expect404("GET profile", { url: `/v1/profiles/${pid}` });
    await expect404("PATCH profile", {
      method: "PATCH",
      url: `/v1/profiles/${pid}`,
      payload: {
        label: "Hijacked",
        birth_date: "1990-01-15",
        birth_time: "12:00",
        relation: "friend",
      },
    });
    await expect404("DELETE other profile", {
      method: "DELETE",
      url: `/v1/profiles/${otherProfile.profile_id}`,
    });

    // Chart / forecast / calendar / map / natal under B's profile
    for (const url of [
      `/v1/profiles/${pid}/chart`,
      `/v1/profiles/${pid}/forecast/day?date=2026-11-06`,
      `/v1/profiles/${pid}/forecast/month?month=2026-11`,
      `/v1/profiles/${pid}/forecast/year?from=2026`,
      `/v1/profiles/${pid}/solar-return?year=2026`,
      `/v1/profiles/${pid}/calendar/months/2026-11`,
      `/v1/profiles/${pid}/calendar/days/2026-11-06`,
      `/v1/profiles/${pid}/calendar/year`,
      `/v1/profiles/${pid}/best-days`,
      `/v1/profiles/${pid}/natal-reading/outline`,
      `/v1/profiles/${pid}/acg/lines`,
      `/v1/profiles/${pid}/acg/heat/love`,
      `/v1/profiles/${pid}/acg/point?lat=41&lon=29`,
      `/v1/profiles/${pid}/acg/countries/TR`,
      `/v1/profiles/${pid}/notification-candidates`,
    ]) {
      await expect404(url, { url });
    }

    await expect404("POST acg recommendations", {
      method: "POST",
      url: `/v1/profiles/${pid}/acg/recommendations`,
      payload: { goal: "love", limit: 3 },
    });

    // Jobs
    await expect404("GET job", { url: `/v1/jobs/${jobId}` });

    // Compatibility
    await expect404("GET compatibility", {
      url: `/v1/compatibility/${compatId}`,
    });
    await expect404("DELETE compatibility", {
      method: "DELETE",
      url: `/v1/compatibility/${compatId}`,
    });
    // Create using B's profile ids must not succeed as A (profiles missing → 404/400)
    {
      const res = await app.inject({
        method: "POST",
        url: "/v1/compatibility",
        headers: { ...headersA, "content-type": "application/json" },
        payload: {
          profile_a_id: profile.profile_id,
          profile_b_id: otherProfile.profile_id,
        },
      });
      assert.ok(
        [400, 404].includes(res.statusCode),
        `compat create with foreign ids: ${res.statusCode}`,
      );
    }

    // Ask threads / messages
    await expect404("GET thread", { url: `/v1/ask/threads/${threadId}` });
    await expect404("DELETE thread", {
      method: "DELETE",
      url: `/v1/ask/threads/${threadId}`,
    });
    await expect404("POST message on foreign thread", {
      method: "POST",
      url: `/v1/ask/threads/${threadId}/messages`,
      payload: { text: "inject" },
    });
    await expect404("POST feedback on foreign message", {
      method: "POST",
      url: `/v1/ask/messages/${messageId}/feedback`,
      payload: { rating: "up" },
    });

    // Reports — A must not hide B's report; list must not include it
    await expect404("DELETE report", {
      method: "DELETE",
      url: `/v1/reports/${reportId}`,
    });
    {
      const list = await app.inject({ url: "/v1/reports", headers: headersA });
      assert.equal(list.statusCode, 200, list.body);
      const items = list.json().items as { report_id: string }[];
      assert.ok(!items.some((r) => r.report_id === reportId));
    }

    // Export is always the caller's data (no id) — ensure B data not in A's export
    {
      const exp = await app.inject({
        method: "POST",
        url: "/v1/me/export",
        headers: headersA,
      });
      // 202 with export body or similar — must not contain B's profile id
      assert.ok([200, 202].includes(exp.statusCode), exp.body);
      assert.doesNotMatch(exp.body, new RegExp(pid));
      assert.doesNotMatch(exp.body, /private question/);
    }

    // Subscriptions / billing — A must not see B's premium / txn
    {
      const bill = await app.inject({
        url: "/v1/billing/status",
        headers: headersA,
      });
      assert.equal(bill.statusCode, 200, bill.body);
      assert.doesNotMatch(bill.body, /idor-b-txn/);
      assert.doesNotMatch(bill.body, /"plan_id"\s*:\s*"premium"/);
      const billB = await app.inject({
        url: "/v1/billing/status",
        headers: headersB,
      });
      assert.equal(billB.statusCode, 200, billB.body);
      // Webhook cannot be used with A's bearer to mutate B (no user id in path);
      // forging events for B requires the webhook secret (covered elsewhere).
      assert.equal(
        (
          await app.inject({
            url: "/v1/billing/status",
            headers: headersA,
          })
        ).statusCode,
        200,
      );
    }

    // Billing without token → 401 (payments surface)
    assert.equal(
      (await app.inject({ url: "/v1/billing/status" })).statusCode,
      401,
    );

    // Map-style place report under B profile
    await expect404("map place report", {
      url: `/v1/profiles/${pid}/acg/places/place-test-1`,
    });
  } finally {
    await app.close();
    await prisma().subscription.deleteMany({
      where: { originalTransactionId: "idor-b-txn" },
    });
    await wipeDemoTenant(emailA);
    await wipeDemoTenant(emailB);
    await clearAuthMode();
    fs.rmSync(folder, { recursive: true, force: true });
  }
});
