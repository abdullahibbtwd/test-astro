import { useCallback, useState } from "react";
import { AppState, View } from "react-native";
import { useFocusEffect } from "expo-router";
import { jobPhase } from "../../api/job-timing";
import { useTranslation } from "react-i18next";
import type { Job } from "../../../contracts/spec-types";
import { Card, Txt, ErrorNotice } from "./index";
const stageLabel = (name: string) => {
  if (
    [
      "input-resolve",
      "compute_chart",
      "natal",
      "compute_forecast",
      "compute_acg",
      "compute_parans",
      "city_scan",
      "goal_scan",
      "locate",
      "relocate",
      "collective",
      "events",
      "scores",
      "best_days",
      "notifications",
      "views",
    ].includes(name)
  )
    return "stageCalculating";
  if (["ground", "ground_forecast", "ground_acg", "grounding"].includes(name))
    return "stageGrounding";
  if (
    ["reading", "sections", "synthesis", "texts", "explanations"].includes(name)
  )
    return "stageWriting";
  if (name === "translation") return "stageTranslating";
  if (["validate", "detox"].includes(name)) return "stageChecking";
  return "preparing";
};
const durations: Record<string, number> = {
  natal_reading: 120,
  month_reading: 90,
  year_reading: 90,
  compatibility: 120,
  place_reading: 60,
  area_reading: 60,
  recommendation: 60,
  solar_return: 120,
  day_reading: 30,
  element_notes: 10,
  calendar_text: 10,
  best_day_text: 10,
};
export function JobProgress({
  job,
  slow,
  failed,
  error,
  retry,
  place,
}: {
  job?: Job;
  slow?: boolean;
  failed?: boolean;
  error?: unknown;
  retry: () => void;
  place?: string;
}) {
  const { t } = useTranslation(),
    [now, setNow] = useState(Date.now());
  useFocusEffect(
    useCallback(() => {
      if (!job || failed) return;
      let timer: ReturnType<typeof setInterval> | undefined;
      const update = () => {
        if (timer) clearInterval(timer);
        if (AppState.currentState === "active") {
          setNow(Date.now());
          timer = setInterval(() => setNow(Date.now()), 1000);
        }
      };
      update();
      const sub = AppState.addEventListener("change", update);
      return () => {
        if (timer) clearInterval(timer);
        sub.remove();
      };
    }, [job, failed]),
  );
  const phase = job ? jobPhase(job, now) : slow ? "slow" : "normal";
  if (failed || error)
    return (
      <ErrorNotice
        error={error ?? job?.error ?? { code: "generation_failed" }}
        retry={retry}
      />
    );
  const seconds = job?.eta_seconds ?? durations[job?.kind ?? ""] ?? 60;
  const elapsed = job
    ? Math.max(0, Math.floor((now - Date.parse(job.created_at)) / 1000))
    : 0;
  return (
    <Card>
      <Txt>
        {place
          ? t("preparingPlaceNamed", { place })
          : t(job ? `preparing_${job.kind}` : "preparing")}
      </Txt>
      <Txt muted>
        {seconds < 60
          ? t("usuallySeconds", { seconds })
          : seconds <= 60
            ? t("usuallyMinute")
            : t("usuallyMinutes", { minutes: Math.ceil(seconds / 60) })}
      </Txt>
      {job && (
        <Txt style={{ fontVariant: ["tabular-nums"] }}>
          {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")}
        </Txt>
      )}
      {phase !== "normal" && (
        <Txt>{t(phase === "very_slow" ? "verySlow" : "slow")}</Txt>
      )}
      {job &&
        job.stages.length > 1 &&
        job.stages.map((stage) => (
          <View key={stage.name} style={{ flexDirection: "row", gap: 12 }}>
            <Txt>
              {stage.status === "ok" || stage.status === "skipped"
                ? "✓"
                : stage.status === "running"
                  ? "◉"
                  : "○"}
            </Txt>
            <Txt>
              {t(stageLabel(stage.name))} ·{" "}
              {t(
                stage.status === "ok" || stage.status === "skipped"
                  ? "ready"
                  : stage.status === "running"
                    ? "preparing"
                    : "waiting",
              )}
            </Txt>
          </View>
        ))}
      <Txt kind="caption" muted>
        {t("leavePreparing")}
      </Txt>
    </Card>
  );
}
