import test from "node:test";
import assert from "node:assert/strict";
import { forecastSegments } from "../local-api/forecast";
test("forecast beat dates match backend day-count thirds and quarters, including leap February", () => {
  assert.deepEqual(
    forecastSegments("2028-02-01", "2028-02-29", ["early", "mid", "late"]),
    {
      early: { from: "2028-02-01", to: "2028-02-09" },
      mid: { from: "2028-02-10", to: "2028-02-19" },
      late: { from: "2028-02-20", to: "2028-02-29" },
    },
  );
  const q = forecastSegments("2027-10-01", "2028-09-30", [
    "q1",
    "q2",
    "q3",
    "q4",
  ]);
  assert.equal(q.q1!.to, "2027-12-30");
  assert.equal(q.q2!.from, "2027-12-31");
  assert.equal(q.q4!.to, "2028-09-30");
});
