import fs from "node:fs";
import path from "node:path";
import { Store } from "./store";
export function exportAccount(store: Store) {
  return {
    format: "astrology-local-export-v1",
    exported_at: new Date().toISOString(),
    account: store.get("me"),
    profiles: store.list("profile:"),
    charts: store.list("chart:"),
    calculation_data: store.list("raw:"),
    natal_readings: store.list("reading:"),
    forecast_readings: store.list("forecast-reading:"),
    forecast_index: store.list("forecast-report:"),
    map_readings: store.list("map-reading:"),
    map_index: store.list("map-report:"),
    compatibility: store.list<any>("compat:").map((r) => ({
      id: r.id,
      context: r.context,
      created_at: r.created_at,
      readings: r.readings,
    })),
    conversations: store.list("ask-thread:"),
    conversation_feedback: store.list("ask-feedback:"),
    saved_reports: store.list("report:"),
  };
}
export function deleteAccount(store: Store, dbPath: string) {
  if (
    store
      .list<any>("job:")
      .some((j) => ["queued", "running"].includes(j.status))
  )
    throw Object.assign(new Error("Wait for active readings before deleting"), {
      statusCode: 409,
    });
  const root = path.resolve(path.dirname(dbPath));
  const cache = path.resolve(root, "map-products");
  if (path.dirname(cache) !== root)
    throw new Error("Invalid account cache path");
  fs.rmSync(cache, { recursive: true, force: true });
  store.clear();
}
