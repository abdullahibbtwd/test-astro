import { FakeProvider } from "./fake-provider";
import { NativeStubProvider } from "./native-stub";
import { RevenueCatStubProvider } from "./revenuecat-stub";
import type { PaymentProvider } from "./types";

export * from "./types";
export { FakeProvider } from "./fake-provider";
export { RevenueCatStubProvider } from "./revenuecat-stub";
export { NativeStubProvider } from "./native-stub";

export type MobileProviderChoice = "unset" | "fake" | "revenuecat" | "native";

/** Resolve mobile provider. Default Fake until owner sets EXPO_PUBLIC_PAYMENT_PROVIDER. */
export function getPaymentProvider(
  choice?: MobileProviderChoice,
): PaymentProvider {
  const selected =
    choice ??
    (process.env.EXPO_PUBLIC_PAYMENT_PROVIDER as MobileProviderChoice | undefined) ??
    "fake";
  if (selected === "revenuecat") return new RevenueCatStubProvider();
  if (selected === "native") return new NativeStubProvider();
  return new FakeProvider();
}
