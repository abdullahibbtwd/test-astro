import test from "node:test";
import assert from "node:assert/strict";
import { Store } from "../local-api/store";
import { ProgressiveReadings } from "../local-api/progressive-readings";
import { fixture } from "../mock-api/fixtures";
import { validate } from "../src/api/zod";

const waitUntil = async (
  ready: () => boolean | Promise<boolean>,
  label = "condition",
) => {
  const deadline = Date.now() + 5000;
  while (!(await ready())) {
    if (Date.now() > deadline) throw new Error(`Timed out waiting for ${label}`);
    await new Promise((resolve) => setImmediate(resolve));
  }
};

async function setup() {
  const store = await Store.open(":memory:");
  const profile = fixture("profile.1.en");
  await store.put("profile:" + profile.profile_id, profile);
  await store.put("raw:" + profile.profile_id, {});
  const tr = fixture("natal.1.tr"),
    en = fixture("natal.1.en");
  const plan = {
    order: tr.sections.map((s: any) => s.key),
    movement: {},
    house: {},
    titles: {},
    routed_ids: {},
  } as any;
  for (const s of tr.sections) {
    plan.movement[s.key] = s.movement;
    plan.house[s.key] = s.house;
    plan.titles[s.key] = {
      tr: s.title,
      en: en.sections.find((x: any) => x.key === s.key).title,
    };
    plan.routed_ids[s.key] = ["internal:" + s.key];
  }
  const counts = { draft: 0, finalize: 0, translation: 0, active: 0, max: 0 };
  const bridge = async (data: any) => {
    if (data.op === "prepare")
      return {
        plan,
        titles: { tr: tr.title, en: en.title },
        parts: { tr: tr.parts, en: en.parts },
      };
    if (["retain", "release"].includes(data.op)) return {};
    if (data.op === "publish") return data.section;
    if (data.op === "translate") {
      counts.translation++;
      return {
        text_en: en.sections.find((s: any) => s.key === data.section_key).text,
      };
    }
    counts.draft++;
    counts.finalize++;
    counts.active++;
    counts.max = Math.max(counts.active, counts.max);
    await new Promise((resolve) => setImmediate(resolve));
    counts.active--;
    return {
      key: data.section_key,
      text_tr: tr.sections.find((s: any) => s.key === data.section_key).text,
      principle_ids: plan.routed_ids[data.section_key],
      draft_tr: "private",
      usage: { private: true },
    };
  };
  const jobs = await ProgressiveReadings.create(store, true, bridge);
  return { store, profile, jobs, counts, plan, bridge };
}

test("ONB pay per read: two calls idle, one read ahead, no eager English, immutable after completion", async () => {
  const { store, profile, jobs, counts, plan } = await setup();
  try {
    await jobs.start(profile);
    await waitUntil(() => counts.draft + counts.finalize >= 2, "initial section work");
    await jobs.close();
    assert.equal(counts.draft + counts.finalize, 2);
    assert.equal(counts.translation, 0);
    await waitUntil(
      async () =>
        !!(await jobs.section(profile, "core_identity", "tr")).section?.text,
      "core section ready",
    );
    const first = (await jobs.section(profile, "core_identity", "tr")).section!;
    validate("NatalSection", first);
    await jobs.opened(profile, "core_identity", "opened");
    await waitUntil(() => counts.draft + counts.finalize >= 4, "read-ahead prefetch");
    await jobs.close();
    assert.equal(counts.draft + counts.finalize, 4);
    await waitUntil(
      async () =>
        !!(await jobs.section(profile, "sun_house", "tr")).section?.text,
      "sun house ready",
    );
    await jobs.opened(profile, "sun_house", "opened");
    await jobs.close();
    await waitUntil(
      async () =>
        !!(await jobs.section(profile, "moon_house", "tr")).section?.text,
      "moon house ready",
    );
    await jobs.opened(profile, "moon_house", "opened");
    await waitUntil(() => counts.draft >= plan.order.length, "full plan prefetch");
    await jobs.close();
    assert.ok(counts.draft >= plan.order.length);
    assert.ok(counts.max >= 1);
    for (let i = 0; i < 3; i++)
      assert.deepEqual(
        (await jobs.section(profile, "core_identity", "tr")).section,
        first,
      );
    await jobs.section(profile, "core_identity", "en");
    await jobs.close();
    assert.equal(counts.translation, 1);
    const result = (await jobs.section(profile, "core_identity", "en")).section;
    assert.ok(result?.text);
    assert.doesNotMatch(
      JSON.stringify(result),
      /principle_ids|draft_tr|usage|context_keys/,
    );
    validate("ReadingOutline", await jobs.outline(profile, "en"));
    validate("NatalReading", (await jobs.reading(profile, "tr")).reading);
  } finally {
    await jobs.close();
    await store.close();
  }
});

