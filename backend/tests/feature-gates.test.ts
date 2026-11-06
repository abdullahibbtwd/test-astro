import test from "node:test";
import assert from "node:assert/strict";
import { prisma } from "../api/db";
import { requireFeature } from "../api/feature-gates";
import { resolveDailyLimit } from "../api/limits";
import {
  loadPlansConfig,
  resetPlansConfigCache,
  type PlansConfig,
} from "../api/plans";
import { demoTenantId, wipeDemoTenant } from "./helpers";

function gatedConfig(): PlansConfig {
  const base = loadPlansConfig();
  return {
    ...base,
    free_launch: { ...base.free_launch, entitle_all: false },
    feature_catalog: {
      ...base.feature_catalog,
      ask: { ...base.feature_catalog.ask, premium: true },
      family: { ...base.feature_catalog.family, premium: true },
      reports: { ...base.feature_catalog.reports, premium: true },
      map: { ...base.feature_catalog.map, premium: true },
    },
    plans: base.plans.map((p) =>
      p.id === "free"
        ? {
            ...p,
            features: [],
            daily_limits: {
              ask: 2,
              natal_reading: 1,
              map_reading: 1,
              forecast_reading: 1,
              compat_reading: 1,
            },
          }
        : {
            ...p,
            features: ["ask", "family", "reports", "map"],
            daily_limits: {
              ask: 50,
              natal_reading: 10,
              map_reading: 10,
              forecast_reading: 10,
              compat_reading: 10,
            },
          },
    ),
  };
}

async function ensureUser(email: string) {
  const id = demoTenantId(email);
  await wipeDemoTenant(email);
  await prisma().subscription.deleteMany({ where: { userId: id } });
  await prisma().user.upsert({
    where: { id },
    create: { id, email, displayName: email },
    update: {},
  });
  return id;
}

test("free user is blocked from premium features", async () => {
  resetPlansConfigCache();
  const config = gatedConfig();
  const id = await ensureUser("free-gate@example.com");
  await assert.rejects(
    () =>
      requireFeature(id, "ask", {
        config,
        env: { ASTRO_FREE_LAUNCH_ENTITLE_ALL: "0" },
      }),
    (error: any) => {
      assert.equal(error.problem?.code, "premium_required");
      assert.equal(error.problem?.status, 403);
      return true;
    },
  );
});

test("premium user is allowed through feature gates", async () => {
  resetPlansConfigCache();
  const config = gatedConfig();
  const id = await ensureUser("premium-gate@example.com");
  await prisma().subscription.create({
    data: {
      userId: id,
      planId: "premium",
      status: "active",
      expiresAt: new Date(Date.now() + 86400000),
      sourceStore: "fake",
      originalTransactionId: `txn-${id}-ok`,
      productId: "premium",
    },
  });
  await requireFeature(id, "ask", {
    config,
    env: { ASTRO_FREE_LAUNCH_ENTITLE_ALL: "0" },
  });
  await requireFeature(id, "map", {
    config,
    env: { ASTRO_FREE_LAUNCH_ENTITLE_ALL: "0" },
  });
});

test("expired subscription falls back to free and is blocked", async () => {
  resetPlansConfigCache();
  const config = gatedConfig();
  const id = await ensureUser("expired-gate@example.com");
  await prisma().subscription.create({
    data: {
      userId: id,
      planId: "premium",
      status: "expired",
      expiresAt: new Date(Date.now() - 60_000),
      sourceStore: "fake",
      originalTransactionId: `txn-${id}-exp`,
      productId: "premium",
    },
  });
  await assert.rejects(
    () =>
      requireFeature(id, "family", {
        config,
        env: { ASTRO_FREE_LAUNCH_ENTITLE_ALL: "0" },
      }),
    (error: any) => error.problem?.code === "premium_required",
  );
  const limit = await resolveDailyLimit(id, "ASK", {
    config,
    env: { ASTRO_FREE_LAUNCH_ENTITLE_ALL: "0" },
  });
  assert.equal(limit, 2);
});

test("cross-tenant isolation: premium on A does not entitle B", async () => {
  resetPlansConfigCache();
  const config = gatedConfig();
  const a = await ensureUser("tenant-a@example.com");
  const b = await ensureUser("tenant-b@example.com");
  await prisma().subscription.create({
    data: {
      userId: a,
      planId: "premium",
      status: "active",
      expiresAt: new Date(Date.now() + 86400000),
      sourceStore: "fake",
      originalTransactionId: `txn-${a}-iso`,
      productId: "premium",
    },
  });
  await requireFeature(a, "reports", {
    config,
    env: { ASTRO_FREE_LAUNCH_ENTITLE_ALL: "0" },
  });
  await assert.rejects(
    () =>
      requireFeature(b, "reports", {
        config,
        env: { ASTRO_FREE_LAUNCH_ENTITLE_ALL: "0" },
      }),
    (error: any) => error.problem?.code === "premium_required",
  );
  const premiumAsk = await resolveDailyLimit(a, "ASK", {
    config,
    env: { ASTRO_FREE_LAUNCH_ENTITLE_ALL: "0" },
  });
  const freeAsk = await resolveDailyLimit(b, "ASK", {
    config,
    env: { ASTRO_FREE_LAUNCH_ENTITLE_ALL: "0" },
  });
  assert.equal(premiumAsk, 50);
  assert.equal(freeAsk, 2);
});
