import { resolveRoute } from "./routes";
import { useProfiles } from "../api/hooks";
import { useEffect } from "react";
import { AppState } from "react-native";
import * as Notifications from "expo-notifications";
import * as BackgroundTask from "expo-background-task";
import * as TaskManager from "expo-task-manager";
import { router } from "expo-router";
import { useApp } from "./state";
import { privateStorage } from "./storage";
import { synchronizeNotifications } from "./notifications";
import { notificationRoute } from "./calendar";
import { notificationTask } from "./notification-background";
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
  }),
});
export function NotificationLifecycle() {
  const me = useApp((s) => s.me),
    lang = useApp((s) => s.language),
    signedIn = useApp((s) => s.signedIn),
    profiles = useProfiles();
  const chartKey = profiles.data?.find((p) => p.is_self)?.chart_key;
  useEffect(() => {
    if (!me || !chartKey) return;
    const key = "notification-chart";
    if (privateStorage.getItem(key) !== chartKey) {
      privateStorage.setItem(key, chartKey);
      privateStorage.removeItem("notification-sync");
      void synchronizeNotifications(me, lang).catch(() => {});
    }
  }, [chartKey, me, lang]);
  useEffect(() => {
    if (!signedIn || !me || !me.notification_prefs.enabled) {
      void TaskManager.isTaskRegisteredAsync(notificationTask)
        .then((registered) =>
          registered
            ? BackgroundTask.unregisterTaskAsync(notificationTask)
            : undefined,
        )
        .catch(() => {});
      return;
    }
    const sync = () => {
      if (!me.current_place) return;
      const date = new Intl.DateTimeFormat("en-CA", {
        timeZone: me.current_place.tz,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }).format(new Date());
      const key = `${date}:${lang}:${me.current_place.place_id}:${JSON.stringify(me.notification_prefs)}`;
      if (privateStorage.getItem("notification-sync") !== key)
        void synchronizeNotifications(me, lang).catch(() => {});
    };
    sync();
    if (me.notification_prefs.enabled)
      void BackgroundTask.registerTaskAsync(notificationTask, {
        minimumInterval: 1440,
      }).catch(() => {});
    const state = AppState.addEventListener("change", (value) => {
      if (value === "active") sync();
    });
    return () => state.remove();
  }, [me, lang, signedIn]);
  useEffect(() => {
    if (!signedIn || !me) return;
    const open = (response: Notifications.NotificationResponse) => {
      const data = response.notification.request.content.data;
      if (
        !data ||
        typeof data.view !== "string" ||
        typeof data.ref !== "string"
      )
        return;
      const id = response.notification.request.identifier;
      if (privateStorage.getItem("last-notification-open") === id) return;
      privateStorage.setItem("last-notification-open", id);
      router.push(
        resolveRoute(
          notificationRoute(
            { view: data.view, ref: data.ref },
            me.self_profile_id ?? undefined,
          ),
        ),
      );
    };
    const listener =
      Notifications.addNotificationResponseReceivedListener(open);
    void Notifications.getLastNotificationResponseAsync()
      .then((value) => {
        if (value) open(value);
      })
      .catch(() => {});
    return () => {
      listener.remove();
    };
  }, [me, lang, signedIn]);
  return null;
}
