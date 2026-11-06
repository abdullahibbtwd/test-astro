import {
  ProviderNotConfiguredError,
  type NormalizedPaymentEvent,
  type OfferProduct,
  type PaymentProvider,
} from "./types";

/**
 * Stub for native App Store Server Notifications / Play RTDN.
 * No StoreKit / Play Billing SDKs until the owner chooses native IAP.
 */
export class NativeStubProvider implements PaymentProvider {
  readonly id = "native" as const;

  verifyWebhookSignature(): boolean {
    throw new ProviderNotConfiguredError("native");
  }

  parseWebhookEvent(): NormalizedPaymentEvent {
    throw new ProviderNotConfiguredError("native");
  }

  async listProducts(): Promise<OfferProduct[]> {
    throw new ProviderNotConfiguredError("native");
  }
}