test("ONB anonymous guards do no work and concurrent requests join; completing stays in Part One", async () => {
  const { store, profile, jobs, counts } = await setup();
  try {
    await assert.rejects(
      jobs.section(profile, "inner_drives", "tr", true),
      (e: any) => e.problem.code === "read_ahead_limit",
    );
    await assert.rejects(
      jobs.section(profile, "identity", "tr", true),
      (e: any) => e.problem.code === "account_required",
    );
    assert.equal((await store.list("job:")).length, 0);
    assert.equal(counts.draft, 0);
    const first = jobs.section(profile, "core_identity", "tr", true);
    await waitUntil(() => counts.draft > 0, "section generation start");
    const results = await Promise.all([
      first,
      ...Array.from({ length: 4 }, () =>
        jobs.section(profile, "core_identity", "tr", true),
      ),
    ]);
    assert.equal(new Set(results.map((r) => r.job?.job_id)).size, 1);
    await jobs.close();
    const complete = await jobs.complete(profile, "tr", true);
    await waitUntil(() => counts.draft >= 5, "anonymous completion");
    await jobs.close();
    const afterFirst = counts.draft;
    assert.ok(afterFirst >= 5);
    assert.equal((await store.get("job:" + complete.job_id)).status, "succeeded");
    await jobs.complete(profile, "tr", true);
    await jobs.close();
    assert.equal(counts.draft, afterFirst);
  } finally {
    await jobs.close();
    await store.close();
  }
});

test("ONB feedback replaces the same vote, stays private, and legacy readings cost nothing", async () => {
  const { store, profile, jobs, counts } = await setup();
  await store.put("reading:" + profile.chart_key, {
    tr: fixture("natal.1.tr"),
    en: fixture("natal.1.en"),
  });
  try {
    await jobs.start(profile);
    await jobs.close();
    assert.equal(counts.draft, 0);
    assert.equal(counts.translation, 0);
    await jobs.opened(profile, "core_identity", "opened");
    const vote = {
      profile_id: profile.profile_id,
      target: { type: "reading" as const },
      rating: "spot_on" as const,
      comment: "private note",
    };
    assert.deepEqual(await jobs.feedback(profile, vote), {
      accuracy: { score: 1, n: 1 },
    });
    assert.deepEqual(
      await jobs.feedback(profile, { ...vote, rating: "partly" }),
      { accuracy: { score: 0.5, n: 1 } },
    );
    assert.doesNotMatch(
      JSON.stringify(await jobs.outline(profile, "en")),
      /private note|principle_ids/,
    );
    await assert.rejects(
      jobs.feedback(profile, { ...vote, comment: "x".repeat(501) }),
    );
  } finally {
    await jobs.close();
    await store.close();
  }
});

test("ONB interrupted completion needs retry and cannot return a forever-running job", async () => {
  const { store, profile, jobs, bridge } = await setup();
  try {
    await jobs.start(profile);
    await jobs.close();
    const job = {
      job_id: "interrupted",
      kind: "natal_section",
      status: "queued",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      eta_seconds: null,
      error: null,
      stages: [],
    };
    await store.put("job:interrupted", job);
    await store.put(`reading-section:${profile.chart_key}:sun_house`, {
      key: "sun_house",
      chart_key: profile.chart_key,
      status: "not_started",
      job_id: job.job_id,
    });
    const key = `reading-complete:${profile.profile_id}:tr:false`;
    await store.put(key, {
      key,
      chart_key: profile.chart_key,
      lang: "tr",
      keys: ["core_identity", "sun_house"],
      job,
    });
    const restarted = await ProgressiveReadings.create(store, true, bridge);
    assert.equal((await restarted.complete(profile, "tr")).status, "failed");
    await assert.rejects(restarted.section(profile, "sun_house", "tr"));
    await restarted.complete(profile, "tr", false, true);
    let status = "running";
    for (let i = 0; i < 200 && status !== "succeeded"; i++) {
      await new Promise((resolve) => setImmediate(resolve));
      status = (await restarted.complete(profile, "tr")).status;
    }
    await restarted.close();
    assert.equal(status, "succeeded");
  } finally {
    await jobs.close();
    await store.close();
  }
});

test("ONB failed translation keeps ready Turkish and explicit retry only translates", async () => {
  const { store, profile, jobs, bridge, counts } = await setup();
  try {
    await jobs.start(profile);
    await waitUntil(() => counts.draft >= 1, "core section draft");
    await jobs.close();
    let fail = true;
    const runner = await ProgressiveReadings.create(store, true, async (data) => {
      if (data.op === "translate" && fail)
        throw new Error("Provider unavailable");
      return bridge(data);
    });
    await runner.section(profile, "core_identity", "en");
    await runner.close();
    assert.ok(
      (await runner.section(profile, "core_identity", "tr")).section?.text,
    );
    await assert.rejects(runner.section(profile, "core_identity", "en"));
    fail = false;
    await runner.section(profile, "core_identity", "en", false, true);
    await runner.close();
    assert.equal(counts.draft, 1);
    assert.equal(counts.translation, 1);
  } finally {
    await jobs.close();
    await store.close();
  }
});
