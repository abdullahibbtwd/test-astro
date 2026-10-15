import test from "node:test";
import assert from "node:assert/strict";
import { computeBirthChart } from "../local-api/engine";
import { runReadingBridge } from "../local-api/readings";
test("approved relationship grounding uses two real charts without model calls", async () => {
  const charts = [];
  for (const date of ["1990-07-13", "1992-02-20"]) {
    charts.push(
      (
        await computeBirthChart(
          {
            date,
            time: "12:30",
            place: { lat: 42.6977, lon: 23.3217, tz: "Europe/Sofia" },
          },
          date,
        )
      ).raw,
    );
  }
  for (const type of ["love", "work"]) {
    const context = {
      type,
      people: [{ label: "Fictional A" }, { label: "Fictional B" }],
    };
    const result = await runReadingBridge("compatibility_bridge.py", {
      context,
      charts,
      dry_run: true,
    });
    assert.deepEqual(result.context, context);
    assert.equal(
      result.reading_type,
      type === "love" ? "personal" : "professional",
    );
    assert.ok(result.counts.synastry > 0);
    assert.ok(result.section_keys.length > 0);
    assert.equal(result.readings, undefined);
  }
});
