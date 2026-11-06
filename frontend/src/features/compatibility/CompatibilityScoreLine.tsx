import { AppText } from "../../design-system/text/AppText";
import type { Compatibility } from "../../../contracts/spec-types";

/** True only for a displayable numeric score — never null / empty / NaN. */
export function isPresentCompatibilityScore(
  score: Compatibility["score"],
): score is { value: number; label: string } {
  return (
    !!score &&
    typeof score.value === "number" &&
    Number.isFinite(score.value) &&
    typeof score.label === "string" &&
    score.label.trim().length > 0
  );
}

/**
 * Renders the numeric score only when the launch flag is on AND the API
 * returned a real score. Absent scores show nothing (no "null", "0%", blank box).
 */
export function CompatibilityScoreLine({
  score,
  enabled,
}: {
  score: Compatibility["score"];
  enabled: boolean;
}) {
  if (!enabled || !isPresentCompatibilityScore(score)) return null;
  return (
    <AppText testID="compatibility-score">
      {score.value} / 100 · {score.label}
    </AppText>
  );
}
