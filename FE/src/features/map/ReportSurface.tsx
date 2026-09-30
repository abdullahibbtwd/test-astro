import { useState, type ReactNode } from "react";
import { View } from "react-native";
import BottomSheet, {
  BottomSheetScrollView,
  BottomSheetBackdrop,
} from "@gorhom/bottom-sheet";
import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import { Screen, Txt, Button, Choices } from "../../design/components";
import { useTheme } from "../../design/theme";
export function ReportSurface({
  title,
  children,
}: {
  title?: string;
  children: ReactNode;
  back?: boolean;
}) {
  const [full, setFull] = useState(false),
    c = useTheme(),
    { t } = useTranslation();
  if (full)
    return (
      <Screen back title={title}>
        <Button
          secondary
          label={t("collapse")}
          onPress={() => setFull(false)}
        />
        {children}
      </Screen>
    );
  return (
    <View style={{ flex: 1 }}>
      <BottomSheet
        index={1}
        snapPoints={["25%", "55%", "92%"]}
        enableDynamicSizing={false}
        enablePanDownToClose
        onClose={() => router.back()}
        backgroundStyle={{ backgroundColor: c.surface }}
        handleIndicatorStyle={{ backgroundColor: c.ink2 }}
        backdropComponent={(props) => (
          <BottomSheetBackdrop
            {...props}
            appearsOnIndex={0}
            disappearsOnIndex={-1}
          />
        )}
      >
        <BottomSheetScrollView
          contentContainerStyle={{ padding: 24, gap: 20, paddingBottom: 48 }}
        >
          <View accessibilityViewIsModal style={{ gap: 20 }}>
            <Choices>
              <Button
                secondary
                label={t("close")}
                onPress={() => router.back()}
              />
              <Button
                secondary
                label={t("expand")}
                onPress={() => setFull(true)}
              />
            </Choices>
            {title && <Txt kind="title">{title}</Txt>}
            {children}
          </View>
        </BottomSheetScrollView>
      </BottomSheet>
    </View>
  );
}
