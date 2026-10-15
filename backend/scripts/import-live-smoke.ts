import fs from "node:fs";
import { randomUUID } from "node:crypto";
import { Store } from "../api/store";
import { ReadingJobs } from "../api/reading-jobs";
import { computeBirthChart } from "../api/engine";
import { validate } from "../../frontend/src/api/zod";
import type { BirthProfile } from "../../frontend/contracts/spec-types";
import { dataDir } from "../api/data-dir";
import path from "node:path";
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
const store = await Store.open(path.join(dataDir(), "app.sqlite"));
try {
  const prior = (await store.list<BirthProfile>("profile:")).find(
    (p: BirthProfile) =>
      p.label === profile.label && p.chart_key === profile.chart_key,
  );
  if (prior) {
    console.log(JSON.stringify({ profileId: prior.profile_id, reused: true }));
  } else {
    await store.transaction(async () => {
      await store.put("profile:" + id, profile);
      await store.put("chart:" + id, chart);
      await store.put("raw:" + id, raw);
    });
    const jobs = await ReadingJobs.create(
      store,
      async () => result,
      true,
    );
    const first = await jobs.get(profile, "en");
    const job = first.job;
    await jobs.close();
    validate("NatalReading", (await jobs.get(profile, "en")).reading);
    validate("NatalReading", (await jobs.get(profile, "tr")).reading);
    console.log(
      JSON.stringify({
        profileId: id,
        jobStatus: job
          ? (await store.get("job:" + job.job_id)).status
          : "cached",
      }),
    );
  }
} finally {
  await store.close();
}
