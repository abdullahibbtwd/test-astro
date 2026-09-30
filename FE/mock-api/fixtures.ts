import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
export const fixtureRoot = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "fixtures",
);
const manifest: { file: string; schema: string }[] = JSON.parse(
  fs.readFileSync(path.join(fixtureRoot, "manifest.json"), "utf8"),
);
const cache = new Map<string, unknown>();
export function fixture(name: string): any {
  if (!manifest.some((m) => m.file === `${name}.json`)) return undefined;
  if (!cache.has(name))
    cache.set(
      name,
      JSON.parse(
        fs.readFileSync(path.join(fixtureRoot, `${name}.json`), "utf8"),
      ),
    );
  return structuredClone(cache.get(name));
}
export function collection(prefix: string, lang: string): any[] {
  return manifest
    .filter(
      (m) => m.file.startsWith(prefix) && m.file.endsWith(`.${lang}.json`),
    )
    .map((m) => fixture(m.file.slice(0, -5)));
}
