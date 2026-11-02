import { View } from "react-native";
import { Txt } from "../../design/components";
import {
  PENDING_ASTROLOGER_BANNER_TEST_ID,
  PENDING_ASTROLOGER_MARK,
} from "./placeholders";

/** High-visibility unfinished-content banner — must not ship in release. */
export function PendingAstrologerBanner({ detail }: { detail: string }) {
  return (
    <View
      testID={PENDING_ASTROLOGER_BANNER_TEST_ID}
      accessibilityRole="alert"
      style={{
        backgroundColor: "#B00020",
        paddingVertical: 10,
        paddingHorizontal: 12,
        borderRadius: 8,
        gap: 4,
      }}
    >
      <Txt kind="caption" style={{ color: "#FFFFFF", fontWeight: "700" }}>
        Unfinished — {PENDING_ASTROLOGER_MARK}
      </Txt>
      <Txt kind="caption" style={{ color: "#FFFFFF" }}>
        {detail}
      </Txt>
    </View>
  );
}
