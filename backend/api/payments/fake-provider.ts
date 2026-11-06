import { createHmac, timingSafeEqual } from "node:crypto";
import type {
  NormalizedPaymentEvent,
  OfferProduct,
  PaymentEventType,
  PaymentProvider,
} from "./types";
import { loadPlansConfig } from "../plans";

/**
 * Dev/test provider. Signs webhooks with HMAC-SHA256 of the raw body using
 * ASTRO_FAKE_PAYMENT_WEBHOOK_SECRET (default: "fake-webhook-secret" in tests).
 * Header: `x-fake-signature: <hex>`.
 */
export class FakeProvider implements PaymentProvider {
  readonly id = "fake" as const;

  constructor(
    private secret = process.env.ASTRO_FAKE_PAYMENT_WEBHOOK_SECRET ||
      "fake-webhook-secret",
  ) {}

  sign(rawBody: string | Buffer): string {
    return createHmac("sha256", this.secret)
      .update(typeof rawBody === "string" ? rawBody : rawBody)
      .digest("hex");
  }

  verifyWebhookSignature(
    headers: Record<string, string | string[] | undefined>,
    rawBody: string | Buffer,
  ): boolean {
    const header = headers["x-fake-signature"];
    const provided = Array.isArray(header) ? header[0] : header;
    if (!provided) return false;
    const expected = this.sign(rawBody);
    try {
      const a = Buffer.from(provided, "hex");
      const b = Buffer.from(expected, "hex");
      return a.length === b.length && timingSafeEqual(a, b);
    } catch {
      return false;
    }
  }

  parseWebhookEvent(rawBody: string | Buffer): NormalizedPaymentEvent {
    const text = typeof rawBody === "string" ? rawBody : rawBody.toString("utf8");
    const body = JSON.parse(text) as Record<string, unknown>;
    const type = String(body.type ?? "unknown") as PaymentEventType;
    return {
      event_id: String(body.event_id ?? ""),
      type: type || "unknown",
      user_id: body.user_id == null ? null : String(body.user_id),
      plan_id: body.plan_id == null ? null : String(body.plan_id),
      product_id: body.product_id == null ? null : String(body.product_id),
      original_transaction_id:
        body.original_transaction_id == null
          ? null
          : String(body.original_transaction_id),
      source_store: "fake",
      status: (body.status as NormalizedPaymentEvent["status"]) ?? "active",
      expires_at: body.expires_at == null ? null : String(body.expires_at),
      occurred_at: String(body.occurred_at ?? new Date().toISOString()),
      raw: body,
    };
  }

  async listProducts(): Promise<OfferProduct[]> {
    const config = loadPlansConfig();
    return config.plans
      .filter((p) => p.id !== config.default_plan_id)
      .map((p) => ({
        product_id:
          p.store_product_ids.apple ||
          p.store_product_ids.google ||
          `fake.${p.id}`,
        plan_id: p.id,
        price_string: null,
        currency_code: null,
        title: p.display_name_en || p.name || p.id,
      }));
  }
}

/** Sample FakeProvider webhook payloads (tests + docs). */
export function fakeSamplePayloads(): Record<string, object> {
  const base = {
    user_id: "user-test-1",
    plan_id: "premium",
    product_id: "fake.premium",
    original_transaction_id: "fake-txn-1",
    occurred_at: "2026-11-06T12:00:00.000Z",
  };
  return {
    purchase: {
      event_id: "fake-evt-purchase-1",
      type: "purchase",
      status: "active",
      expires_at: "2026-12-06T12:00:00.000Z",
      ...base,
    },
    renew: {
      event_id: "fake-evt-renew-1",
      type: "renew",
      status: "active",
      expires_at: "2027-01-06T12:00:00.000Z",
      ...base,
    },
    cancel: {
      event_id: "fake-evt-cancel-1",
      type: "cancel",
      status: "canceled",
      expires_at: "2026-12-06T12:00:00.000Z",
      ...base,
    },
    refund: {
      event_id: "fake-evt-refund-1",
      type: "refund",
      status: "refunded",
      expires_at: "2026-11-06T12:00:00.000Z",
      ...base,
    },
    grace: {
      event_id: "fake-evt-grace-1",
      type: "grace",
      status: "grace",
      expires_at: "2026-12-13T12:00:00.000Z",
      ...base,
    },
    billing_retry: {
      event_id: "fake-evt-retry-1",
      type: "billing_retry",
      status: "grace",
      expires_at: "2026-12-13T12:00:00.000Z",
      ...base,
    },
    restore: {
      event_id: "fake-evt-restore-1",
      type: "restore",
      status: "active",
      expires_at: "2026-12-06T12:00:00.000Z",
      ...base,
    },
    expire: {
      event_id: "fake-evt-expire-1",
      type: "expire",
      status: "expired",
      expires_at: "2026-11-06T12:00:00.000Z",
      ...base,
    },
  };
}
