import {
  dayForecast,
  monthForecast,
  yearForecast,
} from "../api/forecast";
import test from "node:test";
import assert from "node:assert/strict";
import { computeCalendar } from "../api/calendar";
import { fixture } from "../mock/fixtures";
import { validate } from "../../frontend/src/api/zod";
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
  const yearly = yearForecast(
    en,
    profile.profile_id,
    "2026-10",
    "en",
    "personal",
  );
  assert.ok(yearly);
  validate("YearForecast", yearly);
  assert.equal(yearly.from, "2026-10-01");
  assert.equal(yearly.to, "2027-09-30");
  assert.equal(yearly.months.length, 12);
  assert.equal(yearly.months[11]!.month, "2027-09");
  assert.equal(yearly.lens, "personal");
  assert.equal(yearly.reading.status, "absent");
  assert.equal(yearly.quarters[3]!.to, yearly.to);
  for (const event of yearly.highlights.key_events) {
    assert.ok(
      en.items[event.id],
      "Year event must open its real calendar detail",
    );
  }
  assert.equal(
    yearForecast(en, profile.profile_id, "2027-10", "en"),
    undefined,
  );
  validate("BestDaysOverview", en.best);
  for (const item of Object.values(en.items)) validate("CalendarItem", item);
  for (const item of Object.values(en.bestDetails))
    validate("BestDayDetail", item);
  for (const item of en.notifications) validate("NotificationCandidate", item);
  assert.equal(en.months["2026-10"].profile_id, profile.profile_id);
  assert.equal(en.best.horizon.from, "2026-10-01");
  assert.equal(en.months["2026-10"].days.length, 31);
});
