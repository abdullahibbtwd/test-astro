import { type as dsType, space as dsSpace, radius as dsRadius } from "../../design-system/theme/tokens";
import { useTranslation } from "react-i18next";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  AccessibilityInfo,
  Platform,
  AppState,
  PanResponder,
  Pressable,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useSegments } from "expo-router";
import { Txt } from ".";
import { useTheme } from "../theme";
import {
  dismissSnackbar,
  useSnackbar,
  useSnackbarLayout,
} from "./snackbar-store";
export { showSnackbar, dismissSnackbar } from "./snackbar-store";
export function Snackbar() {
  const { t } = useTranslation(),
    announced = useRef<number | null>(null);
  const footerHeight = useSnackbarLayout((s) => s.footerHeight);
  const current = useSnackbar((s) => s.current),
    c = useTheme(),
    insets = useSafeAreaInsets(),
    segments = useSegments();
  const [reader, setReader] = useState(true),
    [active, setActive] = useState(AppState.currentState === "active");
  useEffect(() => {
    let live = true;
    void AccessibilityInfo.isScreenReaderEnabled().then((v) => {
      if (live) setReader(v);
    });
    const a = AccessibilityInfo.addEventListener(
      "screenReaderChanged",
      setReader,
    );
    const b = AppState.addEventListener("change", (v) =>
      setActive(v === "active"),
    );
    return () => {
      live = false;
      a.remove();
      b.remove();
    };
  }, []);
  useEffect(() => {
    if (!current || reader || !active) return;
    const timer = setTimeout(
      () => dismissSnackbar("timeout", current.id),
      5000,
    );
    return () => clearTimeout(timer);
  }, [current, reader, active]);
  useEffect(() => {
    if (
      current &&
      reader &&
      Platform.OS === "ios" &&
      announced.current !== current.id
    ) {
      announced.current = current.id;
      AccessibilityInfo.announceForAccessibilityWithOptions(current.message, {
        queue: true,
      });
    }
  }, [current, reader]);
  const pan = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_, g) =>
          Math.abs(g.dx) > 20 && Math.abs(g.dx) > Math.abs(g.dy),
        onPanResponderRelease: (_, g) => {
          if (Math.abs(g.dx) > 50) dismissSnackbar("swipe");
        },
      }),
    [],
  );
  if (!current) return null;
  return (
    <View
      {...pan.panHandlers}
      accessibilityLiveRegion="polite"
      style={{
        position: "absolute",
        left: 16,
        right: 16,
        bottom:
          segments[0] === "(tabs)"
            ? 78 + insets.bottom
            : 12 + insets.bottom + footerHeight,
        backgroundColor: c.surface,
        paddingHorizontal: dsSpace[4],
        paddingVertical: dsSpace[2],
        borderRadius: dsRadius.md,
        flexDirection: "row",
        alignItems: "center",
        gap: dsSpace[3],
        elevation: 12,
      }}
    >
      <View
        accessible
        accessibilityLabel={current.message}
        accessibilityActions={[{ name: "dismiss", label: t("close") }]}
        onAccessibilityAction={(e) => {
          if (e.nativeEvent.actionName === "dismiss")
            dismissSnackbar("swipe", current.id);
        }}
        style={{ flex: 1 }}
      >
        <Txt style={{ color: c.ink }}>{current.message}</Txt>
      </View>
      {current.action && (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={current.action.label}
          onPress={() => dismissSnackbar("action", current.id)}
          style={{
            minHeight: 44,
            minWidth: 44,
            paddingHorizontal: dsSpace[2],
            justifyContent: "center",
          }}
        >
          <Txt style={{ color: c.accent, fontFamily: dsType.input.fontFamily }}>
            {current.action.label}
          </Txt>
        </Pressable>
      )}
    </View>
  );
}
