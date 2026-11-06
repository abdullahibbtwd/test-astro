import { View } from "react-native";
import { space as dsSpace } from "../../design-system/theme/tokens";
import { ReadingSection } from "../profiles/ReadingScreen";
import { CompatibilityScoreLine } from "./CompatibilityScoreLine";
import type { Compatibility } from "../../../contracts/spec-types";

/** Payload from GeneratedPart ready state (status already gated by <Generated>). */
type ReadyReadingContent = Omit<
  Extract<Compatibility["reading"], { status: "ready" }>,
  "status"
>;

/** Reading sections + optional score line (hidden when score absent / flag off). */
export function CompatibilityReadingBody({
  reading,
  score,
  scoreEnabled,
}: {
  reading: ReadyReadingContent;
  score: Compatibility["score"];
  scoreEnabled: boolean;
}) {
  return (
    <>
      {reading.sections.map((section, index) => (
        <View key={section.key} style={{ gap: dsSpace[4] }}>
          <ReadingSection section={section} initialExpanded={index === 0} />
          {index === 0 && (
            <CompatibilityScoreLine enabled={scoreEnabled} score={score} />
          )}
        </View>
      ))}
    </>
  );
}
