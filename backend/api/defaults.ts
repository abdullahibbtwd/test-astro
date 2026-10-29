import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

/** Tracked API defaults (config, catalogue, me template, country outlines). */
const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "defaults");
const identityPath = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../frontend/config/identity.json",
);
const cache = new Map<string, unknown>();

/** Legal/support URLs shared with the mobile identity config. */
function identityLinks(): { privacy: string; terms: string; support: string } {
  if (!fs.existsSync(identityPath))
    return { privacy: "", terms: "", support: "" };
  const identity = JSON.parse(fs.readFileSync(identityPath, "utf8"));
  return {
    privacy: String(identity.links?.privacy ?? ""),
    terms: String(identity.links?.terms ?? ""),
    support: String(identity.links?.support ?? ""),
  };
}

/** Load a tracked default JSON by basename (without .json). */
export function defaults(name: string): any {
  if (!cache.has(name)) {
    const file = path.join(root, `${name}.json`);
    if (!fs.existsSync(file))
      throw new Error(`Missing API default: ${name}.json`);
    let value = JSON.parse(fs.readFileSync(file, "utf8"));
    if (name === "config") {
      value = { ...value, links: { ...value.links, ...identityLinks() } };
    }
    cache.set(name, value);
  }
  return structuredClone(cache.get(name));
}
