import { resolveRoute } from "../../lib/routes";
import { showSnackbar } from "../../design/components/Snackbar";
import { shareAccountData } from "../exports/data-file";
import Constants from "expo-constants";
import { useState } from "react";
import { Alert, Linking, Switch, View } from "react-native";
import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import * as Notifications from "expo-notifications";
import * as Location from "expo-location";
import {
  Screen,
  Txt,
  Button,
  Row,
  Choices,
  Chip,
  Field,
  Card,
  ErrorNotice,
} from "../../design/components";
import { PlaceSearch } from "../../design/components/PlaceSearch";
import { useApp } from "../../lib/state";
import { useMe, useActions, useConfig } from "../../api/hooks";
import { legalUrl } from "../../config/identity";
export default function AccountScreen({ page = "profile" }: { page?: string }) {
  const { t } = useTranslation(),
    app = useApp(),
    me = useMe(),
    actions = useActions(),
    config = useConfig();
  const [confirm, setConfirm] = useState(false),
    [word, setWord] = useState(""),
    [error, setError] = useState<unknown>(null);
  const run = async (task: () => Promise<unknown>) => {
    setError(null);
    try {
      await task();
    } catch (e) {
      setError(e);
    }
  };
  const link = (kind: "terms" | "privacy" | "support") => {
    const url = legalUrl(kind, config.data?.links[kind]);
    if (url) void Linking.openURL(url);
    else showSnackbar(t("legalUnavailable"));
  };
  const details = me.data ?? app.me;
  return (
    <Screen
      largeTitle
      back
      title={t(page === "location" ? "currentLocation" : page)}
    >
      {page === "profile" && (
        <>
          <Txt kind="display">{details?.display_name}</Txt>
          <Txt muted>{details?.email}</Txt>
          {[
            "myCharts",
            "savedReports",
            "settings",
            "notifications",
            "privacy",
            "about",
          ].map((key) => (
            <Row
              key={key}
              label={t(key)}
              onPress={() =>
                router.push(
                  resolveRoute(
                    `/profile/${key === "myCharts" ? "charts" : key === "savedReports" ? "reports" : key}`,
                  ),
                )
              }
            />
          ))}
          <Button
            secondary
            label={t("signOut")}
            onPress={() =>
              void run(() =>
                actions.logout().then(() => router.replace("/(auth)/welcome")),
              )
            }
          />
        </>
      )}
      {page === "settings" && (
        <>
          <Txt kind="title">{t("language")}</Txt>
          <Choices>
            {(["tr", "en"] as const).map((language) => (
              <Chip
                key={language}
                label={language === "tr" ? "Türkçe" : "English"}
                selected={app.language === language}
                onPress={() =>
                  void run(async () => {
                    await actions.patchMe({ language });
                    app.update({ language });
                  })
                }
              />
            ))}
          </Choices>
          <Txt kind="title">{t("appearance")}</Txt>
          <Choices>
            {(["light", "dark"] as const).map((theme) => (
              <Chip
                key={theme}
                label={t(theme)}
                selected={app.theme === theme || (theme === "dark" && app.theme === "system")}
                onPress={() => void run(() => actions.patchMe({ theme }))}
              />
            ))}
          </Choices>
          <Row
            label={t("currentLocation")}
            detail={details?.current_place?.name}
            onPress={() => router.push("/profile/location")}
          />
        </>
      )}
      {page === "location" && (
        <>
          <Button
            secondary
            label={t("useLocation")}
            onPress={() =>
              void run(async () => {
                const permission =
                  await Location.requestForegroundPermissionsAsync();
                if (!permission.granted) {
                  showSnackbar(t("locationHint"));
                  return;
                }
                const position = await Location.getCurrentPositionAsync({
                  accuracy: Location.Accuracy.Balanced,
                });
                const place = await actions.reverse(
                  position.coords.latitude,
                  position.coords.longitude,
                );
                if (!place) {
                  showSnackbar(t("locationHint"));
                  return;
                }
                await actions.patchMe({ current_place_id: place.place_id });
                router.back();
              })
            }
          />
          <PlaceSearch
            onConfirm={(place) =>
              void run(async () => {
                await actions.patchMe({ current_place_id: place.place_id });
                router.back();
              })
            }
          />
        </>
      )}
      {page === "notifications" && details && (
        <>
          <Txt muted>{t("notificationHint")}</Txt>
          <View
            style={{
              flexDirection: "row",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <Txt>{t("notifications")}</Txt>
            <Switch
              accessibilityLabel={t("notifications")}
              value={details.notification_prefs.enabled}
              onValueChange={(enabled) =>
                void run(async () => {
                  if (enabled) {
                    const permission =
                      await Notifications.requestPermissionsAsync();
                    if (!permission.granted) {
                      Alert.alert(t("notifications"), t("goSettings"), [
                        { text: t("cancel") },
                        {
                          text: t("goSettings"),
                          onPress: () => void Linking.openSettings(),
                        },
                      ]);
                      return;
                    }
                  }
                  await actions.patchMe({
                    notification_prefs: {
                      ...details.notification_prefs,
                      enabled,
                    },
                  });
                  if (!enabled)
                    await Notifications.cancelAllScheduledNotificationsAsync();
                })
              }
            />
          </View>
        </>
      )}
      {page === "privacy" && (
        <>
          <Row
            label={t("consentStatus")}
            detail={
              details?.consents.birth_data?.accepted_at ?? t("notAccepted")
            }
          />
          <Button
            secondary
            label={t("downloadData")}
            onPress={() =>
              void run(async () => {
                const data = await actions.exportData();
                if (process.env.EXPO_PUBLIC_BACKEND_MODE === "local")
                  await shareAccountData(data);
                else showSnackbar(t("exportSent"));
              })
            }
          />
          <Card>
            <Txt kind="title">{t("deleteAccount")}</Txt>
            <Txt>
              {t(
                process.env.EXPO_PUBLIC_BACKEND_MODE === "local"
                  ? "deleteLocalExplanation"
                  : "deleteExplanation",
              )}
            </Txt>
            {!confirm ? (
              <Button
                secondary
                danger
                label={t("deleteAccount")}
                onPress={() => setConfirm(true)}
              />
            ) : (
              <>
                <Field
                  label={t("typeDelete")}
                  value={word}
                  onChangeText={setWord}
                  autoCapitalize="characters"
                />
                <Button
                  danger
                  label={t("deleteAccount")}
                  disabled={word !== t("deleteWord")}
                  onPress={() =>
                    void run(() =>
                      actions
                        .deleteAccount()
                        .then(() => router.replace("/(auth)/welcome")),
                    )
                  }
                />
              </>
            )}
          </Card>
        </>
      )}
      {page === "about" && (
        <>
          <Txt kind="display">{Constants.expoConfig?.name ?? "Astrology"}</Txt>
          <Txt muted>{t("version")} 0.1.0</Txt>
          <Txt>{t("disclaimer")}</Txt>
          <Txt kind="caption">
            Contains data from GeoNames (geonames.org), CC BY 4.0{"\n\n"}Made
            with Natural Earth{"\n\n"}WorldClim, CC BY 4.0{"\n\n"}Planetary
            positions: Swiss Ephemeris (Astrodienst){"\n\n"}Inter & Source Serif
            4 — SIL Open Font License 1.1
          </Txt>
          {(["terms", "privacy", "support"] as const).map((key) => (
            <Row key={key} label={t(key)} onPress={() => link(key)} />
          ))}
          {__DEV__ && (
            <Row label={t("gallery")} onPress={() => router.push("/gallery")} />
          )}
        </>
      )}
      <ErrorNotice
        error={error ?? actions.error ?? me.error}
        retry={() => void me.refetch()}
      />
    </Screen>
  );
}
