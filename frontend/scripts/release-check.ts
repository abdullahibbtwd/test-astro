import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { findPendingAstrologerMarkers } from "../src/features/step3/placeholders";
import { assertProductionApiUrl } from "../src/api/api-base";

const root = process.cwd();
const identity = JSON.parse(
  fs.readFileSync(path.join(root, "config/identity.json"), "utf8"),
);
const eas = JSON.parse(fs.readFileSync(path.join(root, "eas.json"), "utf8"));
const en = JSON.parse(
  fs.readFileSync(path.join(root, "src/i18n/en.json"), "utf8"),
);
const tr = JSON.parse(
  fs.readFileSync(path.join(root, "src/i18n/tr.json"), "utf8"),
);
const failures: string[] = [];
const blocked: string[] = [];

function fail(msg: string) {
  failures.push(msg);
}
function block(msg: string) {
  blocked.push(msg);
  failures.push(`[BLOCKED] ${msg}`);
}

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
      fail(
        `${next} still contains Step 3 pending-astrologer copy (${hits.join(", ")}) — replace before release.`,
      );
  }
}
scanPendingAstrologer(path.join(root, "src"));
scanPendingAstrologer(path.join(root, "app"));

// --- Identity (owner must supply; agent must not guess) ---
if (/draft/i.test(String(identity.consentVersion ?? "")))
  block(
    "config/identity.json consentVersion is still a draft — set the final consent version string.",
  );
if (/example/i.test(String(identity.androidPackage ?? "")))
  block(
    "final Android package name missing: config/identity.json androidPackage is still a placeholder (contains 'example').",
  );
if (/example/i.test(String(identity.iosBundleIdentifier ?? "")))
  block(
    "final iOS bundle id missing: config/identity.json iosBundleIdentifier is still a placeholder (contains 'example').",
  );
if (
  /-dev$/i.test(String(identity.scheme ?? "")) ||
  /\.dev$/i.test(String(identity.scheme ?? "")) ||
  /example/i.test(String(identity.scheme ?? ""))
)
  block(
    "final URL scheme missing: config/identity.json scheme still looks like a development scheme.",
  );
for (const kind of ["privacy", "terms", "support"] as const) {
  if (!String(identity.links?.[kind] ?? "").trim())
    block(
      `config/identity.json links.${kind} is empty — set the public legal/support URL.`,
    );
}

for (const [lang, table] of [
  ["en", en],
  ["tr", tr],
] as const) {
  const text = String(table["consent.birthData"] ?? "");
  if (!text.trim()) fail(`${lang}.json consent.birthData is missing.`);
  else if (/draft|taslak/i.test(text))
    block(
      `${lang}.json consent.birthData is still draft legal copy — replace with reviewed text.`,
    );
}

// --- EAS profile shape ---
const profiles = eas?.build ?? {};
for (const name of ["development", "preview", "production"] as const) {
  if (!profiles[name]) fail(`eas.json missing build profile "${name}".`);
}
if (profiles.preview?.android?.buildType !== "apk")
  fail('eas.json preview.android.buildType must be "apk".');
if (profiles.production?.android?.buildType !== "app-bundle")
  fail('eas.json production.android.buildType must be "app-bundle".');
const prodInc =
  profiles.production?.android?.autoIncrement ?? profiles.production?.autoIncrement;
if (!(prodInc === true || prodInc === "versionCode"))
  fail(
    'eas.json production must auto-increment versionCode (autoIncrement: "versionCode" or true).',
  );
