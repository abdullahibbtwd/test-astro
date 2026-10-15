import { View } from "react-native";
import { BandChip } from "../../design/components/BandChip";
import { useApp } from "../../lib/state";
import {
  formatDay,
  formatMonth,
  formatShort,
  formatRange,
} from "../../lib/dates";
import { mockToday } from "../../api/client";
import { todayLocal } from "../../lib/dates";
import { Fragment } from "react";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import {
  Screen,
  Txt,
  Row,
  Choices,
  Chip,
  Skeleton,
  ErrorNotice,
} from "../../design/components";
import { useApi } from "../../api/resource";
import { useCatalogue } from "../../api/hooks";
import { useProfile } from "../shared/useProfile";
import { MonthGrid } from "./MonthGrid";
import type { BestDaysOverview } from "../../../contracts/spec-types";
export default function BestDaysScreen() {
  const lang = useApp((s) => s.language);
  const { activity } = useLocalSearchParams<{ activity?: string }>(),
    { id, tz } = useProfile(),
    { t } = useTranslation(),
    cat = useCatalogue(),
    query = useApi<BestDaysOverview>(
      `/profiles/${id}/best-days`,
      "BestDaysOverview",
      !!id,
    ),
    today = todayLocal(tz, mockToday),
    data = query.data,
    selected = data?.activities.find((item) => item.activity === activity);
  const open = (date: string) =>
    router.push(`/best-days/${activity}/${date}?profile=${id}`);
  return (
    <Screen back title={selected?.label ?? t("bestDays")}>
      <Txt muted>{t("next90")}</Txt>
      {query.isPending && <Skeleton />}
      {data &&
        !activity &&
        data.activities.map((item) => (
          <View key={item.activity} style={{gap:8}}><Row
            label={item.label}
            detail={`${
              item.top_days.find((date) => date >= today)
                ? formatDay(
                    item.top_days.find((date) => date >= today)!,
                    lang,
                  )
                : ""
            } · ${t("goodDaysCount", { count: item.days.filter((d) => d.grade === "good" || d.grade === "excellent").length })}`}
            onPress={() =>
              router.push(`/best-days/${item.activity}?profile=${id}`)
            }
          />
          {(() => {const next=item.days.find(day=>day.date === item.top_days.find(date=>date>=today));return next ? <BandChip band={next.grade} label={cat.data.grades[next.grade]}/> : null;})()}
          </View>
        ))}
      {selected && (
        <>
          {[...new Set(selected.days.map((day) => day.date.slice(0, 7)))].map(
            (month) => (
              <Fragment key={month}>
                <Txt key={`title${month}`} kind="title">
                  {formatMonth(month, lang)}
                </Txt>
                <MonthGrid
                  bestDays
                  key={month}
                  month={month}
                  days={selected.days
                    .filter((day) => day.date >= today)
                    .map((day) => ({
                      date: day.date,
                      band: day.grade,
                      label: cat.data.grades[day.grade],
                    }))}
                  onSelect={open}
                />
              </Fragment>
            ),
          )}
          {!!selected.top_days.length && (
            <>
              <Txt kind="title">{t("topDays")}</Txt>
              <Choices>
                {selected.top_days
                  .filter((date) => date >= today)
                  .map((date) => (
                    <Chip
                      role="button"
                      key={date}
                      label={formatShort(date, lang)}
                      selected={false}
                      onPress={() => open(date)}
                    />
                  ))}
              </Choices>
            </>
          )}
          {!!selected.windows.length && (
            <>
              <Txt kind="title">{t("goodWindows")}</Txt>
              {selected.windows.map((window) => (
                <Row
                  key={window.start}
                  label={formatRange(window.start, window.end, lang)}
                  onPress={() => open(window.start)}
                />
              ))}
            </>
          )}
          {!!selected.avoid_days.length && (
            <>
              <Txt kind="title">{t("avoidDays")}</Txt>
              <Choices>
                {selected.avoid_days.map((date) => (
                  <Chip
                    role="button"
                    key={date}
                    label={formatShort(date, lang)}
                    selected={false}
                    onPress={() => open(date)}
                  />
                ))}
              </Choices>
            </>
          )}
        </>
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
