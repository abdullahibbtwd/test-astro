import { useState } from "react";
import { Alert } from "react-native";
import * as Notifications from "expo-notifications";
import { prepareNotifications, addReminder } from "../../lib/notifications";
import { useActions } from "../../api/hooks";
import { useApp } from "../../lib/state";
import type { Activity } from "../../../contracts/spec-types";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import {
  Screen,
  Txt,
  Card,
  Button,
  Skeleton,
  ErrorNotice,
} from "../../design/components";
import { useApi } from "../../api/resource";
import { useFlags } from "../../lib/flags";
import { useProfile } from "../shared/useProfile";
import { Generated } from "../shared/Blocks";
import type { BestDayDetail } from "../../../contracts/spec-types";
export default function BestDayScreen() {
  const { activity, date } = useLocalSearchParams<{
      activity: string;
      date: string;
    }>(),
    { id } = useProfile(),
    { t } = useTranslation(),
    flags = useFlags(),
    query = useApi<BestDayDetail>(
      `/profiles/${id}/best-days/${activity}/${date}`,
      "BestDayDetail",
      !!id,
    ),
    data = query.data;
  const [reminderError, setReminderError] = useState<unknown>();
  const actions = useActions(),
    app = useApp();
  const remind = async () => {
    if (!data || !app.me) return;
    try {
      await prepareNotifications();
      const permission = await Notifications.requestPermissionsAsync();
      if (!permission.granted) {
        Alert.alert(t("notifications"), t("goSettings"));
        return;
      }
      const me = app.me.notification_prefs.enabled
        ? app.me
        : await actions.patchMe({
            notification_prefs: { ...app.me.notification_prefs, enabled: true },
          });
      const saved = await addReminder(
        {
          id: `manual:${activity}:${date}`,
          manual: true,
          type: "favorable_window",
          priority: 1,
          trigger_date: date,
          suggested_time: "09:00",
          text: `${data.activity_label} · ${date}`,
          deep_link: {
            view: "best_days",
            ref: `win:${activity as Activity}:${date}`,
          },
        },
        me,
        app.language,
      );
      Alert.alert(t(saved ? "reminderSet" : "reminderLimit"));
    } catch (e) {
      setReminderError(e);
    }
  };
  return (
    <Screen back title={data?.activity_label ?? t("bestDays")}>
      <Txt>{date}</Txt>
      {query.isPending && <Skeleton />}
      {data && (
        <>
          <Txt kind="title">{data.grade_label}</Txt>
          {data.reasons.positive.length > 0 && (
            <Card>
              <Txt kind="title">{t("whatHelps")}</Txt>
              {data.reasons.positive.map((text, i) => (
                <Txt key={i}>{text}</Txt>
              ))}
            </Card>
          )}
          {data.reasons.negative.length > 0 && (
            <Card>
              <Txt kind="title">{t("whatHarder")}</Txt>
              {data.reasons.negative.map((text, i) => (
                <Txt key={i}>{text}</Txt>
              ))}
            </Card>
          )}
          <Generated
            part={data.text}
            retry={() => {
              void query.retry();
            }}
          >
            {(part) => <Txt kind="reading">{part.text}</Txt>}
          </Generated>
          <Button
            secondary
            label={t("remindMe")}
            onPress={() => {
              void remind();
            }}
          />
          {flags.askAstrology && (
            <Button
              secondary
              label={t("askDay")}
              onPress={() =>
                router.push(
                  `/ask?profile=${id}&activity=${activity}&date=${date}`,
                )
              }
            />
          )}
        </>
      )}
      <ErrorNotice
        error={query.error ?? reminderError}
        retry={() => {
          void query.refetch();
        }}
      />
    </Screen>
  );
}
