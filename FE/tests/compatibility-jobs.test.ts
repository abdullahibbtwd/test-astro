import test from "node:test";
import assert from "node:assert/strict";
import { Store } from "../local-api/store";
import { CompatibilityJobs } from "../local-api/compatibility-jobs";
import { fixture } from "../mock-api/fixtures";
import { validate } from "../src/api/zod";
const setup = () => {
  const store = new Store(":memory:");
  const a = fixture("profile.1.en");
  const b = {
    ...a,
    profile_id: "second",
    chart_key: "second-chart",
    label: "Second",
  };
  for (const p of [a, b]) {
    store.put("profile:" + p.profile_id, p);
    store.put("raw:" + p.profile_id, {});
  }
  return {
    store,
    a,
    b,
    input: {
      profile_a_id: a.profile_id,
      profile_b_id: b.profile_id,
      type: "love" as const,
    },
  };
};
const output = (context: any) => ({
  context,
  readings: Object.fromEntries(
    ["en", "tr"].map((lang) => [
      lang,
      {
        title: lang,
        sections: [
          {
            key: "test",
            movement: 0,
            title: lang,
            text: "A complete test reading",
          },
        ],
      },
    ]),
  ),
});
test("compatibility deduplicates both languages and persists results", async () => {
  const { store, input } = setup();
  let calls = 0;
  const jobs = new CompatibilityJobs(store, true, async (data: any) => {
    calls++;
    return output(data.context);
  });
  const first = jobs.create(input, "en");
  assert.equal(
    jobs.create(input, "tr").compatibility_id,
    first.compatibility_id,
  );
  await jobs.close();
  assert.equal(calls, 1);
  const restarted = new CompatibilityJobs(store, false);
  const reading = restarted.get(first.compatibility_id, "tr");
  validate("Compatibility", reading);
  assert.equal(reading.reading.status, "ready");
  assert.equal(restarted.list().length, 1);
  restarted.remove(first.compatibility_id);
  assert.equal(restarted.list().length, 0);
  store.close();
});
test("changed or deleted profiles cannot receive stale compatibility", async () => {
  const { store, input, b } = setup();
  let finish!: (value: any) => void;
  let context: any;
  const jobs = new CompatibilityJobs(store, true, (data: any) => {
    context = data.context;
    return new Promise((resolve) => {
      finish = resolve;
    });
  });
  const first = jobs.create(input, "en");
  await new Promise((resolve) => setImmediate(resolve));
  store.put("profile:" + b.profile_id, { ...b, chart_key: "edited" });
  finish(output(context));
  await jobs.close();
  assert.throws(() => jobs.get(first.compatibility_id, "en"));
  assert.equal(jobs.list().length, 0);
  store.close();
});
test("disabled generation, same-person and unsupported family requests fail without calls", () => {
  const { store, input } = setup();
  const jobs = new CompatibilityJobs(store, false);
  assert.throws(() => jobs.create(input, "en"));
  assert.throws(() =>
    jobs.create({ ...input, profile_b_id: input.profile_a_id }, "en"),
  );
  assert.throws(() => jobs.create({ ...input, type: "family" }, "en"));
  assert.equal(jobs.list().length, 0);
  store.close();
});

test("interrupted jobs require explicit retry and deleted jobs stay deleted", async () => {
  const { store, input } = setup();
  let finish!: (v: any) => void;
  let context: any;
  const jobs = new CompatibilityJobs(store, true, async (data: any) => {
    context = data.context;
    return new Promise((resolve) => {
      finish = resolve;
    });
  });
  const first = jobs.create(input, "en");
  await new Promise((resolve) => setImmediate(resolve));
  const restarted = new CompatibilityJobs(store, false);
  assert.equal(
    restarted.get(first.compatibility_id, "en").reading.status,
    "failed",
  );
  assert.throws(() => restarted.get(first.compatibility_id, "en", true));
  restarted.remove(first.compatibility_id);
  finish(output(context));
  await jobs.close();
  assert.equal(jobs.list().length, 0);
  store.close();
});
test("mismatched generation fails and explicit retry recovers", async () => {
  const { store, input } = setup();
  let calls = 0;
  const jobs = new CompatibilityJobs(store, true, async (data: any) =>
    output(++calls === 1 ? {} : data.context),
  );
  const first = jobs.create(input, "en");
  await jobs.close();
  assert.equal(jobs.get(first.compatibility_id, "en").reading.status, "failed");
  jobs.create(input, "en");
  assert.equal(calls, 1);
  jobs.get(first.compatibility_id, "tr", true);
  await jobs.close();
  assert.equal(jobs.get(first.compatibility_id, "tr").reading.status, "ready");
  assert.equal(calls, 2);
  store.close();
});
