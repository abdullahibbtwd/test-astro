import { FakeProvider } from "./fake-provider";
import { NativeStubProvider } from "./native-stub";
import { RevenueCatStubProvider } from "./revenuecat-stub";
import type { PaymentProvider } from "./types";

export * from "./types";
export { FakeProvider } from "./fake-provider";
export { RevenueCatStubProvider } from "./revenuecat-stub";
export { NativeStubProvider } from "./native-stub";

export type MobileProviderChoice = "unset" | "fake" | "revenuecat" | "native";

const providers: Record<Exclude<MobileProviderChoice, "unset">, PaymentProvider> =
  {
    fake: new FakeProvider(),
    revenuecat: new RevenueCatStubProvider(),
    native: new NativeStubProvider(),
  };

/** Resolve mobile provider. Default Fake until owner sets EXPO_PUBLIC_PAYMENT_PROVIDER. */
export function getPaymentProvider(
  choice?: MobileProviderChoice,
): PaymentProvider {
  const selected =
    choice ??
    (process.env.EXPO_PUBLIC_PAYMENT_PROVIDER as MobileProviderChoice | undefined) ??
    "fake";
  return selected === "unset" ? providers.fake : providers[selected];
}
