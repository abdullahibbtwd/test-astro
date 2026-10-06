import { routes, routeUrl } from "./routes";
export function routeFor(key: readonly unknown[]): string {
  if (key[0] === "generated" && key[2] === "natal")
    return `/chart/reading?profile=${key[3]}`;
  const path = typeof key[2] === "string" ? key[2] : "",
    url = new URL(path, "http://local"),
    parts = url.pathname.split("/"),
    profile = parts[2] ?? "",
    q = url.searchParams;
  if (url.pathname === "/home") return "/(tabs)/ahead?view=day";
  if (path.startsWith("/compatibility/")) return `/match/${parts[2]}`;
  if (parts[3] === "acg") {
    if (parts[4] === "places")
      return routeUrl(
        routes.place(parts[5] ?? "", {
          profile,
          goal: q.get("focus_goal") ?? undefined,
        }),
      );
    if (parts[4] === "countries" || parts[4] === "regions")
      return routeUrl(
        routes.area(
          parts[5] ?? "",
          parts[4] === "countries" ? "country" : "region",
          profile,
        ),
      );
    if (parts[4] === "recommendations")
      return `/map/recommend/result?profile=${profile}&request=${encodeURIComponent(String(key[3] ?? "{}"))}`;
    return `/(tabs)/map?profile=${profile}`;
  }
  if (parts[3] === "calendar" && parts[4] === "items")
    return routeUrl(routes.calendarItem(parts[5] ?? "", profile));
  if (parts[3] === "best-days" && parts[4] && parts[5])
    return `/best-days/${parts[4]}/${parts[5]}?profile=${profile}`;
  if (parts[3] === "solar-return")
    return `/solar-return/${q.get("year")}?profile=${profile}`;
  return routeUrl(
    routes.ahead({
      profile,
      view: parts[4] ?? "day",
      date: q.get("date") ?? undefined,
      month: q.get("month") ?? q.get("from") ?? undefined,
    }),
  );
}
