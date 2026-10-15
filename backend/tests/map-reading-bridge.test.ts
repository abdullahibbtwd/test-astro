import test from "node:test";
import assert from "node:assert/strict";
import { computeBirthChart } from "../api/engine";
import { runReadingBridge } from "../api/readings";
test("all approved map writing pipelines prepare grounded inputs without provider calls", async () => {
  const { raw, chart } = await computeBirthChart(
    {
      date: "1990-07-13",
      time: "12:30",
      place: { lat: 42.6977, lon: 23.3217, tz: "Europe/Sofia" },
    },
    "map-dry-run",
  );
  for (const [kind, input] of [
    [
      "place",
      {
        place: {
          place_id: null,
          name: "Sofia",
          country_code: "BG",
          lat: 42.6977,
          lon: 23.3217,
        },
        focus_goal: null,
      },
    ],
    ["area", { kind: "country", code: "BG" }],
    [
      "recommendation",
      { request: { goal: "love", scope: "BG" }, home: [42.6977, 23.3217] },
    ],
    [
      "recommendation",
      { request: { goal: "overall", scope: "BG" }, home: [42.6977, 23.3217] },
    ],
  ]) {
    const context = {
      version: 1,
      profile_id: "map-dry-run",
      chart_key: chart.chart_key,
      kind,
      input,
    };
    const result = await runReadingBridge("map_reading_bridge.py", {
      context,
      chart: raw,
      dry_run: true,
    });
    assert.deepEqual(result.context, context);
    assert.equal(result.dry_run, true);
    assert.ok((result.units ?? result.sections) > 0);
  }
  await assert.rejects(
    runReadingBridge("map_reading_bridge.py", { chart: raw }),
    /RuntimeError/,
  );
});
