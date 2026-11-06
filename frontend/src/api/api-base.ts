/**
 * Resolve the API base URL. Dev may fall back to the local mock; release
 * builds must set EXPO_PUBLIC_API_URL or fail visibly (never silently hit
 * 127.0.0.1:4010). Production EAS builds additionally reject http:// and
 * sslip.io via assertProductionApiUrl (called from app.config.js).
 */

export function assertProductionApiUrl(
  value: string | undefined | null,
): string {
  const configured = value?.trim() ?? "";
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

export function resolveApiBase(
  env: { EXPO_PUBLIC_API_URL?: string | undefined } | NodeJS.ProcessEnv = process
    .env,
  options: { isDev?: boolean } = {},
): string {
  const configured = env.EXPO_PUBLIC_API_URL?.trim();
  const isDev =
    options.isDev ??
    (typeof __DEV__ !== "undefined"
      ? __DEV__
      : process.env.NODE_ENV !== "production");

  if (configured) {
    // Defense in depth for store binaries: never ship http/sslip when Metro
    // bundled with EAS_BUILD_PROFILE=production (Expo inlines EXPO_PUBLIC_* only,
    // so the hard gate is app.config.js; this catches mis-bundled values).
    if (
      !isDev &&
      (process.env.EAS_BUILD_PROFILE === "production" ||
        process.env.EXPO_PUBLIC_EAS_BUILD_PROFILE === "production")
    ) {
      return assertProductionApiUrl(configured);
    }
    return configured;
  }

  if (isDev) return "http://127.0.0.1:4010/v1";
  throw new Error(
    "EXPO_PUBLIC_API_URL is missing. Set it in EAS project env for this build profile.",
  );
}

export const apiBase = resolveApiBase();
