import fs from "node:fs";
import path from "node:path";

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
