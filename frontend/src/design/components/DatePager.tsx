import { space as dsSpace } from "../../design-system/theme/tokens";
import { ChevronLeft, ChevronRight } from "../../design-system/LegacyIcons";
import { Pressable, View } from "react-native";


import { useTranslation } from "react-i18next";
import { Txt } from ".";
import { IconButton } from "./IconButton";
import { useTheme } from "../theme";
export function DatePager({
  previousDisabled = false,
  nextDisabled = false,
  label,
  onPrevious,
  onNext,
  onPick,
  onToday,
}: {
  previousDisabled?: boolean;
  nextDisabled?: boolean;
  label: string;
  onPrevious: () => void;
  onNext: () => void;
  onPick: () => void;
  onToday?: () => void;
}) {
  const c = useTheme(),
    { t } = useTranslation();
  return (
    <View style={{ flexDirection: "row", alignItems: "center" }}>
      <IconButton
        accessibilityLabel={t("previous")}
        icon={<ChevronLeft color={c.ink} size={22} />}
        onPress={onPrevious}
        disabled={previousDisabled}
      />
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={label}
        onPress={onPick}
        style={{
          flex: 1,
          minHeight: 44,
          justifyContent: "center",
          alignItems: "center",
        }}
      >
        <Txt style={{ textAlign: "center" }}>{label}</Txt>
      </Pressable>
      <IconButton
        accessibilityLabel={t("next")}
        icon={<ChevronRight color={c.ink} size={22} />}
        onPress={onNext}
        disabled={nextDisabled}
      />
      {onToday && (
        <Pressable
          accessibilityRole="button"
          onPress={onToday}
          style={{
            minHeight: 44,
            paddingHorizontal: dsSpace[2],
            flexShrink: 1,
            maxWidth: "28%",
            justifyContent: "center",
          }}
        >
          <Txt style={{ color: c.accent }}>{t("today")}</Txt>
        </Pressable>
      )}
    </View>
  );
}
