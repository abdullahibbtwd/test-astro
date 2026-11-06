/** Decide whether MapCanvas shows the country-outline preview or a provider style. */
export type BasemapMode = "preview" | "provider" | "loading";

export type BasemapReason =
  | "provider"
  | "loading"
  | "empty_style"
  | "offline"
  | "style_failed";

export function resolveBasemap(opts: {
  styleUrl?: string | null;
  online: boolean;
  stylePending: boolean;
  hasStyle: boolean;
}): { mode: BasemapMode; reason: BasemapReason } {
  const url = opts.styleUrl?.trim();
  if (!url) return { mode: "preview", reason: "empty_style" };
  if (!opts.online) return { mode: "preview", reason: "offline" };
  if (opts.stylePending) return { mode: "loading", reason: "loading" };
  if (opts.hasStyle) return { mode: "provider", reason: "provider" };
  return { mode: "preview", reason: "style_failed" };
}
