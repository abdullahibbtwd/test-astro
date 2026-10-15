import type { Query } from "@tanstack/react-query";
import { CONTRACT_VERSION } from "./contract-version";
export const CACHE_MAX_AGE = 30 * 24 * 60 * 60 * 1000;
export const CACHE_SHAPE_VERSION = 2;
export const CACHE_BUSTER = `${CONTRACT_VERSION}:${CACHE_SHAPE_VERSION}`;
export function keepsReading(key: readonly unknown[]) {
  if (key[0] === "generated") return true;
  const path = String(key[2] ?? "").split("?")[0] ?? "";
  return (
    key[0] === "resource" &&
    /(?:\/natal-reading$|\/forecast\/(?:month|year)$|^\/compatibility\/[^/]+$|\/acg\/(?:places|point|countries|regions|recommendations)(?:\/|$)|\/solar-return$)/.test(
      path,
    )
  );
}
export function shouldPersistQuery(query: Query, all: Query[] = []) {
  if (
    query.state.status !== "success" ||
    query.state.error ||
    query.queryKey[0] === "job" ||
    query.queryKey[0] === "guest-core"
  )
    return false;
  const path = String(query.queryKey[2] ?? "");
  if (path.startsWith("/geo/")) return false;
  if (path.includes("/acg/heat/")) {
    const recent = all
      .filter((q) => String(q.queryKey[2]).includes("/acg/heat/"))
      .sort((a, b) => b.state.dataUpdatedAt - a.state.dataUpdatedAt)
      .slice(0, 3);
    return recent.includes(query);
  }
  return true;
}
export function serializeCache(value: unknown) {
  const data = JSON.stringify(value);
  if (typeof __DEV__ !== "undefined" && __DEV__) {
    const bytes = new TextEncoder().encode(data).length;
    console.info("Persisted cache bytes", bytes);
    if (bytes > 5 * 1024 * 1024) console.warn("Persisted cache exceeds 5 MB");
  }
  return data;
}
