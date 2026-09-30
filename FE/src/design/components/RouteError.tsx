import { SafeAreaProvider } from "react-native-safe-area-context";
import type { ErrorBoundaryProps } from "expo-router";
import { useTranslation } from "react-i18next";
import { Screen, Txt, Button } from "./index";
export function RouteError({ retry }: ErrorBoundaryProps) {
  const { t } = useTranslation();
  return (
    <SafeAreaProvider>
      <Screen title={t("screenErrorTitle")}>
        <Txt>{t("screenErrorBody")}</Txt>
        <Button
          label={t("retry")}
          onPress={() => {
            void retry();
          }}
        />
      </Screen>
    </SafeAreaProvider>
  );
}
