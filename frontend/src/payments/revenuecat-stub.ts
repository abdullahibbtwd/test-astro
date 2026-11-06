import {
  ProviderNotConfiguredError,
  type PaymentProvider,
  type PurchaseResult,
  type StoreProduct,
} from "./types";

/** Stub — do not import purchases SDK until owner chooses RevenueCat. */
export class RevenueCatStubProvider implements PaymentProvider {
  readonly id = "revenuecat" as const;

  async initialize(): Promise<void> {
    throw new ProviderNotConfiguredError("revenuecat");
  }
  async getProducts(): Promise<StoreProduct[]> {
    throw new ProviderNotConfiguredError("revenuecat");
  }
  async purchase(): Promise<PurchaseResult> {
    throw new ProviderNotConfiguredError("revenuecat");
  }
  async restore(): Promise<PurchaseResult[]> {
    throw new ProviderNotConfiguredError("revenuecat");
  }
  manageSubscriptionsUrl(): string | null {
    return null;
  }
}
