/**
 * Global HTTP rate limiting (in-process, process memory only).
 *
 * Restart clears every bucket — counters reset. Acceptable for abuse smoothing;
 * not a durable quota store.
 *
 * Hook order (intentional):
 *   1. onRequest — coarse per-IP limit (protects JWT verify from garbage floods)
 *   2. route handler auth (resolveTenant)
 *   3. enforceUserRateLimit — per verified user_id (general / expensive / job-poll)
 *
 * Env:
 *   ASTRO_TRUST_PROXY_HOPS           — Fastify trustProxy hop count (default 0)
 *   ASTRO_RATE_LIMIT_DISABLED=1      — turn off
 *   ASTRO_RATE_LIMIT_WINDOW_MS       — window (default 60000)
 *   ASTRO_RATE_LIMIT_IP_MAX          — coarse per-IP before auth (default 300)
 *   ASTRO_RATE_LIMIT_MAX             — per-user general (default 120)
 *   ASTRO_RATE_LIMIT_EXPENSIVE_MAX   — per-user expensive (default 40)
 *   ASTRO_RATE_LIMIT_JOB_MAX         — per-user GET /jobs/{id} (default 180)
 *
 * Never read X-Forwarded-For manually; use request.ip (requires trustProxy hops).
 */
import type { FastifyInstance, FastifyReply, FastifyRequest } from "fastify";

