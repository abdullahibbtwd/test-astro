import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export type PaymentProviderChoice = "unset" | "revenuecat" | "native";

export type FeatureId = "ask" | "family" | "reports" | "map" | (string & {});

export type DailyLimitKey =
  | "ask"
  | "natal_reading"
  | "map_reading"
  | "forecast_reading"
  | "compat_reading";

export interface FeatureCatalogEntry {
  id: string;
  description?: string;
  /** null = owner undecided → ungated until set. */
  premium: boolean | null;
}

export interface PlanDefinition {
  id: string;
  name: string;
  display_name_en: string;
  display_name_tr: string;
  store_product_ids: { apple: string; google: string };
  features: string[];
  daily_limits: Record<DailyLimitKey, number | null>;
}

export interface PlansConfig {
  version: number;
  provider: PaymentProviderChoice;
  free_launch: { entitle_all: boolean; description?: string };
  feature_catalog: Record<string, FeatureCatalogEntry>;
  plans: PlanDefinition[];
  default_plan_id: string;
  notes?: string[];
}

const CONFIG_PATH = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../config/plans.json",
);

let cached: PlansConfig | null = null;

/** Load repo-root `config/plans.json` (cached). */
export function loadPlansConfig(force = false): PlansConfig {
  if (!force && cached) return structuredClone(cached);
  if (!fs.existsSync(CONFIG_PATH))
    throw new Error(`Missing plans config: ${CONFIG_PATH}`);
  const parsed = JSON.parse(fs.readFileSync(CONFIG_PATH, "utf8")) as PlansConfig;
  cached = parsed;
  return structuredClone(parsed);
}

/** Clear cache (tests). */
export function resetPlansConfigCache(): void {
  cached = null;
}

export function getPlan(
  planId: string,
  config: PlansConfig = loadPlansConfig(),
): PlanDefinition {
  const plan = config.plans.find((p) => p.id === planId);
  if (plan) return plan;
  const fallback = config.plans.find((p) => p.id === config.default_plan_id);
  if (!fallback)
    throw new Error(
      `plans.json missing default plan "${config.default_plan_id}"`,
    );
  return fallback;
}

/**
 * Free-launch entitle-all: env wins when set (`1`/`0`/`true`/`false`),
 * otherwise plans.json `free_launch.entitle_all`.
 */
export function freeLaunchEntitleAll(
  config: PlansConfig = loadPlansConfig(),
  env: NodeJS.ProcessEnv = process.env,
): boolean {
  const raw = env.ASTRO_FREE_LAUNCH_ENTITLE_ALL;
  if (raw === "1" || raw === "true") return true;
  if (raw === "0" || raw === "false") return false;
  return Boolean(config.free_launch?.entitle_all);
}

export function planIdForProduct(
  productId: string,
  store: "apple" | "google",
  config: PlansConfig = loadPlansConfig(),
): string | null {
  if (!productId) return null;
  for (const plan of config.plans) {
    if (plan.store_product_ids?.[store] === productId) return plan.id;
  }
  return null;
}
