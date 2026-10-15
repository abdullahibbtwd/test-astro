import { useMemo } from "react";
import { SvgXml } from "react-native-svg";
import { ornaments } from "../glyphs/glyphs";
import type { ThemeColors } from "../theme/tokens";
import { useTheme } from "../ThemeProvider";
export type OrnamentProps = {
  name: "emblem" | "chartWheel" | "divider" | "cardCorner";
  width: number;
  color?: keyof ThemeColors;
};
export function Ornament({ name, width, color = "accent" }: OrnamentProps) {
  const { colors } = useTheme();
  const xml = useMemo(
    () => ornaments[name].replaceAll("__SURFACE__", colors.surface),
    [name, colors.surface],
  );
  const ratio = name === "emblem" ? 420 / 360 : name === "divider" ? 1 / 10 : 1;
  return (
    <SvgXml
      xml={xml}
      color={colors[color]}
      width={width}
      height={width * ratio}
      accessible={false}
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    />
  );
}
export const Emblem = (props: Omit<OrnamentProps, "name">) => (
  <Ornament {...props} name="emblem" />
);
export const ChartWheel = (props: Omit<OrnamentProps, "name">) => (
  <Ornament {...props} name="chartWheel" />
);
export const Divider = (props: Omit<OrnamentProps, "name">) => (
  <Ornament {...props} name="divider" />
);
