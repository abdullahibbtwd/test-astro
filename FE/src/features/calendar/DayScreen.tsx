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
    <Screen back title={date}>
      {query.isPending && <Skeleton />}
      {data && (
        <>
          <Txt kind="title">{data.tone_label}</Txt>
          <Generated
            part={data.day_note}
            retry={() => {
              void query.retry();
            }}
          >
            {(part) => <Txt kind="reading">{part.text}</Txt>}
          </Generated>
          <MoonBlock moon={data.moon} />
          <Choices>
            {data.retrograde
              .filter((body) => !!cat.data.bodies[body])
              .map((body) => (
                <Chip
                  key={body}
                  label={`${cat.data.bodies[body]} · ${cat.data.terms.retrograde}`}
                  selected={false}
                  onPress={() => router.push("/(tabs)/chart")}
                />
              ))}
          </Choices>
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
            <Txt key={goal}>
              {cat.data.goals[goal as keyof typeof cat.data.goals]} ·{" "}
              {cat.data.day_bands[band]}
            </Txt>
          ))}
          <Choices>
            {data.best_activities.map((activity) => (
              <Chip
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
