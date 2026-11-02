import test from "node:test";
import { openStore, clearUsageCounters } from "./helpers";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { ReadingJobs } from "../api/reading-jobs";
import { prisma } from "../api/db";
import { DEFAULT_TENANT } from "../api/store";
import { Prisma } from "../src/generated/prisma/client.js";
import { fixture } from "../mock/fixtures";
import { validate } from "../../frontend/src/api/zod";

process.env.ASTRO_JOB_FAST = "1";

async function wipeReadingJobs() {
  await prisma().job.deleteMany({
    where: { userId: DEFAULT_TENANT, kind: "READING" },
  });
}

async function waitReading(jobs: ReadingJobs, profile: any, ms = 5000) {
  const start = Date.now();
  while (Date.now() - start < ms) {
    const value = await jobs.get(profile, "en");
    if (value.reading) return value.reading;
    await new Promise((r) => setTimeout(r, 20));
  }
  throw new Error("reading did not become ready");
}

test("reading jobs deduplicate, cache both languages and survive service restart", async () => {
  await clearUsageCounters();
  await wipeReadingJobs();
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), "reading-job-"));
  const store = await openStore();
  const profile = {
    ...fixture("profile.1.en"),
    chart_key: "reading-dedupe-key",
  };
  await store.put("profile:" + profile.profile_id, profile);
  await store.put("raw:" + profile.profile_id, {});
  let count = 0;
  const generator = async () => {
    count++;
    return {
      readings: { en: fixture("natal.1.en"), tr: fixture("natal.1.tr") },
    };
  };
  const jobs = await ReadingJobs.create(store, generator, true);
  try {
    const first = await jobs.get(profile, "en");
    assert.equal(
      (await jobs.get(profile, "tr")).job!.job_id,
      first.job!.job_id,
    );
    await waitReading(jobs, profile);
    await jobs.close();
    assert.equal(count, 1);
    validate("NatalReading", (await jobs.get(profile, "en")).reading);
    const restarted = await ReadingJobs.create(store, generator, true);
    try {
      validate("NatalReading", (await restarted.get(profile, "tr")).reading);
      assert.equal(count, 1);
      for (const report of await store.list("report:"))
        validate("ReportRef", report);
    } finally {
      await restarted.close();
    }
  } finally {
    await jobs.close().catch(() => {});
    await store.close();
    await prisma().job.deleteMany({
      where: { userId: DEFAULT_TENANT, kind: "READING" },
    });
    fs.rmSync(folder, { recursive: true, force: true });
  }
});

test("a deleted profile does not receive a late reading; crash reclaim keeps job pending", async () => {
  await clearUsageCounters();
  await wipeReadingJobs();
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), "reading-stale-"));
  const store = await openStore();
  const profile = {
    ...fixture("profile.1.en"),
    chart_key: "reading-stale-key",
  };
  await store.put("profile:" + profile.profile_id, profile);
  let finish!: (data: any) => void;
  const jobs = await ReadingJobs.create(
    store,
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
    true,
  );
  try {
    const first = await jobs.get(profile, "en");
    const start = Date.now();
    while (Date.now() - start < 3000) {
      const row = await prisma().job.findUnique({
        where: { id: first.job!.job_id },
      });
      if (row?.status === "running") break;
      await new Promise((r) => setTimeout(r, 20));
    }
    await store.remove("profile:" + profile.profile_id);
    finish({
      readings: { en: fixture("natal.1.en"), tr: fixture("natal.1.tr") },
    });
    await jobs.close();
    assert.equal(
      (await prisma().job.findUnique({ where: { id: first.job!.job_id } }))
        ?.status,
      "failed",
    );
    assert.equal((await store.list("report:")).length, 0);

    // Simulate crash: leave a running row, next worker reclaims to pending
    // without running generation when enabled=false.
    await prisma().job.update({
      where: { id: first.job!.job_id },
      data: {
        status: "running",
        finishedAt: null,
        error: Prisma.DbNull,
      },
    });
    const restarted = await ReadingJobs.create(store, undefined, false);
    try {
      assert.equal(
        (await prisma().job.findUnique({ where: { id: first.job!.job_id } }))
          ?.status,
        "pending",
      );
      assert.equal((await restarted.get(profile, "en")).job!.status, "queued");
      // Reclaimed jobs stay pending for the next enabled worker; retry does not
      // invent a new job while generation is paused.
      assert.equal(
        (await restarted.get(profile, "en", true)).job!.status,
        "queued",
      );
      assert.equal(
        (
          await restarted.get(
            { ...profile, chart_key: "reading-stale-new-key" },
            "en",
            true,
          )
        ).absence?.reason,
        "generation_paused",
      );
    } finally {
      await restarted.close();
    }
  } finally {
    await jobs.close().catch(() => {});
    await store.close();
    await prisma().job.deleteMany({
      where: { userId: DEFAULT_TENANT, kind: "READING" },
    });
    fs.rmSync(folder, { recursive: true, force: true });
  }
});
