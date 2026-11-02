import { View } from "react-native";
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
  const types: FamilyRelationshipType[] = [
    "romantic",
    "parent_child",
    "sibling",
  ];
  return (
    <Screen back title="Family Compatibility">
      <PendingAstrologerBanner detail={FAMILY_COMPATIBILITY_PLACEHOLDER} />
      <Txt kind="caption">Person A</Txt>
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
      <Txt kind="caption">Person B</Txt>
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
      <Txt kind="caption">Relationship type</Txt>
      <Choices>
        {types.map((value) => (
          <Chip
            key={value}
            label={value}
            selected={relationshipType === value}
            onPress={() => onRelationshipType(value)}
          />
        ))}
      </Choices>
      <Button
        label="Compute aspects"
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
            Math: {model.math.aspects} · {model.relationship_type} ·{" "}
            {model.profile_a_label} × {model.profile_b_label}
          </Txt>
          <Txt kind="title">Aspects</Txt>
          {model.aspects.length === 0 ? (
            <Txt muted>No aspects in selection (family rules pending).</Txt>
          ) : (
            model.aspects.map((row) => (
              <View
                key={`${row.a_point}-${row.type}-${row.b_point}`}
                testID={`aspect-${row.a_point}-${row.b_point}`}
              >
                <Txt>
                  {row.a_point} {row.type} {row.b_point} · orb{" "}
                  {row.orb.toFixed(3)}° ·{" "}
                  {row.applying ? "applying" : "separating"}
                </Txt>
              </View>
            ))
          )}
          <Txt kind="title">Interpretation</Txt>
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
