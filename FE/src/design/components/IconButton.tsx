import type { ReactNode } from "react";
import { Pressable, View } from "react-native";
import { useTheme } from "../theme";
export function IconButton({
  icon,
  accessibilityLabel,
  onPress,
  badge,
  disabled = false,
}: {
  icon: ReactNode;
  accessibilityLabel: string;
  onPress: () => void;
  badge?: boolean;
  disabled?: boolean;
}) {
  const c = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => ({
        width: 44,
        height: 44,
        alignItems: "center",
        justifyContent: "center",
        borderRadius: 22,
        opacity: disabled ? 0.4 : pressed ? 0.65 : 1,
      })}
    >
      {icon}
      {badge && (
        <View
          style={{
            position: "absolute",
            right: 6,
            top: 6,
            width: 8,
            height: 8,
            borderRadius: 4,
            backgroundColor: c.accent,
          }}
        />
      )}
    </Pressable>
  );
}
