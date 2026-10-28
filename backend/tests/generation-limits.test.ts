import test from "node:test";
import assert from "node:assert/strict";
import { openStore, wipeDemoTenant } from "./helpers";
import { ReadingJobs } from "../api/reading-jobs";
import { MapJobs, mapContext } from "../api/map-jobs";
import { fixture, collection } from "../mock/fixtures";
import { prisma } from "../api/db";
import {
  GENERATION_DAILY_LIMITS,
  tryConsumeUsage,
  utcDay,
} from "../api/limits";

test("natal generation returns 429 after the daily limit with a clear detail", async () => {
  await wipeDemoTenant();
  const store = await openStore();
  const p = fixture("profile.1.en");
  await store.put("profile:" + p.profile_id, p);
  await store.put("raw:" + p.profile_id, {});
  const userId = store.tenant();
  const limit = GENERATION_DAILY_LIMITS.NATAL_READING;
  await prisma().$executeRawUnsafe(
    `DELETE FROM usage_counters WHERE user_id = $1 AND kind = 'NATAL_READING'`,
    userId,
  );
  await prisma().$executeRawUnsafe(
    `INSERT INTO usage_counters (user_id, kind, date, count)
     VALUES ($1, 'NATAL_READING', $2::date, $3)`,
    userId,
    utcDay(),
    limit,
  );
  const jobs = await ReadingJobs.create(
    store,
    async () => {
      throw new Error("should not run");
    },
    true,
  );
  try {
    await assert.rejects(
      () => jobs.get(p, "en"),
      (error: any) => {
        assert.equal(error.problem?.status, 429);
        assert.equal(error.problem?.code, "rate_limited");
        assert.match(String(error.problem?.detail ?? ""), /natal readings/i);
        assert.match(
          String(error.problem?.detail ?? ""),
          new RegExp(String(limit)),
        );
        return true;
      },
    );
  } finally {
    await jobs.close();
    await store.close();
  }
});

test("map generation returns 429 once the daily cap is reached", async () => {
  await wipeDemoTenant();
  const store = await openStore();
  const p = fixture("profile.1.en");
  await store.put("profile:" + p.profile_id, p);
  await store.put("raw:" + p.profile_id, {});
  const userId = store.tenant();
  const limit = GENERATION_DAILY_LIMITS.MAP_READING;
  await prisma().$executeRawUnsafe(
    `DELETE FROM usage_counters WHERE user_id = $1 AND kind = 'MAP_READING'`,
    userId,
  );
  await prisma().$executeRawUnsafe(
    `INSERT INTO usage_counters (user_id, kind, date, count)
     VALUES ($1, 'MAP_READING', $2::date, $3)`,
    userId,
    utcDay(),
    limit,
  );
  const full = collection("place-report.", "en")[0];
  const facts = {
    ...full,
    reading: { status: "absent", absence: { reason: "not_generated" } },
    cards: full.cards.map((c: any) => ({ ...c, text: null })),
  };
  const context = mapContext(p, "place", {
    place: full.place,
    focus_goal: null,
  });
  const jobs = await MapJobs.create(store, true, async () => {
    throw new Error("should not run");
  });
  try {
    await assert.rejects(
      () => jobs.get(context, facts, "en"),
      (error: any) => {
        assert.equal(error.problem?.code, "rate_limited");
        assert.match(String(error.problem?.detail ?? ""), /map readings/i);
        return true;
      },
    );
  } finally {
    await jobs.close();
    await store.close();
  }
});

test("generation usage consume is atomic under concurrent callers", async () => {
  await wipeDemoTenant();
  const store = await openStore();
  const userId = store.tenant();
  const limit = 3;
  await prisma().$executeRawUnsafe(
    `DELETE FROM usage_counters WHERE user_id = $1 AND kind = 'FORECAST_READING'`,
    userId,
  );
  const results = await Promise.all(
    Array.from({ length: 8 }, () =>
      tryConsumeUsage(userId, "FORECAST_READING", limit),
    ),
  );
  const accepted = results.filter((count) => count != null);
  const rejected = results.filter((count) => count == null);
  assert.equal(accepted.length, limit);
  assert.equal(rejected.length, 5);
  assert.deepEqual(
    accepted.sort((a, b) => (a ?? 0) - (b ?? 0)),
    [1, 2, 3],
  );
  await store.close();
});
