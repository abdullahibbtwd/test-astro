import identityJson from "../../config/identity.json";

export type AppIdentity = {
  name: string;
  slug: string;
  scheme: string;
  iosBundleIdentifier: string;
  androidPackage: string;
  /** Stored on Me.consents.birth_data.version when the user accepts. */
  consentVersion: string;
  links: {
    privacy: string;
    terms: string;
    support: string;
  };
};

export const identity = identityJson as AppIdentity;

/** Prefer API meta config links; fall back to identity.json. */
export function legalUrl(
  kind: keyof AppIdentity["links"],
  fromApi?: string | null,
): string {
  const api = fromApi?.trim();
  if (api) return api;
  return identity.links[kind]?.trim() ?? "";
}
