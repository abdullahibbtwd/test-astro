import { DatabaseSync } from "node:sqlite";
import fs from "node:fs";
import path from "node:path";
/** Single-process private store; every write is atomic and contains only this user's data. */
export class Store {
  private db: DatabaseSync;
  constructor(filename: string) {
    fs.mkdirSync(path.dirname(filename), { recursive: true });
    this.db = new DatabaseSync(filename);
    this.db.exec(
      "PRAGMA journal_mode=WAL; PRAGMA secure_delete=ON; CREATE TABLE IF NOT EXISTS records (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    );
  }
  get<T = any>(key: string): T | undefined {
    const row = this.db
      .prepare("SELECT value FROM records WHERE key=?")
      .get(key);
    return row ? JSON.parse(String(row.value)) : undefined;
  }
  put(key: string, value: unknown) {
    this.db
      .prepare(
        "INSERT INTO records VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
      )
      .run(key, JSON.stringify(value));
  }
  remove(key: string) {
    this.db.prepare("DELETE FROM records WHERE key=?").run(key);
  }
  list<T = any>(prefix: string): T[] {
    return this.db
      .prepare("SELECT value FROM records WHERE substr(key,1,?)=? ORDER BY key")
      .all(prefix.length, prefix)
      .map((r) => JSON.parse(String(r.value)));
  }
  transaction<T>(fn: () => T): T {
    this.db.exec("BEGIN IMMEDIATE");
    try {
      const result = fn();
      this.db.exec("COMMIT");
      return result;
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }
  }
  close() {
    this.db.close();
  }
}
