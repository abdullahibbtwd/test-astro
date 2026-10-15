import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createHash } from "node:crypto";
import { Store } from "../local-api/store";
import { ForecastJobs, forecastContext } from "../local-api/forecast-jobs";
import { ReadingJobs } from "../local-api/reading-jobs";
import { MapJobs, mapContext } from "../local-api/map-jobs";
import { CompatibilityJobs } from "../local-api/compatibility-jobs";
import { buildLocalApp } from "../local-api/app";
import { fixture, collection } from "../mock-api/fixtures";
import { validate } from "../src/api/zod";

test("all four guards return busy with the blocking job and no second generator call", async () => {
  for (const kind of ["forecast", "natal", "map", "compatibility"]) {
    const store = await Store.open(":memory:"),
      a = fixture("profile.1.en"),
      b = { ...a, profile_id: "b", chart_key: "b", label: "B" };
    for (const p of [a, b]) await store.put("profile:" + p.profile_id, p);
    let release!: () => void,
      calls = 0;
    const hold = new Promise<void>((r) => {
      release = r;
    });
    const generate = async () => {
      calls++;
      await hold;
      throw new Error("test failure");
    };
    const jobs =
      kind === "forecast"
        ? await ForecastJobs.create(store, true, generate)
        : kind === "natal"
          ? await ReadingJobs.create(store, generate, true)
          : kind === "map"
            ? await MapJobs.create(store, true, generate)
            : await CompatibilityJobs.create(store, true, generate);
    const facts = collection("place-report.", "en")[0];
    let first: any, busy: any;
    try {
      if (jobs instanceof ForecastJobs) {
        const ctx = forecastContext(
          a,
          a.birth.place,
          "2026-10-05",
          "day",
          "general",
        );
        first = await jobs.get(ctx, "en");
        busy = (await jobs.get({ ...ctx, lens: "personal" }, "en")).error;
      } else if (jobs instanceof MapJobs) {
        const ctx = mapContext(a, "place", {
          place: facts.place,
          focus_goal: null,
        });
        first = (await jobs.get(ctx, facts, "en")).reading;
        busy = (
          await jobs.get(
            { ...ctx, input: { ...ctx.input, focus_goal: "love" } },
            facts,
            "en",
          )
        ).reading.error;
      } else if (jobs instanceof ReadingJobs) {
        first = await jobs.get(a, "en");
        try {
          await jobs.get(b, "en");
        } catch (e: any) {
          busy = e.problem;
        }
      } else {
        const input = {
          profile_a_id: a.profile_id,
          profile_b_id: b.profile_id,
          type: "love" as const,
        };
        first = (await jobs.create(input, "en")).reading;
        try {
          await jobs.create({ ...input, type: "work" }, "en");
        } catch (e: any) {
          busy = e.problem;
        }
      }
      await Promise.resolve();
      assert.equal(busy.code, "busy", kind);
      assert.equal(busy.status, 409);
      assert.equal(busy.blocking_job_id, first.job.job_id);
      validate("Problem", busy);
      assert.equal(calls, 1);
    } finally {
      release();
      await jobs.close();
      await store.close();
    }
  }
});
test("paused generation is an absence and peek never starts work", async () => {
  const store = await Store.open(":memory:"),
    p = fixture("profile.1.en");
  await store.put("profile:" + p.profile_id, p);
  let calls = 0;
  const ctx = forecastContext(p, p.birth.place, "2026-10-05", "day", "general"),
    jobs = await ForecastJobs.create(store, true, async () => {
      calls++;
      throw new Error("must not call");
    });
  assert.equal((await jobs.peek(ctx, "en")).absence.reason, "not_generated");
  assert.equal(calls, 0);
  assert.equal((await store.list("job:")).length, 0);
  assert.equal(
    (await (await ForecastJobs.create(store)).get(ctx, "en")).absence.reason,
    "generation_paused",
  );
  assert.equal(
    (await (await ReadingJobs.create(store)).get(p, "en")).absence?.reason,
    "generation_paused",
  );
  const facts = collection("place-report.", "en")[0];
  assert.equal(
    (
      await (
        await MapJobs.create(store)
      ).get(
        mapContext(p, "place", { place: facts.place, focus_goal: null }),
        facts,
        "en",
      )
    ).reading.absence.reason,
    "generation_paused",
  );
  await store.close();
});
test("live Home returns facts and cached text with zero generation", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "fx-home-")),
    dbPath = path.join(dir, "app.sqlite"),
    p = fixture("profile.1.en");
  p.is_self = true;
  let calls = 0;
  const calculateCalendar = async (
    _p: any,
    _place: any,
    start: string,
  ): Promise<any> => {
    const template = fixture("forecast-day.en"),
      days: any = {},
      rawScores: any[] = [];
    for (let n = 1; n <= 31; n++) {
      const date = start.slice(0, 7) + "-" + String(n).padStart(2, "0");
      days[date] = { ...template, date };
      rawScores.push({
        local_date: date,
        goals: template.areas,
        drivers: Object.fromEntries(
          Object.keys(template.areas).map((g) => [g, []]),
        ),
      });
    }
    const cal = {
      days,
      rawScores,
      best: { tz: p.birth.place.tz },
      eventLabels: {},
      notifications: [],
    };
    return { en: cal, tr: cal };
  };
  const app = await buildLocalApp({
    dbPath,
    allowPaid: true,
    generateForecast: async () => {
      calls++;
      throw new Error("must not generate");
    },
    calculateCalendar,
  });
  try {
    const login = (
        await app.inject({
          method: "POST",
          url: "/v1/auth/email/verify",
          payload: { email: "demo@example.com", code: "000000" },
        })
      ).json(),
      headers = { authorization: `Bearer ${login.access_token}` };
    const tenantId = login.me.user_id;
    const store = await Store.open(dbPath);
    await store.runAsAsync(tenantId, async () => {
      await store.put("profile:" + p.profile_id, p);
      await store.put("me", {
        ...fixture("me.en"),
        user_id: tenantId,
        self_profile_id: p.profile_id,
        current_place: p.birth.place,
      });
    });
    const first = await app.inject({ url: "/v1/home", headers });
    assert.equal(first.statusCode, 200);
    const home = first.json();
    validate("HomeSummary", home);
    assert.equal(home.today.absence.reason, "not_generated");
    assert.equal(home.greeting_name, p.label);
    assert.equal(home.tiles.length, 4);
    assert.equal(calls, 0);
    assert.equal((await store.runAsAsync(tenantId, () => store.list("job:"))).length, 0);
    const context = forecastContext(
        p,
        p.birth.place,
        home.date,
        "day",
        "general",
      ),
      key = createHash("sha256").update(JSON.stringify(context)).digest("hex");
    await store.runAsAsync(tenantId, () =>
      store.put("forecast-reading:" + key, {
        en: { reading: "Cached reading" },
        tr: { reading: "Cached TR" },
      }),
    );
    const cached = (await app.inject({ url: "/v1/home", headers })).json();
    assert.equal(cached.today.text, "Cached reading");
    assert.equal(calls, 0);
    assert.equal((await store.runAsAsync(tenantId, () => store.list("job:"))).length, 0);
    await store.close();
  } finally {
    await app.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
