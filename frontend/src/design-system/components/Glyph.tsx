import Svg, { Path, Circle, Rect } from "react-native-svg";
import {
  glyphs,
  glyphGrid,
  type GlyphSet,
  type GlyphElement,
  type IconName,
  type ZodiacName,
  type PlanetName,
  type MotifName,
} from "../glyphs/glyphs";
import { size as sizes, type ThemeColors } from "../theme/tokens";
import { useTheme } from "../ThemeProvider";
export type GlyphProps = {
  name: IconName | ZodiacName | PlanetName | MotifName;
  set?: GlyphSet;
  size?: number;
  color?: keyof ThemeColors;
  strokeWidth?: number;
  accessibilityLabel?: string;
};
export function Glyph({
  name,
  set,
  size,
  color = "accent",
  strokeWidth,
  accessibilityLabel,
}: GlyphProps) {
  const { colors } = useTheme();
  const group =
    set ??
    (["icons", "zodiac", "planets", "motifs"] as const).find(
      (key) => name in glyphs[key],
    );
  const elements =
    group && (glyphs[group] as Record<string, readonly GlyphElement[]>)[name];
  if (!group || !elements) {
    if (__DEV__) console.warn("Unknown design-system glyph");
    return null;
  }
  const grid = glyphGrid[group],
    edge = size ?? (group === "motifs" ? sizes.motif : sizes.glyph);
  return (
    <Svg
      width={edge}
      height={edge}
      viewBox={`0 0 ${grid.viewBox} ${grid.viewBox}`}
      accessible={!!accessibilityLabel}
      accessibilityLabel={accessibilityLabel}
      accessibilityRole={accessibilityLabel ? "image" : undefined}
      accessibilityElementsHidden={!accessibilityLabel}
      importantForAccessibility={
        accessibilityLabel ? "yes" : "no-hide-descendants"
      }
    >
      {elements.map((element, i) => {
        const { el, fill, ...geometry } = element;
        const common = {
          fill: fill ? colors[color] : "none",
          stroke: fill ? "none" : colors[color],
          strokeWidth: strokeWidth ?? grid.strokeWidth,
          strokeLinecap: "round" as const,
          strokeLinejoin: "round" as const,
        };
        if (el === "path")
          return <Path key={i} {...(geometry as { d: string })} {...common} />;
        if (el === "circle")
          return <Circle key={i} {...geometry} {...common} />;
        return <Rect key={i} {...geometry} {...common} />;
      })}
    </Svg>
  );
}
