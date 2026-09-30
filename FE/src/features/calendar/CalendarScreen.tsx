import { ScrollView, View } from "react-native";
import { useEffect, useState } from "react";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import {
  Screen,
  Txt,
  Choices,
  Chip,
  Button,
  Skeleton,
  ErrorNotice,
} from "../../design/components";
import { useCatalogue } from "../../api/hooks";
import { useApi } from "../../api/resource";
import { mockToday } from "../../api/client";
import { todayLocal } from "../../lib/dates";
import { shiftMonth } from "../../lib/calendar";
import { useProfile } from "../shared/useProfile";
import { ItemRows } from "../shared/Blocks";
import { MonthGrid } from "./MonthGrid";
import type { CalendarMonth, Goal } from "../../../contracts/spec-types";
export default function CalendarScreen() {
  const params = useLocalSearchParams<{ month?: string }>(),
    { t } = useTranslation(),
    { id, tz } = useProfile(),
    cat = useCatalogue();
  const today = todayLocal(tz, mockToday),
    [month, setMonth] = useState(params.month ?? today.slice(0, 7)),
    [goal, setGoal] = useState<Goal | null>(null);
  useEffect(() => {
    if (params.month) setMonth(params.month);
  }, [params.month]);
  const query = useApi<CalendarMonth>(
      `/profiles/${id}/calendar/months/${month}`,
      "CalendarMonth",
      !!id,
    ),
    data = query.data;
  return (
    <Screen back title={t("calendar")}>
      <Choices>
        <Button
          secondary
          label={t("previous")}
          disabled={month <= today.slice(0, 7)}
          onPress={() => setMonth(shiftMonth(month, -1))}
        />
        <Txt kind="title">{month}</Txt>
        <Button
          secondary
          label={t("next")}
          disabled={month >= shiftMonth(today.slice(0, 7), 11)}
          onPress={() => setMonth(shiftMonth(month, 1))}
        />
      </Choices>
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <View style={{ flexDirection: "row", gap: 8 }}>
          <Chip
            label={t("all")}
            selected={!goal}
            onPress={() => setGoal(null)}
          />
          {Object.entries(cat.data.goals).map(([key, label]) => (
            <Chip
              key={key}
              label={label}
              selected={goal === key}
              onPress={() => setGoal(key as Goal)}
            />
          ))}
        </View>
      </ScrollView>
      <Choices>
        {(
          [
            ["/best-days", "bestDays"],
            ["/calendar/periods", "periods"],
            ["/calendar/year", "yearOverview"],
          ] as const
        ).map(([path, label]) => (
          <Button
            key={path}
            secondary
            label={t(label)}
            onPress={() => router.push(`${path}?profile=${id}` as never)}
          />
        ))}
      </Choices>
      {query.isPending ? (
        <Skeleton />
      ) : (
        data && (
          <>
            <MonthGrid
              month={month}
              today={today}
              days={data.days.map((day) => ({
                date: day.date,
                band: goal ? day.goals[goal] : day.tone,
                label: goal
                  ? cat.data.day_bands[day.goals[goal]]
                  : day.tone_label,
                tinted:
                  !!goal && day.active_periods.some((p) => p.goal === goal),
                icons: day.events
                  .slice()
                  .sort(
                    (a, b) =>
                      Number(b.kind === "eclipse") -
                      Number(a.kind === "eclipse"),
                  )
                  .slice(0, 3)
                  .map((e) =>
                    e.kind === "eclipse"
                      ? "◐"
                      : e.kind === "lunation"
                        ? "○"
                        : e.kind === "station"
                          ? "↺"
                          : "·",
                  )
                  .join(" "),
              }))}
              onSelect={(date) =>
                router.push(`/calendar/day/${date}?profile=${id}`)
              }
            />
            <Txt kind="title">{t("thisMonth")}</Txt>
            <ItemRows
              profile={id}
              items={[
                ...data.lunations,
                ...data.eclipses,
                ...data.retrograde_periods,
                ...data.major_transits,
                ...data.periods,
              ]}
            />
          </>
        )
      )}
      <ErrorNotice
        error={query.error}
        retry={() => {
          void query.refetch();
        }}
      />
    </Screen>
  );
}
