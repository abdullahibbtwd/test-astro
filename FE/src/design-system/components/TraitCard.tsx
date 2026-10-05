import { Pressable, View, StyleSheet } from "react-native";
import Svg, { Circle, Path } from "react-native-svg";
import { traitScatter, sparklePath, type MotifName } from "../glyphs/glyphs";
import { useTheme } from "../ThemeProvider";
import { radius, size, opacity, space } from "../theme/tokens";
import { AppText } from "../text/AppText";
import { Glyph } from "./Glyph";
import { Ornament } from "./Ornament";
export type TraitCardProps = {
  label: string;
  motif: MotifName;
  selected: boolean;
  onToggle: (next: boolean) => void;
  lang?: "tr" | "en";
};
export function TraitCard({
  label,
  motif,
  selected,
  onToggle,
  lang,
}: TraitCardProps) {
  const { colors } = useTheme(),
    ink = selected ? "onPrimary" : "accent";
  return (
    <Pressable
      accessibilityRole="checkbox"
      accessibilityLabel={label}
      accessibilityState={{ checked: selected }}
      onPress={() => onToggle(!selected)}
      style={{
        flex: 1,
        aspectRatio: size.traitCardAspect,
        borderWidth: size.controlBorder,
        borderColor: selected ? colors.primary : colors.borderControl,
        backgroundColor: selected ? colors.primary : colors.surface,
        borderRadius: radius.card,
        justifyContent: "center",
      }}
    >
      <View
        pointerEvents="none"
        accessible={false}
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
        style={StyleSheet.absoluteFill}
      >
        <View
          style={{
            position: "absolute",
            top: 5,
            bottom: 5,
            left: 5,
            right: 5,
            borderWidth: size.controlBorder,
            borderColor: colors[ink],
            opacity: opacity.traitFrame,
            borderRadius: 2,
          }}
        />
        {([0, 1, 2, 3] as const).map((i) => (
          <View
            key={i}
            style={{
              position: "absolute",
              ...(i < 2 ? { top: 2 } : { bottom: 2 }),
              ...(i % 2 ? { right: 2 } : { left: 2 }),
              transform: [
                { scaleX: i % 2 ? -1 : 1 },
                { scaleY: i < 2 ? 1 : -1 },
              ],
            }}
          >
            <Ornament name="cardCorner" width={18} color={ink} />
          </View>
        ))}
        <Svg
          viewBox="0 0 100 160"
          width="100%"
          height="100%"
          opacity={opacity.traitScatter}
        >
          {traitScatter.dots.map(([cx, cy, r], i) => (
            <Circle key={i} cx={cx} cy={cy} r={r} fill={colors[ink]} />
          ))}
          {traitScatter.sparkles.map(([x, y, s], i) => (
            <Path key={i} d={sparklePath(x, y, s)} fill={colors[ink]} />
          ))}
        </Svg>
        <View style={{ position: "absolute", top: "11%", alignSelf: "center" }}>
          <Glyph name={motif} set="motifs" size={size.motif} color={ink} />
        </View>
        <View
          style={{
            position: "absolute",
            bottom: "11%",
            alignSelf: "center",
            transform: [{ rotate: "180deg" }],
          }}
        >
          <Glyph name={motif} set="motifs" size={size.motif} color={ink} />
        </View>
      </View>
      <AppText
        variant="displayCard"
        color={ink}
        align="center"
        lang={lang}
        numberOfLines={3}
        style={{ paddingHorizontal: space[6] }}
      >
        {label}
      </AppText>
      {selected && (
        <View
          pointerEvents="none"
          style={{
            position: "absolute",
            top: -size.checkBadge / 2,
            alignSelf: "center",
            width: size.checkBadge,
            height: size.checkBadge,
            borderRadius: radius.full,
            backgroundColor: colors.surface,
            borderWidth: size.controlBorder,
            borderColor: colors.primary,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Glyph name="check" size={14} strokeWidth={2} />
        </View>
      )}
    </Pressable>
  );
}
