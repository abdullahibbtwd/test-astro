/**
 * Resolve the API base URL. Dev may fall back to the local mock; release
 * builds must set EXPO_PUBLIC_API_URL or fail visibly (never silently hit
 * 127.0.0.1:4010).
 */
export function resolveApiBase(
  env: { EXPO_PUBLIC_API_URL?: string | undefined } | NodeJS.ProcessEnv = process
    .env,
  options: { isDev?: boolean } = {},
): string {
  const configured = env.EXPO_PUBLIC_API_URL?.trim();
  if (configured) return configured;
  const isDev =
    options.isDev ??
    (typeof __DEV__ !== "undefined"
      ? __DEV__
      : process.env.NODE_ENV !== "production");
  if (isDev) return "http://127.0.0.1:4010/v1";
  throw new Error(
    "EXPO_PUBLIC_API_URL is missing. Set it in eas.json or EAS project env for this build profile.",
  );
}

export const apiBase = resolveApiBase();
