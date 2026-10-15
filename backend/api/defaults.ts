import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

/** Tracked API defaults (config, catalogue, me template, country outlines). */
const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "defaults");
const cache = new Map<string, unknown>();

/** Load a tracked default JSON by basename (without .json). */
export function defaults(name: string): any {
  if (!cache.has(name)) {
    const file = path.join(root, `${name}.json`);
    if (!fs.existsSync(file))
      throw new Error(`Missing API default: ${name}.json`);
    cache.set(name, JSON.parse(fs.readFileSync(file, "utf8")));
  }
  return structuredClone(cache.get(name));
}
