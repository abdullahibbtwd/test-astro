import { dayForecast, monthForecast } from "../local-api/forecast";
import test from "node:test";
import assert from "node:assert/strict";
import { computeCalendar } from "../local-api/calendar";
import { fixture } from "../mock-api/fixtures";
import { validate } from "../src/api/zod";
test("real calendar builds another person's current horizon without model calls", async () => {
  const profile = fixture("profile.1.en");
  const result = await computeCalendar(profile, null, "2026-10-01");
  const en = result.en!;
  validate("CalendarMonth", en.months["2026-10"]);
  validate("CalendarDayDetail", en.days["2026-10-02"]);
  validate("CalendarYear", en.year);
  validate(
    "DayForecast",
    dayForecast(en, fixture("catalogue.en"), profile.profile_id, "2026-10-02"),
  );
  validate("MonthForecast", monthForecast(en, profile.profile_id, "2026-10"));
  validate("BestDaysOverview", en.best);
  for (const item of Object.values(en.items)) validate("CalendarItem", item);
  for (const item of Object.values(en.bestDetails))
    validate("BestDayDetail", item);
  for (const item of en.notifications) validate("NotificationCandidate", item);
  assert.equal(en.months["2026-10"].profile_id, profile.profile_id);
  assert.equal(en.best.horizon.from, "2026-10-01");
  assert.equal(en.months["2026-10"].days.length, 31);
});
