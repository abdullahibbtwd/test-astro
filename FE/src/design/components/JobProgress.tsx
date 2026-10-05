import { useEffect, useState } from "react";
import { AppState } from "react-native";
import { jobPhase } from "../../api/job-timing";
import { useTranslation } from "react-i18next";
import type { Job } from "../../../contracts/spec-types";
import { Card, Txt, Row, ErrorNotice } from "./index";
export function JobProgress({
  job,
  slow,
  failed,
  error,
  retry,
}: {
  job?: Job;
  slow?: boolean;
  failed?: boolean;
  error?: unknown;
  retry: () => void;
}) {
  const { t } = useTranslation();
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!job || failed) return;
    const timer = setInterval(() => {
      if (AppState.currentState === "active") setNow(Date.now());
    }, 1000);
    return () => clearInterval(timer);
  }, [job, failed]);
  const phase = job ? jobPhase(job, now) : slow ? "slow" : "normal";
  if (failed)
    return (
      <ErrorNotice
        error={error ?? job?.error ?? { code: "generation_failed" }}
        retry={retry}
      />
    );
  return (
    <Card>
      <Txt>
        {t(
          failed
            ? "error"
            : phase === "very_slow"
              ? "verySlow"
              : phase === "slow"
                ? "slow"
                : "preparing",
        )}
      </Txt>
      {job?.stages.map((stage) => (
        <Row
          key={stage.name}
          label={t(
            ["reading", "translation", "validate"].includes(stage.name)
              ? stage.name
              : "preparing",
          )}
          detail={stage.status === "ok" ? t("ready") : t("preparing")}
        />
      ))}
    </Card>
  );
}
