import type { PrismaClient, UsageKind } from "../src/generated/prisma/client.js";
import { prisma as getPrisma } from "./db";

type Db = PrismaClient;
type Tx = Parameters<Parameters<PrismaClient["$transaction"]>[0]>[0];

/** UTC calendar day at 00:00:00.000Z for UsageCounter.date. */
export function utcDay(now = new Date()): Date {
  return new Date(
    Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()),
  );
}

/**
 * Atomically consume one unit of daily usage. Returns the new count, or null
 * if the limit would be exceeded (0 rows from the conditional upsert).
 */
export async function tryConsumeUsage(
  userId: string,
  kind: UsageKind,
  limit: number,
  db: Db = getPrisma(),
): Promise<number | null> {
  const day = utcDay();
  const rows = await db.$queryRaw<{ count: number }[]>`
    INSERT INTO usage_counters (user_id, kind, date, count)
    VALUES (${userId}, ${kind}::"UsageKind", ${day}::date, 1)
    ON CONFLICT (user_id, kind, date) DO UPDATE SET
      count = usage_counters.count + 1
    WHERE usage_counters.count < ${limit}
    RETURNING count
  `;
  return rows[0]?.count ?? null;
}

/** Undo one daily usage unit after a failed/cancelled attempt. */
export async function refundUsage(
  userId: string,
  kind: UsageKind,
  db: Db = getPrisma(),
): Promise<void> {
  const day = utcDay();
  await db.$executeRaw`
    UPDATE usage_counters
    SET count = GREATEST(count - 1, 0)
    WHERE user_id = ${userId}
      AND kind = ${kind}::"UsageKind"
      AND date = ${day}::date
  `;
}

/**
 * Atomically consume one guest IP attempt (limit 5 / hour). Expired windows
 * reset to count=1 with a fresh expiry. Returns the new count, or null if
 * the limit is already reached inside an active window.
 */
export async function tryConsumeGuestRate(
  ipHash: string,
  db: Db = getPrisma(),
): Promise<number | null> {
  const rows = await db.$queryRaw<{ count: number }[]>`
    INSERT INTO guest_rate_limits (ip_hash, count, expires_at)
    VALUES (${ipHash}, 1, now() + interval '1 hour')
    ON CONFLICT (ip_hash) DO UPDATE SET
      count = CASE
        WHEN guest_rate_limits.expires_at <= now() THEN 1
        ELSE guest_rate_limits.count + 1
      END,
      expires_at = CASE
        WHEN guest_rate_limits.expires_at <= now() THEN now() + interval '1 hour'
        ELSE guest_rate_limits.expires_at
      END
    WHERE guest_rate_limits.expires_at <= now() OR guest_rate_limits.count < 5
    RETURNING count
  `;
  return rows[0]?.count ?? null;
}

const GUEST_POOL_LOCK = "astrology-guest-pool";

/**
 * Run `fn` under a Postgres transaction advisory lock so guest-pool COUNT +
 * insert cannot race. Never use FOR UPDATE on the aggregate itself.
 */
export async function withGuestPoolLock<T>(
  fn: (tx: Tx) => Promise<T>,
  db: Db = getPrisma(),
): Promise<T> {
  return db.$transaction(async (tx) => {
    await tx.$executeRaw`SELECT pg_advisory_xact_lock(hashtext(${GUEST_POOL_LOCK}))`;
    return fn(tx);
  });
}

/** Non-expired guest sessions currently occupying the pool. */
export async function countActiveGuestSessions(tx: Tx | Db): Promise<number> {
  const rows = await tx.$queryRaw<{ count: bigint }[]>`
    SELECT COUNT(*)::bigint AS count
    FROM guest_sessions
    WHERE expires_at > now()
  `;
  return Number(rows[0]?.count ?? 0);
}
