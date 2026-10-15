import { test } from "node:test";
import assert from "node:assert/strict";
import {
  planNotifications,
  notificationInstant,
  inQuietHours,
  type ReminderCandidate,
} from "../src/lib/notification-policy";
import type { NotificationPrefs } from "../contracts/spec-types";
const prefs: NotificationPrefs = {
  enabled: true,
  time: "09:00",
  max_per_day: 1,
  max_per_week: 3,
  quiet_hours: { start: "22:00", end: "08:00" },
  types: {
    favorable_window: true,
    period_start: true,
    lunation_in_house: true,
    retrograde_start: true,
    station_on_point: true,
    eclipse_hit: true,
  },
};
const candidate = (
  id: string,
  date: string,
  priority: 1 | 2 | 3 = 2,
): ReminderCandidate => ({
  id,
  type: "favorable_window",
  priority,
  trigger_date: date,
  suggested_time: "09:00",
  text: id,
  deep_link: { view: "best_days", ref: `win:love:${date}` },
});
const now = Date.parse("2026-09-28T00:00:00Z");
test("notification caps apply on every rolling seven-day window, by priority and backend order", () => {
  const values = Array.from({ length: 10 }, (_, i) =>
    candidate(String(i), `2026-10-${String(i + 1).padStart(2, "0")}`),
  );
  values.push(candidate("priority", "2026-10-05", 1));
  const plan = planNotifications(values, prefs, "Europe/Istanbul", now);
  assert.ok(plan.some((x) => x.id === "priority"));
  for (const item of plan)
    assert.ok(
      plan.filter(
        (x) =>
          Date.parse(x.date) >= Date.parse(item.date) &&
          Date.parse(x.date) < Date.parse(item.date) + 7 * 86400000,
      ).length <= 3,
    );
  assert.equal(new Set(plan.map((x) => x.date)).size, plan.length);
  assert.deepEqual(
    planNotifications(values, prefs, "Europe/Istanbul", now),
    plan,
  );
});
test("manual reminders win priority ties and count against caps; disabled types and past dates are excluded", () => {
  const normal = candidate("normal", "2026-10-01", 1),
    manual = { ...candidate("manual", "2026-10-01", 1), manual: true };
  assert.deepEqual(
    planNotifications([normal, manual], prefs, "Europe/Istanbul", now).map(
      (x) => x.id,
    ),
    ["manual"],
  );
  assert.equal(
    planNotifications(
      [normal],
      { ...prefs, types: { ...prefs.types, favorable_window: false } },
      "Europe/Istanbul",
      now,
    ).length,
    0,
  );
  assert.equal(
    planNotifications(
      [normal],
      prefs,
      "Europe/Istanbul",
      Date.parse("2026-10-02"),
    ).length,
    0,
  );
  assert.equal(
    planNotifications(
      [normal],
      { ...prefs, enabled: false },
      "Europe/Istanbul",
      now,
    ).length,
    0,
  );
});
test("quiet hours shift delivery and timezone changes alter absolute instants", () => {
  assert.ok(inQuietHours("23:00", "22:00", "08:00"));
  assert.ok(inQuietHours("07:00", "22:00", "08:00"));
  assert.ok(!inQuietHours("09:00", "22:00", "08:00"));
  const values = [candidate("one", "2026-10-01")];
  const item = planNotifications(
    values,
    { ...prefs, time: "07:00" },
    "Europe/Istanbul",
    now,
  )[0]!;
  assert.equal(
    item.instant,
    notificationInstant("2026-10-01", "08:00", "Europe/Istanbul"),
  );
  assert.equal(
    notificationInstant("2026-10-01", "09:00", "Europe/Istanbul") -
      notificationInstant("2026-10-01", "09:00", "Asia/Tokyo"),
    6 * 3600000,
  );
});
