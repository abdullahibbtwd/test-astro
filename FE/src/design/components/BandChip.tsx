import { View } from "react-native";
import { Txt } from ".";
import { bandColor } from "../bands";
import { useTheme } from "../theme";
export function BandChip({ band, label }: { band: string; label: string }) {
  const c = useTheme();
  const shape = ["strongly_supportive", "excellent"].includes(band)
    ? "▲▲"
    : ["supportive", "favorable", "good"].includes(band)
      ? "▲"
      : band === "mixed"
        ? "◆"
        : ["challenging", "strongly_challenging", "avoid"].includes(band)
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
        gap: 4,
        borderRadius: 12,
        paddingHorizontal: 8,
        paddingVertical: 4,
        backgroundColor: bandColor(band, c.bg === "#1A2030") + "25",
      }}
    >
      <Txt kind="caption" style={{ flexShrink: 1 }}>
        {shape} {label}
      </Txt>
    </View>
  );
}
