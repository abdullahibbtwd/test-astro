import { useState } from "react";
import { Alert, View } from "react-native";
import { router, useFocusEffect } from "expo-router";
import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import {
  Screen,
  Txt,
  Row,
  Choices,
  Chip,
  Button,
  Skeleton,
  ErrorNotice,
} from "../../design/components";
import { useReports, useActions } from "../../api/hooks";
import { useApp } from "../../lib/state";
import type { ReportRef } from "../../../contracts/spec-types";
const types: (ReportRef["type"] | "")[] = [
  "",
  "natal",
  "compatibility",
  "place",
  "area",
  "recommendation",
  "forecast_month",
  "forecast_year",
  "solar_return",
];
export default function ReportsScreen() {
  const { t } = useTranslation(),
    lang = useApp((s) => s.language);
  const [type, setType] = useState<ReportRef["type"] | "">("");
  const reports = useReports(type),
    actions = useActions();
  const refetch = reports.refetch;
  useFocusEffect(
    useCallback(() => {
      void refetch();
    }, [refetch]),
  );
  const remove = (report: ReportRef) =>
    Alert.alert(
      t("deleteReport", { title: report.title }),
      t("deleteReportBody"),
      [
        { text: t("cancel"), style: "cancel" },
        {
          text: t("delete"),
          style: "destructive",
          onPress: () => {
            void actions.removeReport(report.report_id).catch(() => {});
          },
        },
      ],
    );
  const items = reports.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <Screen back title={t("savedReports")}>
      <Choices>
        {types.map((value) => (
          <Chip
            key={value}
            label={t(value || "all")}
            selected={type === value}
            onPress={() => setType(value)}
          />
        ))}
      </Choices>
      {reports.isPending ? (
        <Skeleton />
      ) : items.length ? (
        items.map((item) => (
          <View key={item.report_id} style={{ gap: 8 }}>
            <Row
              label={item.title}
              detail={[
                item.subtitle,
                new Intl.DateTimeFormat(lang, { dateStyle: "medium" }).format(
                  new Date(item.created_at),
                ),
              ]
                .filter(Boolean)
                .join(" · ")}
              onPress={() => router.push(item.route as never)}
              onLongPress={() => remove(item)}
            />
            <Button
              secondary
              danger
              label={t("deleteReportAction", { title: item.title })}
              disabled={actions.isPending}
              onPress={() => remove(item)}
            />
          </View>
        ))
      ) : (
        !reports.error && <Txt muted>{t("emptyReports")}</Txt>
      )}
      {reports.hasNextPage && (
        <Button
          secondary
          label={t("loadMore")}
          loading={reports.isFetchingNextPage}
          onPress={() => {
            void reports.fetchNextPage();
          }}
        />
      )}
      <ErrorNotice
        error={reports.error ?? actions.error}
        retry={() => {
          actions.reset();
          void refetch();
        }}
      />
    </Screen>
  );
}
