import { space as dsSpace, radius as dsRadius } from "../../design-system/theme/tokens";
import { AppText } from "../../design-system/text/AppText";
import { Pressable, View } from "react-native";
import { useTheme } from "../theme";
export function Segmented<T extends string>({
  items,
  value,
  onChange,
  accessibilityLabel,
}: {
  items: readonly { value: T; label: string; accessibilityLabel?: string }[];
  value: T;
  onChange: (value: T) => void;
  accessibilityLabel?: string;
}) {
  const c = useTheme();
  return (
    <View
      testID="segmented"
      accessibilityRole="tablist"
      accessibilityLabel={accessibilityLabel}
      style={{
        flexDirection: "row",
        flexWrap: "nowrap",
        width: "100%",
        backgroundColor: c.surfaceAlt,
        borderRadius: dsRadius.md,
      }}
    >
      {items.map((item) => (
        <Pressable
          key={item.value}
          accessibilityRole="tab"
          accessibilityLabel={item.accessibilityLabel ?? item.label}
          accessibilityState={{ selected: value === item.value }}
          onPress={() => onChange(item.value)}
          style={{
            flex: 1,
            minWidth: 0,
            minHeight: 44,
            paddingVertical: dsSpace[1],
            paddingHorizontal: 2,
          }}
        >
          <View
            style={{
              minHeight: 36,
              flex: 1,
              justifyContent: "center",
              borderRadius: 10,
              paddingHorizontal: dsSpace[1],
              backgroundColor: value === item.value ? c.surface : "transparent",
            }}
          >
            <AppText variant="label" maxFontSizeMultiplier={undefined}
              numberOfLines={1}
              adjustsFontSizeToFit
              minimumFontScale={13 / 16}

              style={{
                color: value === item.value ? c.accent : c.ink2,
                textAlign: "center",
              }}
            >
              {item.label}
            </AppText>
          </View>
        </Pressable>
      ))}
    </View>
  );
}
