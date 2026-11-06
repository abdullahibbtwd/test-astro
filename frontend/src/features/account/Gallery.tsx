import { ExportAudit } from "./ExportAudit";
import { ListAudit } from "./ListAudit";
import { Segmented } from "../../design/components/Segmented";
import { IconButton } from "../../design/components/IconButton";
import { ActionSheet } from "../../design/components/ActionSheet";
import { BandChip } from "../../design/components/BandChip";
import { DatePager } from "../../design/components/DatePager";
import { ProfileSwitcher } from "../../design/components/ProfileSwitcher";
import { showSnackbar } from "../../design/components/Snackbar";
import MoreHorizontal from "lucide-react-native/icons/ellipsis";
import { useTheme } from "../../design/theme";
import { useLocalSearchParams } from "expo-router";
import { JobProgress } from "../../design/components/JobProgress";
import { Generated } from "../shared/Blocks";
import { NetworkError } from "../../api/errors";
import type { GeneratedPart, Job } from "../../../contracts/spec-types";
import { diagnosticReports } from "../../lib/telemetry";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Screen,
  Txt,
  Button,
  Card,
  Chip,
  Choices,
  Field,
  Row,
  Skeleton,
  ErrorNotice,
  Progress,
} from "../../design/components";
import { useApp } from "../../lib/state";
export default function Gallery() {
  const [sheet, setSheet] = useState(false),
    [segment, setSegment] = useState("today"),
    c = useTheme();
  const { fx } = useLocalSearchParams<{ fx?: string }>();
  const { t } = useTranslation(),
    app = useApp(),
    [value, setValue] = useState("");
  // Release builds never expose the FX gallery / audit surfaces.
  if (!__DEV__) return null;
  if (fx === "export-audit") return <ExportAudit />;
  if (fx === "list-audit") return <ListAudit />;
  if (fx) {
    const status =
      fx === "queued" ? "queued" : fx === "succeeded" ? "succeeded" : "running";
    const job: Job = {
      job_id: "gallery",
      kind: "natal_reading",
      status,
      created_at: new Date(
        Date.now() - (fx === "very-slow" ? 30 : 4) * 60_000,
      ).toISOString(),
      updated_at: new Date().toISOString(),
      stages: [],
      error: null,
      eta_seconds: null,
    };
    const errors: Record<string, unknown> = {
      offline: new NetworkError(),
      paused: { absence: { reason: "generation_paused" } },
      busy: { code: "busy" },
      server: { status: 503 },
    };
    const generated = (
      fx === "succeeded"
        ? { status: "ready", text: t("ready") }
        : fx === "failed"
          ? { status: "failed", error: { code: "generation_failed" } }
          : fx === "paused"
            ? {
                status: "absent",
                absence: { reason: "generation_paused" },
              }
            : { status: "pending", job }
    ) as GeneratedPart<{ text: string }>;
    return (
      <Screen back title={t("gallery")}>
        <Choices>
          {(["light", "dark"] as const).map((theme) => (
            <Chip
              key={theme}
              label={t(theme)}
              selected={app.theme === theme}
              onPress={() => app.update({ theme })}
            />
          ))}
        </Choices>
        {["queued", "running", "succeeded", "failed", "paused"].includes(fx) ? (
          <Generated part={generated} retry={() => {}}>
            {(part) => <Txt>{part.text}</Txt>}
          </Generated>
        ) : fx === "slow" || fx === "very-slow" ? (
          <JobProgress job={job} retry={() => {}} />
        ) : (
          <ErrorNotice error={errors[fx]} retry={() => {}} />
        )}
      </Screen>
    );
  }
  return (
    <Screen back title={t("gallery")}>
      <Choices>
        {(["tr", "en"] as const).map((language) => (
          <Chip
            key={language}
            label={language}
            selected={app.language === language}
            onPress={() => app.update({ language })}
          />
        ))}
        {(["light", "dark"] as const).map((theme) => (
          <Chip
            key={theme}
            label={t(theme)}
            selected={app.theme === theme}
            onPress={() => app.update({ theme })}
          />
        ))}
      </Choices>
      <Segmented
        value={segment}
        onChange={setSegment}
        items={["today", "month", "year", "calendar"].map((value) => ({
          value,
          label: t(value),
        }))}
      />
      <DatePager
        label={new Intl.DateTimeFormat(app.language, {
          dateStyle: "long",
        }).format(new Date())}
        onPrevious={() => {}}
        onNext={() => {}}
        onPick={() => setSheet(true)}
      />
      <ProfileSwitcher />
      <BandChip band="supportive" label={t("supportive")} />
      <IconButton
        accessibilityLabel={t("more")}
        icon={<MoreHorizontal color={c.ink} size={24} />}
        onPress={() => setSheet(true)}
      />
      <ActionSheet
        open={sheet}
        title={t("gallery")}
        onClose={() => setSheet(false)}
        actions={[
          {
            label: t("delete"),
            destructive: true,
            onPress: () =>
              showSnackbar(t("removed"), {
                action: { label: t("undo"), onPress: () => {} },
              }),
          },
        ]}
      />
      <Button
        secondary
        label={t("undo")}
        onPress={() =>
          showSnackbar(t("removed"), {
            action: { label: t("undo"), onPress: () => {} },
          })
        }
      />
      <Skeleton variant="lines" />
      <Txt kind="display">{t("welcome")}</Txt>
      <Txt kind="reading">{t("disclaimer")}</Txt>
      <Card>
        <Txt kind="title">{t("myCharts")}</Txt>
        <Row label={t("birthDate")} detail="30 Mart 1979" onPress={() => {}} />
      </Card>
      <Field label={t("name")} value={value} onChangeText={setValue} />
      <Button label={t("continue")} onPress={() => {}} />
      <Button secondary label={t("continue")} onPress={() => {}} />
      <Button disabled label={t("save")} onPress={() => {}} />
      <Button loading label={t("save")} onPress={() => {}} />
      <Button danger label={t("delete")} onPress={() => {}} />
      <Txt>{t("diagnostics")}</Txt>
      {diagnosticReports().map((report, i) => (
        <Txt key={i} kind="caption">
          {JSON.stringify(report)}
        </Txt>
      ))}
      <Progress step={3} total={9} />
      <Skeleton />
      <ErrorNotice error={true} retry={() => {}} />
    </Screen>
  );
}
