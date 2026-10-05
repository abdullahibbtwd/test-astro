import { space as dsSpace, radius as dsRadius } from "../../design-system/theme/tokens";
import { View } from "react-native";
import { Txt } from ".";
import { bandColor } from "../bands";
import { useTheme } from "../theme";
export function BandChip({ band, label }: { band: string; label: string }) {
  const c = useTheme();
  const shape = ["strongly_supportive", "excellent"].includes(band)
    ? "▲▲"
    : ["supportive", "favorable", "plus", "good"].includes(band)
      ? "▲"
      : band === "mixed"
        ? "◆"
        : ["challenging", "strongly_challenging", "minus", "avoid"].includes(
              band,
            )
          ? "▼"
          : "○";
  return (
    <View
      accessible
      accessibilityLabel={label}
      style={{
        alignSelf: "flex-start",
        maxWidth: "100%",
        flexDirection: "row",
        alignItems: "center",
        gap: dsSpace[1],
        borderRadius: dsRadius.md,
        paddingHorizontal: dsSpace[2],
        paddingVertical: dsSpace[1],
        backgroundColor: bandColor(band, c.dark) + "25",
      }}
    >
      <Txt kind="caption" style={{ flexShrink: 1 }}>
        {shape} {label}
      </Txt>
    </View>
  );
}
