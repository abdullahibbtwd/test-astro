import test from "node:test";
import assert from "node:assert/strict";
import { openStore, clearUsageCounters } from "./helpers";
import { DEFAULT_TENANT } from "../api/store";
import { ReadingJobs } from "../api/reading-jobs";
import { prisma } from "../api/db";
import { fixture } from "../mock/fixtures";

process.env.ASTRO_JOB_FAST = "1";

async function wipeReadingJobs() {
  await prisma().job.deleteMany({
    where: { userId: DEFAULT_TENANT, kind: "READING" },
  });
}

async function waitJob(
  jobs: ReadingJobs,
  jobId: string,
  status: string,
  ms = 5000,
) {
  const start = Date.now();
  while (Date.now() - start < ms) {
    const job = await jobs.getJob(jobId);
    if (job?.status === status) return job;
    await new Promise((r) => setTimeout(r, 20));
  }
  throw new Error(`job ${jobId} did not reach ${status}`);
}

test("kill worker mid-job: running job is reclaimed to pending and retried", async () => {
  await clearUsageCounters();
  await wipeReadingJobs();
  const store = await openStore();
  const profile = fixture("profile.1.en");
  await store.put("profile:" + profile.profile_id, profile);
  await store.put("raw:" + profile.profile_id, {});
  let finish!: (value: any) => void;
  const hanging = new Promise<any>((resolve) => {
    finish = resolve;
  });
  const first = await ReadingJobs.create(store, () => hanging, true);
  try {
    const enqueued = await first.get(profile, "en");
    assert.ok(enqueued.job);
    await waitJob(first, enqueued.job!.job_id, "running");
    await first.close({ abandon: true });
    assert.equal(
      (await prisma().job.findUnique({ where: { id: enqueued.job!.job_id } }))
        ?.status,
      "running",
    );

    let runs = 0;
    const second = await ReadingJobs.create(
      store,
      async () => {
        runs++;
        return {
          readings: { en: fixture("natal.1.en"), tr: fixture("natal.1.tr") },
        };
      },
      true,
    );
    try {
      assert.equal(
        (await prisma().job.findUnique({ where: { id: enqueued.job!.job_id } }))
          ?.status,
        "pending",
      );
      await waitJob(second, enqueued.job!.job_id, "succeeded");
      assert.equal(runs, 1);
      assert.ok((await second.get(profile, "en")).reading);
    } finally {
      finish({
        readings: { en: fixture("natal.1.en"), tr: fixture("natal.1.tr") },
      });
      await second.close();
    }
  } finally {
    await first.close({ abandon: true }).catch(() => {});
    await store.close();
    await prisma().job.deleteMany({
      where: { userId: DEFAULT_TENANT, kind: "READING" },
    });
  }
});

test("two reading jobs at once both complete (no 409 busy)", async () => {
  await clearUsageCounters();
  await wipeReadingJobs();
  const store = await openStore();
  const a = fixture("profile.1.en");
  const b = {
    ...fixture("profile.1.en"),
    profile_id: "durable-b",
    chart_key: "durable-b-key",
    label: "B",
  };
  for (const p of [a, b]) {
    await store.put("profile:" + p.profile_id, p);
    await store.put("raw:" + p.profile_id, {});
  }
  let releases: Array<() => void> = [];
  const jobs = await ReadingJobs.create(
    store,
    async () => {
      await new Promise<void>((r) => releases.push(r));
      return {
        readings: { en: fixture("natal.1.en"), tr: fixture("natal.1.tr") },
      };
    },
    true,
  );
  try {
    const first = await jobs.get(a, "en");
    const second = await jobs.get(b, "en");
    assert.ok(first.job && second.job);
    assert.notEqual(first.job!.job_id, second.job!.job_id);
    // Both claimed without busy error.
    await waitJob(jobs, first.job!.job_id, "running");
    await waitJob(jobs, second.job!.job_id, "running");
    assert.equal(releases.length, 2);
    for (const release of releases) release();
    await waitJob(jobs, first.job!.job_id, "succeeded");
    await waitJob(jobs, second.job!.job_id, "succeeded");
    assert.ok((await jobs.get(a, "en")).reading);
    assert.ok((await jobs.get(b, "en")).reading);
  } finally {
    for (const release of releases) release();
    await jobs.close();
    await store.close();
    await prisma().job.deleteMany({
      where: { userId: DEFAULT_TENANT, kind: "READING" },
    });
  }
});

test("failing job reaches failed after 3 retries", async () => {
  await clearUsageCounters();
  await wipeReadingJobs();
  const store = await openStore();
  const profile = {
    ...fixture("profile.1.en"),
    chart_key: "durable-fail-key",
  };
  await store.put("profile:" + profile.profile_id, profile);
  await store.put("raw:" + profile.profile_id, {});
  let calls = 0;
  const jobs = await ReadingJobs.create(
    store,
    async () => {
      calls++;
      throw new Error("boom");
    },
    true,
  );
  try {
    const enqueued = await jobs.get(profile, "en");
    assert.ok(enqueued.job);
    await waitJob(jobs, enqueued.job!.job_id, "failed", 10_000);
    const row = await prisma().job.findUnique({
      where: { id: enqueued.job!.job_id },
    });
    assert.equal(row?.status, "failed");
    assert.equal(row?.attempts, 3);
    assert.equal(calls, 3);
    const seen = await jobs.get(profile, "en");
    assert.equal(seen.job?.status, "failed");
  } finally {
    await jobs.close();
    await store.close();
    await prisma().job.deleteMany({
      where: { userId: DEFAULT_TENANT, kind: "READING" },
    });
  }
});

test("app sees job status move queued → running → succeeded via getJob", async () => {
  await clearUsageCounters();
  await wipeReadingJobs();
  const store = await openStore();
  const profile = {
    ...fixture("profile.1.en"),
    chart_key: "durable-poll-key",
  };
  await store.put("profile:" + profile.profile_id, profile);
  await store.put("raw:" + profile.profile_id, {});
  let finish!: (value: any) => void;
  const jobs = await ReadingJobs.create(
    store,
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
    true,
  );
  try {
    const enqueued = await jobs.get(profile, "en");
    assert.equal(enqueued.job?.status, "queued");
    await waitJob(jobs, enqueued.job!.job_id, "running");
    assert.equal(
      (await jobs.getJob(enqueued.job!.job_id))?.status,
      "running",
    );
    finish({
      readings: { en: fixture("natal.1.en"), tr: fixture("natal.1.tr") },
    });
    await waitJob(jobs, enqueued.job!.job_id, "succeeded");
    assert.ok((await jobs.get(profile, "en")).reading);
  } finally {
    await jobs.close();
    await store.close();
    await prisma().job.deleteMany({
      where: { userId: DEFAULT_TENANT, kind: "READING" },
    });
  }
});
