import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { useProfiles } from "../../api/hooks";
import { FamilyCompatibilitySkeleton } from "../step3/FamilyCompatibilitySkeleton";
import {
  buildFamilySkeleton,
  type FamilyMathResult,
  type FamilyRelationshipType,
  type FamilySkeletonModel,
} from "../step3/math";
import type { SkeletonStatus } from "../step3/SolarReturnSkeleton";

export type FamilyAspectsLoader = (input: {
  profileAId: string;
  profileBId: string;
  relationshipType: FamilyRelationshipType;
  profileALabel: string;
  profileBLabel: string;
}) => Promise<FamilyMathResult>;

/**
 * Family Compatibility skeleton — wires Phase 3 compute_synastry_aspects
 * through an injectable loader (API / bridge / test mock). Interpretation is
 * always the pending-astrologer placeholder.
 */
export default function FamilyCompatibilityScreen({
  loadAspects,
}: {
  loadAspects?: FamilyAspectsLoader;
}) {
  const { t } = useTranslation(),
    profiles = useProfiles(),
    list =
      profiles.data?.map((p) => ({
        id: p.profile_id,
        label: p.label,
      })) ?? [],
    [a, setA] = useState(""),
    [b, setB] = useState(""),
    [relationshipType, setRelationshipType] =
      useState<FamilyRelationshipType>("romantic"),
    [status, setStatus] = useState<SkeletonStatus>("idle"),
    [model, setModel] = useState<FamilySkeletonModel | null>(null),
    [error, setError] = useState<unknown>();

  const compute = useCallback(async () => {
    if (!a || !b || a === b) return;
    const labelA = list.find((p) => p.id === a)?.label ?? a;
    const labelB = list.find((p) => p.id === b)?.label ?? b;
    setStatus("loading");
    setError(undefined);
    try {
      if (!loadAspects) {
        throw new Error(
          "Family aspects loader missing — wire compute_synastry_aspects",
        );
      }
      const math = await loadAspects({
        profileAId: a,
        profileBId: b,
        relationshipType,
        profileALabel: labelA,
        profileBLabel: labelB,
      });
      setModel(buildFamilySkeleton(math));
      setStatus("ready");
    } catch (err) {
      setError(err);
      setStatus("error");
    }
  }, [a, b, list, loadAspects, relationshipType]);

  return (
    <FamilyCompatibilitySkeleton
      profileA={a}
      profileB={b}
      profiles={list.length ? list : [{ id: "demo-a", label: t("personA") }, { id: "demo-b", label: t("personB") }]}
      onSelectA={setA}
      onSelectB={setB}
      relationshipType={relationshipType}
      onRelationshipType={setRelationshipType}
      status={profiles.isPending && !list.length ? "loading" : status}
      model={model}
      error={error ?? profiles.error}
      onCompute={() => {
        void compute();
      }}
      onRetry={() => {
        void compute();
      }}
    />
  );
}
