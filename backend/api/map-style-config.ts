/**
 * Public MapLibre style URL overrides from env (not secrets).
 * Any access token embedded in the URL is visible to every client.
 */

export const MAP_STYLE_ENV = {
  light: "ASTRO_MAP_STYLE_LIGHT",
  dark: "ASTRO_MAP_STYLE_DARK",
} as const;

export type MapStyleUrls = { light: string; dark: string };

/** Empty / unset is allowed. Non-empty values must be absolute https URLs. */
export function validateMapStyleUrl(
  name: string,
  raw: string | undefined,
): string | null {
  if (raw === undefined || raw.trim() === "") return null;
  const value = raw.trim();
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    return `${name} must be an absolute https URL (got an invalid URL)`;
  }
  if (parsed.protocol !== "https:") {
    return `${name} must use https (got ${parsed.protocol.replace(":", "")})`;
  }
  return null;
}

/** Apply light/dark env overrides onto a Config.map_style_url object. */
export function applyMapStyleEnv(
  mapStyleUrl: MapStyleUrls,
  env: NodeJS.ProcessEnv = process.env,
): MapStyleUrls {
  const light = env.ASTRO_MAP_STYLE_LIGHT?.trim();
  const dark = env.ASTRO_MAP_STYLE_DARK?.trim();
  return {
    light: light || mapStyleUrl.light,
    dark: dark || mapStyleUrl.dark,
  };
}
