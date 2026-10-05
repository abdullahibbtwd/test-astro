import { useEffect, useMemo, useState } from "react";
import { AccessibilityInfo, AppState, PanResponder, Pressable, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useSegments } from "expo-router";
import { Txt } from ".";
import { useTheme } from "../theme";
import { dismissSnackbar, useSnackbar } from "./snackbar-store";
export { showSnackbar, dismissSnackbar } from "./snackbar-store";
export function Snackbar() {
  const current = useSnackbar(s => s.current), c = useTheme(), insets = useSafeAreaInsets(), segments = useSegments();
  const [reader, setReader] = useState(true), [active, setActive] = useState(AppState.currentState === "active");
  useEffect(() => {
    let live = true;
    void AccessibilityInfo.isScreenReaderEnabled().then(v => { if (live) setReader(v); });
    const a = AccessibilityInfo.addEventListener("screenReaderChanged", setReader);
    const b = AppState.addEventListener("change", v => setActive(v === "active"));
    return () => { live = false; a.remove(); b.remove(); };
  }, []);
  useEffect(() => {
    if (!current || reader || !active) return;
    const timer = setTimeout(() => dismissSnackbar("timeout", current.id), 5000);
    return () => clearTimeout(timer);
  }, [current, reader, active]);
  const pan = useMemo(() => PanResponder.create({ onMoveShouldSetPanResponder: (_, g) => Math.abs(g.dx) > 20 && Math.abs(g.dx) > Math.abs(g.dy), onPanResponderRelease: (_, g) => { if (Math.abs(g.dx) > 50) dismissSnackbar("swipe"); } }), []);
  if (!current) return null;
  return <View {...pan.panHandlers} accessibilityLiveRegion="polite" style={{ position: "absolute", left: 16, right: 16, bottom: segments[0] === "(tabs)" ? 78 + insets.bottom : 12 + insets.bottom, backgroundColor: c.ink, paddingHorizontal: 16, paddingVertical: 8, borderRadius: 12, flexDirection: "row", alignItems: "center", gap: 12, elevation: 12 }}>
    <Txt style={{ color: c.bg, flex: 1 }}>{current.message}</Txt>
    {current.action && <Pressable accessibilityRole="button" accessibilityLabel={current.action.label} onPress={() => dismissSnackbar("action", current.id)} style={{ minHeight: 44, justifyContent: "center" }}><Txt style={{ color: c.bg, fontFamily: "Inter-SemiBold" }}>{current.action.label}</Txt></Pressable>}
  </View>;
}
