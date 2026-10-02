import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { Store } from "../local-api/store";
import { ReadingJobs } from "../local-api/reading-jobs";
import { fixture } from "../mock-api/fixtures";
import { validate } from "../src/api/zod";
test("reading jobs deduplicate, cache both languages and survive service restart", async () => {
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), "reading-job-"));
  const store = new Store(path.join(folder, "test.sqlite"));
  const profile = fixture("profile.1.en");
  store.put("profile:" + profile.profile_id, profile);
  store.put("raw:" + profile.profile_id, {});
  let count = 0;
  const generator = async () => {
    count++;
    return {
      readings: { en: fixture("natal.1.en"), tr: fixture("natal.1.tr") },
    };
  };
  try {
    const jobs = new ReadingJobs(store, generator, true);
    const first = jobs.get(profile, "en");
    assert.equal(jobs.get(profile, "tr").job!.job_id, first.job!.job_id);
    await jobs.close();
    assert.equal(count, 1);
    validate("NatalReading", jobs.get(profile, "en").reading);
    const restarted = new ReadingJobs(store, generator, true);
    validate("NatalReading", restarted.get(profile, "tr").reading);
    assert.equal(count, 1);
    for (const report of store.list("report:")) validate("ReportRef", report);
  } finally {
    store.close();
    fs.rmSync(folder, { recursive: true, force: true });
  }
});
test("a deleted profile does not receive a late reading and an interrupted job needs explicit retry", async () => {
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), "reading-stale-"));
  const store = new Store(path.join(folder, "test.sqlite"));
  const profile = fixture("profile.1.en");
  store.put("profile:" + profile.profile_id, profile);
  let finish!: (data: any) => void;
  const jobs = new ReadingJobs(
    store,
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
    true,
  );
  try {
    const first = jobs.get(profile, "en");
    await new Promise((resolve) => setImmediate(resolve));
    store.remove("profile:" + profile.profile_id);
    finish({
      readings: { en: fixture("natal.1.en"), tr: fixture("natal.1.tr") },
    });
    await jobs.close();
    assert.equal(store.get("job:" + first.job!.job_id).status, "failed");
    assert.equal(store.list("report:").length, 0);
    const key = profile.chart_key;
    store.put("reading-job:" + key, {
      key,
      job: { ...first.job, status: "running" },
    });
    const restarted = new ReadingJobs(store, undefined, false);
    assert.equal(restarted.get(profile, "en").job!.status, "failed");
    assert.throws(() => restarted.get(profile, "en", true));
  } finally {
    await jobs.close();
    store.close();
    fs.rmSync(folder, { recursive: true, force: true });
  }
});
