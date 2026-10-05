import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useReports } from "../../api/hooks";
import { useGenerated } from "../../api/jobs";
import { Button, Txt, Skeleton } from "../../design/components";
import { JobProgress } from "../../design/components/JobProgress";
import { ReadingSection } from "../profiles/ReadingScreen";
import type { BirthProfile, NatalReading } from "../../../contracts/spec-types";
export function InlineReading({ profile }: { profile: BirthProfile }) {
  const { t } = useTranslation(),
    reports = useReports("natal"),
    [requested, setRequested] = useState(false);
  const saved = reports.data?.pages.some((page) =>
    page.items.some((r) => r.profile_id === profile.profile_id),
  );
  const enabled = requested || !!saved || !!profile.natal_reading_job;
  const reading = useGenerated<NatalReading>(
    ["natal", profile.profile_id, profile.chart_key],
    `/profiles/${profile.profile_id}/natal-reading`,
    "NatalReading",
    enabled,
  );
  const { hasNextPage, isFetchingNextPage, fetchNextPage } = reports;
  useEffect(() => {
    if (!saved && hasNextPage && !isFetchingNextPage) void fetchNextPage();
  }, [saved, hasNextPage, isFetchingNextPage, fetchNextPage]);
  if (reading.data)
    return (
      <>
        {reading.data.sections.map((section, i) => (
          <ReadingSection
            key={section.key}
            section={section}
            initialExpanded={i === 0}
            askRoute={`/ask?profile=${profile.profile_id}&section_key=${section.key}`}
          />
        ))}
      </>
    );
  if (!enabled)
    return reports.isPending ? (
      <Skeleton variant="lines" />
    ) : (
      <>
        <Button
          label={t("prepareMyReading")}
          onPress={() => setRequested(true)}
        />
        <Txt kind="caption" muted>
          {t("usuallyMinutes", { minutes: 2 })}
        </Txt>
      </>
    );
  return (
    <JobProgress
      job={reading.job}
      error={reading.error}
      slow={reading.slow}
      failed={reading.state === "failed"}
      retry={() => void reading.retry()}
    />
  );
}
