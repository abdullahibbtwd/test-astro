import {
  ProviderNotConfiguredError,
  type PaymentProvider,
  type PurchaseResult,
  type StoreProduct,
} from "./types";

/** Stub — no react-native-iap / StoreKit / Play Billing until owner chooses native. */
export class NativeStubProvider implements PaymentProvider {
  readonly id = "native" as const;

  async initialize(): Promise<void> {
    throw new ProviderNotConfiguredError("native");
  }
  async getProducts(): Promise<StoreProduct[]> {
    throw new ProviderNotConfiguredError("native");
  }
  async purchase(): Promise<PurchaseResult> {
    throw new ProviderNotConfiguredError("native");
  }
  async restore(): Promise<PurchaseResult[]> {
    throw new ProviderNotConfiguredError("native");
  }
  manageSubscriptionsUrl(): string | null {
    return null;
  }
}
