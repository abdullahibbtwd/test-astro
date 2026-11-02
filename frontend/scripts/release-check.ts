import fs from "node:fs";
import path from "node:path";
import { findPendingAstrologerMarkers } from "../src/features/step3/placeholders";

const root = process.cwd();
const identity = JSON.parse(
  fs.readFileSync(path.join(root, "config/identity.json"), "utf8"),
);
const en = JSON.parse(
  fs.readFileSync(path.join(root, "src/i18n/en.json"), "utf8"),
);
const tr = JSON.parse(
  fs.readFileSync(path.join(root, "src/i18n/tr.json"), "utf8"),
);
const failures: string[] = [];

/** Step 3 unfinished-copy markers must be gone before a store release. */
function scanPendingAstrologer(dir: string, rel = ""): void {
  for (const name of fs.readdirSync(dir)) {
    if (name === "node_modules" || name === "artifacts" || name.startsWith("."))
      continue;
    const full = path.join(dir, name);
    const next = rel ? `${rel}/${name}` : name;
    const stat = fs.statSync(full);
    if (stat.isDirectory()) {
      scanPendingAstrologer(full, next);
      continue;
    }
    if (!/\.(tsx?|jsx?|json)$/.test(name)) continue;
    // release-check.ts only documents the gate; skip self-matches on this file.
    if (next.replace(/\\/g, "/").endsWith("scripts/release-check.ts")) continue;
    const text = fs.readFileSync(full, "utf8");
    const hits = findPendingAstrologerMarkers(text);
    if (hits.length)
      failures.push(
        `${next} still contains Step 3 pending-astrologer copy (${hits.join(", ")}) — replace before release.`,
      );
  }
}
scanPendingAstrologer(path.join(root, "src"));
scanPendingAstrologer(path.join(root, "app"));

if (/draft/i.test(String(identity.consentVersion ?? "")))
  failures.push(
    "config/identity.json consentVersion is still a draft — set the final consent version string.",
  );
if (/example/i.test(String(identity.androidPackage ?? "")))
  failures.push(
    "config/identity.json androidPackage is still a placeholder (contains 'example').",
  );
if (/example/i.test(String(identity.iosBundleIdentifier ?? "")))
  failures.push(
    "config/identity.json iosBundleIdentifier is still a placeholder (contains 'example').",
  );
if (/-dev$/i.test(String(identity.scheme ?? "")) || /\.dev$/i.test(String(identity.scheme ?? "")))
  failures.push(
    "config/identity.json scheme still looks like a development scheme — set the production URL scheme.",
  );
for (const kind of ["privacy", "terms", "support"] as const) {
  if (!String(identity.links?.[kind] ?? "").trim())
    failures.push(
      `config/identity.json links.${kind} is empty — set the public legal/support URL.`,
    );
}
for (const [lang, table] of [
  ["en", en],
  ["tr", tr],
] as const) {
  const text = String(table["consent.birthData"] ?? "");
  if (!text.trim())
    failures.push(`${lang}.json consent.birthData is missing.`);
  else if (/draft|taslak/i.test(text))
    failures.push(
      `${lang}.json consent.birthData is still draft legal copy — replace with reviewed text.`,
    );
}

if (failures.length) {
  console.error(failures.join("\n"));
  process.exit(1);
}
console.log("release:check ok");
