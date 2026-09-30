import { useColorScheme } from "react-native";
import { useApp } from "../lib/state";
import { colors } from "./tokens";
export function useTheme() {
  const preference = useApp((s) => s.theme),
    system = useColorScheme();
  return colors[
    preference === "system"
      ? system === "dark"
        ? "dark"
        : "light"
      : preference
  ];
}