export type RateLimitConfig = {
  disabled: boolean;
  windowMs: number;
  ipMax: number;
  max: number;
  expensiveMax: number;
  jobMax: number;
  trustProxyHops: number;
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

export function readTrustProxyHops(
  env: NodeJS.ProcessEnv = process.env,
): number {
  const raw = env.ASTRO_TRUST_PROXY_HOPS;
  if (raw === undefined || raw === "") return 0;
  const n = Number(raw);
  if (!Number.isFinite(n) || n < 0) return 0;
  return Math.floor(n);
}

export function readRateLimitConfig(
  env: NodeJS.ProcessEnv = process.env,
): RateLimitConfig {
  return {
    disabled: env.ASTRO_RATE_LIMIT_DISABLED === "1",
    windowMs: Math.max(
      1000,
      Number(env.ASTRO_RATE_LIMIT_WINDOW_MS ?? 60_000) || 60_000,
    ),
    // Separate from, and much higher than, per-user general (120).
    ipMax: Math.max(1, Number(env.ASTRO_RATE_LIMIT_IP_MAX ?? 300) || 300),
    max: Math.max(1, Number(env.ASTRO_RATE_LIMIT_MAX ?? 120) || 120),
    expensiveMax: Math.max(
      1,
      Number(env.ASTRO_RATE_LIMIT_EXPENSIVE_MAX ?? 40) || 40,
    ),
    // Mobile JobWatcher: serial polls, ≥1s between starts → ≤60/min; 180 = 3× headroom.
    jobMax: Math.max(1, Number(env.ASTRO_RATE_LIMIT_JOB_MAX ?? 180) || 180),
    trustProxyHops: readTrustProxyHops(env),
  };
}

export function isExemptPath(url: string): boolean {
  const path = (url.split("?")[0] ?? url).replace(/\/+$/, "") || "/";
  return path === "/v1/meta/config";
}

/** GET /v1/jobs/{id} — status polls; own generous per-user bucket (not general). */
export function isJobPollRoute(method: string, url: string): boolean {
  const path = (url.split("?")[0] ?? url).replace(/\/+$/, "") || "/";
  return method.toUpperCase() === "GET" && /^\/v1\/jobs\/[^/]+$/.test(path);
}

export function isExpensiveRoute(method: string, url: string): boolean {
  const path = url.split("?")[0] ?? url;
  const key = `${method.toUpperCase()}:${path}`;
  return expensivePatterns.some((re) => re.test(key));
}

function problemPayload(kind: "expensive" | "general") {
  return {
    type: "about:blank",
    title: "Too many requests",
    status: 429,
    code: "rate_limited" as const,
    detail:
      kind === "expensive"
        ? "Expensive endpoint rate limit exceeded. Try again shortly."
        : "API rate limit exceeded. Try again shortly.",
  };
}

function touchBucket(
  buckets: Map<string, Bucket>,
  key: string,
  windowMs: number,
  now: number,
): Bucket {
  let bucket = buckets.get(key);
  if (!bucket || bucket.resetAt <= now) {
    bucket = { count: 0, resetAt: now + windowMs };
    buckets.set(key, bucket);
  }
  bucket.count += 1;
  return bucket;
}

function sendLimited(
  reply: FastifyReply,
  bucket: Bucket,
  limit: number,
  now: number,
  kind: "expensive" | "general",
) {
  const remaining = Math.max(0, limit - bucket.count);
  const retryAfter = Math.max(1, Math.ceil((bucket.resetAt - now) / 1000));
  void reply.header("X-RateLimit-Limit", String(limit));
  void reply.header("X-RateLimit-Remaining", String(remaining));
  void reply.header(
    "X-RateLimit-Reset",
    String(Math.ceil(bucket.resetAt / 1000)),
  );
  void reply.header("Retry-After", String(retryAfter));
  return reply
    .code(429)
    .type("application/problem+json")
    .send(problemPayload(kind));
}

export type RateLimiter = {
  config: RateLimitConfig;
  /** Call after resolveTenant with the verified user/tenant id. */
  enforceUserRateLimit: (
    request: FastifyRequest,
    reply: FastifyReply,
    userId: string,
  ) => boolean;
  /** Test helper */
  _buckets: Map<string, Bucket>;
};

/**
 * Registers the pre-auth IP limit (onRequest) and returns enforceUserRateLimit
 * for use after JWT/session verification in the route handler.
 */
export function registerRateLimit(
  app: FastifyInstance,
  config: RateLimitConfig = readRateLimitConfig(),
): RateLimiter | null {
  // Process-local Map only — lost on restart (limits reset).
  const buckets = new Map<string, Bucket>();
  const noop: RateLimiter = {
    config,
    enforceUserRateLimit: () => false,
    _buckets: buckets,
  };
  if (config.disabled) return noop;

  app.addHook("onRequest", async (request, reply) => {
    if (isExemptPath(request.url)) return;
    // Coarse per-IP ONLY — never key on Authorization here (pre-auth).
    const ip = request.ip || "unknown";
    const now = Date.now();
    const key = `ip:${ip}`;
    const bucket = touchBucket(buckets, key, config.windowMs, now);
    if (bucket.count > config.ipMax) {
      return sendLimited(reply, bucket, config.ipMax, now, "general");
    }
    void reply.header("X-RateLimit-Limit", String(config.ipMax));
    void reply.header(
      "X-RateLimit-Remaining",
      String(Math.max(0, config.ipMax - bucket.count)),
    );
  });

  const timer = setInterval(() => {
    const now = Date.now();
    for (const [key, bucket] of buckets)
      if (bucket.resetAt <= now) buckets.delete(key);
  }, Math.min(config.windowMs, 30_000));
  timer.unref?.();
  app.addHook("onClose", async () => clearInterval(timer));

  const enforceUserRateLimit = (
    request: FastifyRequest,
    reply: FastifyReply,
    userId: string,
  ): boolean => {
    if (!userId || isExemptPath(request.url)) return false;
    const jobPoll = isJobPollRoute(request.method, request.url);
    const expensive =
      !jobPoll && isExpensiveRoute(request.method, request.url);
    const limit = jobPoll
      ? config.jobMax
      : expensive
        ? config.expensiveMax
        : config.max;
    const now = Date.now();
    const key = `${jobPoll ? "ju" : expensive ? "eu" : "gu"}:${userId}`;
    const bucket = touchBucket(buckets, key, config.windowMs, now);
    if (bucket.count > limit) {
      void sendLimited(
        reply,
        bucket,
        limit,
        now,
        expensive ? "expensive" : "general",
      );
      return true;
    }
    void reply.header("X-RateLimit-Limit", String(limit));
    void reply.header(
      "X-RateLimit-Remaining",
      String(Math.max(0, limit - bucket.count)),
    );
    void reply.header(
      "X-RateLimit-Reset",
      String(Math.ceil(bucket.resetAt / 1000)),
    );
    return false;
  };

  return { config, enforceUserRateLimit, _buckets: buckets };
}
