import { useCallback, useState } from "react";
import { Alert } from "react-native";
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
      {query.items.map((thread) => (
        <Row
          key={thread.thread_id}
          label={thread.title || t("newConversation")}
          detail={thread.updated_at.slice(0, 10)}
          onPress={() => router.push(`/ask/${thread.thread_id}`)}
          onLongPress={() =>
            Alert.alert(t("deleteConversation"), thread.title, [
              { text: t("cancel"), style: "cancel" },
              {
                text: t("delete"),
                style: "destructive",
                onPress: () => {
                  void request("DELETE", `/ask/threads/${thread.thread_id}`)
                    .then(() => refetch())
                    .catch(setError);
                },
              },
            ])
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
