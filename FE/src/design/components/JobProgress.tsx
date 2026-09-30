import { useTranslation } from "react-i18next";
import type { Job } from "../../../contracts/spec-types";
import { Card, Txt, Row, Button } from "./index";
export function JobProgress({
  job,
  slow,
  failed,
  retry,
}: {
  job?: Job;
  slow?: boolean;
  failed?: boolean;
  retry: () => void;
}) {
  const { t } = useTranslation();
  return (
    <Card>
      <Txt>{t(failed ? "error" : slow ? "slow" : "preparing")}</Txt>
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
      {failed && <Button secondary label={t("retry")} onPress={retry} />}
    </Card>
  );
}
