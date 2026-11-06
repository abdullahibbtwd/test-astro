import { View } from "react-native";
import { useTranslation } from "react-i18next";
import {
  Screen,
  Txt,
  Button,
  Choices,
  Chip,
  Skeleton,
  ErrorNotice,
} from "../../design/components";
import { PendingAstrologerBanner } from "./PendingAstrologerBanner";
import { FAMILY_COMPATIBILITY_PLACEHOLDER } from "./placeholders";
import type {
  FamilyRelationshipType,
  FamilySkeletonModel,
} from "./math";
import type { SkeletonStatus } from "./SolarReturnSkeleton";

export function FamilyCompatibilitySkeleton({
  profileA,
  profileB,
  profiles,
  onSelectA,
  onSelectB,
  relationshipType,
  onRelationshipType,
  status,
  model,
  error,
  onCompute,
  onRetry,
}: {
  profileA: string;
  profileB: string;
  profiles: { id: string; label: string }[];
  onSelectA: (id: string) => void;
  onSelectB: (id: string) => void;
  relationshipType: FamilyRelationshipType;
  onRelationshipType: (value: FamilyRelationshipType) => void;
  status: SkeletonStatus;
  model: FamilySkeletonModel | null;
  error?: unknown;
  onCompute: () => void;
  onRetry?: () => void;
}) {
  const { t } = useTranslation();
  const types: FamilyRelationshipType[] = [
    "romantic",
    "parent_child",
    "sibling",
  ];
  const typeLabels: Record<FamilyRelationshipType, string> = {
    romantic: t("romantic"),
    parent_child: t("parentChild"),
    sibling: t("sibling"),
  };
  return (
    <Screen back title={t("familyCompatibility")}>
      <PendingAstrologerBanner detail={FAMILY_COMPATIBILITY_PLACEHOLDER} />
      <Txt kind="caption">{t("personA")}</Txt>
      <Choices>
        {profiles.map((p) => (
          <Chip
            key={`a-${p.id}`}
            label={p.label}
            selected={profileA === p.id}
            onPress={() => onSelectA(p.id)}
          />
        ))}
      </Choices>
      <Txt kind="caption">{t("personB")}</Txt>
      <Choices>
        {profiles.map((p) => (
          <Chip
            key={`b-${p.id}`}
            label={p.label}
            selected={profileB === p.id}
            onPress={() => onSelectB(p.id)}
          />
        ))}
      </Choices>
      <Txt kind="caption">{t("relationshipType")}</Txt>
      <Choices>
        {types.map((value) => (
          <Chip
            key={value}
            label={typeLabels[value]}
            selected={relationshipType === value}
            onPress={() => onRelationshipType(value)}
          />
        ))}
      </Choices>
      <Button
        label={t("computeAspects")}
        disabled={!profileA || !profileB || profileA === profileB}
        loading={status === "loading"}
        onPress={onCompute}
      />
      {status === "loading" && (
        <View testID="family-compatibility-loading">
          <Skeleton />
        </View>
      )}
      {status === "ready" && model && (
        <View testID="family-compatibility-ready" style={{ gap: 10 }}>
          <Txt kind="caption">
            {t("math")}: {model.math.aspects} ·{" "}
            {typeLabels[model.relationship_type]} ·{" "}
            {model.profile_a_label} × {model.profile_b_label}
          </Txt>
          <Txt kind="title">{t("aspects")}</Txt>
          {model.aspects.length === 0 ? (
            <Txt muted>{t("noFamilyAspects")}</Txt>
          ) : (
            model.aspects.map((row) => (
              <View
                key={`${row.a_point}-${row.type}-${row.b_point}`}
                testID={`aspect-${row.a_point}-${row.b_point}`}
              >
                <Txt>
                  {row.a_point} {row.type} {row.b_point} · {t("orb")}{" "}
                  {row.orb.toFixed(3)}° ·{" "}
                  {row.applying ? t("applying") : t("separating")}
                </Txt>
              </View>
            ))
          )}
          <Txt kind="title">{t("interpretation")}</Txt>
          <View testID="family-compatibility-placeholder">
            <Txt kind="reading">{model.interpretation}</Txt>
          </View>
        </View>
      )}
      {status === "error" && (
        <View testID="family-compatibility-error">
          <ErrorNotice
            error={error ?? new Error("Family compatibility failed")}
            retry={onRetry}
          />
        </View>
      )}
    </Screen>
  );
}
