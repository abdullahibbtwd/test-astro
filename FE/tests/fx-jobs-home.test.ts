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
    const store = new Store(":memory:"),
      a = fixture("profile.1.en"),
      b = { ...a, profile_id: "b", chart_key: "b", label: "B" };
    for (const p of [a, b]) store.put("profile:" + p.profile_id, p);
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
        ? new ForecastJobs(store, true, generate)
        : kind === "natal"
          ? new ReadingJobs(store, generate, true)
          : kind === "map"
            ? new MapJobs(store, true, generate)
            : new CompatibilityJobs(store, true, generate);
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
        first = jobs.get(ctx, "en");
        busy = jobs.get({ ...ctx, lens: "personal" }, "en").error;
      } else if (jobs instanceof MapJobs) {
        const ctx = mapContext(a, "place", {
          place: facts.place,
          focus_goal: null,
        });
        first = jobs.get(ctx, facts, "en").reading;
        busy = jobs.get(
          { ...ctx, input: { ...ctx.input, focus_goal: "love" } },
          facts,
          "en",
        ).reading.error;
      } else if (jobs instanceof ReadingJobs) {
        first = jobs.get(a, "en");
        try {
          jobs.get(b, "en");
        } catch (e: any) {
          busy = e.problem;
        }
      } else {
        const input = {
          profile_a_id: a.profile_id,
          profile_b_id: b.profile_id,
          type: "love" as const,
        };
        first = jobs.create(input, "en").reading;
        try {
          jobs.create({ ...input, type: "work" }, "en");
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
      store.close();
    }
  }
});
test("paused generation is an absence and peek never starts work", () => {
  const store = new Store(":memory:"),
    p = fixture("profile.1.en");
  store.put("profile:" + p.profile_id, p);
  let calls = 0;
  const ctx = forecastContext(p, p.birth.place, "2026-10-05", "day", "general"),
    jobs = new ForecastJobs(store, true, async () => {
      calls++;
      throw new Error("must not call");
    });
  assert.equal(jobs.peek(ctx, "en").absence.reason, "not_generated");
  assert.equal(calls, 0);
  assert.equal(store.list("job:").length, 0);
  assert.equal(
    new ForecastJobs(store).get(ctx, "en").absence.reason,
    "generation_paused",
  );
  assert.equal(
    new ReadingJobs(store).get(p, "en").absence?.reason,
    "generation_paused",
  );
  const facts = collection("place-report.", "en")[0];
  assert.equal(
    new MapJobs(store).get(
      mapContext(p, "place", { place: facts.place, focus_goal: null }),
      facts,
      "en",
    ).reading.absence.reason,
    "generation_paused",
  );
  store.close();
});
test("live Home returns facts and cached text with zero generation", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "fx-home-")),
    dbPath = path.join(dir, "app.sqlite"),
    store = new Store(dbPath),
    p = fixture("profile.1.en");
  p.is_self = true;
  store.put("profile:" + p.profile_id, p);
  store.put("me", {
    ...fixture("me.en"),
    self_profile_id: p.profile_id,
    current_place: p.birth.place,
  });
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
  const app = buildLocalApp({
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
    const first = await app.inject({ url: "/v1/home", headers });
    assert.equal(first.statusCode, 200);
    const home = first.json();
    validate("HomeSummary", home);
    assert.equal(home.today.absence.reason, "not_generated");
    assert.equal(home.greeting_name, p.label);
    assert.equal(home.tiles.length, 4);
    assert.equal(calls, 0);
    assert.equal(store.list("job:").length, 0);
    const context = forecastContext(
        p,
        p.birth.place,
        home.date,
        "day",
        "general",
      ),
      key = createHash("sha256").update(JSON.stringify(context)).digest("hex");
    store.put("forecast-reading:" + key, {
      en: { reading: "Cached reading" },
      tr: { reading: "Cached TR" },
    });
    const cached = (await app.inject({ url: "/v1/home", headers })).json();
    assert.equal(cached.today.text, "Cached reading");
    assert.equal(calls, 0);
    assert.equal(store.list("job:").length, 0);
  } finally {
    await app.close();
    store.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
