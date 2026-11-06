import test from "node:test";
import assert from "node:assert/strict";
import { prisma } from "../api/db";
import {
  computeEntitlements,
  withComputedEntitlements,
} from "../api/entitlements";
import { resetPlansConfigCache } from "../api/plans";
import { demoTenantId, wipeDemoTenant } from "./helpers";

const userId = () => demoTenantId("entitlements-user@example.com");

async function ensureUser() {
  const id = userId();
  await wipeDemoTenant("entitlements-user@example.com");
  await prisma().subscription.deleteMany({ where: { userId: id } });
  await prisma().user.upsert({
    where: { id },
    create: { id, email: "entitlements-user@example.com", displayName: "E" },
    update: {},
  });
  return id;
}

test("free launch entitle_all grants all catalog features", async () => {
  resetPlansConfigCache();
  const id = await ensureUser();
  const computed = await computeEntitlements(prisma(), id, {
    env: { ASTRO_FREE_LAUNCH_ENTITLE_ALL: "1" },
  });
  assert.equal(computed.free_launch, true);
  assert.equal(computed.entitlements.all, true);
  assert.equal(computed.entitlements.ask, true);
  assert.equal(computed.entitlements.map, true);
});

test("without free launch, no subscription → default (free) plan features", async () => {
  resetPlansConfigCache();
  const id = await ensureUser();
  const computed = await computeEntitlements(prisma(), id, {
    env: { ASTRO_FREE_LAUNCH_ENTITLE_ALL: "0" },
  });
  assert.equal(computed.free_launch, false);
  assert.equal(computed.plan_id, "free");
  assert.equal(computed.entitlements.all, undefined);
  // free plan features list is empty placeholders until owner fills them
  assert.deepEqual(computed.entitlements, {});
});

test("active premium subscription grants plan features when free launch off", async () => {
  resetPlansConfigCache();
  const id = await ensureUser();
  await prisma().subscription.create({
    data: {
      userId: id,
      planId: "premium",
      status: "active",
      expiresAt: new Date(Date.now() + 86400000),
      sourceStore: "fake",
      originalTransactionId: `txn-${id}-active`,
      productId: "placeholder.premium",
    },
  });
  const computed = await computeEntitlements(prisma(), id, {
    env: { ASTRO_FREE_LAUNCH_ENTITLE_ALL: "0" },
  });
  assert.equal(computed.plan_id, "premium");
  assert.equal(computed.entitlements.ask, true);
  assert.equal(computed.entitlements.family, true);
  assert.equal(computed.subscription?.status, "active");
});

test("expired subscription falls back to free plan", async () => {
  resetPlansConfigCache();
  const id = await ensureUser();
  await prisma().subscription.create({
    data: {
      userId: id,
      planId: "premium",
      status: "expired",
      expiresAt: new Date(Date.now() - 86400000),
      sourceStore: "fake",
      originalTransactionId: `txn-${id}-expired`,
      productId: "placeholder.premium",
    },
  });
  const computed = await computeEntitlements(prisma(), id, {
    env: { ASTRO_FREE_LAUNCH_ENTITLE_ALL: "0" },
  });
  assert.equal(computed.plan_id, "free");
  assert.deepEqual(computed.entitlements, {});
});

test("withComputedEntitlements keeps Me.entitlements as Record<string, true>", async () => {
  resetPlansConfigCache();
  const id = await ensureUser();
  const me = await withComputedEntitlements(prisma(), {
    user_id: id,
    entitlements: { all: true },
  });
  for (const v of Object.values(me.entitlements)) assert.equal(v, true);
});
