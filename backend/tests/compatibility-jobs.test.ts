import test from "node:test";
import { openStore, waitFinish } from "./helpers";
import assert from "node:assert/strict";
import { Store } from "../api/store";
import { CompatibilityJobs } from "../api/compatibility-jobs";
import { fixture } from "../mock/fixtures";
import { validate } from "../../frontend/src/api/zod";
const setup = async () => {
  const store = await openStore();
  const a = fixture("profile.1.en");
  const b = {
    ...a,
    profile_id: "second",
    chart_key: "second-chart",
    label: "Second",
  };
  for (const p of [a, b]) {
    await store.put("profile:" + p.profile_id, p);
    await store.put("raw:" + p.profile_id, {});
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
  const { store, input } = await setup();
  let calls = 0;
  const jobs = await CompatibilityJobs.create(store, true, async (data: any) => {
    calls++;
    return output(data.context);
  });
  const first = await jobs.create(input, "en");
  assert.equal(
    (await jobs.create(input, "tr")).compatibility_id,
    first.compatibility_id,
  );
  await jobs.close();
  assert.equal(calls, 1);
  const restarted = await CompatibilityJobs.create(store, false);
  const reading = await restarted.get(first.compatibility_id, "tr");
  validate("Compatibility", reading);
  assert.equal(reading.reading.status, "ready");
  assert.equal((await restarted.list()).length, 1);
  await restarted.remove(first.compatibility_id);
  assert.equal((await restarted.list()).length, 0);
  await store.close();
});
test("changed or deleted profiles cannot receive stale compatibility", async () => {
  const { store, input, b } = await setup();
  let finish!: (value: any) => void;
  let context: any;
  const jobs = await CompatibilityJobs.create(store, true, (data: any) => {
    context = data.context;
    return new Promise((resolve) => {
      finish = resolve;
    });
  });
  const first = await jobs.create(input, "en");
  await new Promise((resolve) => setImmediate(resolve));
  await store.put("profile:" + b.profile_id, { ...b, chart_key: "edited" });
  (await waitFinish(() => finish))(output(context));
  await jobs.close();
  await assert.rejects(() => jobs.get(first.compatibility_id, "en"));
  assert.equal((await jobs.list()).length, 0);
  await store.close();
});
test("disabled generation, same-person and unsupported family requests fail without calls", async () => {
  const { store, input } = await setup();
  const jobs = await CompatibilityJobs.create(store, false);
  await assert.rejects(() => jobs.create(input, "en"));
  await assert.rejects(() =>
    jobs.create({ ...input, profile_b_id: input.profile_a_id }, "en"),
  );
  await assert.rejects(() => jobs.create({ ...input, type: "family" }, "en"));
  assert.equal((await jobs.list()).length, 0);
  await store.close();
});

test("interrupted jobs require explicit retry and deleted jobs stay deleted", async () => {
  const { store, input } = await setup();
  let finish!: (v: any) => void;
  let context: any;
  const jobs = await CompatibilityJobs.create(store, true, async (data: any) => {
    context = data.context;
    return new Promise((resolve) => {
      finish = resolve;
    });
  });
  const first = await jobs.create(input, "en");
  await new Promise((resolve) => setImmediate(resolve));
  const restarted = await CompatibilityJobs.create(store, false);
  assert.equal(
    (await restarted.get(first.compatibility_id, "en")).reading.status,
    "failed",
  );
  await assert.rejects(() =>
    restarted.get(first.compatibility_id, "en", true),
  );
  await restarted.remove(first.compatibility_id);
  (await waitFinish(() => finish))(output(context));
  await jobs.close();
  assert.equal((await jobs.list()).length, 0);
  await store.close();
});
test("mismatched generation fails and explicit retry recovers", async () => {
  const { store, input } = await setup();
  let calls = 0;
  const jobs = await CompatibilityJobs.create(store, true, async (data: any) =>
    output(++calls === 1 ? {} : data.context),
  );
  const first = await jobs.create(input, "en");
  await jobs.close();
  assert.equal(
    (await jobs.get(first.compatibility_id, "en")).reading.status,
    "failed",
  );
  await jobs.create(input, "en");
  assert.equal(calls, 1);
  await jobs.get(first.compatibility_id, "tr", true);
  await jobs.close();
  assert.equal(
    (await jobs.get(first.compatibility_id, "tr")).reading.status,
    "ready",
  );
  assert.equal(calls, 2);
  await store.close();
});
