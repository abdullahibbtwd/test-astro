import { useMemo, useState, type PropsWithChildren } from "react";
import { View, ScrollView, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { LinearGradient } from "expo-linear-gradient";
import { SvgXml } from "react-native-svg";
import { sky } from "../glyphs/glyphs";
import { size, space, radius } from "../theme/tokens";
import { useTheme } from "../ThemeProvider";
export type ScreenProps = PropsWithChildren<{
  arch?: boolean;
  grain?: boolean;
  backdrop?: "orbits" | "plain";
  scroll?: boolean;
}>;
export function Screen({
  arch = false,
  grain = false,
  backdrop = "orbits",
  scroll = true,
  children,
}: ScreenProps) {
  const { colors } = useTheme(),
    safe = useSafeAreaInsets(),
    [width, setWidth] = useState(0);
  const xml = useMemo(
    () =>
      (backdrop === "orbits" ? sky.withOrbits : sky.plain)
        .replaceAll("__HAIRLINE__", colors.hairline)
        .replaceAll("__STAR__", colors.star),
    [backdrop, colors],
  );
  const padding = {
    paddingTop: safe.top + size.screenPaddingTop,
    paddingHorizontal: size.screenPaddingX + (arch ? size.archInset : 0),
    paddingBottom: safe.bottom + space[8],
    gap: space[6],
  };
  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <View
        pointerEvents="none"
        accessible={false}
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
        style={StyleSheet.absoluteFill}
      >
        <SvgXml
          xml={xml}
          width="100%"
          height="100%"
          preserveAspectRatio="xMidYMid slice"
        />
        {grain && (
          <LinearGradient
            colors={["transparent", colors.surfaceDeep]}
            style={{
              position: "absolute",
              bottom: 0,
              height: "55%",
              width: "100%",
            }}
          />
        )}
        {arch && (
          <View
            onLayout={(e) => setWidth(e.nativeEvent.layout.width)}
            style={{
              position: "absolute",
              top: safe.top + size.archInset,
              bottom: safe.bottom + size.archInset,
              left: size.archInset,
              right: size.archInset,
              borderWidth: size.controlBorder,
              borderColor: colors.accent,
              borderTopLeftRadius: width / 2,
              borderTopRightRadius: width / 2,
              borderBottomLeftRadius: radius.card,
              borderBottomRightRadius: radius.card,
            }}
          >
            <View
              style={{
                position: "absolute",
                top: 7,
                bottom: 7,
                left: 7,
                right: 7,
                borderWidth: size.controlBorder,
                borderColor: colors.hairline,
                borderTopLeftRadius: (width - 14) / 2,
                borderTopRightRadius: (width - 14) / 2,
                borderBottomLeftRadius: radius.card,
                borderBottomRightRadius: radius.card,
              }}
            />
          </View>
        )}
      </View>
      {scroll ? (
        <ScrollView
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={padding}
        >
          {children}
        </ScrollView>
      ) : (
        <View style={[{ flex: 1 }, padding]}>{children}</View>
      )}
    </View>
  );
}
