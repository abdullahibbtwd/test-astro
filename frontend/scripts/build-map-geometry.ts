import { readFileSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath, URL } from "node:url";
const require = createRequire(import.meta.url);
const sourcePath = new URL(
  "../../backend/mock/fixtures/geo-countries.json",
  import.meta.url,
);
const targetPath = new URL(
  "../../backend/mock/fixtures/geo-countries-simple.json",
  import.meta.url,
);
// Shared topology keeps neighbouring countries on the same simplified border.
// keep-shapes retains every country; country properties and the source worldview are unchanged.
execFileSync(
  process.execPath,
  [
    require.resolve("mapshaper/bin/mapshaper"),
    fileURLToPath(sourcePath),
    "-simplify",
    "weighted",
    "12%",
    "keep-shapes",
    "-o",
    fileURLToPath(targetPath),
    "format=geojson",
    "precision=0.001",
    "force",
  ],
  { stdio: "inherit" },
);
const source = JSON.parse(readFileSync(sourcePath, "utf8"));
const result = JSON.parse(readFileSync(targetPath, "utf8"));
if (
  JSON.stringify(
    source.features.map((f: { properties: unknown }) => f.properties),
  ) !==
    JSON.stringify(
      result.features.map((f: { properties: unknown }) => f.properties),
    ) ||
  result.features.some((f: { geometry: unknown }) => !f.geometry)
)
  throw new Error("Country identity or geometry lost during simplification");
const compact = JSON.stringify(result);
if (Buffer.byteLength(compact) > 400_000)
  throw new Error("Country geometry exceeds the 400 KB budget");
writeFileSync(targetPath, compact);
const manifestPath = new URL(
  "../../backend/mock/fixtures/manifest.json",
  import.meta.url,
);
const manifest = JSON.parse(readFileSync(manifestPath, "utf8")) as {
  file: string;
  schema: string;
}[];
if (!manifest.some((item) => item.file === "geo-countries-simple.json"))
  manifest.push({
    file: "geo-countries-simple.json",
    schema: "CountryGeometry",
  });
writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n");
console.info(
  JSON.stringify({
    countries: result.features.length,
    bytes: Buffer.byteLength(compact),
    originalCompactBytes: Buffer.byteLength(JSON.stringify(source)),
  }),
);
