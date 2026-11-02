/**
 * Optional Sentry error reporting for the API.
 * Missing SENTRY_DSN disables reporting (warn + continue). Never logs the DSN value.
 */
import * as Sentry from "@sentry/node";

const EMAIL_RE = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi;
const BIRTH_DATE_RE = /\b(?:19|20)\d{2}-\d{2}-\d{2}\b/g;
const BEARER_RE = /Bearer\s+[A-Za-z0-9._~+/=-]+/gi;
const JWTISH_RE = /\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/g;

const SENSITIVE_KEY =
  /^(authorization|cookie|set-cookie|access[_-]?token|refresh[_-]?token|id[_-]?token|identity[_-]?token|token|apikey|api[_-]?key|password|secret|email|birth([_-].*)?)$/i;

function scrubString(value: string): string {
  return value
    .replace(BEARER_RE, "Bearer [Filtered]")
    .replace(JWTISH_RE, "[Filtered]")
    .replace(EMAIL_RE, "[Filtered]")
    .replace(BIRTH_DATE_RE, "[Filtered]");
}

function scrubDeep(value: unknown, key?: string): unknown {
  if (key && SENSITIVE_KEY.test(key)) return "[Filtered]";
  if (typeof value === "string") return scrubString(value);
  if (Array.isArray(value)) return value.map((item) => scrubDeep(item));
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      out[k] = scrubDeep(v, k);
    }
    return out;
  }
  return value;
}

/** Strip emails, birth dates, tokens, and request bodies before send. */
export function scrubSentryEvent(
  event: Sentry.ErrorEvent,
): Sentry.ErrorEvent | null {
  const next = scrubDeep(event) as Sentry.ErrorEvent;
  if (next.request) {
    delete next.request.data;
    delete next.request.cookies;
    if (next.request.headers) {
      next.request.headers = scrubDeep(next.request.headers) as Record<
        string,
        string
      >;
    }
    if (next.request.query_string) {
      next.request.query_string = scrubString(String(next.request.query_string));
    }
  }
  if (next.user) {
    delete next.user.email;
    delete next.user.ip_address;
    delete next.user.username;
  }
  return next;
}

let initialized = false;

export type InitSentryOptions = {
  /** Extra beforeSend hook (e.g. tests collecting events). Runs after scrubbing. */
  afterScrub?: (event: Sentry.ErrorEvent) => Sentry.ErrorEvent | null;
};

/**
 * Initialize Sentry from `SENTRY_DSN`. Returns false when unset (warns, does not throw).
 */
export function initSentry(
  env: NodeJS.ProcessEnv = process.env,
  options: InitSentryOptions = {},
): boolean {
  const dsn = env.SENTRY_DSN?.trim();
  if (!dsn) {
    console.warn(
      "SENTRY_DSN is not set; backend error reporting is disabled",
    );
    return false;
  }
  Sentry.init({
    dsn,
    sendDefaultPii: false,
    integrations: [
      Sentry.httpIntegration({
        maxRequestBodySize: "none",
      }),
    ],
    beforeSend(event) {
      const scrubbed = scrubSentryEvent(event);
      if (!scrubbed) return null;
      return options.afterScrub ? options.afterScrub(scrubbed) : scrubbed;
    },
  });
  initialized = true;
  return true;
}

export function sentryEnabled(): boolean {
  return initialized;
}

export { Sentry };
