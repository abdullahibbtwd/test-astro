import type { PrismaClient } from "../../src/generated/prisma/client.js";
import { syncUserEntitlementsJson, computeEntitlements } from "../entitlements";
import { loadPlansConfig } from "../plans";
import type { NormalizedPaymentEvent } from "./types";

export type ApplyResult =
  | { applied: true; subscription_id: string | null }
  | { applied: false; reason: "duplicate" | "missing_user" | "missing_event_id" };

function statusForEvent(
  event: NormalizedPaymentEvent,
): "active" | "grace" | "expired" | "canceled" | "refunded" {
  if (event.status) return event.status;
  switch (event.type) {
    case "purchase":
    case "renew":
    case "restore":
      return "active";
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
      return "active";
  }
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
  const expiresAt = event.expires_at ? new Date(event.expires_at) : null;
  const txn = event.original_transaction_id;

  let subscriptionId: string | null = null;

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

  const computed = await computeEntitlements(db, event.user_id);
  await syncUserEntitlementsJson(db, event.user_id, computed);

  return { applied: true, subscription_id: subscriptionId };
}
