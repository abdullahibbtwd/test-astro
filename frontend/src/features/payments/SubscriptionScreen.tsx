import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Linking, View } from "react-native";
import { router, useFocusEffect } from "expo-router";
import { useTranslation } from "react-i18next";
import { Screen, Txt, Button, ErrorNotice, Row } from "../../design/components";
import { usePaymentsUiEnabled } from "../../lib/flags";
import { useMe } from "../../api/hooks";
import { useOnline } from "../../api/online";
import { accessToken, apiBase } from "../../api/client";
import { getPaymentProvider } from "../../payments";
import { showSnackbar } from "../../design/components/Snackbar";

type BillingStatus = {
  plan_id: string;
  free_launch: boolean;
  entitlements: Record<string, true>;
  subscription: {
    plan_id: string;
    status: string;
    expires_at: string | null;
    source_store: string;
    original_transaction_id: string | null;
    product_id: string | null;
  } | null;
};

async function fetchBillingStatus(): Promise<BillingStatus> {
  const token = accessToken();
  const res = await fetch(`${apiBase}/billing/status`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!res.ok) throw new Error(`billing_status_${res.status}`);
  return (await res.json()) as BillingStatus;
}

export default function SubscriptionScreen() {
  const { t } = useTranslation();
  const enabled = usePaymentsUiEnabled();
  const online = useOnline();
  const me = useMe();
  const [status, setStatus] = useState<BillingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [restoring, setRestoring] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setStatus(await fetchBillingStatus());
    } catch (e) {
      setStatus({
        plan_id: me.data?.entitlements?.all ? "free_launch" : "free",
        free_launch: Boolean(me.data?.entitlements?.all),
        entitlements: me.data?.entitlements ?? {},
        subscription: null,
      });
      setError(e);
    } finally {
      setLoading(false);
    }
  }, [me.data?.entitlements]);

  useFocusEffect(
    useCallback(() => {
      if (enabled && online) void load();
    }, [enabled, online, load]),
  );
  useEffect(() => {
    if (!online) setLoading(false);
  }, [online]);

  if (!enabled) {
    return (
      <Screen title={t("subscriptionTitle")} back>
        <Txt muted>{t("paymentsUiOff")}</Txt>
      </Screen>
    );
  }

  const restore = async () => {
    if (!online) return;
    setRestoring(true);
    setError(null);
    try {
      const provider = getPaymentProvider();
      await provider.initialize();
      const results = await provider.restore();
      showSnackbar(
        results.length
          ? t("subscriptionRestoreOk")
          : t("subscriptionRestoreEmpty"),
      );
      await load();
    } catch (e) {
      setError(e);
    } finally {
      setRestoring(false);
    }
  };

  const manage = () => {
    const url = getPaymentProvider().manageSubscriptionsUrl();
    if (url) void Linking.openURL(url);
    else showSnackbar(t("subscriptionManageUnavailable"));
  };

  return (
    <Screen title={t("subscriptionTitle")} back>
      {!online && <Txt muted>{t("offlineDisabled")}</Txt>}
      {loading && (
        <View style={{ paddingVertical: 24, alignItems: "center" }}>
          <ActivityIndicator />
          <Txt muted>{t("subscriptionLoading")}</Txt>
        </View>
      )}
      {!loading && status && (
        <>
          <Txt kind="title">{t("subscriptionPlan")}</Txt>
          <Txt>{status.plan_id}</Txt>
          {status.free_launch && <Txt muted>{t("subscriptionFreeLaunch")}</Txt>}
          {status.subscription ? (
            <>
              <Row
                label={t("subscriptionStatus")}
                detail={status.subscription.status}
              />
              <Row
                label={t("subscriptionExpires")}
                detail={status.subscription.expires_at ?? "—"}
              />
              <Row
                label={t("subscriptionStore")}
                detail={status.subscription.source_store}
              />
            </>
          ) : (
            <Txt muted>{t("subscriptionNone")}</Txt>
          )}
        </>
      )}
      {error != null && <ErrorNotice error={error} retry={() => void load()} />}
      <Button
        label={restoring ? t("subscriptionRestoring") : t("paywallRestore")}
        onPress={() => void restore()}
        disabled={!online || restoring}
      />
      <Button secondary label={t("subscriptionManage")} onPress={manage} />
      <Button
        secondary
        label={t("paywallTitle")}
        onPress={() => router.push("/paywall")}
      />
    </Screen>
  );
}
