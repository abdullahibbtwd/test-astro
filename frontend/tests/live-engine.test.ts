import test from "node:test";
import assert from "node:assert/strict";
import { computeBirthChart } from "../local-api/engine";
import { validate } from "../src/api/zod";
const birth = {
  date: "1990-07-13",
  time: "12:30",
  place: { lat: 42.6977, lon: 23.3217, tz: "Europe/Sofia" },
};
test("real engine computes distinct charts and matches their birth time zones", async () => {
  const a = await computeBirthChart(birth, "test-a");
  const b = await computeBirthChart({ ...birth, date: "1991-01-13" }, "test-b");
  validate("ChartData", a.chart);
  validate("ChartData", b.chart);
  assert.notEqual(a.chart.points[0]!.longitude, b.chart.points[0]!.longitude);
  assert.equal(a.chart.tz, "Europe/Sofia");
  assert.equal(new Date(a.chart.utc).toISOString(), "1990-07-13T09:30:00.000Z");
  assert.equal(a.chart.houses.length, 12);
  assert.notEqual(a.chart.chart_key, b.chart.chart_key);
});
test("engine rejects invalid and daylight-saving ambiguous/nonexistent birth times", async () => {
  await assert.rejects(
    computeBirthChart({ ...birth, date: "1990-02-30" }, "bad"),
  );
  await assert.rejects(
    computeBirthChart({ ...birth, date: "2020-03-29", time: "03:30" }, "gap"),
  );
  await assert.rejects(
    computeBirthChart({ ...birth, date: "2020-10-25", time: "03:30" }, "fold"),
  );
});
