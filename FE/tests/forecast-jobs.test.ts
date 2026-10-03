import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { Store } from "../local-api/store";
import { ForecastJobs, forecastContext } from "../local-api/forecast-jobs";
import { fixture } from "../mock-api/fixtures";
import { validate } from "../src/api/zod";
test("forecast jobs deduplicate across languages, persist, isolate lenses and refuse stale results", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "forecast-job-"));
  const store = new Store(path.join(dir, "db.sqlite"));
  const p = fixture("profile.1.en");
  store.put("profile:" + p.profile_id, p);
  const ctx = forecastContext(p, p.birth.place, "2026-10-03", "day", "general");
  let calls = 0,
    finish!: (value: any) => void;
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
  const jobs = new ForecastJobs(store, true, gen);
  try {
    const first = jobs.get(ctx, "en");
    assert.equal(first.status, "pending");
    assert.deepEqual(jobs.get(ctx, "tr"), first);
    finish(null);
    await jobs.close();
    assert.deepEqual(jobs.get(ctx, "en"), {
      status: "ready",
      text: "English reading",
    });
    assert.equal(calls, 1);
    const restarted = new ForecastJobs(store, false, gen);
    assert.deepEqual(restarted.get(ctx, "tr"), {
      status: "ready",
      text: "Türkçe yorum",
    });
    assert.equal(
      restarted.get({ ...ctx, lens: "personal" }, "en").status,
      "absent",
    );
    const second = jobs.get({ ...ctx, lens: "personal" }, "en");
    assert.equal(second.status, "pending");
    store.put("profile:" + p.profile_id, { ...p, chart_key: "edited" });
    finish(null);
    await jobs.close();
    const failed = jobs.get({ ...ctx, lens: "personal" }, "en");
    assert.equal(failed.status, "failed");
    assert.equal(calls, 2);
    for (const job of store.list("job:")) validate("Job", job);
  } finally {
    await jobs.close();
    store.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
test("forecast validation rejects wrong windows and interrupted jobs require explicit retry", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "forecast-invalid-"));
  const store = new Store(path.join(dir, "db.sqlite"));
  const p = fixture("profile.1.en");
  store.put("profile:" + p.profile_id, p);
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
  const first = new ForecastJobs(store, true, generator);
  try {
    first.get(context, "en");
    await first.close();
    assert.equal(first.get(context, "en").status, "failed");
    assert.equal(store.list("forecast-reading:").length, 0);
    const record = store.list<any>("forecast-job:")[0];
    store.put("forecast-job:" + record.key, {
      ...record,
      job: { ...record.job, status: "running" },
    });
    const restarted = new ForecastJobs(store, true, generator);
    assert.equal(restarted.get(context, "en").status, "failed");
    assert.equal(calls, 1);
    restarted.get(context, "en", true);
    await restarted.close();
    assert.equal(restarted.get(context, "en").status, "ready");
    assert.equal(calls, 2);
  } finally {
    await first.close();
    store.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
