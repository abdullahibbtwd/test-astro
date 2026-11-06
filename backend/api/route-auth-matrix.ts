/**
 * Source of truth for route authorization levels.
 * Kept in sync with registrations in app.ts, browser-auth-routes,
 * guest-onboarding, payments/webhook-route, billing-status-route.
 *
 * Auth levels:
 * - public: no Bearer required
 * - user: Bearer JWT (or demo opaque access token) required
 * - webhook: HMAC signature (no Bearer)
 * - admin: none today (reserved)
 * - guest: X-Guest-Token capability (not Bearer)
 * - capability: poll_token / flow id (browser sign-in)
 */
export type AuthLevel =
  | "public"
  | "user"
  | "webhook"
  | "admin"
  | "guest"
  | "capability";

export type RouteAuthEntry = {
  method: string;
  path: string;
  auth: AuthLevel;
  notes?: string;
};

/** Paths use the /v1 prefix as served. `{param}` matches Fastify params. */
export const ROUTE_AUTH_MATRIX: RouteAuthEntry[] = [
  // --- public (generic loop: auth|meta|geo) ---
  { method: "POST", path: "/v1/auth/email/start", auth: "public" },
  { method: "POST", path: "/v1/auth/email/verify", auth: "public" },
  { method: "POST", path: "/v1/auth/apple", auth: "public" },
  { method: "POST", path: "/v1/auth/google", auth: "public" },
  {
    method: "POST",
    path: "/v1/auth/refresh",
    auth: "public",
    notes: "Authorized by refresh_token body, not Bearer",
  },
  {
    method: "POST",
    path: "/v1/auth/logout",
    auth: "public",
    notes: "Authorized by refresh_token body, not Bearer",
  },
  { method: "GET", path: "/v1/meta/config", auth: "public" },
  { method: "GET", path: "/v1/meta/catalogue", auth: "public" },
  { method: "GET", path: "/v1/geo/countries.geojson", auth: "public" },

  // --- browser sign-in (registered only when SupabaseAuth is wired) ---
  { method: "POST", path: "/v1/auth/browser/start", auth: "public" },
  {
    method: "POST",
    path: "/v1/auth/browser/poll",
    auth: "capability",
    notes: "64-hex poll_token",
  },
  {
    method: "POST",
    path: "/v1/auth/browser/cancel",
    auth: "capability",
    notes: "64-hex poll_token",
  },
  {
    method: "GET",
    path: "/v1/auth/browser/callback/:id",
    auth: "capability",
    notes: "flow id + UUID code query",
  },

  // --- webhook ---
  {
    method: "POST",
    path: "/v1/webhooks/payments",
    auth: "webhook",
    notes: "HMAC signature; no Bearer",
  },

  // --- guest onboarding (when ASTRO_GUEST_ONBOARDING=1) ---
  { method: "POST", path: "/v1/onboarding/reading", auth: "guest" },
  { method: "GET", path: "/v1/onboarding/reading", auth: "guest" },
  { method: "DELETE", path: "/v1/onboarding/reading", auth: "guest" },
  {
    method: "POST",
    path: "/v1/me/onboarding/claim",
    auth: "user",
    notes: "Bearer + guest_token body",
  },

  // --- billing ---
  { method: "GET", path: "/v1/billing/status", auth: "user" },

  // --- user (Bearer) ---
  { method: "GET", path: "/v1/me", auth: "user" },
  { method: "PATCH", path: "/v1/me", auth: "user" },
  { method: "DELETE", path: "/v1/me", auth: "user" },
  { method: "POST", path: "/v1/me/export", auth: "user" },
  { method: "GET", path: "/v1/places/search", auth: "user", notes: "public when guest onboarding enabled" },
  { method: "GET", path: "/v1/places/reverse", auth: "user" },
  { method: "GET", path: "/v1/places/{place_id}", auth: "user", notes: "public when guest onboarding enabled" },
  { method: "GET", path: "/v1/profiles", auth: "user" },
  { method: "POST", path: "/v1/profiles", auth: "user" },
  { method: "GET", path: "/v1/profiles/{id}", auth: "user" },
  { method: "PATCH", path: "/v1/profiles/{id}", auth: "user" },
  { method: "DELETE", path: "/v1/profiles/{id}", auth: "user" },
  { method: "GET", path: "/v1/profiles/{id}/chart", auth: "user" },
  { method: "GET", path: "/v1/profiles/{id}/natal-reading", auth: "user" },
  { method: "GET", path: "/v1/profiles/{id}/natal-reading/outline", auth: "user" },
  { method: "GET", path: "/v1/profiles/{id}/natal-reading/sections/{key}", auth: "user" },
  { method: "POST", path: "/v1/profiles/{id}/natal-reading/progress", auth: "user" },
  { method: "POST", path: "/v1/profiles/{id}/natal-reading/complete", auth: "user" },
  { method: "POST", path: "/v1/feedback/reading", auth: "user" },
  { method: "GET", path: "/v1/profiles/{id}/chart/elements", auth: "user" },
  { method: "GET", path: "/v1/home", auth: "user" },
  { method: "GET", path: "/v1/profiles/{id}/forecast/day", auth: "user" },
  { method: "GET", path: "/v1/profiles/{id}/forecast/month", auth: "user" },
  { method: "GET", path: "/v1/profiles/{id}/forecast/year", auth: "user" },
  { method: "GET", path: "/v1/profiles/{id}/solar-return", auth: "user" },
  { method: "POST", path: "/v1/compatibility", auth: "user" },
  { method: "GET", path: "/v1/compatibility", auth: "user" },
  { method: "GET", path: "/v1/compatibility/{id}", auth: "user" },
  { method: "DELETE", path: "/v1/compatibility/{id}", auth: "user" },
  { method: "GET", path: "/v1/profiles/{id}/acg/lines", auth: "user" },
  { method: "GET", path: "/v1/profiles/{id}/acg/heat/{goal}", auth: "user" },
  { method: "GET", path: "/v1/profiles/{id}/acg/lines/{body}/{angle}/places", auth: "user" },
  { method: "GET", path: "/v1/profiles/{id}/acg/places/{place_id}", auth: "user" },
  { method: "GET", path: "/v1/profiles/{id}/acg/point", auth: "user" },
  { method: "GET", path: "/v1/profiles/{id}/acg/countries/{iso2}", auth: "user" },
  { method: "GET", path: "/v1/profiles/{id}/acg/regions/{admin1_id}", auth: "user" },
  { method: "POST", path: "/v1/profiles/{id}/acg/recommendations", auth: "user" },
  { method: "GET", path: "/v1/profiles/{id}/calendar/months/{month}", auth: "user" },
  { method: "GET", path: "/v1/profiles/{id}/calendar/days/{date}", auth: "user" },
  { method: "GET", path: "/v1/profiles/{id}/calendar/items/{item_id}", auth: "user" },
  { method: "GET", path: "/v1/profiles/{id}/calendar/periods", auth: "user" },
  { method: "GET", path: "/v1/profiles/{id}/calendar/year", auth: "user" },
  { method: "GET", path: "/v1/profiles/{id}/best-days", auth: "user" },
  { method: "GET", path: "/v1/profiles/{id}/best-days/{activity}/{date}", auth: "user" },
  { method: "GET", path: "/v1/profiles/{id}/notification-candidates", auth: "user" },
  { method: "POST", path: "/v1/ask/threads", auth: "user" },
  { method: "GET", path: "/v1/ask/threads", auth: "user" },
  { method: "GET", path: "/v1/ask/threads/{id}", auth: "user" },
  { method: "DELETE", path: "/v1/ask/threads/{id}", auth: "user" },
  { method: "POST", path: "/v1/ask/threads/{id}/messages", auth: "user" },
  { method: "POST", path: "/v1/ask/messages/{message_id}/feedback", auth: "user" },
  { method: "GET", path: "/v1/reports", auth: "user" },
  { method: "DELETE", path: "/v1/reports/{report_id}", auth: "user" },
  { method: "GET", path: "/v1/jobs/{job_id}", auth: "user" },
];

