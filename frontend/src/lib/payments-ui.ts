/**
 * Payments UI is OFF by default. Enable with EXPO_PUBLIC_PAYMENTS_UI=1
 * or meta config flag `paymentsUi` once the owner is ready.
 */
export function paymentsUiEnvEnabled(
  env: NodeJS.ProcessEnv = process.env,
): boolean {
  return env.EXPO_PUBLIC_PAYMENTS_UI === "1" || env.EXPO_PUBLIC_PAYMENTS_UI === "true";
}
