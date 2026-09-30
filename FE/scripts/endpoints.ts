/** Explicit endpoint inventory from FE_02. Types are extracted separately, never inferred from fixtures. */
export type Endpoint = {
  method: string;
  path: string;
  response?: string;
  body?: string;
  status?: number;
  backend: "NEW" | "WRAP" | "DERIVED";
  query?: string[];
  generated?: boolean;
  stream?: boolean;
};
const endpoint = (
  method: string,
  path: string,
  response: string | undefined,
  backend: Endpoint["backend"],
  options: Partial<Endpoint> = {},
): Endpoint => ({ method, path, response, backend, ...options });
export const endpoints: Endpoint[] = [
  endpoint("post", "/auth/email/start", undefined, "NEW", {
    body: "EmailStart",
    status: 204,
  }),
  endpoint("post", "/auth/email/verify", "Session", "NEW", {
    body: "EmailVerify",
  }),
  endpoint("post", "/auth/apple", "Session", "NEW", { body: "AppleSignIn" }),
  endpoint("post", "/auth/google", "Session", "NEW", { body: "GoogleSignIn" }),
  endpoint("post", "/auth/refresh", "Session", "NEW", {
    body: "RefreshSession",
  }),
  endpoint("post", "/auth/logout", undefined, "NEW", {
    body: "RefreshSession",
    status: 204,
  }),
  endpoint("get", "/me", "Me", "NEW"),
  endpoint("patch", "/me", "Me", "NEW", { body: "MeInput" }),
  endpoint("delete", "/me", undefined, "NEW", { status: 202 }),
  endpoint("post", "/me/export", undefined, "NEW", { status: 202 }),
  endpoint("get", "/places/search", "PlaceCandidate[]", "NEW", {
    query: ["q", "kind", "limit"],
  }),
  endpoint("get", "/places/reverse", "PlaceOrNull", "NEW", {
    query: ["lat", "lon"],
  }),
  endpoint("get", "/places/{place_id}", "Place", "NEW"),
  endpoint("get", "/profiles", "BirthProfile[]", "NEW"),
  endpoint("post", "/profiles", "BirthProfile", "NEW", {
    body: "BirthProfileInput",
    status: 201,
  }),
  endpoint("get", "/profiles/{id}", "BirthProfile", "NEW"),
  endpoint("patch", "/profiles/{id}", "BirthProfile", "NEW", {
    body: "BirthProfilePatch",
  }),
  endpoint("delete", "/profiles/{id}", undefined, "NEW", { status: 204 }),
  endpoint("get", "/profiles/{id}/chart", "ChartData", "WRAP"),
  endpoint("get", "/profiles/{id}/natal-reading", "NatalReading", "WRAP", {
    generated: true,
  }),
  endpoint("get", "/profiles/{id}/chart/elements", "ChartElements", "NEW", {
    generated: true,
  }),
  endpoint("get", "/home", "HomeSummary", "DERIVED"),
  endpoint("get", "/profiles/{id}/forecast/day", "DayForecast", "WRAP", {
    query: ["date", "lens"],
  }),
  endpoint("get", "/profiles/{id}/forecast/month", "MonthForecast", "WRAP", {
    query: ["month", "lens"],
  }),
  endpoint("get", "/profiles/{id}/forecast/year", "YearForecast", "WRAP", {
    query: ["from", "lens"],
  }),
  endpoint("get", "/profiles/{id}/solar-return", "SolarReturn", "NEW", {
    query: ["year", "place_id"],
  }),
  endpoint("post", "/compatibility", "Compatibility", "WRAP", {
    body: "CompatibilityInput",
    status: 201,
  }),
  endpoint("get", "/compatibility", "CompatibilityPage", "WRAP", {
    query: ["cursor", "limit"],
  }),
  endpoint("get", "/compatibility/{id}", "Compatibility", "WRAP"),
  endpoint("delete", "/compatibility/{id}", undefined, "NEW", { status: 204 }),
  endpoint("get", "/profiles/{id}/acg/lines", "AcgLines", "WRAP"),
  endpoint("get", "/profiles/{id}/acg/heat/{goal}", "AcgHeat", "DERIVED"),
  endpoint(
    "get",
    "/profiles/{id}/acg/lines/{body}/{angle}/places",
    "LinePlaces",
    "DERIVED",
    { query: ["limit"] },
  ),
  endpoint(
    "get",
    "/profiles/{id}/acg/places/{place_id}",
    "PlaceReport",
    "WRAP",
    { query: ["focus_goal"] },
  ),
  endpoint("get", "/profiles/{id}/acg/point", "PlaceReport", "WRAP", {
    query: ["lat", "lon", "focus_goal"],
  }),
  endpoint("get", "/profiles/{id}/acg/countries/{iso2}", "AreaReport", "WRAP"),
  endpoint(
    "get",
    "/profiles/{id}/acg/regions/{admin1_id}",
    "AreaReport",
    "WRAP",
  ),
  endpoint(
    "post",
    "/profiles/{id}/acg/recommendations",
    "Recommendation",
    "WRAP",
    { body: "RecommendationRequest" },
  ),
  endpoint("get", "/geo/countries.geojson", "CountryGeometry", "WRAP"),
  endpoint("get", "/geo/regions/{iso2}.geojson", "RegionGeometry", "WRAP"),
  endpoint(
    "get",
    "/profiles/{id}/calendar/months/{month}",
    "CalendarMonth",
    "WRAP",
  ),
  endpoint(
    "get",
    "/profiles/{id}/calendar/days/{date}",
    "CalendarDayDetail",
    "WRAP",
  ),
  endpoint(
    "get",
    "/profiles/{id}/calendar/items/{item_id}",
    "CalendarItem",
    "WRAP",
  ),
  endpoint("get", "/profiles/{id}/calendar/periods", "PeriodRef[]", "WRAP", {
    query: ["from", "to", "goal"],
  }),
  endpoint("get", "/profiles/{id}/calendar/year", "CalendarYear", "WRAP"),
  endpoint("get", "/profiles/{id}/best-days", "BestDaysOverview", "WRAP"),
  endpoint(
    "get",
    "/profiles/{id}/best-days/{activity}/{date}",
    "BestDayDetail",
    "WRAP",
  ),
  endpoint(
    "get",
    "/profiles/{id}/notification-candidates",
    "NotificationCandidate[]",
    "WRAP",
    { query: ["from", "to"] },
  ),
  endpoint("post", "/ask/threads", "Thread", "NEW", { body: "ThreadInput" }),
  endpoint("get", "/ask/threads", "ThreadPage", "NEW", {
    query: ["cursor", "limit"],
  }),
  endpoint("get", "/ask/threads/{id}", "Thread", "NEW"),
  endpoint("delete", "/ask/threads/{id}", undefined, "NEW", { status: 204 }),
  endpoint("post", "/ask/threads/{id}/messages", undefined, "NEW", {
    body: "AskRequest",
    stream: true,
  }),
  endpoint("post", "/ask/messages/{message_id}/feedback", undefined, "NEW", {
    body: "FeedbackInput",
    status: 204,
  }),
  endpoint("get", "/reports", "ReportPage", "NEW", {
    query: ["type", "cursor", "limit"],
  }),
  endpoint("delete", "/reports/{report_id}", undefined, "NEW", { status: 204 }),
  endpoint("get", "/jobs/{job_id}", "Job", "NEW"),
  endpoint("get", "/meta/catalogue", "Catalogue", "DERIVED"),
  endpoint("get", "/meta/config", "Config", "NEW"),
];
