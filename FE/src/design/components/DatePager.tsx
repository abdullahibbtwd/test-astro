import { Pressable, View } from "react-native";
import { ChevronLeft, ChevronRight } from "lucide-react-native";
import { useTranslation } from "react-i18next";
import { Txt } from ".";
import { IconButton } from "./IconButton";
import { useTheme } from "../theme";
export function DatePager({ label, onPrevious, onNext, onPick, onToday }: { label: string; onPrevious: () => void; onNext: () => void; onPick: () => void; onToday?: () => void }) {
  const c = useTheme(), { t } = useTranslation();
  return <View style={{ flexDirection: "row", alignItems: "center" }}>
    <IconButton accessibilityLabel={t("previous")} icon={<ChevronLeft color={c.ink} size={22} />} onPress={onPrevious} />
    <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPick} style={{ flex: 1, minHeight: 44, justifyContent: "center", alignItems: "center" }}><Txt numberOfLines={1}>{label}</Txt></Pressable>
    <IconButton accessibilityLabel={t("next")} icon={<ChevronRight color={c.ink} size={22} />} onPress={onNext} />
    {onToday && <Pressable accessibilityRole="button" onPress={onToday} style={{ minHeight: 44, paddingHorizontal: 8, justifyContent: "center" }}><Txt style={{ color: c.accent }}>{t("today")}</Txt></Pressable>}
  </View>;
}
