import { useCapabilities } from "./capabilities";
import { useConfig } from "../api/hooks";
import { paymentsUiEnvEnabled } from "./payments-ui";

/** Safe until GET /meta/config arrives — match server keep-off for unfinished surfaces. */
export const flagDefaults: Record<string, boolean> = {
  askAstrology: false,
  solarReturn: false,
  familyCompatibility: false,
  compatibilityScore: false,
  elementNotes: false,
  dayScoreNumbers: true,
  homeEnergyTile: false,
  /** Paywall / subscription management — off until owner enables. */
  paymentsUi: false,
};
const defaults = flagDefaults;
export function useFlags(): Record<string, boolean> {
  const config = useConfig();
  const unavailable = useCapabilities((s) => s.unavailable);
  return {
    ...defaults,
    ...config.data?.flags,
    ...Object.fromEntries(Object.keys(unavailable).map((k) => [k, false])),
    // Env wins so local/dev can flip without backend config.
    ...(paymentsUiEnvEnabled() ? { paymentsUi: true } : {}),
  };
}
export function usePaymentsUiEnabled(): boolean {
  return Boolean(useFlags().paymentsUi);
}
