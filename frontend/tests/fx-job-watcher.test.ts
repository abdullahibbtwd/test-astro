import { test } from "node:test";
import assert from "node:assert/strict";
import { JobWatcher } from "../src/api/job-watcher-core";
import type { Job } from "../contracts/spec-types";
test("one scheduler spaces three jobs, pauses in background, resumes and completes once", async () => {
  let now = 0,
    nextId = 0;
  const timers = new Map<number, { at: number; fn: () => void }>(),
    calls: { id: string; time: number }[] = [],
    complete: string[] = [];
  const job = (id: string): Job =>
    ({
      job_id: id,
      kind: "natal_reading",
      status: now >= 10000 ? "succeeded" : "running",
      created_at: new Date(0).toISOString(),
      updated_at: new Date(now).toISOString(),
      eta_seconds: null,
      error: null,
      stages: [],
    }) as Job;
  const watcher = new JobWatcher({
    now: () => now,
    setTimer: ((fn: () => void, delay: number) => {
      const id = ++nextId;
      timers.set(id, { at: now + delay, fn });
      return id;
    }) as any,
    clearTimer: ((id: number) => timers.delete(id)) as any,
    fetch: async (_lang, id) => {
      calls.push({ id, time: now });
      return job(id);
    },
    publish: () => {},
    complete: (e) => complete.push(e.job.job_id),
  });
  async function advance(to: number) {
    while (true) {
      const entry = [...timers].sort((a, b) => a[1].at - b[1].at)[0];
      if (!entry || entry[1].at > to) break;
      timers.delete(entry[0]);
      now = entry[1].at;
      entry[1].fn();
      await Promise.resolve();
      await Promise.resolve();
    }
    now = to;
  }
  for (const id of ["a", "b", "c"])
    watcher.register("en", { id, created_at: new Date(0).toISOString() }, [
      "resource",
      "en",
      id,
    ]);
  watcher.register("en", { id: "a" }, ["resource", "en", "second-parent"]);
  watcher.setActive(true);
  await advance(7000);
  assert.ok(calls.length > 3);
  for (let i = 1; i < calls.length; i++)
    assert.ok(calls[i]!.time - calls[i - 1]!.time >= 1000);
  const before = calls.length;
  watcher.setActive(false);
  await advance(20000);
  assert.equal(calls.length, before);
  watcher.setActive(true);
  await advance(22000);
  assert.deepEqual([...complete].sort(), ["a", "b", "c"]);
  watcher.register("en", { id: "a" }, ["resource", "en", "a"]);
  await advance(30000);
  assert.equal(complete.length, 3);
  watcher.clear();
});
