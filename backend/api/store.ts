import { AsyncLocalStorage } from "node:async_hooks";
import type { Prisma, PrismaClient, SessionKind } from "../src/generated/prisma/client.js";
import { disconnectPrisma, prisma as getPrisma } from "./db";

/** System tenant holds sessions and auth-mode; never user chart data. */
export const SYSTEM_TENANT = "__system__";
/** Fallback tenant for unit tests that do not set a request user. */
export const DEFAULT_TENANT = "__default__";

const tenantAls = new AsyncLocalStorage<string>();

export type StoreTarget =
  | string
  | { databaseUrl: string }
  | { sqlite: string };

/**
 * Per-tenant JSON store on Postgres via Prisma.
 * User tenants → Record rows (FK to User).
 * SYSTEM_TENANT → SystemConfig + Session (access/refresh credentials).
 */
export class Store {
  private db: PrismaClient;
  private closed = false;

  private constructor(db: PrismaClient) {
    this.db = db;
  }

  static async open(target: StoreTarget): Promise<Store> {
    if (typeof target === "object" && "sqlite" in target)
      throw new Error("SQLite store removed; set DATABASE_URL");
    if (typeof target === "string" && (target === ":memory:" || target.endsWith(".sqlite")))
      throw new Error("SQLite store removed; set DATABASE_URL");
    if (typeof target === "object" && "databaseUrl" in target)
      process.env.DATABASE_URL = target.databaseUrl;
    else if (typeof target === "string" && target.startsWith("postgres"))
      process.env.DATABASE_URL = target;
    else if (!process.env.DATABASE_URL)
      throw new Error("DATABASE_URL is required");
    return new Store(getPrisma());
  }

  runAs<T>(tenantId: string, fn: () => T): T {
    return tenantAls.run(tenantId, fn);
  }

  async runAsAsync<T>(tenantId: string, fn: () => Promise<T>): Promise<T> {
    return tenantAls.run(tenantId, fn);
  }

  tenant(): string {
    return tenantAls.getStore() ?? DEFAULT_TENANT;
  }

  async get<T = any>(key: string): Promise<T | undefined> {
    const tenant = this.tenant();
    if (tenant === SYSTEM_TENANT) return this.getSystem(key);
    const row = await this.db.record.findUnique({
      where: { tenantId_key: { tenantId: tenant, key } },
    });
    return row ? (row.value as T) : undefined;
  }

  async put(key: string, value: unknown): Promise<void> {
    const tenant = this.tenant();
    if (tenant === SYSTEM_TENANT) {
      await this.putSystem(key, value);
      return;
    }
    await this.db.record.upsert({
      where: { tenantId_key: { tenantId: tenant, key } },
      create: { tenantId: tenant, key, value: value as Prisma.InputJsonValue },
      update: { value: value as Prisma.InputJsonValue },
    });
  }

  async remove(key: string): Promise<void> {
    const tenant = this.tenant();
    if (tenant === SYSTEM_TENANT) {
      await this.removeSystem(key);
      return;
    }
    await this.db.record
      .delete({ where: { tenantId_key: { tenantId: tenant, key } } })
      .catch(() => undefined);
  }

  async list<T = any>(prefix: string): Promise<T[]> {
    const tenant = this.tenant();
    if (tenant === SYSTEM_TENANT) {
      if (prefix === "guest:" || prefix.startsWith("guest")) return [];
      const rows = await this.db.systemConfig.findMany({
        where: { key: { startsWith: prefix } },
        orderBy: { key: "asc" },
      });
      return rows.map((r) => r.value as T);
    }
    const rows = await this.db.record.findMany({
      where: { tenantId: tenant, key: { startsWith: prefix } },
      orderBy: { key: "asc" },
    });
    return rows.map((r) => r.value as T);
  }

  async transaction<T>(fn: () => Promise<T>): Promise<T> {
    return this.db.$transaction(async (tx) => {
      const previous = this.db;
      this.db = tx as unknown as PrismaClient;
      try {
        return await fn();
      } finally {
        this.db = previous;
      }
    });
  }

  /** Delete all keys for the current tenant only (not sessions/system). */
  async clear(): Promise<void> {
    const tenant = this.tenant();
    if (tenant === SYSTEM_TENANT) {
      await this.db.session.deleteMany({});
      await this.db.systemConfig.deleteMany({});
      return;
    }
    await this.db.record.deleteMany({ where: { tenantId: tenant } });
  }

  async close(): Promise<void> {
    // Shared Prisma client — disconnect once from API shutdown via disconnectPrisma().
    this.closed = true;
  }

  private parseCredentialKey(key: string): {
    kind: SessionKind;
    tokenHash: string;
  } | null {
    // access:<hash> | refresh:<hash> | supabase:<scope>:access:<hash>
    const parts = key.split(":");
    const kindPart = parts.at(-2);
    const hash = parts.at(-1);
    if (!hash || (kindPart !== "access" && kindPart !== "refresh")) return null;
    return {
      kind: kindPart === "access" ? "ACCESS" : "REFRESH",
      tokenHash: hash,
    };
  }

  private async getSystem<T>(key: string): Promise<T | undefined> {
    const cred = this.parseCredentialKey(key);
    if (cred) {
      const row = await this.db.session.findUnique({
        where: { tokenHash: cred.tokenHash },
      });
      if (!row || row.kind !== cred.kind) return undefined;
      if (row.kind === "ACCESS")
        return { expires: row.expiresAt.getTime(), owner: row.userId } as T;
      // accessTokenHash stores the full access credential key (or its digest).
      return {
        expires: row.expiresAt.getTime(),
        owner: row.userId,
        accessKey: row.accessTokenHash ?? undefined,
        accessHash: row.accessTokenHash?.split(":").at(-1),
      } as T;
    }
    const row = await this.db.systemConfig.findUnique({ where: { key } });
    return row ? (row.value as T) : undefined;
  }

  private async putSystem(key: string, value: unknown): Promise<void> {
    const cred = this.parseCredentialKey(key);
    if (cred) {
      const body = value as {
        expires: number;
        owner: string;
        accessKey?: string;
        accessHash?: string;
      };
      await this.db.session.upsert({
        where: { tokenHash: cred.tokenHash },
        create: {
          userId: body.owner,
          kind: cred.kind,
          tokenHash: cred.tokenHash,
          expiresAt: new Date(body.expires),
          accessTokenHash: body.accessKey ?? body.accessHash ?? null,
        },
        update: {
          userId: body.owner,
          expiresAt: new Date(body.expires),
          accessTokenHash: body.accessKey ?? body.accessHash ?? null,
        },
      });
      return;
    }
    await this.db.systemConfig.upsert({
      where: { key },
      create: { key, value: value as Prisma.InputJsonValue },
      update: { value: value as Prisma.InputJsonValue },
    });
  }

  private async removeSystem(key: string): Promise<void> {
    const cred = this.parseCredentialKey(key);
    if (cred) {
      await this.db.session
        .delete({ where: { tokenHash: cred.tokenHash } })
        .catch(() => undefined);
      return;
    }
    await this.db.systemConfig
      .delete({ where: { key } })
      .catch(() => undefined);
  }
}
