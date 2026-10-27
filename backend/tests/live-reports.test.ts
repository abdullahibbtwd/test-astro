import test from "node:test";
import { openStore } from "./helpers";
import assert from "node:assert/strict";
import { Store } from "../api/store";
import { ForecastJobs, forecastContext } from "../api/forecast-jobs";
import { forecastSegments } from "../api/forecast";
import { CompatibilityJobs } from "../api/compatibility-jobs";
import { fixture } from "../mock/fixtures";
import { validate } from "../../frontend/src/api/zod";
const setup = async () => {
  const store = await openStore();
  const p = { ...fixture("profile.1.en"), is_self: false, current_place: null };
  await store.put("profile:" + p.profile_id, p);
  return { store, p };
};
const generate = async ({ context }: any) => {
  const keys =
    context.horizon === "month"
      ? ["overview", "early", "mid", "late", "focus"]
      : ["overview", "q1", "q2", "q3", "q4", "focus"];
  const to = context.horizon === "month" ? "2026-10-31" : "2027-09-30";
  return {
    context,
    from: context.target,
    to,
    segments: forecastSegments(context.target, to, keys.slice(1, -1)),
    readings: Object.fromEntries(
      ["en", "tr"].map((lang) => [
        lang,
        Object.fromEntries(keys.map((key) => [key, lang + " reading"])),
      ]),
    ),
  };
};
test("forecast reports are ready-only, bilingual, persistent and preserve lens/date routes", async () => {
  const { store, p } = await setup();
  const jobs = await ForecastJobs.create(store, true, generate);
  const ctx = forecastContext(
    p,
    p.birth.place,
    "2026-10-01",
    "month",
    "professional",
  );
  await jobs.get(ctx, "en");
  assert.equal((await jobs.reports("en")).length, 0);
  await jobs.close();
  await jobs.get({ ...ctx, horizon: "year" }, "en");
  await jobs.close();
  const en = await jobs.reports("en"),
    tr = await (await ForecastJobs.create(store, false)).reports("tr");
  assert.equal(en.length, 2);
  assert.equal(tr.length, 2);
  for (const r of [...en, ...tr]) validate("ReportRef", r);
  assert.notEqual(en[0]!.title, tr[0]!.title);
  assert.ok(tr.some((r) => r.title.startsWith("Aylık öngörü ·")));
  assert.ok(en.some((r) => r.title === "Monthly forecast · October 2026"));
  assert.ok(
    en.some(
      (r) =>
        r.route ===
        `/ahead?view=month&profile=${p.profile_id}&month=2026-10&lens=professional`,
    ),
  );
  await store.put("profile:" + p.profile_id, {
    ...p,
    current_place: { ...p.birth.place, lat: 0 },
  });
  assert.equal((await jobs.reports("en")).length, 0);
  await store.put("profile:" + p.profile_id, { ...p, chart_key: "edited" });
  assert.equal((await jobs.reports("en")).length, 0);
  await store.close();
});
test("compatibility reports omit pending, stale and deleted readings", async () => {
  const { store, p } = await setup();
  const b = { ...p, profile_id: "b", chart_key: "b", label: "B" };
  await store.put("profile:b", b);
  const jobs = await CompatibilityJobs.create(store, true, async ({ context }: any) => ({
    context,
    readings: Object.fromEntries(
      ["en", "tr"].map((lang) => [
        lang,
        {
          title: lang,
          sections: [
            { key: "test", title: lang, text: "Reading", movement: 0 },
          ],
        },
      ]),
    ),
  }));
  const c = await jobs.create(
    { profile_a_id: p.profile_id, profile_b_id: "b", type: "work" },
    "en",
  );
  assert.equal((await jobs.reports("en")).length, 0);
  await jobs.close();
  const r = (await jobs.reports("tr"))[0]!;
  validate("ReportRef", r);
  assert.equal(r.title, "İş uyumu");
  assert.equal(r.route, "/match/" + c.compatibility_id);
  await store.put("profile:b", { ...b, chart_key: "edited" });
  assert.equal((await jobs.reports("en")).length, 0);
  await store.put("profile:b", b);
  await jobs.remove(c.compatibility_id);
  assert.equal((await jobs.reports("en")).length, 0);
  await store.close();
});
