import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { Store } from "../api/store";
import { MapJobs, mapContext } from "../api/map-jobs";
import { fixture, collection } from "../mock/fixtures";
import { mapRecommendation } from "../mock/scripts/recommend";
import { validate } from "../../frontend/src/api/zod";
const absent = { status: "absent", absence: { reason: "not_generated" } };
async function setup() {
  const store = await Store.open(":memory:");
  const p = fixture("profile.1.en");
  await store.put("profile:" + p.profile_id, p);
  await store.put("raw:" + p.profile_id, {});
  const full = collection("place-report.", "en")[0];
  const facts = {
    ...full,
    reading: absent,
    cards: full.cards.map((c: any) => ({ ...c, text: null })),
  };
  const context = mapContext(p, "place", {
    place: full.place,
    focus_goal: null,
  });
  const readings = Object.fromEntries(
    ["en", "tr"].map((lang) => {
      const doc = fixture(`place-report.${full.place.place_id}.${lang}`);
      return [
        lang,
        {
          reading: doc.reading,
          card_texts: Object.fromEntries(
            doc.cards.map((c: any) => [c.goal, c.text]),
          ),
        },
      ];
    }),
  );
  return { store, p, facts, context, readings };
}
test("place readings retain immediate facts, deduplicate languages and persist ready reports", async () => {
  const { store, facts, context, readings } = await setup();
  let count = 0;
  const jobs = await MapJobs.create(store, true, async () => {
    count++;
    return { context, readings };
  });
  try {
    const first = await jobs.get(context, facts, "en");
    assert.equal(first.reading.status, "pending");
    assert.deepEqual(first.goal_scores, facts.goal_scores);
    assert.equal(
      (await jobs.get(context, facts, "tr")).reading.job.job_id,
      first.reading.job.job_id,
    );
    await jobs.close();
    assert.equal(count, 1);
    const ready = await jobs.get(context, facts, "en");
    assert.equal(ready.reading.status, "ready");
    assert.deepEqual(ready.lines_display, facts.lines_display);
    assert.ok(ready.cards.every((c: any) => !!c.text));
    validate("PlaceReport", ready);
    const restarted = await MapJobs.create(store);
    assert.equal(
      (await restarted.get(context, facts, "tr")).reading.status,
      "ready",
    );
    assert.equal((await restarted.reports("tr")).length, 1);
    validate("ReportRef", (await restarted.reports("tr"))[0]);
    assert.ok(
      (await restarted.reports("en"))[0]!.route.includes(
        encodeURIComponent(facts.place.place_id),
      ),
    );
  } finally {
    await jobs.close();
    await store.close();
  }
});
test("failed map jobs require explicit retry and incomplete or stale readings never enter history", async () => {
  const { store, p, facts, context, readings } = await setup();
  let mode = "invalid",
    count = 0;
  const jobs = await MapJobs.create(store, true, async () => {
    count++;
    if (mode === "stale") await store.remove("profile:" + p.profile_id);
    return {
      context,
      readings: mode === "invalid" ? { en: {}, tr: {} } : readings,
    };
  });
  try {
    await jobs.get(context, facts, "en");
    await jobs.close();
    assert.equal((await jobs.get(context, facts, "en")).reading.status, "failed");
    assert.equal(count, 1);
    assert.equal((await jobs.reports("en")).length, 0);
    mode = "stale";
    await jobs.get(context, facts, "en", true);
    await jobs.close();
    assert.equal(count, 2);
    assert.equal((await store.list("map-reading:")).length, 0);
    await store.put("profile:" + p.profile_id, p);
    mode = "valid";
    await jobs.get(context, facts, "en", true);
    await jobs.close();
    assert.equal((await jobs.get(context, facts, "en")).reading.status, "ready");
    await store.put("profile:" + p.profile_id, { ...p, chart_key: "edited" });
    assert.equal((await jobs.reports("en")).length, 0);
  } finally {
    await jobs.close();
    await store.close();
  }
});
test("area reading uses the area context; interrupted work is not automatically restarted", async () => {
  const { store, p } = await setup();
  const facts = { ...collection("area-report.", "en")[0], overview: absent };
  const context = mapContext(p, "area", {
    kind: "country",
    code: facts.area.id,
  });
  const generator = async () => ({
    context,
    readings: {
      en: { overview: { status: "ready", text: "English overview" } },
      tr: { overview: { status: "ready", text: "Türkçe" } },
    },
  });
  const jobs = await MapJobs.create(store, true, generator);
  try {
    await jobs.get(context, facts, "en");
    await jobs.close();
    assert.equal((await jobs.get(context, facts, "tr")).overview.text, "Türkçe");
    validate("AreaReport", await jobs.get(context, facts, "en"));
    const record = (await store.list<any>("map-reading-job:"))[0];
    await store.remove("map-reading:" + record.key);
    await store.put("map-reading-job:" + record.key, {
      ...record,
      job: { ...record.job, status: "running" },
    });
    const restarted = await MapJobs.create(store, false, generator);
    assert.equal(
      (await restarted.get(context, facts, "en")).overview.status,
      "failed",
    );
    assert.equal(
      (await restarted.get(context, facts, "en", true)).overview.status,
      "absent",
    );
    assert.equal((await restarted.reports("en")).length, 0);
  } finally {
    await jobs.close();
    await store.close();
  }
});
test("recommendation prose cannot change ranking and home changes hide saved results", async () => {
  const { store, p } = await setup();
  const root = path.resolve("..");
  const raw = JSON.parse(
    fs.readFileSync(
      path.join(
        root,
        "acg_run/20260928-113431_8l9/recommend_love_world_1979-03-30.json",
      ),
      "utf8",
    ),
  );
  const facts = {
    ...mapRecommendation(root, "en", fixture("catalogue.en"), raw),
    explanations: absent,
  };
  const current = p.current_place ?? p.birth.place;
  const context = mapContext(p, "recommendation", {
    request: { goal: "love" },
    home: [current.lat, current.lon],
  });
  let invalid = true;
  const jobs = await MapJobs.create(store, true, async () => {
    const value = structuredClone(raw);
    if (invalid) value.cities = [];
    return { context, raw: value };
  });
  try {
    await jobs.get(context, facts, "en");
    await jobs.close();
    assert.equal(
      (await jobs.get(context, facts, "en")).explanations.status,
      "failed",
    );
    invalid = false;
    await jobs.get(context, facts, "en", true);
    await jobs.close();
    const ready = await jobs.get(context, facts, "en");
    assert.equal(ready.explanations.status, "ready");
    assert.deepEqual(ready.places, facts.places);
    validate("Recommendation", ready);
    assert.equal(
      (await jobs.reports("en"))[0]!.route.startsWith("/map/recommend/result?"),
      true,
    );
    if (p.is_self)
      await store.put("me", {
        current_place: { ...current, lat: current.lat + 1 },
      });
    else
      await store.put("profile:" + p.profile_id, {
        ...p,
        current_place: { ...current, lat: current.lat + 1 },
      });
    assert.equal((await jobs.reports("en")).length, 0);
  } finally {
    await jobs.close();
    await store.close();
  }
});
