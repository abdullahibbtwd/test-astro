import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

/** Runtime data root (SQLite leftovers, dossiers, map-products, auth-config, budget). */
export function dataDir(): string {
  const configured = process.env.DATA_DIR?.trim();
  const root = configured
    ? path.resolve(configured)
    : path.join(path.dirname(fileURLToPath(import.meta.url)), "..", ".local-data");
  fs.mkdirSync(root, { recursive: true });
  return root;
}
