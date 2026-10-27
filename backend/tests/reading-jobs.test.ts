import test from "node:test";
import { openStore } from "./helpers";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { Store } from "../api/store";
import { ReadingJobs } from "../api/reading-jobs";
import { fixture } from "../mock/fixtures";
import { validate } from "../../frontend/src/api/zod";
test("reading jobs deduplicate, cache both languages and survive service restart", async () => {
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), "reading-job-"));
  const store = await openStore();
  const profile = fixture("profile.1.en");
  await store.put("profile:" + profile.profile_id, profile);
  await store.put("raw:" + profile.profile_id, {});
  let count = 0;
  const generator = async () => {
    count++;
    return {
      readings: { en: fixture("natal.1.en"), tr: fixture("natal.1.tr") },
    };
  };
  try {
    const jobs = await ReadingJobs.create(store, generator, true);
    const first = await jobs.get(profile, "en");
    assert.equal(
      (await jobs.get(profile, "tr")).job!.job_id,
      first.job!.job_id,
    );
    await jobs.close();
    assert.equal(count, 1);
    validate("NatalReading", (await jobs.get(profile, "en")).reading);
    const restarted = await ReadingJobs.create(store, generator, true);
    validate("NatalReading", (await restarted.get(profile, "tr")).reading);
    assert.equal(count, 1);
    for (const report of await store.list("report:"))
      validate("ReportRef", report);
  } finally {
    await store.close();
    fs.rmSync(folder, { recursive: true, force: true });
  }
});
test("a deleted profile does not receive a late reading and an interrupted job needs explicit retry", async () => {
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), "reading-stale-"));
  const store = await openStore();
  const profile = fixture("profile.1.en");
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
    await new Promise((resolve) => setImmediate(resolve));
    await store.remove("profile:" + profile.profile_id);
    finish({
      readings: { en: fixture("natal.1.en"), tr: fixture("natal.1.tr") },
    });
    await jobs.close();
    assert.equal(
      (await store.get("job:" + first.job!.job_id)).status,
      "failed",
    );
    assert.equal((await store.list("report:")).length, 0);
    const key = profile.chart_key;
    await store.put("reading-job:" + key, {
      key,
      job: { ...first.job, status: "running" },
    });
    const restarted = await ReadingJobs.create(store, undefined, false);
    assert.equal(
      (await restarted.get(profile, "en")).job!.status,
      "failed",
    );
    assert.equal(
      (await restarted.get(profile, "en", true)).absence?.reason,
      "generation_paused",
    );
  } finally {
    await jobs.close();
    await store.close();
    fs.rmSync(folder, { recursive: true, force: true });
  }
});
