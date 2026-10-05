import { Pressable } from "react-native";
import { AppText } from "../text/AppText";
import { useTheme } from "../ThemeProvider";
import { size as sizes, radius, space, opacity } from "../theme/tokens";
export type ButtonProps = {
  variant?: "primary" | "outline" | "ghost";
  size?: "lg" | "md";
  onPress: () => void;
  disabled?: boolean;
  children: string;
  lang?: "tr" | "en";
};
export function Button({
  variant = "primary",
  size = "lg",
  onPress,
  disabled,
  children,
  lang,
}: ButtonProps) {
  const { colors } = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: !!disabled }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => ({
        minHeight: size === "lg" ? sizes.buttonLg : sizes.buttonMd,
        width: "100%",
        paddingHorizontal: size === "lg" ? space[6] : space[4],
        paddingVertical: space[2],
        borderRadius: radius.md,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: variant === "primary" ? colors.primary : undefined,
        borderWidth: variant === "outline" ? sizes.controlBorder : 0,
        borderColor: pressed ? colors.accent : colors.borderControl,
        opacity: disabled
          ? opacity.disabled
          : pressed && variant === "primary"
            ? 0.88
            : 1,
      })}
    >
      <AppText
        variant="button"
        color={variant === "primary" ? "onPrimary" : "accent"}
        align="center"
        lang={lang}
      >
        {children}
      </AppText>
    </Pressable>
  );
}
