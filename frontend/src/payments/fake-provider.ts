import type {
  PaymentProvider,
  PurchaseResult,
  StoreProduct,
} from "./types";

/** Dev/test provider — no store SDK, prices stay null. */
export class FakeProvider implements PaymentProvider {
  readonly id = "fake" as const;
  private owned: PurchaseResult[] = [];

  async initialize(): Promise<void> {}

  async getProducts(planProductIds: string[]): Promise<StoreProduct[]> {
    return planProductIds.filter(Boolean).map((productId) => ({
      productId,
      planId: productId.includes("premium") ? "premium" : "unknown",
      priceString: null,
      currencyCode: null,
      title: productId,
    }));
  }

  async purchase(productId: string): Promise<PurchaseResult> {
    const result: PurchaseResult = {
      productId,
      originalTransactionId: `fake-mobile-${productId}-${Date.now()}`,
      expiresAt: new Date(Date.now() + 30 * 86400000).toISOString(),
    };
    this.owned = [result];
    return result;
  }

  async restore(): Promise<PurchaseResult[]> {
    return [...this.owned];
  }

  manageSubscriptionsUrl(): string | null {
    return null;
  }
}
