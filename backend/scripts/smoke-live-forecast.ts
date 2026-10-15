import fs from "node:fs";
import { computeBirthChart } from "../api/engine";
import { runReadingBridge } from "../api/readings";
const horizon = process.argv[2] ?? "day";
if (!["day", "month", "year"].includes(horizon))
  throw new Error("Invalid horizon");
const current = { lat: 42.6977, lon: 23.3217, tz: "Europe/Sofia" };
const id = "69f8c19f-34cd-46b7-8898-3433dacc1f21";
const { raw, chart } = await computeBirthChart(
  { date: "1990-07-13", time: "12:30", place: current },
  id,
);
const context = {
  version: 2,
  profile_id: id,
  chart_key: chart.chart_key,
  current,
  target: horizon === "day" ? "2026-10-03" : "2026-10-01",
  horizon,
  lens: "general",
};
const result = await runReadingBridge("forecast_bridge.py", {
  chart: raw,
  context,
});
fs.mkdirSync("artifacts/live", { recursive: true });
fs.writeFileSync(
  `artifacts/live/forecast-${horizon}-smoke.json`,
  JSON.stringify(result),
);
console.log(
  JSON.stringify({
    horizon,
    from: result.from,
    to: result.to,
    validationWarnings: result.validation_warning_count,
    budgetReservedOrSpent: result.budget_reserved_or_spent_usd,
  }),
);
