import { loadPlansConfig, type PaymentProviderChoice } from "../plans";
import { FakeProvider } from "./fake-provider";
import { NativeStubProvider } from "./native-stub";
import { RevenueCatStubProvider } from "./revenuecat-stub";
import type { PaymentProvider } from "./types";

export * from "./types";
export { FakeProvider, fakeSamplePayloads } from "./fake-provider";
export { RevenueCatStubProvider } from "./revenuecat-stub";
export { NativeStubProvider } from "./native-stub";

/**
 * Resolve the active payment provider.
 * - plans.json `provider: "unset"` → FakeProvider in non-production / when
 *   ASTRO_PAYMENT_PROVIDER=fake (tests/dev).
 * - Explicit ASTRO_PAYMENT_PROVIDER overrides plans.json.
 */
export function getPaymentProvider(
  choice?: PaymentProviderChoice | "fake",
): PaymentProvider {
  const envChoice = process.env.ASTRO_PAYMENT_PROVIDER as
    | PaymentProviderChoice
    | "fake"
    | undefined;
  const fromPlans = loadPlansConfig().provider;
  const selected = choice ?? envChoice ?? fromPlans;

  if (selected === "fake") return new FakeProvider();
  if (selected === "revenuecat") return new RevenueCatStubProvider();
  if (selected === "native") return new NativeStubProvider();

  // unset → Fake for local/test; stub error surface in production until configured.
  if (process.env.NODE_ENV === "production" && process.env.ASTRO_PAYMENT_PROVIDER !== "fake")
    return new RevenueCatStubProvider(); // surfaces ProviderNotConfiguredError
  return new FakeProvider();
}
