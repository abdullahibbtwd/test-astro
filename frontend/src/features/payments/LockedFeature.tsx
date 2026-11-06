import { View } from "react-native";
import { useTranslation } from "react-i18next";
import { router } from "expo-router";
import { Txt, Button } from "../../design/components";
import { usePaymentsUiEnabled } from "../../lib/flags";
import { isPremiumRequired } from "../../api/errors";

/** Locked-feature placeholder when API returns premium_required (or local gate). */
export function LockedFeature({
  feature,
  error,
}: {
  feature?: string;
  error?: unknown;
}) {
  const { t } = useTranslation();
  const paymentsUi = usePaymentsUiEnabled();
  const premium = error == null || isPremiumRequired(error);
  if (!premium) return null;
  return (
    <View style={{ gap: 12, paddingVertical: 16 }}>
      <Txt kind="title">🔒 {t("lockedFeatureTitle")}</Txt>
      <Txt muted>
        {feature
          ? t("lockedFeatureBodyNamed", { feature })
          : t("lockedFeatureBody")}
      </Txt>
      {paymentsUi ? (
        <Button
          label={t("paywallTitle")}
          onPress={() => router.push("/paywall")}
        />
      ) : (
        <Txt muted>{t("paymentsUiOff")}</Txt>
      )}
    </View>
  );
}
