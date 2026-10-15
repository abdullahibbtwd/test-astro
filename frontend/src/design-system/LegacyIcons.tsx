import { View, type ColorValue } from "react-native";
import { Glyph } from "./components/Glyph";
import { useTheme } from "./ThemeProvider";
import type { IconName } from "./glyphs/glyphs";
import type { ThemeColors } from "./theme/tokens";
type Props = { color?: ColorValue; size?: number; strokeWidth?: number };
const icon = (name: IconName, reverse = false) => function KitIcon({ color, size, strokeWidth }: Props) {
  const { colors } = useTheme();
  const semantic = (Object.keys(colors) as (keyof ThemeColors)[]).find(key => colors[key] === color) ?? "accent";
  const glyph = <Glyph name={name} set="icons" size={size} color={semantic} strokeWidth={strokeWidth} />;
  return reverse ? <View style={{ transform: [{ rotate: "180deg" }] }}>{glyph}</View> : glyph;
};
export const ArrowLeft = icon("arrow-left"), ChevronRight = icon("chevron-right"), ChevronLeft = icon("chevron-right", true), ChevronDown = icon("chevron-down"), Check = icon("check"), CalendarDays = icon("calendar"), MapPin = icon("map-pin"), CircleUserRound = icon("user"), MessageCircle = icon("chat"), Info = icon("info"), Search = icon("search"), X = icon("close");
