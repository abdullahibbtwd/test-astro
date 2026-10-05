import Constants from "expo-constants";
import { useState } from "react";
import { Alert, Linking, Switch, View } from "react-native";
import * as Notifications from "expo-notifications";
import { useTranslation } from "react-i18next";
import { useMe, useActions, useCatalogue } from "../../api/hooks";
import { useApp } from "../../lib/state";
import {
  Screen,
  Txt,
  Button,
  Choices,
  Chip,
  ErrorNotice,
} from "../../design/components";
import { DateTimeField } from "../../design/components/DateTimeField";
import {
  prepareNotifications,
  synchronizeNotifications,
} from "../../lib/notifications";
import type {
  NotificationPrefs,
  NotificationType,
} from "../../../contracts/spec-types";
export default function NotificationsScreen() {
  const { t } = useTranslation(),
    me = useMe(),
    app = useApp(),
    actions = useActions(),
    cat = useCatalogue(),
    [error, setError] = useState<unknown>();
  const prefs = (me.data ?? app.me)?.notification_prefs;
  const save = async (values: Partial<NotificationPrefs>) => {
    if (!prefs) return;
    setError(undefined);
    try {
      if (values.enabled) {
        await prepareNotifications();
        const permission = await Notifications.requestPermissionsAsync();
        if (!permission.granted) {
          Alert.alert(t("notifications"), t("goSettings"), [
            { text: t("cancel") },
            {
              text: t("goSettings"),
              onPress: () => {
                void Linking.openSettings();
              },
            },
          ]);
          return;
        }
      }
      const updated = await actions.patchMe({
        notification_prefs: { ...prefs, ...values },
      });
      await synchronizeNotifications(updated, app.language);
    } catch (e) {
      setError(e);
    }
  };
  return (
    <Screen largeTitle back title={t("notifications")}>
      <Txt muted>{t("notificationHint")}</Txt>
      {prefs && (
        <>
          <View
            style={{
              flexDirection: "row",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <Txt>{t("notifications")}</Txt>
            <Switch
              accessibilityLabel={t("notifications")}
              disabled={actions.isPending}
              value={prefs.enabled}
              onValueChange={(enabled) => {
                void save({ enabled });
              }}
            />
          </View>
          {Object.entries(cat.data.notification_types).map(([type, label]) => (
            <View
              key={type}
              style={{
                flexDirection: "row",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 12,
              }}
            >
              <View style={{ flex: 1 }}>
                <Txt>{label}</Txt>
                <Txt kind="caption" muted>
                  {t(`notification_${type}`)}
                </Txt>
              </View>
              <Switch
                accessibilityLabel={label}
                disabled={actions.isPending}
                value={prefs.types[type as NotificationType]}
                onValueChange={(value) => {
                  void save({ types: { ...prefs.types, [type]: value } });
                }}
              />
            </View>
          ))}
          <DateTimeField
            mode="time"
            label={t("deliveryTime")}
            value={prefs.time}
            onChange={(time) => {
              void save({ time });
            }}
          />
          <Txt>{t("maxPerDay")}</Txt>
          <Choices>
            {[1, 2].map((value) => (
              <Chip
                key={value}
                label={String(value)}
                selected={prefs.max_per_day === value}
                onPress={() => {
                  void save({ max_per_day: value });
                }}
              />
            ))}
          </Choices>
          <Txt>{t("maxPerWeek")}</Txt>
          <Choices>
            {[1, 2, 3, 4, 5, 6, 7].map((value) => (
              <Chip
                key={value}
                label={String(value)}
                selected={prefs.max_per_week === value}
                onPress={() => {
                  void save({ max_per_week: value });
                }}
              />
            ))}
          </Choices>
          <DateTimeField
            mode="time"
            label={t("quietStart")}
            value={prefs.quiet_hours.start}
            onChange={(start) => {
              void save({ quiet_hours: { ...prefs.quiet_hours, start } });
            }}
          />
          <DateTimeField
            mode="time"
            label={t("quietEnd")}
            value={prefs.quiet_hours.end}
            onChange={(end) => {
              void save({ quiet_hours: { ...prefs.quiet_hours, end } });
            }}
          />
          <Button
            secondary
            label={t("testNotification")}
            onPress={() => {
              void (async () => {
                try {
                  await prepareNotifications();
                  const permission =
                    await Notifications.requestPermissionsAsync();
                  if (!permission.granted) {
                    await Linking.openSettings();
                    return;
                  }
                  await Notifications.scheduleNotificationAsync({
                    content: {
                      title: Constants.expoConfig?.name ?? "Astrology",
                      body: t("testNotificationBody"),
                    },
                    trigger: {
                      type: Notifications.SchedulableTriggerInputTypes
                        .TIME_INTERVAL,
                      seconds: 2,
                      channelId: "astrology",
                    },
                  });
                } catch (e) {
                  setError(e);
                }
              })();
            }}
          />
        </>
      )}
      <ErrorNotice error={error ?? me.error ?? actions.error} />
    </Screen>
  );
}
