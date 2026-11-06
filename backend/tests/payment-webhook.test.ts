import test from "node:test";
import assert from "node:assert/strict";
import { buildLocalApp } from "../api/app";
import { prisma } from "../api/db";
import { FakeProvider, fakeSamplePayloads } from "../api/payments";
import { computeEntitlements } from "../api/entitlements";
import { demoTenantId, wipeDemoTenant, tempDataDir } from "./helpers";

const email = "webhook-user@example.com";
const userId = () => demoTenantId(email);

async function ensureUser() {
  const id = userId();
  await wipeDemoTenant(email);
  await prisma().paymentEvent.deleteMany({
    where: { id: { startsWith: "fake-evt-" } },
  });
  await prisma().subscription.deleteMany({ where: { userId: id } });
  await prisma().user.upsert({
    where: { id },
    create: { id, email, displayName: "Webhook" },
    update: {},
  });
  return id;
}

async function postWebhook(app: Awaited<ReturnType<typeof buildLocalApp>>, payload: object) {
  const provider = new FakeProvider();
  const body = JSON.stringify({
    ...payload,
    user_id: userId(),
  });
  const sig = provider.sign(body);
  return app.inject({
    method: "POST",
    url: "/v1/webhooks/payments",
    headers: {
      "content-type": "application/json",
      "x-fake-signature": sig,
    },
    payload: body,
  });
}

test("webhook rejects invalid signature", async () => {
  process.env.ASTRO_PAYMENT_PROVIDER = "fake";
  const dir = tempDataDir();
  const app = await buildLocalApp({
    dbPath: dir + "/app.sqlite",
    allowPaid: false,
  });
  try {
    await ensureUser();
    const body = JSON.stringify(fakeSamplePayloads().purchase);
    const res = await app.inject({
      method: "POST",
      url: "/v1/webhooks/payments",
      headers: {
        "content-type": "application/json",
        "x-fake-signature": "deadbeef",
      },
      payload: body,
    });
    assert.equal(res.statusCode, 401);
  } finally {
    await app.close();
  }
});

test("purchase then renew; duplicate event is idempotent", async () => {
  process.env.ASTRO_PAYMENT_PROVIDER = "fake";
  process.env.ASTRO_FREE_LAUNCH_ENTITLE_ALL = "0";
  const dir = tempDataDir();
  const app = await buildLocalApp({
    dbPath: dir + "/app.sqlite",
    allowPaid: false,
  });
  try {
    const id = await ensureUser();
    const samples = fakeSamplePayloads();

    const first = await postWebhook(app, samples.purchase);
    assert.equal(first.statusCode, 200);
    assert.equal(first.json().applied, true);

    const dup = await postWebhook(app, samples.purchase);
    assert.equal(dup.statusCode, 200);
    assert.equal(dup.json().applied, false);
    assert.equal(dup.json().reason, "duplicate");

    const renew = await postWebhook(app, samples.renew);
    assert.equal(renew.statusCode, 200);
    assert.equal(renew.json().applied, true);

    const subs = await prisma().subscription.findMany({ where: { userId: id } });
    assert.equal(subs.length, 1);
    assert.equal(subs[0].status, "active");
    assert.equal(subs[0].planId, "premium");

    const entitlements = await computeEntitlements(prisma(), id, {
      env: { ASTRO_FREE_LAUNCH_ENTITLE_ALL: "0" },
    });
    assert.equal(entitlements.plan_id, "premium");
  } finally {
    await app.close();
    delete process.env.ASTRO_FREE_LAUNCH_ENTITLE_ALL;
  }
});

test("unknown event types are ignored safely; stale timestamps rejected", async () => {
  process.env.ASTRO_PAYMENT_PROVIDER = "fake";
  process.env.ASTRO_FREE_LAUNCH_ENTITLE_ALL = "0";
  const dir = tempDataDir();
  const app = await buildLocalApp({
    dbPath: dir + "/app.sqlite",
    allowPaid: false,
  });
  try {
    const id = await ensureUser();
    const unknown = await postWebhook(app, {
      event_id: "fake-evt-unknown-1",
      type: "not_a_real_event",
      status: "active",
      user_id: id,
      plan_id: "premium",
      product_id: "fake.premium",
      original_transaction_id: "fake-txn-unk",
      occurred_at: new Date().toISOString(),
      expires_at: "2027-01-01T00:00:00.000Z",
    });
    assert.equal(unknown.statusCode, 200);
    assert.equal(unknown.json().applied, false);
    assert.equal(unknown.json().reason, "unknown_type");
    assert.equal(
      await prisma().subscription.count({ where: { userId: id } }),
      0,
    );

    const stale = await postWebhook(app, {
      event_id: "fake-evt-stale-1",
      type: "purchase",
      status: "active",
      user_id: id,
      plan_id: "premium",
      product_id: "fake.premium",
      original_transaction_id: "fake-txn-stale",
      occurred_at: new Date(Date.now() - 60 * 60_000).toISOString(),
      expires_at: "2027-01-01T00:00:00.000Z",
    });
    assert.equal(stale.statusCode, 200);
    assert.equal(stale.json().applied, false);
    assert.equal(stale.json().reason, "stale_or_future");
    assert.equal(
      await prisma().subscription.count({ where: { userId: id } }),
      0,
    );
  } finally {
    await app.close();
    delete process.env.ASTRO_FREE_LAUNCH_ENTITLE_ALL;
  }
});

test("cancel, refund, grace, billing_retry, restore, expire samples", async () => {
  process.env.ASTRO_PAYMENT_PROVIDER = "fake";
  const dir = tempDataDir();
  const app = await buildLocalApp({
    dbPath: dir + "/app.sqlite",
    allowPaid: false,
  });
  try {
    const id = await ensureUser();
    const samples = fakeSamplePayloads();
    for (const key of [
      "purchase",
      "cancel",
      "refund",
      "grace",
      "billing_retry",
      "restore",
      "expire",
    ] as const) {
      // Unique event ids already; re-bind user each time
      const res = await postWebhook(app, samples[key]);
      assert.equal(res.statusCode, 200, key);
      assert.equal(res.json().applied, true, key);
    }
    const sub = await prisma().subscription.findFirst({
      where: { userId: id },
      orderBy: { updatedAt: "desc" },
    });
    assert.equal(sub?.status, "expired");
  } finally {
    await app.close();
  }
});
