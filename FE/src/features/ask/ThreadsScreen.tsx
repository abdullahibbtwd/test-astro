import { formatDate } from "../../lib/dates";
import { removeDeletedReference } from "../../api/deleted-cache";
import { useCallback, useState } from "react";
import {
  deferDelete,
  useDeletedItems,
} from "../../design/components/deferred-delete";
import { router, useLocalSearchParams, useFocusEffect } from "expo-router";
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
import { useApp } from "../../lib/state";
import { useFlags } from "../../lib/flags";
import { askContext } from "../../api/sse";
import type { ThreadPage, Thread } from "../../../contracts/spec-types";
export default function ThreadsScreen() {
  const params = useLocalSearchParams<Record<string, string>>(),
    app = useApp(),
    { t } = useTranslation(),
    flags = useFlags(),
    query = usePages<ThreadPage>(
      "/ask/threads",
      "ThreadPage",
      !!flags.askAstrology,
    ),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  const hidden = useDeletedItems((s) => s.hidden);
  const refetch = query.refetch;
  useFocusEffect(
    useCallback(() => {
      if (flags.askAstrology) void refetch();
    }, [refetch, flags.askAstrology]),
  );
  const create = async () => {
    setBusy(true);
    try {
      const thread = await request<Thread>("POST", "/ask/threads", "Thread", {
        profile_id:
          params.profile ?? app.activeProfileId ?? app.me?.self_profile_id,
      });
      const context = new URLSearchParams(
        askContext(params) as Record<string, string>,
      );
      router.push(`/ask/${thread.thread_id}?${context}`);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  if (!flags.askAstrology)
    return (
      <Screen back title={t("ask")}>
        <Txt>{t("featureUnavailable")}</Txt>
      </Screen>
    );
  return (
    <Screen back title={t("ask")}>
      <Button
        label={t("newConversation")}
        loading={busy}
        onPress={() => {
          void create();
        }}
      />
      {query.isPending && <Skeleton />}
      {query.items
        .filter((thread) => !hidden[`thread:${thread.thread_id}`])
        .map((thread) => (
          <Row
            key={thread.thread_id}
            label={thread.title || t("newConversation")}
            detail={formatDate(thread.updated_at.slice(0, 10), app.language)}
            onPress={() => router.push(`/ask/${thread.thread_id}`)}
            onLongPress={() =>
              deferDelete(
                `thread:${thread.thread_id}`,
                async () => {
                  await request("DELETE", `/ask/threads/${thread.thread_id}`);
                  removeDeletedReference("thread_id", thread.thread_id);
                  await refetch();
                },
                {
                  removed: t("removed"),
                  undo: t("undo"),
                  failed: t("deleteFailed"),
                },
              )
            }
          />
        ))}
      {query.hasNextPage && (
        <Button
          secondary
          label={t("loadMore")}
          loading={query.isFetchingNextPage}
          onPress={() => void query.fetchNextPage()}
        />
      )}
      <ErrorNotice
        error={error ?? query.error}
        retry={() => {
          void refetch();
        }}
      />
    </Screen>
  );
}
