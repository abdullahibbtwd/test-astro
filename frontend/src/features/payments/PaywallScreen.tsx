import { useEffect, useState } from "react";
import { ActivityIndicator, View } from "react-native";
import { useTranslation } from "react-i18next";
import { router } from "expo-router";
import { Screen, Txt, Button, ErrorNotice } from "../../design/components";
import { usePaymentsUiEnabled } from "../../lib/flags";
import { getPaymentProvider, type StoreProduct } from "../../payments";

/** Product ids come from owner-filled store ids — empty until configured. Prices from store only. */
const PLACEHOLDER_PRODUCT_IDS: string[] = [];

export default function PaywallScreen() {
  const { t } = useTranslation();
  const enabled = usePaymentsUiEnabled();
  const [loading, setLoading] = useState(true);
  const [purchasing, setPurchasing] = useState(false);
  const [products, setProducts] = useState<StoreProduct[]>([]);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const provider = getPaymentProvider();
        await provider.initialize();
        const list = await provider.getProducts(
          PLACEHOLDER_PRODUCT_IDS.filter(Boolean),
        );
        if (!cancelled) setProducts(list);
      } catch (e) {
        if (!cancelled) setError(e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [enabled]);

  if (!enabled) {
    return (
      <Screen title={t("paywallTitle")} back>
        <Txt muted>{t("paymentsUiOff")}</Txt>
      </Screen>
    );
  }

  const buy = async (productId: string) => {
    setPurchasing(true);
    setError(null);
    try {
      const provider = getPaymentProvider();
      await provider.purchase(productId);
      router.back();
    } catch (e) {
      setError(e);
    } finally {
      setPurchasing(false);
    }
  };

  return (
    <Screen title={t("paywallTitle")} back>
      <Txt kind="title">{t("paywallHeadline")}</Txt>
      <Txt muted>{t("paywallBody")}</Txt>
      {loading && (
        <View style={{ paddingVertical: 24, alignItems: "center" }}>
          <ActivityIndicator />
          <Txt muted>{t("paywallLoading")}</Txt>
        </View>
      )}
      {!loading && products.length === 0 && !error && (
        <Txt muted>{t("paywallNoProducts")}</Txt>
      )}
      {products.map((p) => (
        <View key={p.productId} style={{ gap: 8, marginVertical: 12 }}>
          <Txt kind="title">{p.title ?? p.productId}</Txt>
          <Txt muted>{p.priceString ?? t("paywallPriceFromStore")}</Txt>
          <Button
            label={
              purchasing ? t("paywallPurchasing") : t("paywallSubscribe")
            }
            onPress={() => void buy(p.productId)}
            disabled={purchasing || !p.productId}
          />
        </View>
      ))}
      {error != null && <ErrorNotice error={error} />}
      <Button
        secondary
        label={t("paywallRestore")}
        onPress={() => router.push("/profile/subscription")}
      />
    </Screen>
  );
}
