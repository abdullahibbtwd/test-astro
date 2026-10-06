import { space as dsSpace } from "../../design-system/theme/tokens";
import { BandChip } from "../../design/components/BandChip";
import { View } from "react-native";
import { useApp } from "../../lib/state";
import { formatDay } from "../../lib/dates";
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
import { useFlags } from "../../lib/flags";
import { useProfile } from "../shared/useProfile";
import { Generated, ItemRows, MoonBlock } from "../shared/Blocks";
import type { CalendarDayDetail } from "../../../contracts/spec-types";
export default function DayScreen() {
  const lang = useApp((s) => s.language);
  const { date } = useLocalSearchParams<{ date: string }>(),
    { id } = useProfile(),
    { t } = useTranslation(),
    cat = useCatalogue(),
    flags = useFlags(),
    query = useApi<CalendarDayDetail>(
      `/profiles/${id}/calendar/days/${date}`,
      "CalendarDayDetail",
      !!id,
    ),
    data = query.data;
  return (
    <Screen back title={formatDay(date, lang, { weekday: true })}>
      {query.isPending && <Skeleton />}
      {data && (
        <>
          <BandChip band={data.tone} label={data.tone_label} />
          <Generated
            part={data.day_note}
            retry={() => {
              void query.retry();
            }}
          >
            {(part) => <Txt kind="reading">{part.text}</Txt>}
          </Generated>
          <MoonBlock moon={data.moon} />
          {data.retrograde.length > 0 && (
            <Txt>
              {cat.data.terms.retrograde}:{" "}
              {data.retrograde
                .map((body) => cat.data.bodies[body])
                .filter(Boolean)
                .join(", ")}
            </Txt>
          )}
          <ItemRows profile={id} items={[...data.events, ...data.transits]} />
          {data.active_periods.map((period) => (
            <Button
              key={period.id}
              secondary
              label={`${cat.data.goals[period.goal]} · ${t(period.kind)}`}
              onPress={() =>
                router.push(
                  `/calendar/item/${encodeURIComponent(period.id)}?profile=${id}`,
                )
              }
            />
          ))}
          <Txt kind="title">{t("lifeAreas")}</Txt>
          {Object.entries(data.goals).map(([goal, band]) => (
            <View key={goal} style={{ gap: dsSpace[2] }}>
              <Txt>{cat.data.goals[goal as keyof typeof cat.data.goals]}</Txt>
              <BandChip band={band} label={cat.data.day_bands[band]} />
            </View>
          ))}
          <Choices>
            {data.best_activities.map((activity) => (
              <Chip
                role="button"
                key={activity.activity}
                label={`${activity.label} · ${cat.data.grades[activity.grade]}`}
                selected={false}
                onPress={() =>
                  router.push(
                    `/best-days/${activity.activity}/${date}?profile=${id}`,
                  )
                }
              />
            ))}
          </Choices>
          {flags.askAstrology && (
            <Button
              label={t("askDay")}
              onPress={() => router.push(`/ask?profile=${id}&date=${date}`)}
            />
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
