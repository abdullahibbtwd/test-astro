import type { PrismaClient } from "../src/generated/prisma/client.js";
import type { Problem } from "../../frontend/contracts/spec-types";
import { computeEntitlements } from "./entitlements";
import { problemError } from "./job-problems";
import {
  freeLaunchEntitleAll,
  loadPlansConfig,
  type FeatureId,
  type PlansConfig,
} from "./plans";
import { prisma as getPrisma } from "./db";

export function premiumRequiredProblem(feature: string): Problem {
  return {
    type: "about:blank",
    title: "Premium required",
    status: 403,
    code: "premium_required",
    detail: `Feature "${feature}" requires an active premium plan.`,
  };
}

/**
 * Enforce a feature gate for `userId`.
 * - free launch → always allow
 * - feature.premium === null → ungated (owner undecided)
 * - feature.premium === false → always allow
 * - feature.premium === true → require entitlements[feature] or entitlements.all
 */
export async function requireFeature(
  userId: string,
  feature: FeatureId,
  opts?: {
    db?: PrismaClient;
    config?: PlansConfig;
    env?: NodeJS.ProcessEnv;
    now?: Date;
  },
): Promise<void> {
  const config = opts?.config ?? loadPlansConfig();
  const env = opts?.env ?? process.env;
  if (freeLaunchEntitleAll(config, env)) return;

  const entry = config.feature_catalog?.[feature];
  if (!entry || entry.premium == null || entry.premium === false) return;

  const db = opts?.db ?? getPrisma();
  const computed = await computeEntitlements(db, userId, {
    config,
    env,
    now: opts?.now,
  });
  if (computed.entitlements.all || computed.entitlements[feature]) return;
  throw problemError(premiumRequiredProblem(feature));
}
