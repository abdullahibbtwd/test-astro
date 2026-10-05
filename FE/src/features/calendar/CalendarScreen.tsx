import { resolveRoute } from "../../lib/routes";
import { ContentList } from "../../design/components/ContentList";
import DateTimePicker from "@react-native-community/datetimepicker";
import { Platform } from "react-native";
import { DatePager } from "../../design/components/DatePager";
import { useApp } from "../../lib/state";
import { formatMonth } from "../../lib/dates";
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
import { calendarRows } from "../shared/Blocks";
import { MonthGrid } from "./MonthGrid";
import type { CalendarMonth, Goal } from "../../../contracts/spec-types";
export default function CalendarScreen({
  embedded = false,
}: {
  embedded?: boolean;
}) {
  const lang = useApp((s) => s.language);
  const [picking, setPicking] = useState(false);
  const Surface = embedded ? ContentList : Screen;
  const params = useLocalSearchParams<{ month?: string; date?: string }>(),
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
    <Surface
      {...(embedded ? {} : { list: true, back: true, title: t("calendar") })}
    >
      <DatePager
        label={formatMonth(month, lang)}
        previousDisabled={month <= today.slice(0, 7)}
        nextDisabled={month >= shiftMonth(today.slice(0, 7), 11)}
        onPrevious={() => setMonth(shiftMonth(month, -1))}
        onNext={() => setMonth(shiftMonth(month, 1))}
        onPick={() => setPicking(true)}
        onToday={
          month === today.slice(0, 7)
            ? undefined
            : () => setMonth(today.slice(0, 7))
        }
      />
      {picking && (
        <DateTimePicker
          mode="date"
          value={new Date(`${month}-15T12:00:00`)}
          minimumDate={new Date(`${today}T12:00:00`)}
          maximumDate={
            new Date(`${shiftMonth(today.slice(0, 7), 11)}-28T12:00:00`)
          }
          onChange={(_, date) => {
            if (Platform.OS !== "ios") setPicking(false);
            if (date)
              setMonth(
                `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`,
              );
          }}
        />
      )}
      {picking && Platform.OS === "ios" && (
        <Button label={t("done")} onPress={() => setPicking(false)} />
      )}
      <ScrollView
        horizontal
        style={{ flexGrow: 0 }}
        showsHorizontalScrollIndicator={false}
      >
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
            onPress={() => router.push(resolveRoute(`${path}?profile=${id}`))}
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
              selected={params.date}
              days={data.days.map((day) => ({
                date: day.date,
                band: goal ? day.goals[goal] : day.tone,
                label: goal
                  ? cat.data.day_bands[day.goals[goal]]
                  : day.tone_label,
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
                        ? e.id.endsWith(":full")
                          ? "●"
                          : "○"
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
            {calendarRows(
              [
                ...data.lunations,
                ...data.eclipses,
                ...data.retrograde_periods,
                ...data.major_transits,
                ...data.periods,
              ],
              id,
              lang,
            )}
          </>
        )
      )}
      <ErrorNotice
        error={query.error}
        retry={() => {
          void query.refetch();
        }}
      />
    </Surface>
  );
}
