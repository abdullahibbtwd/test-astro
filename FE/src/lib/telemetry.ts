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
