import { Text, type TextProps, type TextStyle } from "react-native";
import { useApp } from "../../lib/state";
import {
  type as textStyles,
  type TypeStyleName,
  type ThemeColors,
} from "../theme/tokens";
import { useTheme } from "../ThemeProvider";
import { upper } from "./upper";
export type AppTextProps = TextProps & {
  variant?: TypeStyleName;
  color?: keyof ThemeColors;
  lang?: "tr" | "en";
  align?: TextStyle["textAlign"];
};
export function AppText({
  variant = "body",
  color = "ink",
  lang,
  align,
  style,
  children,
  ...props
}: AppTextProps) {
  const currentLanguage = useApp((s) => s.language),
    { colors } = useTheme();
  const { uppercase, ...font } = textStyles[variant];
  if (__DEV__ && uppercase && typeof children !== "string")
    console.warn("Uppercase AppText expects string children");
  return (
    <Text
      maxFontSizeMultiplier={variant.startsWith("display") ? 1.2 : 1.5}
      {...props}
      style={[
        font,
        { color: colors[color], textAlign: align, includeFontPadding: false },
        style,
      ]}
    >
      {uppercase && typeof children === "string"
        ? upper(children, lang ?? currentLanguage)
        : children}
    </Text>
  );
}
