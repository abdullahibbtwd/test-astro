/** Decide whether MapCanvas shows the country-outline preview or a provider style. */
export type BasemapMode = "preview" | "provider" | "loading";

export function resolveBasemap(opts: {
  styleUrl?: string | null;
  online: boolean;
  stylePending: boolean;
  hasStyle: boolean;
}): BasemapMode {
  const url = opts.styleUrl?.trim();
  if (!url) return "preview";
  if (!opts.online) return "preview";
  if (opts.stylePending) return "loading";
  if (opts.hasStyle) return "provider";
  return "preview";
}
