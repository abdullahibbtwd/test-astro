import type { PrismaClient } from "../src/generated/prisma/client.js";
import { prisma as getPrisma } from "./db";

/** Delete expired auth sessions, guest sessions, and guest rate-limit rows. */
export async function cleanupExpired(
  db: PrismaClient = getPrisma(),
): Promise<{ sessions: number; guestSessions: number; guestRateLimits: number }> {
  const now = new Date();
  const [sessions, guestSessions, guestRateLimits] = await Promise.all([
    db.session.deleteMany({ where: { expiresAt: { lte: now } } }),
    db.guestSession.deleteMany({ where: { expiresAt: { lte: now } } }),
    db.guestRateLimit.deleteMany({ where: { expiresAt: { lte: now } } }),
  ]);
  return {
    sessions: sessions.count,
    guestSessions: guestSessions.count,
    guestRateLimits: guestRateLimits.count,
  };
}

/**
 * Periodically purge expired rows. Returns a stop function.
 * Call from API startup (e.g. app.ts) and clear on shutdown.
 */
export function startCleanupTimer(
  intervalMs = 60_000,
  db: PrismaClient = getPrisma(),
): () => void {
  const tick = () => {
    void cleanupExpired(db).catch(() => {});
  };
  tick();
  const timer = setInterval(tick, intervalMs);
  (timer as unknown as { unref?: () => void }).unref?.();
  return () => clearInterval(timer);
}
