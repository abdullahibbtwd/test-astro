import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const identity = JSON.parse(
  fs.readFileSync(path.join(root, "config/identity.json"), "utf8"),
);

/** Keep in sync with src/api/api-base.ts assertProductionApiUrl (plain JS for Expo config). */
function assertProductionApiUrl(value) {
  const configured = String(value ?? "").trim();
  if (!configured) {
    throw new Error(
      "EXPO_PUBLIC_API_URL is empty. Set the production API https URL in EAS environment variables before building the production profile.",
    );
  }
  if (/^http:/i.test(configured)) {
    throw new Error(
      `EXPO_PUBLIC_API_URL must be https for production (got http): ${configured}`,
    );
  }
  if (/sslip\.io/i.test(configured)) {
    throw new Error(
      `EXPO_PUBLIC_API_URL must not use sslip.io for production (got ${configured}). Set the final API domain in EAS env.`,
    );
  }
  if (!/^https:/i.test(configured)) {
    throw new Error(
      `EXPO_PUBLIC_API_URL must be an https URL for production (got ${configured}).`,
    );
  }
  return configured;
}

/**
 * Single source of truth for Android package + deep-link scheme:
 * `config/identity.json` → this file → Expo prebuild (gradle applicationId,
 * AndroidManifest intent-filters) and runtime `src/config/identity.ts`.
 *
 * Do not hard-code package/scheme in gradle, manifests, or scripts.
 */
export default ({ config }) => {
  const profile = process.env.EAS_BUILD_PROFILE ?? "";
  // Production EAS builds fail fast if the API base is missing or unsafe.
  if (profile === "production") {
    assertProductionApiUrl(process.env.EXPO_PUBLIC_API_URL);
  }

  const googleIosScheme = process.env.GOOGLE_IOS_URL_SCHEME;
  return {
    ...config,
    name: identity.name,
    slug: identity.slug,
    scheme: identity.scheme,
    ios: {
      ...(config.ios ?? {}),
      bundleIdentifier: identity.iosBundleIdentifier,
    },
    android: {
      ...(config.android ?? {}),
      package: identity.androidPackage,
      intentFilters: [
        {
          action: "VIEW",
          category: ["BROWSABLE", "DEFAULT"],
          data: [{ scheme: identity.scheme }],
        },
      ],
    },
    plugins: [
      ...(config.plugins ?? []),
      ...(googleIosScheme
        ? [
            [
              "@react-native-google-signin/google-signin",
              { iosUrlScheme: googleIosScheme },
            ],
          ]
        : []),
    ],
  };
};
