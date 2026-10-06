import { useCapabilities } from "./capabilities";
import { useConfig } from "../api/hooks";
const defaults: Record<string, boolean> = {
  askAstrology: true,
  solarReturn: true,
  familyCompatibility: true,
  compatibilityScore: false,
  elementNotes: false,
  dayScoreNumbers: true,
  homeEnergyTile: false,
};
export function useFlags() {
  const config = useConfig();
  const unavailable = useCapabilities((s) => s.unavailable);
  return {
    ...defaults,
    ...config.data?.flags,
    ...Object.fromEntries(Object.keys(unavailable).map((k) => [k, false])),
  };
}
