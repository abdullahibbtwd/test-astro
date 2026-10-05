import { formatDate } from "../../lib/dates";
import { useApp } from "../../lib/state";
import { removeDeletedReference } from "../../api/deleted-cache";
import {
  deferDelete,
  useDeletedItems,
} from "../../design/components/deferred-delete";
import { router, useLocalSearchParams, useFocusEffect } from "expo-router";
import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import {
  Screen,
  Txt,
  Row,
  Button,
  Skeleton,
  ErrorNotice,
} from "../../design/components";
import { usePages } from "../../api/pages";
import { request } from "../../api/client";
import { useCatalogue } from "../../api/hooks";
import type { CompatibilityPage } from "../../../contracts/spec-types";
export default function MatchScreen() {
  const lang = useApp(s => s.language);
  const { other } = useLocalSearchParams<{ other?: string }>(),
    { t } = useTranslation(),
    cat = useCatalogue(),
    query = usePages<CompatibilityPage>("/compatibility", "CompatibilityPage");
  const hidden = useDeletedItems((s) => s.hidden);
  const refetch = query.refetch;
  useFocusEffect(
    useCallback(() => {
      void refetch();
    }, [refetch]),
  );
  const remove = (id: string) =>
    deferDelete(
      `match:${id}`,
      async () => {
        await request("DELETE", `/compatibility/${id}`);
        removeDeletedReference("compatibility_id", id);
        await refetch();
      },
      { removed: t("removed"), undo: t("undo"), failed: t("deleteFailed") },
    );
  return (
    <Screen title={t("whoFits")}>
      <Button
        label={t("newCompatibility")}
        onPress={() =>
          router.push(`/match/new${other ? `?other=${other}` : ""}`)
        }
      />
      {query.isPending && <Skeleton />}
      {query.items.length
        ? query.items
            .filter((item) => !hidden[`match:${item.compatibility_id}`])
            .map((item) => (
              <Row
                key={item.compatibility_id}
                label={`${item.people.a.label} & ${item.people.b.label}`}
                detail={`${cat.data.compat_types[item.type]} · ${t(item.status === "pending" ? "preparing" : item.status === "failed" ? "error" : "ready")} · ${formatDate(item.created_at.slice(0, 10), lang)}`}
                onPress={() => router.push(`/match/${item.compatibility_id}`)}
                onLongPress={() => remove(item.compatibility_id)}
              />
            ))
        : !query.isPending &&
          !query.error && <Txt muted>{t("emptyCompatibility")}</Txt>}
      {query.hasNextPage && (
        <Button
          secondary
          label={t("loadMore")}
          loading={query.isFetchingNextPage}
          onPress={() => void query.fetchNextPage()}
        />
      )}
      <ErrorNotice
        error={query.error}
        retry={() => {
          void refetch();
        }}
      />
    </Screen>
  );
}
