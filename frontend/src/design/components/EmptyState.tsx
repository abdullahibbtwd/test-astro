import { View } from "react-native";
import { useTranslation } from "react-i18next";
import { space as dsSpace } from "../../design-system/theme/tokens";
import { Button, Txt } from "./index";

/** Shared zero-data state. Pass i18n keys only — never hardcoded copy. */
export function EmptyState({
  titleKey,
  bodyKey,
  actionKey,
  onAction,
}: {
  titleKey: string;
  bodyKey?: string;
  actionKey?: string;
  onAction?: () => void;
}) {
  const { t } = useTranslation();
  return (
    <View
      accessible
      accessibilityRole="summary"
      style={{ gap: dsSpace[3], paddingVertical: dsSpace[4] }}
    >
      <Txt muted>{t(titleKey)}</Txt>
      {bodyKey ? (
        <Txt kind="caption" muted>
          {t(bodyKey)}
        </Txt>
      ) : null}
      {actionKey && onAction ? (
        <Button secondary label={t(actionKey)} onPress={onAction} />
      ) : null}
    </View>
  );
}
