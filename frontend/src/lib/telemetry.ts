// Only allowlisted technical fields can leave the device. Vendors stay disabled without credentials.
const allowed = new Set([
  "kind",
  "step",
  "route",
  "seconds",
  "rating",
  "target",
  "section",
  "type",
]);
export function safeEvent(
  name: string,
  properties: Record<string, unknown> = {},
) {
  return {
    name,
    properties: Object.fromEntries(
      Object.entries(properties)
        .filter(([key, value]) => allowed.has(key) && typeof value !== "object")
        .map(([key, value]) => [
          key,
          key === "route"
            ? String(value)
                .replace(
                  /(\/(?:profiles|places|compatibility)\/)[^/?]+/g,
                  "$1:id",
                )
                .replace(/[0-9a-f]{8}-[0-9a-f-]{27,}/gi, ":id")
                .split("?")[0]
            : value,
        ]),
    ),
  };
}
export function scrubError() {
  return { message: "Application error", tags: { area: "frontend" } };
}

/** Sentry beforeSend: drop PII, reading text, emails, Authorization, birth data. */
export function beforeSendEvent(event: Record<string, unknown>) {
  const diagnostic =
    event.extra &&
    typeof event.extra === "object" &&
    (event.extra as { diagnostic?: unknown }).diagnostic
      ? { diagnostic: (event.extra as { diagnostic: unknown }).diagnostic }
      : undefined;
  return {
    ...scrubError(),
    type: event.type,
    // Only our pre-scrubbed structural diagnostic is forwarded.
    extra: diagnostic,
  };
}

/** Sentry beforeBreadcrumb: keep navigation/http shells only; drop everything else. */
export function beforeBreadcrumbEvent(breadcrumb: {
  category?: string;
  data?: Record<string, unknown>;
  message?: string;
}) {
  if (breadcrumb.category === "navigation")
    return {
      category: "navigation",
      data: safeEvent("navigation", {
        route: String(breadcrumb.data?.to ?? breadcrumb.data?.route ?? ""),
      }).properties,
    };
  if (breadcrumb.category === "http")
    return {
      category: "http",
      data: { status_code: breadcrumb.data?.status_code },
    };
  return null;
}

type Diagnostic = {
  kind: "error" | "contract_violation";
  schema?: string;
  issues?: { path: (string | number)[]; code: string }[];
};
const reports: Diagnostic[] = [];
let sink: ((report: Diagnostic) => void) | undefined;
let initialized = false;
export const diagnosticReports = () => [...reports];
function record(report: Diagnostic) {
  if (
    typeof __DEV__ !== "undefined"
      ? __DEV__
      : process.env.NODE_ENV !== "production"
  ) {
    reports.push(report);
    if (reports.length > 50) reports.shift();
  }
  sink?.(report);
}
export async function initTelemetry() {
  if (initialized) return;
  initialized = true;
  const dsn = process.env.EXPO_PUBLIC_SENTRY_DSN;
  if (!dsn) return;
  const Sentry = await import("@sentry/react-native");
  Sentry.init({
    dsn,
    sendDefaultPii: false,
    enableAutoSessionTracking: false,
    enableNative: false,
    defaultIntegrations: false,
    beforeSend: (event) =>
      beforeSendEvent(event as unknown as Record<string, unknown>) as typeof event,
    beforeBreadcrumb: (breadcrumb) =>
      beforeBreadcrumbEvent({
        category: breadcrumb.category,
        data: breadcrumb.data as Record<string, unknown> | undefined,
        message: breadcrumb.message,
      }) as typeof breadcrumb | null,
  });
  sink = (report) =>
    Sentry.captureMessage(report.kind, { extra: { diagnostic: report } });
}
// Never forward error.message, user content, response payloads, or caller context.
export function reportError(
  _error: unknown,
  _context?: Record<string, unknown>,
) {
  record({ kind: "error" });
}
export function reportContractViolation(
  schema: string,
  issues: { path: (string | number)[]; code: string }[],
) {
  record({
    kind: "contract_violation",
    schema: /^[A-Za-z0-9_]+$/.test(schema) ? schema : "unknown",
    issues: issues.map((issue) => ({
      path: issue.path.map((p) =>
        typeof p === "number"
          ? p
          : [
                "status",
                "reading",
                "today",
                "areas",
                "band",
                "tone",
                "goal",
                "body",
                "moon",
                "points",
                "features",
                "properties",
                "type",
                "text",
                "stages",
                "people",
                "date",
                "profile_id",
              ].includes(p)
            ? p
            : ":key",
      ),
      code: issue.code,
    })),
  });
}
