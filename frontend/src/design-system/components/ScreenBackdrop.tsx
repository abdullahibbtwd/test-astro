import { useMemo, useState } from "react";
import { View, StyleSheet } from "react-native";
import { SvgXml } from "react-native-svg";
import { LinearGradient } from "expo-linear-gradient";
import { useTheme } from "../ThemeProvider";
import { sky } from "../glyphs/glyphs";
import { size, radius } from "../theme/tokens";
/** Background only: existing screens keep their safe areas, lists, keyboard handling and footers. */
export function ScreenBackdrop({ arch = false, grain = false }: { arch?: boolean; grain?: boolean }) {
  const { colors } = useTheme(), [width, setWidth] = useState(0);
  const xml = useMemo(() => sky.withOrbits.replaceAll("__HAIRLINE__", colors.hairline).replaceAll("__STAR__", colors.star), [colors]);
  return <View pointerEvents="none" accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={StyleSheet.absoluteFill}>
    <SvgXml xml={xml} width="100%" height="100%" preserveAspectRatio="xMidYMid slice" />
    {grain && <LinearGradient colors={["transparent", colors.surfaceDeep]} style={{ position: "absolute", bottom: 0, width: "100%", height: "55%" }} />}
    {arch && <View onLayout={e => setWidth(e.nativeEvent.layout.width)} style={{ position: "absolute", top: size.archInset, bottom: size.archInset, left: size.archInset, right: size.archInset, borderWidth: size.controlBorder, borderColor: colors.accent, borderTopLeftRadius: width / 2, borderTopRightRadius: width / 2, borderBottomLeftRadius: radius.card, borderBottomRightRadius: radius.card }}><View style={{ position: "absolute", top: 7, bottom: 7, left: 7, right: 7, borderWidth: size.controlBorder, borderColor: colors.hairline, borderTopLeftRadius: (width - 14) / 2, borderTopRightRadius: (width - 14) / 2, borderBottomLeftRadius: radius.card, borderBottomRightRadius: radius.card }} /></View>}
  </View>;
}
