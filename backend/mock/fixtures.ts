import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
export const fixtureRoot = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "fixtures",
);
type ManifestEntry = { file: string; schema: string };
let manifest: ManifestEntry[] | undefined;
const cache = new Map<string, unknown>();
function loadManifest(): ManifestEntry[] {
  if (!manifest) {
    const file = path.join(fixtureRoot, "manifest.json");
    if (!fs.existsSync(file))
      throw new Error(
        `Mock fixtures missing (${file}). Extract fixtures/frontend-demo-fixtures.zip first.`,
      );
    manifest = JSON.parse(fs.readFileSync(file, "utf8"));
  }
  return manifest!;
}
export function fixture(name: string): any {
  if (!loadManifest().some((m) => m.file === `${name}.json`)) return undefined;
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
  return loadManifest()
    .filter(
      (m) => m.file.startsWith(prefix) && m.file.endsWith(`.${lang}.json`),
    )
    .map((m) => fixture(m.file.slice(0, -5)));
}
