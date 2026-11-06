import type { PrismaClient } from "../src/generated/prisma/client.js";
import {
  freeLaunchEntitleAll,
  getPlan,
  loadPlansConfig,
  type PlansConfig,
} from "./plans";

export type SubscriptionStatus =
  | "active"
  | "grace"
  | "expired"
  | "canceled"
  | "refunded";

export type StoreSource = "apple" | "google" | "fake" | "none";

export interface SubscriptionSnapshot {
  plan_id: string;
  status: SubscriptionStatus;
  expires_at: string | null;
  source_store: StoreSource;
  original_transaction_id: string | null;
  product_id: string | null;
}

export interface ComputedEntitlements {
  /** Feature keys granted (and `all` during free launch). Matches Me.entitlements. */
  entitlements: Record<string, true>;
  plan_id: string;
  subscription: SubscriptionSnapshot | null;
  free_launch: boolean;
}

const ENTITLING_STATUSES: ReadonlySet<SubscriptionStatus> = new Set([
  "active",
  "grace",
]);

function isStillValid(
  status: SubscriptionStatus,
  expiresAt: Date | null,
  now: Date,
): boolean {
  if (!ENTITLING_STATUSES.has(status)) return false;
  if (expiresAt && expiresAt.getTime() <= now.getTime()) return false;
  return true;
}

function featuresForPlan(
  planId: string,
  config: PlansConfig,
): Record<string, true> {
  const plan = getPlan(planId, config);
  const out: Record<string, true> = {};
  for (const id of plan.features) out[id] = true;
  return out;
}

function allCatalogFeatures(config: PlansConfig): Record<string, true> {
  const out: Record<string, true> = { all: true };
  for (const id of Object.keys(config.feature_catalog ?? {})) out[id] = true;
  return out;
}

/**
 * Resolve the user's plan + entitlements from Subscription rows and plans.json.
 * Free-launch flag forces `{ all: true, …catalog }` without reading store state
 * for gating, but still returns the latest subscription snapshot when present.
 */
export async function computeEntitlements(
  db: PrismaClient,
  userId: string,
  opts?: { now?: Date; config?: PlansConfig; env?: NodeJS.ProcessEnv },
): Promise<ComputedEntitlements> {
  const config = opts?.config ?? loadPlansConfig();
  const now = opts?.now ?? new Date();
  const freeLaunch = freeLaunchEntitleAll(config, opts?.env ?? process.env);

  const row = await db.subscription.findFirst({
    where: { userId },
    orderBy: [{ updatedAt: "desc" }, { createdAt: "desc" }],
  });

  const subscription: SubscriptionSnapshot | null = row
    ? {
        plan_id: row.planId,
        status: row.status as SubscriptionStatus,
        expires_at: row.expiresAt?.toISOString() ?? null,
        source_store: row.sourceStore as StoreSource,
        original_transaction_id: row.originalTransactionId,
        product_id: row.productId,
      }
    : null;

  if (freeLaunch) {
    return {
      entitlements: allCatalogFeatures(config),
      plan_id: subscription?.plan_id ?? config.default_plan_id,
      subscription,
      free_launch: true,
    };
  }

  const entitled =
    subscription &&
    isStillValid(
      subscription.status,
      row?.expiresAt ?? null,
      now,
    );

  const plan_id = entitled
    ? subscription!.plan_id
    : config.default_plan_id;

  return {
    entitlements: featuresForPlan(plan_id, config),
    plan_id,
    subscription,
    free_launch: false,
  };
}

/** Persist computed entitlements onto User.entitlements (cache for admin/debug). */
export async function syncUserEntitlementsJson(
  db: PrismaClient,
  userId: string,
  computed: ComputedEntitlements,
): Promise<void> {
  await db.user.update({
    where: { id: userId },
    data: {
      entitlements: {
        features: computed.entitlements,
        plan_id: computed.plan_id,
        free_launch: computed.free_launch,
        subscription: computed.subscription,
      } as object,
    },
  });
}

/** Overlay computed feature entitlements onto a Me payload (contract shape). */
export async function withComputedEntitlements<T extends { entitlements: Record<string, true>; user_id: string }>(
  db: PrismaClient,
  me: T,
  opts?: { sync?: boolean; now?: Date },
): Promise<T> {
  const computed = await computeEntitlements(db, me.user_id, { now: opts?.now });
  if (opts?.sync !== false) {
    await syncUserEntitlementsJson(db, me.user_id, computed).catch(() => undefined);
  }
  return { ...me, entitlements: computed.entitlements };
}
