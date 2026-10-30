import { useCapabilities } from "./capabilities";
import { useConfig } from "../api/hooks";
/** Safe until GET /meta/config arrives — match server keep-off for unfinished surfaces. */
export const flagDefaults: Record<string, boolean> = {
  askAstrology: false,
  solarReturn: false,
  familyCompatibility: false,
  compatibilityScore: false,
  elementNotes: false,
  regionOutlines: false,
  dayScoreNumbers: true,
  homeEnergyTile: false,
};
const defaults = flagDefaults;
export function useFlags() {
  const config = useConfig();
  const unavailable = useCapabilities((s) => s.unavailable);
  return {
    ...defaults,
    ...config.data?.flags,
    ...Object.fromEntries(Object.keys(unavailable).map((k) => [k, false])),
  };
}
