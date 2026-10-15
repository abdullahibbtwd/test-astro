import fs from "node:fs";
import { Store } from "../local-api/store";
import { ForecastJobs, forecastContext } from "../local-api/forecast-jobs";
const horizon = process.argv[2] ?? "day";
if (!["day", "month", "year"].includes(horizon))
  throw new Error("Invalid horizon");
const result = JSON.parse(
  fs.readFileSync(`artifacts/live/forecast-${horizon}-smoke.json`, "utf8"),
);
const store = await Store.open(".local-data/app.sqlite");
try {
  const c = result.context,
    p = await store.get("profile:" + c.profile_id);
  if (!p || p.label !== "Fictional AI test")
    throw new Error("Fictional test profile not found");
  const current =
    (p.is_self ? (await store.get("me"))?.current_place : p.current_place) ??
    p.birth.place;
  const context = forecastContext(p, current, c.target, c.horizon, c.lens);
  if (JSON.stringify(context) !== JSON.stringify(c))
    throw new Error("Test context no longer matches profile");
  if (
    (await store.list<any>("forecast-job:")).some((r: any) =>
      ["running", "queued"].includes(r.job.status),
    )
  )
    throw new Error("Wait for active forecast jobs before import");
  const jobs = await ForecastJobs.create(store, true, async () => result);
  await jobs.get(context, "en", true);
  await jobs.close();
  if (
    (await jobs.get(context, "en")).status !== "ready" ||
    (await jobs.get(context, "tr")).status !== "ready"
  )
    throw new Error("Import failed validation");
  console.log(
    JSON.stringify({ profileId: p.profile_id, horizon, status: "ready" }),
  );
} finally {
  await store.close();
}
