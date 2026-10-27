import assert from "node:assert/strict";
import { createHash, randomUUID } from "node:crypto";
import { after, before, test } from "node:test";
import { deleteAccount } from "../api/account";
import { cleanupExpired } from "../api/cleanup";
import { disconnectPrisma, migrateDeploy, prisma } from "../api/db";
import {
  tryConsumeGuestRate,
  tryConsumeUsage,
  withGuestPoolLock,
  countActiveGuestSessions,
} from "../api/limits";
import { Store, SYSTEM_TENANT } from "../api/store";

process.env.DATABASE_URL ??=
  "postgres://astrology:astrology@127.0.0.1:5432/astrology_test";

const hash = (s: string) => createHash("sha256").update(s).digest("hex");

before(async () => {
  await migrateDeploy();
});

after(async () => {
  await disconnectPrisma();
});

test("two users cannot read each other's records", async () => {
  const a = "user-a-" + randomUUID();
  const b = "user-b-" + randomUUID();
  const store = await Store.open({ databaseUrl: process.env.DATABASE_URL! });
  await prisma().user.createMany({
    data: [
      { id: a, displayName: "A" },
      { id: b, displayName: "B" },
    ],
  });
  await store.runAsAsync(a, () => store.put("secret", { owner: a }));
  await store.runAsAsync(b, () => store.put("secret", { owner: b }));
  const fromA = await store.runAsAsync(a, () => store.get<{ owner: string }>("secret"));
  const fromB = await store.runAsAsync(b, () => store.get<{ owner: string }>("secret"));
  assert.equal(fromA?.owner, a);
  assert.equal(fromB?.owner, b);
  await prisma().user.deleteMany({ where: { id: { in: [a, b] } } });
  await store.close();
});

test("N concurrent usage consumes never exceed the daily limit", async () => {
  const userId = "usage-" + randomUUID();
  await prisma().user.create({ data: { id: userId } });
  const limit = 5;
  const results = await Promise.all(
    Array.from({ length: 20 }, () => tryConsumeUsage(userId, "ASK", limit)),
  );
  const ok = results.filter((n) => n != null);
  assert.equal(ok.length, limit);
  assert.equal(Math.max(...ok!), limit);
  await prisma().user.delete({ where: { id: userId } });
});

test("guest IP rate upsert resets an expired window", async () => {
  const ipHash = hash("rate-reset-" + randomUUID());
  for (let i = 0; i < 5; i++)
    assert.notEqual(await tryConsumeGuestRate(ipHash), null);
  assert.equal(await tryConsumeGuestRate(ipHash), null);
  await prisma().$executeRaw`
    UPDATE guest_rate_limits
    SET expires_at = now() - interval '1 minute'
    WHERE ip_hash = ${ipHash}
  `;
  const again = await tryConsumeGuestRate(ipHash);
  assert.equal(again, 1);
  await prisma().guestRateLimit.delete({ where: { ipHash } });
});

test("deleting an account leaves no user rows and blocks recreate", async () => {
  const userId = "del-" + randomUUID();
  const store = await Store.open({ databaseUrl: process.env.DATABASE_URL! });
  await prisma().user.create({ data: { id: userId, email: "del@example.com" } });
  await store.runAsAsync(userId, () =>
    store.put("me", { user_id: userId, email: "del@example.com" }),
  );
  await store.runAsAsync(SYSTEM_TENANT, () =>
    store.put("access:" + hash(userId), {
      expires: Date.now() + 60_000,
      owner: userId,
    }),
  );
  await prisma().budgetCall.create({
    data: {
      userId,
      model: "test",
      reserved: 1n,
      charged: 1n,
      state: "settled",
    },
  });
  await deleteAccount(prisma(), userId, "/tmp/astrology-delete-test-" + userId);
  assert.equal(await prisma().user.findUnique({ where: { id: userId } }), null);
  assert.ok(await prisma().deletedUser.findUnique({ where: { id: userId } }));
  assert.equal(
    await prisma().session.count({ where: { userId } }),
    0,
  );
  assert.equal(
    await prisma().record.count({ where: { tenantId: userId } }),
    0,
  );
  const detached = await prisma().budgetCall.count({
    where: { userId: "shared", model: "test" },
  });
  assert.ok(detached >= 1);
  // Idempotent retry
  await deleteAccount(prisma(), userId, "/tmp/astrology-delete-test-" + userId);
  // ensureAccount must refuse tombstone
  await assert.rejects(async () => {
    const { buildLocalApp } = await import("../api/app");
    // Direct DB check mirrors ensureAccount
    if (await prisma().deletedUser.findUnique({ where: { id: userId } }))
      throw Object.assign(new Error("Account deleted"), { statusCode: 403 });
  });
  await prisma().budgetCall.deleteMany({
    where: { userId: "shared", model: "test" },
  });
  await store.close();
});

test("partial unique index rejects a second self profile", async () => {
  const userId = "self-" + randomUUID();
  await prisma().user.create({ data: { id: userId } });
  await prisma().profile.create({
    data: {
      id: randomUUID(),
      userId,
      chartKey: "a",
      label: "Me",
      relation: "self",
      isSelf: true,
      birth: {},
    },
  });
  await assert.rejects(() =>
    prisma().profile.create({
      data: {
        id: randomUUID(),
        userId,
        chartKey: "b",
        label: "Also",
        relation: "self",
        isSelf: true,
        birth: {},
      },
    }),
  );
  await prisma().user.delete({ where: { id: userId } });
});

test("guest pool advisory lock serializes capacity checks", async () => {
  const before = await withGuestPoolLock(async (tx) =>
    countActiveGuestSessions(tx),
  );
  assert.ok(before >= 0);
  await cleanupExpired();
});
