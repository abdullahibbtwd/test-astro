import type { PrismaClient } from "../../src/generated/prisma/client.js";
import { syncUserEntitlementsJson, computeEntitlements } from "../entitlements";
import { loadPlansConfig } from "../plans";
import type { NormalizedPaymentEvent } from "./types";

export type ApplyResult =
  | { applied: true; subscription_id: string | null }
  | {
      applied: false;
      reason:
        | "duplicate"
        | "missing_user"
        | "missing_event_id"
        | "unknown_type"
        | "stale_or_future";
    };

/** Reject events older/newer than this window (replay / clock skew). */
export const WEBHOOK_TIMESTAMP_TOLERANCE_MS = 15 * 60_000;

const KNOWN_TYPES = new Set([
  "purchase",
  "renew",
  "restore",
  "grace",
  "billing_retry",
  "cancel",
  "refund",
  "expire",
]);

function statusForEvent(
  event: NormalizedPaymentEvent,
): "active" | "grace" | "expired" | "canceled" | "refunded" | null {
  switch (event.type) {
    case "purchase":
    case "renew":
    case "restore":
      return event.status === "grace" ? "grace" : "active";
    case "grace":
    case "billing_retry":
      return "grace";
    case "cancel":
      return "canceled";
    case "refund":
      return "refunded";
    case "expire":
      return "expired";
    default:
      return null;
  }
}

export function webhookTimestampFresh(
  occurredAt: string,
  now = Date.now(),
  toleranceMs = WEBHOOK_TIMESTAMP_TOLERANCE_MS,
): boolean {
  const ts = Date.parse(occurredAt);
  if (!Number.isFinite(ts)) return false;
  return Math.abs(now - ts) <= toleranceMs;
}

/**
 * Apply a normalized payment event exactly once (idempotent on event_id).
 * Same event twice must not double-apply subscription mutations.
 */
export async function applyPaymentEvent(
  db: PrismaClient,
  providerId: string,
  event: NormalizedPaymentEvent,
): Promise<ApplyResult> {
  if (!event.event_id) return { applied: false, reason: "missing_event_id" };

  const existing = await db.paymentEvent.findUnique({
    where: { id: event.event_id },
  });
  if (existing) return { applied: false, reason: "duplicate" };

  if (!KNOWN_TYPES.has(event.type) || event.type === "unknown") {
    try {
      await db.paymentEvent.create({
        data: {
          id: event.event_id,
          provider: providerId,
          type: event.type || "unknown",
          userId: event.user_id,
          payload: event.raw as object,
        },
      });
    } catch {
      return { applied: false, reason: "duplicate" };
    }
    return { applied: false, reason: "unknown_type" };
  }

  if (!webhookTimestampFresh(event.occurred_at)) {
    try {
      await db.paymentEvent.create({
        data: {
          id: event.event_id,
          provider: providerId,
          type: event.type,
          userId: event.user_id,
          payload: event.raw as object,
        },
      });
    } catch {
      return { applied: false, reason: "duplicate" };
    }
    return { applied: false, reason: "stale_or_future" };
  }

  if (!event.user_id) {
    await db.paymentEvent.create({
      data: {
        id: event.event_id,
        provider: providerId,
        type: event.type,
        userId: null,
        payload: event.raw as object,
      },
    });
    return { applied: false, reason: "missing_user" };
  }

  const user = await db.user.findUnique({ where: { id: event.user_id } });
  if (!user) {
    await db.paymentEvent.create({
      data: {
        id: event.event_id,
        provider: providerId,
        type: event.type,
        userId: event.user_id,
        payload: event.raw as object,
      },
    });
    return { applied: false, reason: "missing_user" };
  }

  const config = loadPlansConfig();
  const planId =
    event.plan_id ||
    (event.product_id
      ? config.plans.find(
          (p) =>
            p.store_product_ids.apple === event.product_id ||
            p.store_product_ids.google === event.product_id ||
            `fake.${p.id}` === event.product_id,
        )?.id
      : null) ||
    "premium";

  const status = statusForEvent(event);
  if (!status) return { applied: false, reason: "unknown_type" };
  const expiresAt = event.expires_at ? new Date(event.expires_at) : null;
  const txn = event.original_transaction_id;

  let subscriptionId: string | null = null;

  try {
    await db.$transaction(async (tx) => {
      await tx.paymentEvent.create({
        data: {
          id: event.event_id,
          provider: providerId,
          type: event.type,
          userId: event.user_id,
          payload: event.raw as object,
        },
      });

      if (txn) {
        const row = await tx.subscription.upsert({
          where: {
            sourceStore_originalTransactionId: {
              sourceStore: event.source_store,
              originalTransactionId: txn,
            },
          },
          create: {
            userId: event.user_id!,
            planId,
            status,
            expiresAt,
            sourceStore: event.source_store,
            originalTransactionId: txn,
            productId: event.product_id,
          },
          update: {
            userId: event.user_id!,
            planId,
            status,
            expiresAt,
            productId: event.product_id,
          },
        });
        subscriptionId = row.id;
      } else {
        const latest = await tx.subscription.findFirst({
          where: { userId: event.user_id! },
          orderBy: { updatedAt: "desc" },
        });
        if (latest) {
          const row = await tx.subscription.update({
            where: { id: latest.id },
            data: {
              planId,
              status,
              expiresAt,
              productId: event.product_id,
            },
          });
          subscriptionId = row.id;
        } else {
          const row = await tx.subscription.create({
            data: {
              userId: event.user_id!,
              planId,
              status,
              expiresAt,
              sourceStore: event.source_store,
              originalTransactionId: null,
              productId: event.product_id,
            },
          });
          subscriptionId = row.id;
        }
      }
    });
  } catch {
    // Concurrent duplicate delivery: primary key on payment_events.id.
    const raced = await db.paymentEvent.findUnique({
      where: { id: event.event_id },
    });
    if (raced) return { applied: false, reason: "duplicate" };
    throw Object.assign(new Error("Payment event apply failed"), {
      statusCode: 503,
    });
  }

  const computed = await computeEntitlements(db, event.user_id);
  await syncUserEntitlementsJson(db, event.user_id, computed);

  return { applied: true, subscription_id: subscriptionId };
}
