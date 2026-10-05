import { removeDeletedReference } from "../../api/deleted-cache";
import Swipeable from "react-native-gesture-handler/ReanimatedSwipeable";
import { MoreHorizontal } from "lucide-react-native";
import { ActionSheet } from "../../design/components/ActionSheet";
import { IconButton } from "../../design/components/IconButton";
import { useTheme } from "../../design/theme";
import {
  deferDelete,
  useDeletedItems,
} from "../../design/components/deferred-delete";
import { useState } from "react";
import { ScrollView, View } from "react-native";
import { router, useFocusEffect } from "expo-router";
import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import {
  Screen,
  Txt,
  Row,
  Chip,
  Button,
  Skeleton,
  ErrorNotice,
} from "../../design/components";
import { useReports, useActions } from "../../api/hooks";
import { useFlags } from "../../lib/flags";
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
  const flags = useFlags(),
    c = useTheme(),
    hidden = useDeletedItems((s) => s.hidden),
    [menu, setMenu] = useState<ReportRef | null>(null);
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
    deferDelete(
      `report:${report.report_id}`,
      async () => {
        await actions.removeReport(report.report_id);
        removeDeletedReference("report_id", report.report_id);
        await refetch();
      },
      { removed: t("removed"), undo: t("undo"), failed: t("deleteFailed") },
    );
  const items = (
    reports.data?.pages.flatMap((page) => page.items) ?? []
  ).filter((item) => !hidden[`report:${item.report_id}`]);
  return (
    <Screen largeTitle back title={t("savedReports")}>
      <ScrollView
        horizontal
        style={{ flexGrow: 0 }}
        showsHorizontalScrollIndicator={false}
      >
        <View style={{ flexDirection: "row", gap: 8 }}>
          {types
            .filter((value) => value !== "solar_return" || flags.solarReturn)
            .map((value) => (
              <Chip
                key={value}
                label={t(value || "all")}
                selected={type === value}
                onPress={() => setType(value)}
              />
            ))}
        </View>
      </ScrollView>
      {reports.isPending ? (
        <Skeleton />
      ) : items.length ? (
        items.map((item) => (
          <Swipeable
            key={item.report_id}
            renderRightActions={() => (
              <Button danger label={t("delete")} onPress={() => remove(item)} />
            )}
          >
            <View
              style={{ flexDirection: "row", alignItems: "center", gap: 8 }}
            >
              <View style={{ flex: 1 }}>
                <Row
                  label={item.title}
                  detail={[
                    item.subtitle,
                    new Intl.DateTimeFormat(lang, {
                      dateStyle: "medium",
                    }).format(new Date(item.created_at)),
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                  onPress={() => router.push(item.route as never)}
                  onLongPress={() => setMenu(item)}
                />
              </View>
              <IconButton
                accessibilityLabel={t("reportActions", { title: item.title })}
                icon={<MoreHorizontal color={c.ink} size={22} />}
                onPress={() => setMenu(item)}
              />
            </View>
          </Swipeable>
        ))
      ) : (
        !reports.error && <Txt muted>{t("emptyReports")}</Txt>
      )}
      <ActionSheet
        open={!!menu}
        title={menu?.title ?? ""}
        onClose={() => setMenu(null)}
        actions={
          menu
            ? [
                {
                  label: t("open"),
                  onPress: () => router.push(menu.route as never),
                },
                {
                  label: t("delete"),
                  destructive: true,
                  onPress: () => remove(menu),
                },
              ]
            : []
        }
      />
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
