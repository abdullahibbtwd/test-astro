import FamilyCompatibilityScreen, {
  type FamilyAspectsLoader,
} from "../../src/features/compatibility/FamilyCompatibilityScreen";
import { request } from "../../src/api/client";
import type { Compatibility, FamilyRelation } from "../../contracts/spec-types";
import type { SynastryAspectRow } from "../../src/features/step3/math";
import { RouteError as ErrorBoundary } from "../../src/design/components/RouteError";

/** Map skeleton relationship types onto CompatibilityInput.family_relation. */
function toFamilyRelation(
  relationshipType: "romantic" | "parent_child" | "sibling",
): FamilyRelation {
  if (relationshipType === "parent_child") return "parent_child";
  if (relationshipType === "sibling") return "siblings";
  return "other";
}

const loadAspects: FamilyAspectsLoader = async (input) => {
  const result = await request<Compatibility & { aspects?: SynastryAspectRow[] }>(
    "POST",
    "/compatibility",
    "Compatibility",
    {
      profile_a_id: input.profileAId,
      profile_b_id: input.profileBId,
      type: "family",
      family_relation: toFamilyRelation(input.relationshipType),
    },
  );
  return {
    relationship_type: input.relationshipType,
    profile_a_label: input.profileALabel,
    profile_b_label: input.profileBLabel,
    aspects: Array.isArray(result.aspects) ? result.aspects : [],
  };
};

export default function FamilyCompatibilityRoute() {
  return <FamilyCompatibilityScreen loadAspects={loadAspects} />;
}

export { ErrorBoundary };
