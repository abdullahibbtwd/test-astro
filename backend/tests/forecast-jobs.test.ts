import test from "node:test";
import { openStore, waitFinish } from "./helpers";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { ForecastJobs, forecastContext } from "../api/forecast-jobs";
import { fixture } from "../mock/fixtures";
import { validate } from "../../frontend/src/api/zod";

test("forecast jobs deduplicate across languages, persist, isolate lenses and refuse stale results", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "forecast-job-"));
  const store = await openStore();
  const p = fixture("profile.1.en");
  await store.put("profile:" + p.profile_id, p);
  const ctx = forecastContext(p, p.birth.place, "2026-10-03", "day", "general");
  let calls = 0;
  let finish: ((value: any) => void) | undefined;
  const gen = async (input: any) => {
    calls++;
    await new Promise((resolve) => {
      finish = resolve;
    });
    return {
      context: input.context,
      from: ctx.target,
      to: ctx.target,
      segments: {},
      readings: {
        en: { reading: "English reading" },
        tr: { reading: "Türkçe yorum" },
      },
    };
  };
  const jobs = await ForecastJobs.create(store, true, gen);
  try {
    const first = await jobs.get(ctx, "en");
    assert.equal(first.status, "pending");
    assert.equal((await jobs.get(ctx, "tr")).job.job_id, first.job.job_id);
    (await waitFinish(() => finish))(null);
    finish = undefined;
    await jobs.close();
    assert.deepEqual(await jobs.get(ctx, "en"), {
      status: "ready",
      text: "English reading",
    });
    assert.equal(calls, 1);
    const restarted = await ForecastJobs.create(store, false, gen);
    assert.deepEqual(await restarted.get(ctx, "tr"), {
      status: "ready",
      text: "Türkçe yorum",
    });
    assert.equal(
      (await restarted.get({ ...ctx, lens: "personal" }, "en")).status,
      "absent",
    );
    const second = await jobs.get({ ...ctx, lens: "personal" }, "en");
    assert.equal(second.status, "pending");
    // Park in generate first so profile edit does not race the job's DB reads.
    const release = await waitFinish(() => finish);
    await store.put("profile:" + p.profile_id, { ...p, chart_key: "edited" });
    release(null);
    finish = undefined;
    await jobs.close();
    const failed = await jobs.get({ ...ctx, lens: "personal" }, "en");
    assert.equal(failed.status, "failed");
    assert.equal(calls, 2);
    for (const job of await store.list("job:")) validate("Job", job);
  } finally {
    finish?.(null);
    await jobs.close();
    await store.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
test("forecast validation rejects wrong windows and interrupted jobs require explicit retry", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "forecast-invalid-"));
  const store = await openStore();
  const p = fixture("profile.1.en");
  await store.put("profile:" + p.profile_id, p);
  const context = forecastContext(
    p,
    p.birth.place,
    "2026-10-03",
    "day",
    "general",
  );
  let calls = 0;
  const generator = async () => {
    calls++;
    return {
      context,
      from: context.target,
      to: calls === 1 ? "2026-10-04" : context.target,
      segments: {},
      readings: { en: { reading: "English" }, tr: { reading: "Türkçe" } },
    };
  };
  const first = await ForecastJobs.create(store, true, generator);
  try {
    await first.get(context, "en");
    await first.close();
    assert.equal((await first.get(context, "en")).status, "failed");
    assert.equal((await store.list("forecast-reading:")).length, 0);
    const record = (await store.list<any>("forecast-job:"))[0];
    await store.put("forecast-job:" + record.key, {
      ...record,
      job: { ...record.job, status: "running" },
    });
    const restarted = await ForecastJobs.create(store, true, generator);
    assert.equal((await restarted.get(context, "en")).status, "failed");
    assert.equal(calls, 1);
    await restarted.get(context, "en", true);
    await restarted.close();
    assert.equal((await restarted.get(context, "en")).status, "ready");
    assert.equal(calls, 2);
  } finally {
    await first.close();
    await store.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
