/**
 * Store / billing provider abstraction.
 * No real Apple, Google, or RevenueCat network calls in phase 1.
 */

export type PaymentEventType =
  | "renew"
  | "cancel"
  | "refund"
  | "grace"
  | "billing_retry"
  | "restore"
  | "purchase"
  | "expire"
  | "unknown";

export interface NormalizedPaymentEvent {
  /** Provider-stable event id used for idempotency. */
  event_id: string;
  type: PaymentEventType;
  user_id: string | null;
  plan_id: string | null;
  product_id: string | null;
  original_transaction_id: string | null;
  source_store: "apple" | "google" | "fake" | "none";
  status: "active" | "grace" | "expired" | "canceled" | "refunded";
  expires_at: string | null;
  occurred_at: string;
  raw: unknown;
}

export interface OfferProduct {
  product_id: string;
  plan_id: string;
  /** Prices come from the store at runtime — never hard-code currency amounts. */
  price_string: string | null;
  currency_code: string | null;
  title: string | null;
}

export interface PaymentProvider {
  readonly id: "fake" | "revenuecat" | "native" | "unset";
  /** Verify webhook authenticity. Throws or returns false on failure. */
  verifyWebhookSignature(
    headers: Record<string, string | string[] | undefined>,
    rawBody: string | Buffer,
  ): boolean | Promise<boolean>;
  /** Parse provider payload into a normalized event. */
  parseWebhookEvent(
    rawBody: string | Buffer,
    headers?: Record<string, string | string[] | undefined>,
  ): NormalizedPaymentEvent | Promise<NormalizedPaymentEvent>;
  /** Dev/test helper: list catalog product ids (no live store). */
  listProducts(): Promise<OfferProduct[]>;
}

export class ProviderNotConfiguredError extends Error {
  constructor(provider: string) {
    super(
      `Payment provider "${provider}" is a stub until the owner chooses and configures it.`,
    );
    this.name = "ProviderNotConfiguredError";
  }
}
