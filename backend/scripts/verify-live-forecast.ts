import { validate } from "../../frontend/src/api/zod";
const base = "http://127.0.0.1:4020/v1";
const response = await fetch(base + "/auth/email/verify", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email: "demo@example.com", code: "000000" }),
});
const session = (await response.json()) as any;
if (!response.ok) throw new Error("Preview login failed");
for (const lang of ["en", "tr"]) {
  for (const [horizon, query, schema] of [
    ["day", "date=2026-10-03", "DayForecast"],
    ["month", "month=2026-10", "MonthForecast"],
    ["year", "from=2026-10", "YearForecast"],
  ]) {
    const r = await fetch(
      `${base}/profiles/69f8c19f-34cd-46b7-8898-3433dacc1f21/forecast/${horizon}?${query}&lang=${lang}`,
      { headers: { Authorization: `Bearer ${session.access_token}` } },
    );
    if (!r.ok) throw new Error(`Forecast request failed: ${horizon}/${lang}`);
    const value = validate(schema!, await r.json()) as any;
    if (value.reading.status !== "ready")
      throw new Error("Fresh reading not available");
    console.log(`${horizon}/${lang}: validated and ready`);
  }
}
