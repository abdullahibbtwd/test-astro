import { space as dsSpace, radius as dsRadius } from "../../design-system/theme/tokens";
import { useApp } from "../../lib/state";
import { formatRange } from "../../lib/dates";
import { Pressable, View } from "react-native";
import { useEffect, useState } from "react";
import { Sheet } from "../../design/components/Sheet";
import { BandChip } from "../../design/components/BandChip";
import { useTheme } from "../../design/theme";
import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import { useApi } from "../../api/resource";
import { useCatalogue } from "../../api/hooks";
import { useFlags } from "../../lib/flags";
import {
  Txt,
  Card,
  Choices,
  Chip,
  Button,
  Row,
  Skeleton,
  ErrorNotice,
} from "../../design/components";
import {
  Generated,
  Score,
  ItemRows,
  MoonBlock,
  DateLinks,
  Domains,
} from "../shared/Blocks";
import type {
  DayForecast,
  MonthForecast,
  YearForecast,
  Lens,
  Goal,
} from "../../../contracts/spec-types";
export function DayView({
  profile,
  date,
  lens,
  focusArea,
}: {
  profile: string;
  date: string;
  lens: Lens;
  focusArea?: string;
}) {
  const { t } = useTranslation(),
    cat = useCatalogue(),
    flags = useFlags(),
    query = useApi<DayForecast>(
      `/profiles/${profile}/forecast/day?date=${date}&lens=${lens}`,
      "DayForecast",
    ),
    data = query.data;
  const [area, setArea] = useState<Goal | null>(
      focusArea && Object.hasOwn(cat.data.goals, focusArea)
        ? (focusArea as Goal)
        : null,
    ),
    colors = useTheme();
  const linkedArea =
    focusArea && Object.hasOwn(cat.data.goals, focusArea)
      ? (focusArea as Goal)
      : null;
  useEffect(() => {
    if (linkedArea) setArea(linkedArea);
  }, [linkedArea]);
  const first: Goal[] = ["love", "family", "career", "money"],
    goals = [
      ...first,
      ...Object.keys(cat.data.goals).filter(
        (key) => !first.includes(key as Goal),
      ),
    ] as Goal[];
  // A deep-linked area is available in its sheet without changing the familiar tile order.
  return (
    <>
      {query.isPending && <Skeleton />}
      {data && (
        <>
          <Card>
            <Score
              label={t("dayOverview")}
              score={data.score_10}
              band={data.tone_label}
              bandKey={data.tone}
            />
            <Generated
              part={data.day_note}
              retry={() => {
                void query.retry();
              }}
            >
              {(part) => <Txt kind="reading">{part.text}</Txt>}
            </Generated>
          </Card>
          <Generated
            part={data.reading}
            retry={() => {
              void query.retry();
            }}
          >
            {(part) => <Txt kind="reading">{part.text}</Txt>}
          </Generated>
          <Txt kind="title">{t("lifeAreas")}</Txt>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: dsSpace[2] }}>
            {goals.map(
              (goal) =>
                data.areas[goal] && (
                  <Pressable
                    key={goal}
                    accessibilityRole="button"
                    accessibilityLabel={`${cat.data.goals[goal]}, ${data.areas[goal].label}`}
                    onPress={() => setArea(goal)}
                    style={{
                      width: "48.5%",
                      minHeight: 88,
                      padding: dsSpace[3],
                      gap: dsSpace[2],
                      borderRadius: dsRadius.md,
                      borderWidth: 1,
                      borderColor: colors.hair,
                      backgroundColor: colors.surface,
                    }}
                  >
                    <Txt>{cat.data.goals[goal]}</Txt>
                    <BandChip
                      band={data.areas[goal].band}
                      label={data.areas[goal].label}
                    />
                    {flags.dayScoreNumbers && (
                      <View
                        accessibilityLabel={`${data.areas[goal].score_10} / 10`}
                        style={{ flexDirection: "row", gap: 2 }}
                      >
                        {Array.from({ length: 10 }, (_, i) => (
                          <View
                            key={i}
                            style={{
                              flex: 1,
                              height: 4,
                              backgroundColor:
                                i < data.areas[goal].score_10
                                  ? colors.accent
                                  : colors.hair,
                            }}
                          />
                        ))}
                      </View>
                    )}
                  </Pressable>
                ),
            )}
          </View>
          <Sheet
            open={!!area}
            title={area ? cat.data.goals[area] : ""}
            onClose={() => {
              setArea(null);
              if (focusArea) router.setParams({ area: undefined });
            }}
          >
            {area &&
              data.areas[area]?.drivers.map((driver, i) => (
                <Txt key={i}>{driver}</Txt>
              ))}
            <Button
              label={t("openInCalendar")}
              onPress={() => {
                setArea(null);
                router.push(`/calendar/day/${date}?profile=${profile}`);
              }}
            />
          </Sheet>
          <Domains items={data.domains} />
          <Txt kind="title">{t("importantTransits")}</Txt>
          {!data.transits.length && !data.events.length && (
            <Txt muted>{t("noTransits")}</Txt>
          )}
          <ItemRows
            profile={profile}
            items={[...data.transits].sort(
              (a, b) =>
                Number(b.importance === "major") -
                Number(a.importance === "major"),
            )}
          />
          <ItemRows profile={profile} items={data.events} />
          <MoonBlock moon={data.moon} />
          <Choices>
            {data.retrograde
              .filter((body) => !!cat.data.bodies[body])
              .map((body) => (
                <Chip role="button"
                  key={body}
                  label={`${cat.data.bodies[body]} · ${cat.data.terms.retrograde}`}
                  selected={false}
                  onPress={() => router.push("/(tabs)/chart")}
                />
              ))}
          </Choices>
          {data.advice && (
            <Card>
              <Txt kind="title">{t("advice")}</Txt>
              <Txt kind="reading">{data.advice}</Txt>
            </Card>
          )}
          {!!data.best_activities.length && (
            <>
              <Txt kind="title">{t("goodFor")}</Txt>
              <Choices>
                {data.best_activities.map((activity) => (
                  <Chip role="button"
                    key={activity.activity}
                    label={`${activity.label} · ${cat.data.grades[activity.grade]}`}
                    selected={false}
                    onPress={() =>
                      router.push(
                        `/best-days/${activity.activity}/${date}?profile=${profile}`,
                      )
                    }
                  />
                ))}
              </Choices>
            </>
          )}
          {flags.askAstrology && (
            <Button
              secondary
              label={t("askDay")}
              onPress={() =>
                router.push(`/ask?date=${date}&profile=${profile}`)
              }
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
    </>
  );
}
export function MonthView({
  profile,
  month,
  lens,
}: {
  profile: string;
  month: string;
  lens: Lens;
}) {
  const { t } = useTranslation(),
    flags = useFlags(),
    query = useApi<MonthForecast>(
      `/profiles/${profile}/forecast/month?month=${month}&lens=${lens}`,
      "MonthForecast",
    ),
    data = query.data;
  return (
    <>
      {query.isPending && <Skeleton />}
      {data && (
        <>
          <Generated
            part={data.reading}
            retry={() => {
              void query.retry();
            }}
          >
            {(part) => (
              <>
                <Txt kind="title">{t("mainTheme")}</Txt>
                <Txt kind="reading">{part.overview}</Txt>
                <Txt kind="title">{part.focus_title}</Txt>
                <Txt kind="reading">{part.focus}</Txt>
                {(["early", "mid", "late"] as const).map((key) => (
                  <Card key={key}>
                    <Txt muted>
                      {data.segments[key].from} – {data.segments[key].to}
                    </Txt>
                    <Txt kind="reading">{part[key]}</Txt>
                  </Card>
                ))}
              </>
            )}
          </Generated>
          <Domains items={data.domains} />
          {!!data.highlights.favorable_days.length && (
            <>
              <Txt kind="title">{t("favorableDays")}</Txt>
              <DateLinks
                dates={data.highlights.favorable_days}
                profile={profile}
              />
            </>
          )}
          {!!data.highlights.challenging_days.length && (
            <>
              <Txt kind="title">{t("challengingDays")}</Txt>
              <DateLinks
                dates={data.highlights.challenging_days}
                profile={profile}
              />
            </>
          )}
          <ItemRows profile={profile} items={data.highlights.periods} />
          <ItemRows profile={profile} items={data.highlights.major_transits} />
          <ItemRows
            profile={profile}
            items={[
              ...data.highlights.lunations,
              ...data.highlights.eclipses,
              ...data.highlights.retrogrades,
            ]}
          />
          {flags.askAstrology && (
            <Button
              secondary
              label={t("ask")}
              onPress={() =>
                router.push(`/ask?profile=${profile}&month=${month}`)
              }
            />
          )}
          <Button
            secondary
            label={t("calendar")}
            onPress={() =>
              router.push(`/calendar?month=${month}&profile=${profile}`)
            }
          />
        </>
      )}
      <ErrorNotice
        error={query.error}
        retry={() => {
          void query.refetch();
        }}
      />
    </>
  );
}
export function YearView({
  profile,
  month,
  lens,
}: {
  profile: string;
  month: string;
  lens: Lens;
}) {
  const lang = useApp(s => s.language);
  const { t } = useTranslation(),
    flags = useFlags(),
    query = useApi<YearForecast>(
      `/profiles/${profile}/forecast/year?from=${month}&lens=${lens}`,
      "YearForecast",
    ),
    data = query.data;
  return (
    <>
      {query.isPending && <Skeleton />}
      {data && (
        <>
          <Txt kind="title">
            {formatRange(data.from, data.to, lang)}
          </Txt>
          <Generated
            part={data.reading}
            retry={() => {
              void query.retry();
            }}
          >
            {(part) => (
              <>
                <Txt kind="reading">{part.overview}</Txt>
                <Txt kind="title">{part.focus_title}</Txt>
                <Txt kind="reading">{part.focus}</Txt>
                {data.quarters.map((q) => (
                  <Card key={q.key}>
                    <Txt muted>
                      {formatRange(q.from, q.to, lang)}
                    </Txt>
                    <Txt kind="reading">{part[q.key]}</Txt>
                  </Card>
                ))}
              </>
            )}
          </Generated>
          <Domains items={data.domains} />
          <ItemRows
            profile={profile}
            items={[
              ...data.highlights.strongest_periods,
              ...data.highlights.challenging_periods,
              ...data.highlights.key_events,
              ...data.highlights.retrogrades,
            ]}
          />
          <Txt kind="title">{t("monthByMonth")}</Txt>
          {data.months.map((m) => (
            <Row
              key={m.month}
              label={m.label}
              onPress={() =>
                router.push(`/forecast/month/${m.month}?profile=${profile}`)
              }
            />
          ))}
        </>
      )}
      {flags.solarReturn && (
        <Button
          secondary
          label={t("solar_return")}
          onPress={() =>
            router.push(`/solar-return/${month.slice(0, 4)}?profile=${profile}`)
          }
        />
      )}
      <ErrorNotice
        error={query.error}
        retry={() => {
          void query.refetch();
        }}
      />
    </>
  );
}
