import fs from "node:fs";
import { computeBirthChart, bridge } from "../local-api/engine";
import { LiveMap } from "../local-api/map";
import { MapJobs, mapContext } from "../local-api/map-jobs";
import { Store } from "../local-api/store";
import { fixture } from "../mock-api/fixtures";
import { runReadingBridge } from "../local-api/readings";
const kind = process.argv[2] ?? "place";
if (!["place", "area", "recommendation"].includes(kind))
  throw new Error("Invalid map test");
const filename = `artifacts/live/map-${kind}-smoke.json`;
if (fs.existsSync(filename))
  throw new Error(
    "Existing live result must be reviewed before repeating paid work",
  );
const id = "69f8c19f-34cd-46b7-8898-3433dacc1f21";
const birth = {
  date: "1990-07-13",
  time: "12:30",
  place: { lat: 42.6977, lon: 23.3217, tz: "Europe/Sofia" },
};
const { chart, raw } = await computeBirthChart(birth, id);
const p = {
  ...fixture("profile.1.en"),
  profile_id: id,
  chart_key: chart.chart_key,
  is_self: false,
  birth,
  current_place: null,
};
const store = new Store(":memory:");
store.put("profile:" + id, p);
store.put("raw:" + id, raw);
const maps = new LiveMap(store);
let input: any, facts: any;
if (kind === "place") {
  const place = (
    await bridge({ action: "places", query: "Sofia", lang: "en" })
  )[0];
  input = {
    place: {
      place_id: place.place_id,
      name: place.name,
      country_code: place.country_code,
      lat: place.lat,
      lon: place.lon,
    },
    focus_goal: null,
  };
  facts = await maps.placeReport(p, input.place, "en");
} else if (kind === "area") {
  input = { kind: "country", code: "BG" };
  facts = await maps.area(p, "country", "BG", "en");
} else {
  input = {
    request: {
      goal: "love",
      scope: "world",
    },
    home: [birth.place.lat, birth.place.lon],
  };
  facts = await maps.recommend(p, input.request, "en");
  if (!facts.places.length)
    throw new Error(
      "This smoke test requires actual destinations before any paid calls",
    );
}
const context = mapContext(
  p,
  kind as "place" | "area" | "recommendation",
  input,
);
let output: any;
const jobs = new MapJobs(store, true, async (data) => {
  output = await runReadingBridge("map_reading_bridge.py", data);
  fs.mkdirSync("artifacts/live", { recursive: true });
  fs.writeFileSync(filename, JSON.stringify({ output, facts }));
  return output;
});
try {
  jobs.get(context, facts, "en");
  await jobs.close();
  const result: any = jobs.get(context, facts, "en");
  const field =
    kind === "place"
      ? "reading"
      : kind === "area"
        ? "overview"
        : "explanations";
  if (result[field].status !== "ready")
    throw new Error(
      "Map integration failed validation; inspect sanitized job state",
    );
  console.log(
    JSON.stringify({
      kind,
      status: result[field].status,
      reports: jobs.reports("en").length,
    }),
  );
} finally {
  await jobs.close();
  store.close();
}
