import { View } from "react-native";
import { AppText } from "../text/AppText";
import { space } from "../theme/tokens";
export function Title({
  children,
  variant = "displayTitle",
  subtitle,
  lang,
}: {
  children: string;
  variant?: "displayHero" | "displayTitle" | "displaySection" | "displayCard";
  subtitle?: string;
  lang?: "tr" | "en";
}) {
  return (
    <View style={{ gap: space[3] }}>
      <AppText
        variant={variant}
        color="accent"
        align="center"
        lang={lang}
        accessibilityRole="header"
        adjustsFontSizeToFit={variant === "displayHero"}
        numberOfLines={variant === "displayHero" ? 1 : undefined}
      >
        {children}
      </AppText>
      {subtitle && (
        <AppText color="inkSoft" align="center" lang={lang}>
          {subtitle}
        </AppText>
      )}
    </View>
  );
}
