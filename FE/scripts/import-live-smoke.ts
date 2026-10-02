import fs from "node:fs";
import { randomUUID } from "node:crypto";
import { Store } from "../local-api/store";
import { ReadingJobs } from "../local-api/reading-jobs";
import { computeBirthChart } from "../local-api/engine";
import { validate } from "../src/api/zod";
import type { BirthProfile } from "../contracts/spec-types";
const result = JSON.parse(
  fs.readFileSync("artifacts/live/natal-smoke.json", "utf8"),
);
const id = randomUUID();
const place = {
  place_id: "gn-727011",
  name: "Sofia",
  admin1: null,
  country_code: "BG",
  country_name: "Bulgaria",
  lat: 42.6977,
  lon: 23.3217,
  tz: "Europe/Sofia",
};
const birth = { date: "1990-07-13", time: "12:30", place };
const { raw, chart } = await computeBirthChart(birth, id);
if (
  result.readings.en.chart_key !== chart.chart_key ||
  result.readings.tr.chart_key !== chart.chart_key
)
  throw new Error("Smoke result does not match calculated chart");
const now = new Date().toISOString();
const profile: BirthProfile = {
  profile_id: id,
  chart_key: chart.chart_key,
  label: "Fictional AI test",
  relation: "friend",
  is_self: false,
  gender: null,
  current_place: null,
  birth: { ...birth, tz: chart.tz, utc: chart.utc },
  big_three: {
    sun: chart.points.find((p) => p.body === "sun")!.sign,
    moon: chart.points.find((p) => p.body === "moon")!.sign,
    ascendant: chart.axes.asc.sign,
  },
  created_at: now,
  updated_at: now,
};
validate("BirthProfile", profile);
const store = new Store(".local-data/app.sqlite");
try {
  const prior = store
    .list<BirthProfile>("profile:")
    .find(
      (p) => p.label === profile.label && p.chart_key === profile.chart_key,
    );
  if (prior) {
    console.log(JSON.stringify({ profileId: prior.profile_id, reused: true }));
  } else {
    store.transaction(() => {
      store.put("profile:" + id, profile);
      store.put("chart:" + id, chart);
      store.put("raw:" + id, raw);
    });
    const jobs = new ReadingJobs(store, async () => result, true);
    const job = jobs.get(profile, "en").job;
    await jobs.close();
    validate("NatalReading", jobs.get(profile, "en").reading);
    validate("NatalReading", jobs.get(profile, "tr").reading);
    console.log(
      JSON.stringify({
        profileId: id,
        jobStatus: job ? store.get("job:" + job.job_id).status : "cached",
      }),
    );
  }
} finally {
  store.close();
}
