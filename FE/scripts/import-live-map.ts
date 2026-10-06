import fs from "node:fs";
import { Store } from "../local-api/store";
import { MapJobs, mapContext } from "../local-api/map-jobs";
import { LiveMap } from "../local-api/map";
const kind = process.argv[2] ?? "place";
if (!["place", "area", "recommendation"].includes(kind))
  throw new Error("Invalid map test");
const { output, facts: original } = JSON.parse(
  fs.readFileSync(`artifacts/live/map-${kind}-smoke.json`, "utf8"),
);
const store = new Store(".local-data/app.sqlite");
try {
  if (
    store
      .list<any>("job:")
      .some((j) => ["running", "queued"].includes(j.status))
  )
    throw new Error("Wait for active jobs before importing");
  const c = output.context,
    p = store.get("profile:" + c.profile_id);
  if (
    !p ||
    p.label !== "Fictional AI test" ||
    c.profile_id !== "69f8c19f-34cd-46b7-8898-3433dacc1f21"
  )
    throw new Error("Fictional test profile not found");
  if (JSON.stringify(mapContext(p, c.kind, c.input)) !== JSON.stringify(c))
    throw new Error("Chart context no longer matches");
  const maps = new LiveMap(store);
  let facts;
  if (kind === "place")
    facts = await maps.placeReport(
      p,
      c.input.place,
      "en",
      c.input.focus_goal ?? undefined,
    );
  else if (kind === "area")
    facts = await maps.area(p, c.input.kind, c.input.code, "en");
  else {
    const current =
      (p.is_self ? store.get("me")?.current_place : p.current_place) ??
      p.birth.place;
    if (
      JSON.stringify([current.lat, current.lon]) !==
      JSON.stringify(c.input.home)
    )
      throw new Error("Current location changed");
    facts = await maps.recommend(p, c.input.request, "en");
  }
  if (JSON.stringify(facts) !== JSON.stringify(original))
    throw new Error("Deterministic facts changed since generation");
  const jobs = new MapJobs(store, true, async () => output);
  jobs.get(c, facts, "en", true);
  await jobs.close();
  const field =
    kind === "place"
      ? "reading"
      : kind === "area"
        ? "overview"
        : "explanations";
  for (const lang of ["en", "tr"] as const)
    if ((jobs.get(c, facts, lang) as any)[field].status !== "ready")
      throw new Error("Import failed validation");
  console.log(JSON.stringify({ kind, status: "ready", profile: p.label }));
} finally {
  store.close();
}
