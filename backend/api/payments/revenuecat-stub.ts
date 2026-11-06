import {
  ProviderNotConfiguredError,
  type NormalizedPaymentEvent,
  type OfferProduct,
  type PaymentProvider,
} from "./types";

/**
 * Stub until the owner chooses RevenueCat and supplies project keys/webhook auth.
 * Does not call RevenueCat APIs or embed secrets.
 */
export class RevenueCatStubProvider implements PaymentProvider {
  readonly id = "revenuecat" as const;

  verifyWebhookSignature(): boolean {
    throw new ProviderNotConfiguredError("revenuecat");
  }

  parseWebhookEvent(): NormalizedPaymentEvent {
    throw new ProviderNotConfiguredError("revenuecat");
  }

  async listProducts(): Promise<OfferProduct[]> {
    throw new ProviderNotConfiguredError("revenuecat");
  }
}