for (const name of ["development", "preview", "production"] as const) {
  const p = profiles[name];
  if (!p) continue;
  if (p.node !== "22.14.0")
    fail(`eas.json ${name}.node must be pinned to "22.14.0" (got ${JSON.stringify(p.node)}).`);
  if (p.android?.image !== "sdk-57")
    fail(`eas.json ${name}.android.image must be "sdk-57".`);
  if (p.android?.ndk !== "27.1.12297006")
    fail(`eas.json ${name}.android.ndk must be "27.1.12297006".`);
  // No baked API hosts in eas.json — values belong in EAS project env.
  const envBlock = p.env ?? {};
  for (const [key, val] of Object.entries(envBlock)) {
    if (key === "EXPO_PUBLIC_API_URL")
      fail(
        `eas.json ${name}.env embeds EXPO_PUBLIC_API_URL — move it to EAS environment variables (value was ${JSON.stringify(val)}).`,
      );
    if (typeof val === "string" && /sslip\.io/i.test(val))
      fail(`eas.json ${name}.env contains sslip.io — remove it.`);
  }
}

// --- Production API URL when present in the local/CI env ---
const apiUrl = process.env.EXPO_PUBLIC_API_URL;
if (process.env.EAS_BUILD_PROFILE === "production" || process.env.RELEASE_CHECK_STRICT === "1") {
  try {
    assertProductionApiUrl(apiUrl);
  } catch (err) {
    block(err instanceof Error ? err.message : String(err));
  }
} else if (apiUrl?.trim()) {
  if (/sslip\.io/i.test(apiUrl) || /^http:/i.test(apiUrl.trim())) {
    block(
      `EXPO_PUBLIC_API_URL in the current environment is not production-safe (${apiUrl.trim()}). Set the final https API domain in EAS production env (and locally when RELEASE_CHECK_STRICT=1).`,
    );
  }
} else {
  block(
    "final API domain missing: EXPO_PUBLIC_API_URL is unset. Set it in EAS env for preview/production (https, no sslip.io for production).",
  );
}

// --- Map style URLs live on the API host; identity.json holds owner attestation ---
for (const kind of ["light", "dark"] as const) {
  const url = String(identity.mapStyleUrls?.[kind] ?? "").trim();
  if (!url) {
    block(
      `map style URL missing: config/identity.json mapStyleUrls.${kind} (owner attestation). Also set ASTRO_MAP_STYLE_${kind.toUpperCase()} on the API/Coolify host.`,
    );
  } else if (!/^https:/i.test(url) || /sslip\.io/i.test(url)) {
    block(
      `map style URL invalid: config/identity.json mapStyleUrls.${kind} must be https and not sslip.io.`,
    );
  }
}

// --- Secrets / keystores must not be tracked by git ---
try {
  const tracked = execFileSync(
    "git",
    [
      "-C",
      root,
      "ls-files",
      "*.jks",
      "*.keystore",
      "credentials.json",
      "**/local.properties",
    ],
    { encoding: "utf8" },
  )
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
  for (const file of tracked) {
    fail(
      `Git tracks signing/SDK secret material at ${file} — remove from the index (never commit keystores or local.properties).`,
    );
  }
} catch {
  // Outside a git work tree: skip tracked-file probe.
}
if (fs.existsSync(path.join(root, "credentials.json")))
  fail(
    "credentials.json present at frontend root — do not commit; EAS remote credentials are preferred.",
  );

// --- Hardening plugin present ---
const appJson = JSON.parse(fs.readFileSync(path.join(root, "app.json"), "utf8"));
const plugins: unknown[] = appJson?.expo?.plugins ?? [];
const hasHardening = plugins.some(
  (p) =>
    p === "./plugins/withAndroidReleaseHardening.js" ||
    (Array.isArray(p) && p[0] === "./plugins/withAndroidReleaseHardening.js"),
);
if (!hasHardening)
  fail("app.json must register ./plugins/withAndroidReleaseHardening.js");

if (failures.length) {
  console.error("release:check FAILED\n");
  console.error(failures.join("\n"));
  if (blocked.length) {
    console.error("\n--- BLOCKED (owner inputs required; agent must not guess) ---");
    console.error(blocked.map((b) => `• ${b}`).join("\n"));
  }
  process.exit(1);
}
console.log("release:check ok");
