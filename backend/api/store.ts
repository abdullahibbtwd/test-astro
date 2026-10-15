import { AsyncLocalStorage } from "node:async_hooks";
import { DatabaseSync } from "node:sqlite";
import fs from "node:fs";
import path from "node:path";
import pg from "pg";

/** System tenant holds sessions and auth-mode; never user chart data. */
export const SYSTEM_TENANT = "__system__";
/** Fallback tenant for unit tests that do not set a request user. */
export const DEFAULT_TENANT = "__default__";

type PgQuerier = {
  query: (
    text: string,
    params?: unknown[],
  ) => Promise<{ rows: Record<string, unknown>[] }>;
};

type Backend =
  | { kind: "sqlite"; db: DatabaseSync }
  | { kind: "postgres"; pool: pg.Pool; querier: PgQuerier };

const tenantAls = new AsyncLocalStorage<string>();

export type StoreTarget =
  | string
  | { databaseUrl: string }
  | { sqlite: string };

/**
 * Per-tenant JSON KV. Keys are isolated by tenant_id (auth subject or demo user id).
 * SQLite remains available for in-process tests; Postgres is used when DATABASE_URL is set.
 */
export class Store {
  private backend: Backend;
  private closed = false;

  private constructor(backend: Backend) {
    this.backend = backend;
  }

  static async open(target: StoreTarget): Promise<Store> {
    if (typeof target === "object" && "databaseUrl" in target) {
      const pool = new pg.Pool({
        connectionString: target.databaseUrl,
        max: 10,
      });
      await pool.query(`
        CREATE TABLE IF NOT EXISTS records (
          tenant_id TEXT NOT NULL,
          key TEXT NOT NULL,
          value TEXT NOT NULL,
          PRIMARY KEY (tenant_id, key)
        )
      `);
      return new Store({ kind: "postgres", pool, querier: pool });
    }
    const filename =
      typeof target === "string" ? target : target.sqlite;
    if (filename !== ":memory:") {
      fs.mkdirSync(path.dirname(filename), { recursive: true });
    }
    const db = new DatabaseSync(filename);
    db.exec("PRAGMA journal_mode=WAL; PRAGMA secure_delete=ON;");
    const existing = db
      .prepare(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='records'",
      )
      .get() as { name: string } | undefined;
    if (existing) {
      const cols = (
        db.prepare("PRAGMA table_info(records)").all() as { name: string }[]
      ).map((c) => c.name);
      if (cols.length === 2 && cols.includes("key") && cols.includes("value")) {
        db.exec(`
          ALTER TABLE records RENAME TO records_legacy;
          CREATE TABLE records (
            tenant_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (tenant_id, key)
          );
          INSERT INTO records (tenant_id, key, value)
          SELECT '${DEFAULT_TENANT}', key, value FROM records_legacy;
          DROP TABLE records_legacy;
        `);
      }
    } else {
      db.exec(`
        CREATE TABLE records (
          tenant_id TEXT NOT NULL,
          key TEXT NOT NULL,
          value TEXT NOT NULL,
          PRIMARY KEY (tenant_id, key)
        )
      `);
    }
    return new Store({ kind: "sqlite", db });
  }

  /** Run work as a specific tenant (request user or system). */
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
    if (this.backend.kind === "sqlite") {
      const row = this.backend.db
        .prepare(
          "SELECT value FROM records WHERE tenant_id=? AND key=?",
        )
        .get(tenant, key) as { value: string } | undefined;
      return row ? JSON.parse(String(row.value)) : undefined;
    }
    const { rows } = await this.backend.querier.query(
      "SELECT value FROM records WHERE tenant_id=$1 AND key=$2",
      [tenant, key],
    );
    return rows[0] ? JSON.parse(String(rows[0].value)) : undefined;
  }

  async put(key: string, value: unknown): Promise<void> {
    const tenant = this.tenant();
    const payload = JSON.stringify(value);
    if (this.backend.kind === "sqlite") {
      this.backend.db
        .prepare(
          `INSERT INTO records(tenant_id, key, value) VALUES (?,?,?)
           ON CONFLICT(tenant_id, key) DO UPDATE SET value=excluded.value`,
        )
        .run(tenant, key, payload);
      return;
    }
    await this.backend.querier.query(
      `INSERT INTO records(tenant_id, key, value) VALUES ($1,$2,$3)
       ON CONFLICT(tenant_id, key) DO UPDATE SET value=EXCLUDED.value`,
      [tenant, key, payload],
    );
  }

  async remove(key: string): Promise<void> {
    const tenant = this.tenant();
    if (this.backend.kind === "sqlite") {
      this.backend.db
        .prepare("DELETE FROM records WHERE tenant_id=? AND key=?")
        .run(tenant, key);
      return;
    }
    await this.backend.querier.query(
      "DELETE FROM records WHERE tenant_id=$1 AND key=$2",
      [tenant, key],
    );
  }

  async list<T = any>(prefix: string): Promise<T[]> {
    const tenant = this.tenant();
    if (this.backend.kind === "sqlite") {
      return this.backend.db
        .prepare(
          "SELECT value FROM records WHERE tenant_id=? AND substr(key,1,?)=? ORDER BY key",
        )
        .all(tenant, prefix.length, prefix)
        .map((r) => JSON.parse(String((r as { value: string }).value)));
    }
    const { rows } = await this.backend.querier.query(
      "SELECT value FROM records WHERE tenant_id=$1 AND starts_with(key, $2) ORDER BY key",
      [tenant, prefix],
    );
    return rows.map((r) => JSON.parse(String(r.value)));
  }

  async transaction<T>(fn: () => Promise<T>): Promise<T> {
    if (this.backend.kind === "sqlite") {
      this.backend.db.exec("BEGIN IMMEDIATE");
      try {
        const result = await fn();
        this.backend.db.exec("COMMIT");
        return result;
      } catch (error) {
        this.backend.db.exec("ROLLBACK");
        throw error;
      }
    }
    const client = await this.backend.pool.connect();
    const previous = this.backend;
    this.backend = {
      kind: "postgres",
      pool: previous.pool,
      querier: client,
    };
    try {
      await client.query("BEGIN");
      try {
        const result = await fn();
        await client.query("COMMIT");
        return result;
      } catch (error) {
        await client.query("ROLLBACK");
        throw error;
      }
    } finally {
      this.backend = previous;
      client.release();
    }
  }

  /** Delete all keys for the current tenant only. */
  async clear(): Promise<void> {
    const tenant = this.tenant();
    if (this.backend.kind === "sqlite") {
      this.backend.db
        .prepare("DELETE FROM records WHERE tenant_id=?")
        .run(tenant);
      this.backend.db.exec("PRAGMA wal_checkpoint(TRUNCATE)");
      return;
    }
    await this.backend.querier.query(
      "DELETE FROM records WHERE tenant_id=$1",
      [tenant],
    );
  }

  async close(): Promise<void> {
    if (this.closed) return;
    this.closed = true;
    if (this.backend.kind === "sqlite") this.backend.db.close();
    else await this.backend.pool.end();
  }
}
