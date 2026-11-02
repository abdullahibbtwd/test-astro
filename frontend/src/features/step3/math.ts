/**
 * Wire Step 3 UI models to Phase 1–3 engine math.
 *
 * Solar Return: find_solar_return_utc + compute_solar_return_chart
 * Family: compute_synastry_aspects(relationship_type)
 *
 * Interpretation text is NOT produced here — placeholders only until the
 * astrologer delivers copy.
 */

import type { ChartData } from "../../../contracts/spec-types";
import {
  FAMILY_COMPATIBILITY_PLACEHOLDER,
  SOLAR_RETURN_PLACEHOLDER,
} from "./placeholders";

export type FamilyRelationshipType = "romantic" | "parent_child" | "sibling";

/** Row shape from backend/engine synastry_aspects.compute_synastry_aspects. */
export interface SynastryAspectRow {
  a_point: string;
  b_point: string;
  type: string;
  scheme: string;
  orb: number;
  separation: number;
  applying: boolean;
}

/** Math output from find_solar_return_utc + compute_solar_return_chart (API-adapted). */
export interface SolarReturnMathResult {
  return_utc: string;
  year: number;
  /** Frontend ChartData (natal wheel shape) derived from the engine chart. */
  chart: ChartData;
  place_label?: string;
}

export interface SolarReturnSkeletonModel extends SolarReturnMathResult {
  interpretation: typeof SOLAR_RETURN_PLACEHOLDER;
  math: {
    moment: "find_solar_return_utc";
    chart: "compute_solar_return_chart";
  };
}

export interface FamilyMathResult {
  relationship_type: FamilyRelationshipType;
  profile_a_label: string;
  profile_b_label: string;
  aspects: SynastryAspectRow[];
}

export interface FamilySkeletonModel extends FamilyMathResult {
  interpretation: typeof FAMILY_COMPATIBILITY_PLACEHOLDER;
  math: {
    aspects: "compute_synastry_aspects";
  };
}

/** Attach the Solar Return placeholder to a Phase 1–2 math result. */
export function buildSolarReturnSkeleton(
  math: SolarReturnMathResult,
): SolarReturnSkeletonModel {
  return {
    ...math,
    interpretation: SOLAR_RETURN_PLACEHOLDER,
    math: {
      moment: "find_solar_return_utc",
      chart: "compute_solar_return_chart",
    },
  };
}

/** Attach the Family placeholder to a Phase 3 aspect-math result. */
export function buildFamilySkeleton(
  math: FamilyMathResult,
): FamilySkeletonModel {
  return {
    ...math,
    interpretation: FAMILY_COMPATIBILITY_PLACEHOLDER,
    math: { aspects: "compute_synastry_aspects" },
  };
}
