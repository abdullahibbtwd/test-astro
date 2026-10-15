const longKinds = new Set([
  "natal_reading",
  "month_reading",
  "year_reading",
  "compatibility",
  "place_reading",
  "area_reading",
  "recommendation",
  "solar_return",
]);
const normalized = (path: string) => path.replace(/\/\([^/]+\)/g, "");
export function shouldNotifyJob(
  kind: string,
  destination: string,
  pathname: string,
  params: Record<string, unknown>,
  activeProfile?: string | null,
) {
  if (!longKinds.has(kind)) return false;
  const target = new URL(destination, "http://local");
  const currentPath = String(params.reportPath ?? pathname);
  const samePath =
    normalized(target.pathname) === normalized(currentPath) ||
    (kind === "natal_reading" && currentPath === "/chart");
  if (!samePath) return true;
  for (const key of ["profile", "view", "date", "month", "goal", "kind"]) {
    const value = target.searchParams.get(key);
    if (
      value &&
      value !==
        String(
          params[key] ??
            (key === "profile"
              ? (activeProfile ?? "")
              : key === "view"
                ? "day"
                : ""),
        )
    )
      return true;
  }
  return false;
}
