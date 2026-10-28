import { createHash } from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { Store, DEFAULT_TENANT } from "../api/store";
import { prisma } from "../api/db";

/** Shared throwaway DB for the Node test suite (never the live `astrology` DB). */
export const TEST_DATABASE_URL =
  process.env.DATABASE_URL ??
  "postgres://astrology:astrology@127.0.0.1:5432/astrology_test";

process.env.DATABASE_URL = TEST_DATABASE_URL;
process.env.ASTRO_DEMO_AUTH ??= "1";

/** Record.tenant_id FK requires a User row for unit-test DEFAULT_TENANT writes. */
async function ensureDefaultTenantUser(): Promise<void> {
  await prisma().user.upsert({
    where: { id: DEFAULT_TENANT },
    create: { id: DEFAULT_TENANT, displayName: "Default test tenant" },
    update: {},
  });
}

export async function openStore(): Promise<Store> {
  await ensureDefaultTenantUser();
  // Shared Postgres replaces per-test :memory: DBs — wipe default-tenant KV so
  // job/unit tests do not see leftover ready/pending rows from earlier cases.
  await prisma().record.deleteMany({ where: { tenantId: DEFAULT_TENANT } });
  return Store.open({ databaseUrl: TEST_DATABASE_URL });
}

/** Sticky auth-mode in system_config breaks later demo suites on shared Postgres. */
export async function clearAuthMode(): Promise<void> {
  await prisma().systemConfig.deleteMany({ where: { key: "auth-mode" } });
}

/** Shared-DB leftover Ask/profile/guest counters make later suites hit 429. */
export async function clearUsageCounters(userId?: string): Promise<void> {
  await prisma().usageCounter.deleteMany(
    userId ? { where: { userId } } : undefined,
  );
  await prisma().guestRateLimit.deleteMany({});
}

/** Stable demo login id: sha256 of the trimmed, lowercased email. */
export function demoTenantId(email = "demo@example.com"): string {
  return createHash("sha256").update(email.trim().toLowerCase()).digest("hex");
}

/**
 * Drop one demo login's KV rows and deletion tombstone.
 * openStore() only clears DEFAULT_TENANT, so demo@example.com otherwise
 * keeps jobs, profiles, and a self id from earlier cases on astrology_test.
 */
export async function wipeDemoTenant(email = "demo@example.com"): Promise<void> {
  const tenantId = demoTenantId(email);
  await prisma().record.deleteMany({ where: { tenantId } });
  await prisma().usageCounter.deleteMany({ where: { userId: tenantId } });
  await prisma().deletedUser.deleteMany({ where: { id: tenantId } });
}

/** Temp folder for map-products / dossier paths; Store itself uses DATABASE_URL. */
export function tempDataDir(prefix = "astro-test-"): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

export function dataDbPath(dir: string): string {
  return path.join(dir, "app.sqlite");
}

/**
 * Generators in job tests park on a Promise and assign `finish = resolve`.
 * Postgres scheduling can leave `finish` unset when the test continues; wait
 * until the generator registers, then return that resolver once.
 */
export async function waitFinish(
  get: () => ((value?: any) => void) | undefined,
): Promise<(value?: any) => void> {
  for (let i = 0; i < 200; i++) {
    const fn = get();
    if (fn) return fn;
    await new Promise((r) => setImmediate(r));
  }
  throw new Error("generator did not register finish");
}

/**
 * Mirror production guest-pool scoping (app.ts): guest KV lives under tenant
 * `guest-pool` so it does not collide with the account store on shared Postgres.
 */
export async function openGuestScopedStore(): Promise<{
  store: Store;
  guest: Store;
}> {
  await prisma().user.upsert({
    where: { id: "guest-pool" },
    create: { id: "guest-pool", displayName: "Guest pool" },
    update: {},
  });
  await prisma().record.deleteMany({ where: { tenantId: "guest-pool" } });
  await prisma().guestSession.deleteMany({}).catch(() => undefined);
  await clearUsageCounters();
  const store = await openStore();
  const guestTenant = "guest-pool";
  const guest = {
    get: <T = any>(key: string) =>
      store.runAsAsync(guestTenant, () => store.get<T>(key)),
    put: (key: string, value: unknown) =>
      store.runAsAsync(guestTenant, () => store.put(key, value)),
    remove: (key: string) =>
      store.runAsAsync(guestTenant, () => store.remove(key)),
    list: <T = any>(prefix: string) =>
      store.runAsAsync(guestTenant, () => store.list<T>(prefix)),
    transaction: <T>(fn: () => Promise<T>) =>
      store.runAsAsync(guestTenant, () => store.transaction(fn)),
    clear: () => store.runAsAsync(guestTenant, () => store.clear()),
    close: () => store.close(),
    runAs: store.runAs.bind(store),
    runAsAsync: store.runAsAsync.bind(store),
    tenant: () => guestTenant,
  } as unknown as Store;
  return { store, guest };
}
