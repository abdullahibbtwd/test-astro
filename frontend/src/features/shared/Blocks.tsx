import { space as dsSpace } from "../../design-system/theme/tokens";
import { Divider } from "../../design-system/components/Ornament";
import { routes } from "../../lib/routes";
import { BandChip } from "../../design/components/BandChip";
import { bandColor } from "../../design/bands";
import type { ReactNode } from "react";
import { View } from "react-native";
import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import {
  Skeleton,
  Card,
  Txt,
  Row,
  Choices,
  Chip,
  ErrorNotice,
} from "../../design/components";
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
  if (
    part.status === "absent" &&
    ["generation_paused", "not_generated"].includes(part.absence.reason)
  )
    return (
      <ErrorNotice
        error={{ code: "absent", absence: part.absence }}
        retry={part.absence.reason === "not_generated" ? retry : undefined}
      />
    );
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
  return (
    <>
      <Skeleton variant="lines" lines={3} />
      <JobProgress
        job={part.status === "pending" ? part.job : undefined}
        failed={part.status === "failed"}
        error={part.status === "failed" ? part.error : undefined}
        retry={retry}
      />
    </>
  );
}
export function Score({
  label,
  score,
  band,
  bandKey,
  compact = false,
}: {
  label: string;
  score: number;
  band: string;
  bandKey?: string;
  /** Denser layout for narrow home tiles — softer type, single-line band. */
  compact?: boolean;
}) {
  const flags = useFlags(),
    c = useTheme();
  return (
    <View
      accessible
      accessibilityLabel={`${label}${flags.dayScoreNumbers ? `, ${score} / 10` : ""}, ${band}`}
      style={{ gap: compact ? dsSpace[1] : dsSpace[2], flexGrow: compact ? 1 : undefined }}
    >
      <View
        style={{
          flexDirection: "row",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: dsSpace[2],
        }}
      >
        <Txt
          kind={compact ? "caption" : undefined}
          numberOfLines={1}
          style={{ flexShrink: 1 }}
        >
          {label}
        </Txt>
        {flags.dayScoreNumbers && (
          <Txt kind="caption" muted>
            {score}/10
          </Txt>
        )}
      </View>
      {flags.dayScoreNumbers && (
        <View style={{ flexDirection: "row", gap: compact ? 2 : 3 }}>
          {Array.from({ length: 10 }, (_, i) => (
            <View
              key={i}
              style={{
                flex: 1,
                height: compact ? 3 : 4,
                backgroundColor:
                  i < score
                    ? bandColor(bandKey ?? "quiet", c.dark)
                    : c.hair,
                borderRadius: 2,
                opacity: compact ? (i < score ? 0.85 : 0.5) : 1,
              }}
            />
          ))}
        </View>
      )}
      <BandChip band={bandKey ?? "quiet"} label={band} compact={compact} />
    </View>
  );
}
type CalendarRowItem =
  CalendarEventRef | TransitEpisode | PeriodRef | RetrogradeRef;
export function calendarRows(
  items: CalendarRowItem[],
  profile: string,
  lang: string,
) {
  return items.map((item) => (
    <Row
      key={item.id}
      label={item.label}
      detail={
        "start" in item
          ? `${formatDate(item.start, lang)} – ${formatDate(item.end, lang)}${"phase_label" in item ? ` · ${item.phase_label}` : ""}`
          : undefined
      }
      onPress={() => router.push(routes.calendarItem(item.id, profile))}
    />
  ));
}
export function ItemRows({
  items,
  profile,
}: {
  items: CalendarRowItem[];
  profile: string;
}) {
  const lang = useApp((s) => s.language);
  return <View>{calendarRows(items, profile, lang)}</View>;
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
          role="button"
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
          <Txt kind="reading">{item.text}</Txt><Divider width={180} />
        </Card>
      ))}
    </>
  );
}
