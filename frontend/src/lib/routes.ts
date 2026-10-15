import type { Href } from "expo-router";
type Params = Record<string, string | undefined>;
const clean = (params: Params) =>
  Object.fromEntries(
    Object.entries(params).filter(
      (entry): entry is [string, string] => entry[1] !== undefined,
    ),
  );
export const routes = {
  place: (placeId: string, params: Params = {}) =>
    ({
      pathname: "/map/place/[placeId]",
      params: { ...clean(params), placeId },
    }) as const,
  area: (areaId: string, kind: string, profile?: string) =>
    ({
      pathname: "/map/area/[areaId]",
      params: { ...clean({ profile }), areaId, kind },
    }) as const,
  ahead: (params: Params = {}) =>
    ({ pathname: "/(tabs)/ahead", params: clean(params) }) as const,
  calendarItem: (id: string, profile?: string) =>
    ({
      pathname: "/calendar/item/[id]",
      params: { ...clean({ profile }), id },
    }) as const,
};
const patterns: { pathname: string; parts: string[] }[] = [
  { pathname: "/gallery", parts: ["gallery"] },
  { pathname: "/", parts: [] },
  { pathname: "/(auth)/link", parts: ["(auth)", "link"] },
  { pathname: "/(auth)/welcome", parts: ["(auth)", "welcome"] },
  { pathname: "/(tabs)/ahead", parts: ["(tabs)", "ahead"] },
  { pathname: "/(tabs)/chart", parts: ["(tabs)", "chart"] },
  { pathname: "/(tabs)", parts: ["(tabs)"] },
  { pathname: "/(tabs)/map", parts: ["(tabs)", "map"] },
  { pathname: "/(tabs)/match", parts: ["(tabs)", "match"] },
  { pathname: "/ahead/calendar", parts: ["ahead", "calendar"] },
  { pathname: "/ahead/today", parts: ["ahead", "today"] },
  { pathname: "/ask", parts: ["ask"] },
  { pathname: "/best-days", parts: ["best-days"] },
  { pathname: "/calendar", parts: ["calendar"] },
  { pathname: "/calendar/periods", parts: ["calendar", "periods"] },
  { pathname: "/calendar/year", parts: ["calendar", "year"] },
  { pathname: "/chart/export", parts: ["chart", "export"] },
  { pathname: "/chart/focus", parts: ["chart", "focus"] },
  { pathname: "/chart/reading", parts: ["chart", "reading"] },
  { pathname: "/forecast/year", parts: ["forecast", "year"] },
  { pathname: "/map/full", parts: ["map", "full"] },
  { pathname: "/map/point", parts: ["map", "point"] },
  { pathname: "/map/recommend", parts: ["map", "recommend"] },
  { pathname: "/map/recommend/result", parts: ["map", "recommend", "result"] },
  { pathname: "/match/new", parts: ["match", "new"] },
  { pathname: "/profile/about", parts: ["profile", "about"] },
  { pathname: "/profile", parts: ["profile"] },
  { pathname: "/profile/location", parts: ["profile", "location"] },
  { pathname: "/profile/notifications", parts: ["profile", "notifications"] },
  { pathname: "/profile/privacy", parts: ["profile", "privacy"] },
  { pathname: "/profile/reports", parts: ["profile", "reports"] },
  { pathname: "/profile/settings", parts: ["profile", "settings"] },
  { pathname: "/profile/charts", parts: ["profile", "charts"] },
  { pathname: "/profile/charts/new", parts: ["profile", "charts", "new"] },
  { pathname: "/(onboarding)/[step]", parts: ["(onboarding)", "[step]"] },
  { pathname: "/ask/[threadId]", parts: ["ask", "[threadId]"] },
  { pathname: "/best-days/[activity]", parts: ["best-days", "[activity]"] },
  {
    pathname: "/best-days/[activity]/[date]",
    parts: ["best-days", "[activity]", "[date]"],
  },
  { pathname: "/calendar/day/[date]", parts: ["calendar", "day", "[date]"] },
  { pathname: "/calendar/item/[id]", parts: ["calendar", "item", "[id]"] },
  { pathname: "/chart/section/[key]", parts: ["chart", "section", "[key]"] },
  {
    pathname: "/forecast/month/[month]",
    parts: ["forecast", "month", "[month]"],
  },
  { pathname: "/map/area/[areaId]", parts: ["map", "area", "[areaId]"] },
  {
    pathname: "/map/line/[body]/[angle]",
    parts: ["map", "line", "[body]", "[angle]"],
  },
  { pathname: "/map/place/[placeId]", parts: ["map", "place", "[placeId]"] },
  { pathname: "/match/[id]", parts: ["match", "[id]"] },
  { pathname: "/profile/charts/[id]", parts: ["profile", "charts", "[id]"] },
  { pathname: "/solar-return/[year]", parts: ["solar-return", "[year]"] },
];
/** API links cannot open external hosts, traverse paths, or select unknown screens. */
export function resolveRoute(value: unknown): Href {
  const fallback: Href = "/(tabs)";
  if (
    typeof value !== "string" ||
    !value.startsWith("/") ||
    value.startsWith("//") ||
    /[\\\x00-\x20]/.test(value)
  )
    return fallback;
  const [path, search = ""] = value.split("?");
  if (!path || path.includes("#")) return fallback;
  try {
    const parts = path.split("/").filter(Boolean).map(decodeURIComponent);
    if (
      parts.some(
        (part) => part === "." || part === ".." || /[\/\\\x00-\x1f]/.test(part),
      )
    )
      return fallback;
    for (const pattern of [
      ...patterns,
      ...patterns
        .filter((p) => p.parts[0] === "(tabs)")
        .map((p) => ({ ...p, parts: p.parts.slice(1) })),
    ]) {
      if (parts.length !== pattern.parts.length) continue;
      const params: Record<string, string> = {};
      for (const [key, val] of new URLSearchParams(search))
        if (!["__proto__", "constructor", "prototype"].includes(key))
          params[key] = val;
      if (
        !pattern.parts.every((part, index) => {
          if (part.startsWith("[")) {
            params[part.slice(1, -1)] = parts[index]!;
            return true;
          }
          return part === parts[index];
        })
      )
        continue;
      // Paths are the checked-in Expo route allowlist; dynamic values remain separate parameters.
      return { pathname: pattern.pathname, params } as Href;
    }
  } catch {
    /* Malformed percent encoding falls back safely. */
  }
  return fallback;
}

export function routeUrl(route: {
  pathname: string;
  params?: Record<string, string>;
}): string {
  let path = route.pathname;
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(route.params ?? {})) {
    const token = `[${key}]`;
    if (path.includes(token))
      path = path.replace(token, encodeURIComponent(value));
    else query.set(key, value);
  }
  return path + (query.size ? `?${query}` : "");
}
