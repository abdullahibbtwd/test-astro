/**
 * Compatibility numeric score adapter.
 *
 * Returns null until docs/COMPATIBILITY_SCORING.md records an approved
 * formula_id AND compatibility_score_weights.json is filled. Never invents
 * weights or labels.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export type CompatibilityScore = { value: number; label: string } | null;

type WeightsFile = {
  _meta?: { status?: string };
  formula_id?: string | null;
  scale?: { min?: number; max?: number; label_bands?: unknown[] };
  aspect_type_weights?: { weights?: Record<string, number> };
  planet_pair_weights?: { weights?: Record<string, number> };
  relationship_type_multipliers?: Record<string, number | null>;
};

const WEIGHTS_PATH = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "engine",
  "rules",
  "compatibility_score_weights.json",
);

export function loadCompatibilityScoreWeights(
  filePath = process.env.ASTRO_COMPAT_SCORE_WEIGHTS ?? WEIGHTS_PATH,
): WeightsFile {
  try {
    const raw = fs.readFileSync(filePath, "utf8");
    return JSON.parse(raw) as WeightsFile;
  } catch {
    return { formula_id: null };
  }
}

/** True only when a concrete formula and at least one aspect weight exist. */
export function scoringConfigured(weights: WeightsFile = loadCompatibilityScoreWeights()): boolean {
  if (!weights.formula_id || typeof weights.formula_id !== "string") return false;
  const aspectWeights = weights.aspect_type_weights?.weights ?? {};
  return Object.keys(aspectWeights).length > 0;
}

/**
 * Compute a 0–100 compatibility score, or null when blocked / unconfigured.
 * Callers must keep `compatibilityScore` flag off until this returns non-null
 * in production fixtures.
 */
export function computeCompatibilityScore(_input: {
  type: string;
  aspects?: Array<{ type?: string; a_point?: string; b_point?: string; orb?: number }>;
}): CompatibilityScore {
  const weights = loadCompatibilityScoreWeights();
  if (!scoringConfigured(weights)) return null;
  // Intentionally unimplemented: formula options are BLOCKED in
  // docs/COMPATIBILITY_SCORING.md. Do not invent arithmetic here.
  return null;
}
