import { bandColor } from "../../design/bands";
import type { ReactNode } from "react";
import { View } from "react-native";
import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import { Card, Txt, Row, Choices, Chip } from "../../design/components";
import { JobProgress } from "../../design/components/JobProgress";
import { useTheme } from "../../design/theme";
import { useFlags } from "../../lib/flags";
import { useApp } from "../../lib/state";
import { formatDate } from "../../lib/dates";
import type {
  GeneratedPart,
  CalendarEventRef,
  TransitEpisode,
  PeriodRef,
  RetrogradeRef,
  MoonInfo,
} from "../../../contracts/spec-types";
export function Generated<T>({
  part,
  retry,
  children,
}: {
  part: GeneratedPart<T> | null | undefined;
  retry: () => void;
  children: (data: T) => ReactNode;
}) {
  const { t } = useTranslation();
  if (!part) return null;
  if (part.status === "absent")
    return (
      <Txt muted>
        {t(
          part.absence.reason === "placidus_undefined_high_latitude"
            ? "relocationAbsent"
            : part.absence.reason === "time_not_exact"
              ? "exactTimeRequired"
              : "readingAbsent",
        )}
      </Txt>
    );
  if (part.status === "ready") return <>{children(part)}</>;
  const expired =
    part.status === "pending" &&
    Date.now() - Date.parse(part.job.created_at) >= 600000;
  return (
    <JobProgress
      job={part.status === "pending" ? part.job : undefined}
      failed={part.status === "failed" || expired}
      slow={
        part.status === "pending" &&
        Date.now() - Date.parse(part.job.created_at) >= 180000
      }
      retry={retry}
    />
  );
}
export function Score({
  label,
  score,
  band,
  bandKey,
}: {
  label: string;
  score: number;
  band: string;
  bandKey?: string;
}) {
  const flags = useFlags(),
    c = useTheme();
  return (
    <View
      accessible
      accessibilityLabel={`${label}${flags.dayScoreNumbers ? `, ${score} / 10` : ""}, ${band}`}
      style={{ gap: 8 }}
    >
      <Txt>{label}</Txt>
      {flags.dayScoreNumbers && (
        <>
          <Txt kind="title">{score} / 10</Txt>
          <View style={{ flexDirection: "row", gap: 3 }}>
            {Array.from({ length: 10 }, (_, i) => (
              <View
                key={i}
                style={{
                  flex: 1,
                  height: 5,
                  backgroundColor:
                    i < score
                      ? bandColor(bandKey ?? "quiet", c.bg === "#1A2030")
                      : c.hair,
                  borderRadius: 2,
                }}
              />
            ))}
          </View>
        </>
      )}
      <Txt kind="caption" muted>
        {band}
      </Txt>
    </View>
  );
}
export function ItemRows({
  items,
  profile,
}: {
  items: (CalendarEventRef | TransitEpisode | PeriodRef | RetrogradeRef)[];
  profile: string;
}) {
  const lang = useApp((s) => s.language);
  return (
    <View>
      {items.map((item) => (
        <Row
          key={item.id}
          label={item.label}
          detail={
            "start" in item
              ? `${formatDate(item.start, lang)} – ${formatDate(item.end, lang)}${"phase_label" in item ? ` · ${item.phase_label}` : ""}`
              : undefined
          }
          onPress={() =>
            router.push(
              `/calendar/item/${encodeURIComponent(item.id)}?profile=${profile}`,
            )
          }
        />
      ))}
    </View>
  );
}
export function MoonBlock({ moon }: { moon: MoonInfo }) {
  const { t } = useTranslation();
  return (
    <Card>
      <Txt kind="title">{t("moon")}</Txt>
      <Txt>
        {moon.phase_label} · {moon.sign_label}
      </Txt>
      {moon.void_of_course.map((range, i) => (
        <Txt key={i} muted>
          {t("voidMoon")}: {range.start}–{range.end}
        </Txt>
      ))}
    </Card>
  );
}
export function DateLinks({
  dates,
  profile,
}: {
  dates: string[];
  profile: string;
}) {
  const lang = useApp((s) => s.language);
  return (
    <Choices>
      {dates.map((date) => (
        <Chip
          key={date}
          label={formatDate(date, lang)}
          selected={false}
          onPress={() =>
            router.push(`/calendar/day/${date}?profile=${profile}`)
          }
        />
      ))}
    </Choices>
  );
}
export function Domains({
  items,
}: {
  items?: { key: string; title: string; text: string }[];
}) {
  return (
    <>
      {items?.map((item) => (
        <Card key={item.key}>
          <Txt kind="title">{item.title}</Txt>
          <Txt kind="reading">{item.text}</Txt>
        </Card>
      ))}
    </>
  );
}
