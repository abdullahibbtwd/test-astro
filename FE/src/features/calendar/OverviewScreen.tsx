import { radius as dsRadius } from "../../design-system/theme/tokens";
import { ContentSections } from "../../design/components/ContentList";
import { useApp } from "../../lib/state";
import { formatMonth, formatRange } from "../../lib/dates";
import { mockToday } from "../../api/client";
import { todayLocal } from "../../lib/dates";
import { shiftMonth } from "../../lib/calendar";
import { useState } from "react";
import { Pressable, ScrollView, View } from "react-native";
import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import {
  Screen,
  Txt,
  Button,
  Choices,
  Skeleton,
  ErrorNotice,
} from "../../design/components";
import { useApi } from "../../api/resource";
import { useCatalogue } from "../../api/hooks";
import { useProfile } from "../shared/useProfile";
import { calendarRows } from "../shared/Blocks";
import { useTheme } from "../../design/theme";
import { bandColor } from "../../design/bands";
import type { CalendarYear, PeriodRef } from "../../../contracts/spec-types";
export default function OverviewScreen({
  periods = false,
}: {
  periods?: boolean;
}) {
  const lang = useApp((s) => s.language);
  const { id, tz } = useProfile(),
    { t } = useTranslation(),
    cat = useCatalogue(),
    c = useTheme(),
    [list, setList] = useState(false),
    query = useApi<CalendarYear>(
      `/profiles/${id}/calendar/year`,
      "CalendarYear",
      !!id,
    ),
    data = query.data;
  const periodQuery = useApi<PeriodRef[]>(
    `/profiles/${id}/calendar/periods`,
    "PeriodRef[]",
    !!id && periods,
  );
  const values = periods ? periodQuery.data : data?.periods;
  if (!periods || list) {
    const events = periods
      ? (values ?? [])
      : data
        ? [
            ...data.eclipses,
            ...data.lunations,
            ...data.retrograde_periods,
            ...data.major_transits,
            ...data.periods,
          ]
        : [];
    const groups = new Map<string, typeof events>();
    for (const event of events) {
      const month = String(
        "start" in event
          ? event.start
          : "date" in event
            ? event.date
            : (event.id.match(/\d{4}-\d{2}-\d{2}/)?.[0] ?? ""),
      ).slice(0, 7);
      groups.set(month, [...(groups.get(month) ?? []), event]);
    }
    return (
      <Screen
        scroll={false}
        back
        title={t(periods ? "periods" : "yearOverview")}
      >
        <ContentSections
          header={
            <>
              {periods && (
                <Button
                  secondary
                  label={t("timeline")}
                  onPress={() => setList(false)}
                />
               )}
              {(query.isPending || (periods && periodQuery.isPending)) && (
                <Skeleton />
              )}
              <ErrorNotice
                error={query.error ?? periodQuery.error}
                retry={() => {
                  void query.refetch();
                  if (periods) void periodQuery.refetch();
                }}
              />
            </>
          }
          sections={[...groups]
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([month, items]) => ({
              key: month,
              header: (
                <Txt kind="title">
                  {month ? formatMonth(month, lang) : t("periods")}
                </Txt>
              ),
              children: calendarRows(items, id, lang),
            }))}
        />
      </Screen>
    );
  }
  return (
    <Screen list back title={t(periods ? "periods" : "yearOverview")}>
      {(query.isPending || (periods && periodQuery.isPending)) && <Skeleton />}
      {data && (
        <>
          {periods && (
            <Choices>
              <Button
                secondary
                label={t("timeline")}
                onPress={() => setList(false)}
              />
              <Button
                secondary
                label={t("list")}
                onPress={() => setList(true)}
              />
            </Choices>
          )}
          {periods && !list ? (
            <ScrollView horizontal>
              <View style={{ width: 1000, gap: 20 }}>
                <View style={{ flexDirection: "row" }}>
                  {Array.from({ length: 12 }, (_, i) => (
                    <Txt key={i} kind="caption" style={{ width: 1000 / 12 }}>
                      {formatMonth(
                        shiftMonth(data.horizon.from.slice(0, 7), i),
                        lang,
                      )}
                    </Txt>
                  ))}
                </View>
                {Object.entries(cat.data.goals).map(([goal, label]) => (
                  <View key={goal}>
                    <Txt>{label}</Txt>
                    <View
                      style={{
                        height: Math.max(
                          48,
                          (values?.filter((p) => p.goal === goal).length ?? 0) *
                            28,
                        ),
                        backgroundColor: c.surfaceAlt,
                      }}
                    >
                      {todayLocal(tz, mockToday) >= data.horizon.from &&
                        todayLocal(tz, mockToday) <= data.horizon.to && (
                          <View
                            pointerEvents="none"
                            style={{
                              position: "absolute",
                              top: 0,
                              bottom: 0,
                              width: 2,
                              backgroundColor: c.accent,
                              left:
                                ((Date.parse(todayLocal(tz, mockToday)) -
                                  Date.parse(data.horizon.from)) /
                                  (Date.parse(data.horizon.to) -
                                    Date.parse(data.horizon.from) +
                                    86400000)) *
                                1000,
                            }}
                          />
                        )}
                      {values
                        ?.filter((p) => p.goal === goal)
                        .map((period, index) => {
                          const start = Date.parse(data.horizon.from),
                            span =
                              Date.parse(data.horizon.to) - start + 86400000,
                            left = Math.max(
                              0,
                              ((Date.parse(period.start) - start) / span) *
                                1000,
                            ),
                            right = Math.min(
                              1000,
                              ((Date.parse(period.end) + 86400000 - start) /
                                span) *
                                1000,
                            );
                          return (
                            <Pressable
                              hitSlop={12}
                              key={period.id}
                              accessibilityRole="button"
                              accessibilityLabel={`${period.label}, ${formatRange(period.start, period.end, lang)}`}
                              onPress={() =>
                                router.push(
                                  `/calendar/item/${encodeURIComponent(period.id)}?profile=${id}`,
                                )
                              }
                              style={{
                                position: "absolute",
                                left,
                                top: index * 28,
                                width: Math.max(4, right - left),
                                height: period.strength === "strong" ? 22 : 14,
                                backgroundColor: bandColor(
                                  period.kind,
                                  c.dark,
                                ),
                                borderRadius: dsRadius.card,
                              }}
                            />
                          );
                        })}
                    </View>
                  </View>
                ))}
              </View>
            </ScrollView>
          ) : periods ? (
            Object.entries(cat.data.goals).map(([goal, label]) => (
              <View key={goal}>
                <Txt kind="title">{label}</Txt>
                {calendarRows(
                  values?.filter((p) => p.goal === goal) ?? [],
                  id,
                  lang,
                )}
              </View>
            ))
          ) : (
            <>
              {calendarRows(
                [
                  ...data.eclipses,
                  ...data.lunations,
                  ...data.retrograde_periods,
                  ...data.major_transits,
                  ...data.periods,
                ],
                id,
                lang,
              )}
            </>
          )}
        </>
      )}
      <ErrorNotice
        error={query.error ?? periodQuery.error}
        retry={() => {
          void query.refetch();
          if (periods) void periodQuery.refetch();
        }}
      />
    </Screen>
  );
}
