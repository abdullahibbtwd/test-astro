import fs from "node:fs";
import path from "node:path";
import type { PrismaClient } from "../src/generated/prisma/client.js";
import { Store } from "./store";

const STALE_JOB_MS = 15 * 60_000;

export async function exportAccount(store: Store) {
  return {
    format: "astrology-local-export-v1",
    exported_at: new Date().toISOString(),
    account: await store.get("me"),
    profiles: await store.list("profile:"),
    charts: await store.list("chart:"),
    calculation_data: await store.list("raw:"),
    natal_readings: await store.list("reading:"),
    natal_sections: (await store.list<any>("reading-section:")).map((s) => ({
      chart_key: s.chart_key,
      key: s.key,
      text_tr: s.text_tr,
      text_en: s.text_en,
      movement: s.movement,
      house: s.house,
      generated_at: s.generated_at,
    })),
    reading_progress: await store.list("reading-progress:"),
    reading_feedback: await store.list("reading-feedback:"),
    forecast_readings: await store.list("forecast-reading:"),
    forecast_index: await store.list("forecast-report:"),
    map_readings: await store.list("map-reading:"),
    map_index: await store.list("map-report:"),
    compatibility: (await store.list<any>("compat:")).map((r) => ({
      id: r.id,
      context: r.context,
      created_at: r.created_at,
      readings: r.readings,
    })),
    conversations: await store.list("ask-thread:"),
    conversation_feedback: await store.list("ask-feedback:"),
    saved_reports: await store.list("report:"),
  };
}

function wipeMapProductsCache(dataRoot: string) {
  const root = path.resolve(dataRoot);
  const cache = path.resolve(root, "map-products");
  if (path.dirname(cache) !== root)
    throw new Error("Invalid account cache path");
  fs.rmSync(cache, { recursive: true, force: true });
}

/**
 * Idempotent account deletion. Never re-initializes the account.
 * - No user + already tombstoned → success
 * - queued/running jobs older than 15 minutes are treated as dead (ignored for 409)
 */
export async function deleteAccount(
  db: PrismaClient,
  userId: string,
  dataRoot: string,
): Promise<void> {
  const user = await db.user.findUnique({ where: { id: userId } });
  const tombstone = await db.deletedUser.findUnique({ where: { id: userId } });

  if (!user) {
    if (!tombstone) {
      await db.deletedUser.upsert({
        where: { id: userId },
        create: { id: userId },
        update: {},
      });
    }
    wipeMapProductsCache(dataRoot);
    return;
  }

  const freshAfter = new Date(Date.now() - STALE_JOB_MS);
  const blocking = await db.job.count({
    where: {
      userId,
      status: { in: ["queued", "running"] },
      updatedAt: { gt: freshAfter },
    },
  });
  if (blocking > 0)
    throw Object.assign(new Error("Wait for active readings before deleting"), {
      statusCode: 409,
    });

  await db.$transaction(async (tx) => {
    await tx.deletedUser.upsert({
      where: { id: userId },
      create: { id: userId },
      update: { deletedAt: new Date() },
    });
    await tx.session.deleteMany({ where: { userId } });
    await tx.usageCounter.deleteMany({ where: { userId } });
    await tx.budgetCall.updateMany({
      where: { userId },
      data: { userId: "shared" },
    });
    await tx.budgetSettings.deleteMany({ where: { userId } });
    await tx.user.delete({ where: { id: userId } });
  });

  wipeMapProductsCache(dataRoot);
}
