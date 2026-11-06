/**
 * Mobile payment provider abstraction.
 * Prices must come from the store at runtime — never hard-code amounts.
 * No native SDKs until the owner chooses RevenueCat or native IAP.
 */

export interface StoreProduct {
  productId: string;
  planId: string;
  /** Localized price from the store SDK (null in FakeProvider). */
  priceString: string | null;
  currencyCode: string | null;
  title: string | null;
}

export interface PurchaseResult {
  productId: string;
  originalTransactionId: string;
  expiresAt: string | null;
}

export interface PaymentProvider {
  readonly id: "fake" | "revenuecat" | "native" | "unset";
  initialize(): Promise<void>;
  getProducts(planProductIds: string[]): Promise<StoreProduct[]>;
  purchase(productId: string): Promise<PurchaseResult>;
  restore(): Promise<PurchaseResult[]>;
  /** Deep-link / manage URL when available; null for Fake. */
  manageSubscriptionsUrl(): string | null;
}

export class ProviderNotConfiguredError extends Error {
  constructor(provider: string) {
    super(
      `Payment provider "${provider}" is not configured. Owner must choose RevenueCat or native IAP.`,
    );
    this.name = "ProviderNotConfiguredError";
  }
}
