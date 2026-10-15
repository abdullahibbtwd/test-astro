import Constants from "expo-constants";
import { Platform } from "react-native";
import { useApp } from "./state";
import * as Notifications from "expo-notifications";
import { request } from "../api/client";
import { privateStorage } from "./storage";
import { shiftDate } from "./calendar";
import {
  planNotifications,
  type ReminderCandidate,
} from "./notification-policy";
import type {
  Me,
  NotificationCandidate,
  BirthProfile,
} from "../../contracts/spec-types";
export async function prepareNotifications() {
  if (Platform.OS === "android")
    await Notifications.setNotificationChannelAsync("astrology", {
      name: "Astrology",
      importance: Notifications.AndroidImportance.DEFAULT,
    });
}
const prefix = "astrology:";
let chain: Promise<unknown> = Promise.resolve();
export function synchronizeNotifications(me: Me, lang: string) {
  const run = async () => {
    if (!me.notification_prefs.enabled) {
      await Notifications.cancelAllScheduledNotificationsAsync();
      return [];
    }
    await prepareNotifications();
    const permission = await Notifications.getPermissionsAsync();
    if (!permission.granted) return [];
    const tz =
      me.current_place?.tz ??
      (
        await request<BirthProfile[]>("GET", "/profiles", "BirthProfile[]")
      ).find((p) => p.is_self)?.birth.tz;
    if (!tz) return [];
    const today = new Intl.DateTimeFormat("en-CA", {
      timeZone: tz,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(new Date());
    if (!me.self_profile_id) return [];
    const candidates = await request<NotificationCandidate[]>(
      "GET",
      `/profiles/${me.self_profile_id}/notification-candidates?from=${today}&to=${shiftDate(today, 14)}`,
      "NotificationCandidate[]",
    );
    const manual = (
      JSON.parse(
        privateStorage.getItem("manual-reminders") ?? "[]",
      ) as ReminderCandidate[]
    ).filter((item) => item.trigger_date >= today);
    privateStorage.setItem("manual-reminders", JSON.stringify(manual));
    const plan = planNotifications(
      [...candidates, ...manual],
      me.notification_prefs,
      tz,
    );
    const scheduled = await Notifications.getAllScheduledNotificationsAsync();
    const expected = new Map(plan.map((item) => [prefix + item.id, item]));
    for (const item of scheduled) {
      if (!item.identifier.startsWith(prefix)) continue;
      const next = expected.get(item.identifier);
      if (
        !next ||
        item.content.data?.instant !== next.instant ||
        item.content.body !== next.text
      )
        await Notifications.cancelScheduledNotificationAsync(item.identifier);
      else expected.delete(item.identifier);
    }
    for (const [identifier, item] of expected) {
      if (
        !useApp.getState().signedIn ||
        useApp.getState().me?.user_id !== me.user_id
      )
        return [];
      await Notifications.scheduleNotificationAsync({
        identifier,
        content: {
          title: Constants.expoConfig?.name ?? "Astrology",
          body: item.text,
          data: {
            ...item.deep_link,
            type: item.type,
            profile: me.self_profile_id,
            instant: item.instant,
            lang,
          },
        },
        trigger: {
          type: Notifications.SchedulableTriggerInputTypes.DATE,
          date: new Date(item.instant),
          channelId: "astrology",
        },
      });
    }
    privateStorage.setItem(
      "notification-sync",
      `${today}:${lang}:${me.current_place?.place_id ?? ""}:${JSON.stringify(me.notification_prefs)}`,
    );
    return plan;
  };
  const next = chain.then(run, run);
  chain = next.catch(() => {});
  return next;
}
export async function addReminder(
  candidate: ReminderCandidate,
  me: Me,
  lang: string,
) {
  const values = JSON.parse(
    privateStorage.getItem("manual-reminders") ?? "[]",
  ) as ReminderCandidate[];
  privateStorage.setItem(
    "manual-reminders",
    JSON.stringify([
      ...values.filter((x) => x.id !== candidate.id),
      { ...candidate, manual: true },
    ]),
  );
  const plan = await synchronizeNotifications(me, lang);
  return plan.some((item) => item.id === candidate.id);
}
