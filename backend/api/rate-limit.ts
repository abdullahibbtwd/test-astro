/**
 * Global HTTP rate limiting (in-process).
 *
 * Env:
 *   ASTRO_RATE_LIMIT_DISABLED=1     — turn off (CI / local inject storms)
 *   ASTRO_RATE_LIMIT_WINDOW_MS      — window length (default 60000)
 *   ASTRO_RATE_LIMIT_MAX            — general requests per window (default 120)
 *   ASTRO_RATE_LIMIT_EXPENSIVE_MAX  — expensive routes per window (default 20)
 */
import type { FastifyInstance, FastifyRequest } from "fastify";

export type RateLimitConfig = {
  disabled: boolean;
  windowMs: number;
  max: number;
  expensiveMax: number;
};

type Bucket = { count: number; resetAt: number };

const expensivePatterns: RegExp[] = [
  /^POST:\/v1\/compatibility$/,
  /^POST:\/v1\/ask\/threads$/,
  /^POST:\/v1\/ask\/threads\/[^/]+\/messages$/,
  /^POST:\/v1\/profiles$/,
  /^POST:\/v1\/profiles\/[^/]+$/,
  /^POST:\/v1\/onboarding\/reading$/,
  /^POST:\/v1\/me\/export$/,
  /^POST:\/v1\/me\/onboarding\/claim$/,
  /^POST:\/v1\/profiles\/[^/]+\/acg\/recommendations$/,
  /^GET:\/v1\/profiles\/[^/]+\/natal-reading(?:\/|$)/,
  /^GET:\/v1\/profiles\/[^/]+\/solar-return$/,
  /^GET:\/v1\/profiles\/[^/]+\/forecast\/(?:day|month|year)$/,
  /^GET:\/v1\/profiles\/[^/]+\/acg\/(?:lines|heat\/[^/]+)$/,
];

export function readRateLimitConfig(
  env: NodeJS.ProcessEnv = process.env,
): RateLimitConfig {
  return {
    disabled: env.ASTRO_RATE_LIMIT_DISABLED === "1",
    windowMs: Math.max(
      1000,
      Number(env.ASTRO_RATE_LIMIT_WINDOW_MS ?? 60_000) || 60_000,
    ),
    max: Math.max(1, Number(env.ASTRO_RATE_LIMIT_MAX ?? 120) || 120),
    expensiveMax: Math.max(
      1,
      Number(env.ASTRO_RATE_LIMIT_EXPENSIVE_MAX ?? 20) || 20,
    ),
  };
}

export function isExpensiveRoute(method: string, url: string): boolean {
  const path = url.split("?")[0] ?? url;
  const key = `${method.toUpperCase()}:${path}`;
  return expensivePatterns.some((re) => re.test(key));
}

function clientKey(request: FastifyRequest): string {
  const auth = String(request.headers.authorization ?? "").trim();
  if (auth) return `auth:${auth.slice(0, 64)}`;
  const xf = String(request.headers["x-forwarded-for"] ?? "")
    .split(",")[0]
    ?.trim();
  if (xf) return `ip:${xf}`;
  return `ip:${request.ip || "unknown"}`;
}

export function registerRateLimit(
  app: FastifyInstance,
  config: RateLimitConfig = readRateLimitConfig(),
) {
  if (config.disabled) return;
  const buckets = new Map<string, Bucket>();

  app.addHook("onRequest", async (request, reply) => {
    const expensive = isExpensiveRoute(request.method, request.url);
    const limit = expensive ? config.expensiveMax : config.max;
    const key = `${expensive ? "e" : "g"}:${clientKey(request)}`;
    const now = Date.now();
    let bucket = buckets.get(key);
    if (!bucket || bucket.resetAt <= now) {
      bucket = { count: 0, resetAt: now + config.windowMs };
      buckets.set(key, bucket);
    }
    bucket.count += 1;
    const remaining = Math.max(0, limit - bucket.count);
    const retryAfter = Math.max(1, Math.ceil((bucket.resetAt - now) / 1000));
    void reply.header("X-RateLimit-Limit", String(limit));
    void reply.header("X-RateLimit-Remaining", String(remaining));
    void reply.header("X-RateLimit-Reset", String(Math.ceil(bucket.resetAt / 1000)));
    if (bucket.count > limit) {
      void reply.header("Retry-After", String(retryAfter));
      return reply.code(429).send({
        type: "about:blank",
        title: "Too many requests",
        status: 429,
        code: "rate_limited",
        detail: expensive
          ? "Expensive endpoint rate limit exceeded. Try again shortly."
          : "API rate limit exceeded. Try again shortly.",
      });
    }
  });

  // Bound memory: drop expired buckets occasionally.
  const timer = setInterval(() => {
    const now = Date.now();
    for (const [key, bucket] of buckets)
      if (bucket.resetAt <= now) buckets.delete(key);
  }, Math.min(config.windowMs, 30_000));
  timer.unref?.();
  app.addHook("onClose", async () => clearInterval(timer));
}