/** Expand template path to a concrete URL for inject tests. */
export function concretePath(template: string): string {
  return template
    .replace(/\{id\}/g, "00000000-0000-4000-8000-000000000001")
    .replace(/\{place_id\}/g, "place-test-1")
    .replace(/\{key\}/g, "sun")
    .replace(/\{goal\}/g, "love")
    .replace(/\{body\}/g, "sun")
    .replace(/\{angle\}/g, "asc")
    .replace(/\{iso2\}/g, "TR")
    .replace(/\{admin1_id\}/g, "TR-34")
    .replace(/\{month\}/g, "2026-11")
    .replace(/\{date\}/g, "2026-11-06")
    .replace(/\{item_id\}/g, "item-1")
    .replace(/\{activity\}/g, "meeting")
    .replace(/\{job_id\}/g, "00000000-0000-4000-8000-000000000099")
    .replace(/\{report_id\}/g, "map-deadbeef-en")
    .replace(/\{message_id\}/g, "00000000-0000-4000-8000-000000000088")
    .replace(/:id\b/g, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
}

export const EXPECTED_AUTH_RESULTS = {
  user: {
    noToken: 401,
    malformedToken: 401,
    expiredToken: 401,
    wrongAudience: 401,
    wrongIssuer: 401,
    validToken: "non-401 (200/400/404/409/503 depending on resource state)",
  },
  public: {
    anyBearer: "Bearer ignored; route does not require auth (not 401 from auth)",
  },
  webhook: {
    missingOrBadSignature: 401,
    validSignature: 200,
  },
  admin: "No admin routes exist.",
} as const;
