import { space as dsSpace, radius as dsRadius } from "../../design-system/theme/tokens";
import { View } from "react-native";
import { Txt } from ".";
import { bandColor } from "../bands";
import { useTheme } from "../theme";
export function BandChip({
  band,
  label,
  compact = false,
}: {
  band: string;
  label: string;
  compact?: boolean;
}) {
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
        alignSelf: compact ? "stretch" : "flex-start",
        maxWidth: "100%",
        flexDirection: "row",
        alignItems: "center",
        gap: dsSpace[1],
        borderRadius: dsRadius.md,
        paddingHorizontal: compact ? dsSpace[1] : dsSpace[2],
        paddingVertical: compact ? 2 : dsSpace[1],
        backgroundColor: bandColor(band, c.dark) + (compact ? "18" : "25"),
        minHeight: compact ? 22 : undefined,
      }}
    >
      <Txt
        kind="caption"
        numberOfLines={1}
        adjustsFontSizeToFit
        minimumFontScale={0.75}
        style={{ flexShrink: 1, flexGrow: compact ? 1 : 0 }}
      >
        {shape} {label}
      </Txt>
    </View>
  );
}
