import { useApp } from "../lib/state";
import { colors } from "./tokens";
/** System preference maps to the brand default; explicit light is the Parchment theme. */
export function useTheme() {
  const preference = useApp(s => s.theme);
  return preference === "light" ? colors.light : colors.dark;
}
