import fs from "node:fs";
import { computeBirthChart } from "../local-api/engine";
import { generateReading } from "../local-api/readings";
import { validate } from "../src/api/zod";
// Explicitly fictional input approved for the integration test. Never reads a user's profile.
const { raw, chart } = await computeBirthChart(
  {
    date: "1990-07-13",
    time: "12:30",
    place: { lat: 42.6977, lon: 23.3217, tz: "Europe/Sofia" },
  },
  "integration-test",
);
const result = await generateReading(raw, "integration-test", chart.chart_key);
for (const lang of ["tr", "en"])
  validate("NatalReading", result.readings[lang]);
fs.mkdirSync("artifacts/live", { recursive: true });
fs.writeFileSync("artifacts/live/natal-smoke.json", JSON.stringify(result));
console.log(
  JSON.stringify({
    sections: result.readings.en.sections.length,
    budgetReservedOrSpent: result.budget_reserved_or_spent_usd,
  }),
);
