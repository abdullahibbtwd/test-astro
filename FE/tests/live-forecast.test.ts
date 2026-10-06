import test from "node:test";
import assert from "node:assert/strict";
import { computeBirthChart } from "../local-api/engine";
import { runReadingBridge } from "../local-api/readings";
import { forecastSegments } from "../local-api/forecast";
test("real predictive pipeline matches calendar-month and year beat boundaries without model calls", async () => {
  const current = { lat: 42.6977, lon: 23.3217, tz: "Europe/Sofia" };
  const { raw } = await computeBirthChart(
    { date: "1990-07-13", time: "12:30", place: current },
    "forecast-test",
  );
  for (const horizon of ["day", "month", "year"] as const) {
    const context = { horizon, lens: "general", target: "2028-02-01", current };
    const result = await runReadingBridge("forecast_bridge.py", {
      chart: raw,
      context,
      dry_run: true,
    });
    assert.deepEqual(result.context, context);
    assert.equal(result.from, "2028-02-01");
    assert.equal(
      result.to,
      horizon === "day"
        ? "2028-02-01"
        : horizon === "month"
          ? "2028-02-29"
          : "2029-01-31",
    );
    if (horizon !== "day")
      assert.deepEqual(
        result.segments,
        forecastSegments(
          result.from,
          result.to,
          horizon === "month"
            ? ["early", "mid", "late"]
            : ["q1", "q2", "q3", "q4"],
        ),
      );
    assert.equal(result.readings, undefined);
  }
});
