import { useEffect, useRef, useState } from "react";
import {
  AccessibilityInfo,
  Alert,
  Share,
  View,
  ScrollView,
} from "react-native";
import * as Clipboard from "expo-clipboard";
import * as Crypto from "expo-crypto";
import { router, useLocalSearchParams } from "expo-router";
import { useNetInfo } from "@react-native-community/netinfo";
import { useTranslation } from "react-i18next";
import { z } from "zod";
import {
  Screen,
  Txt,
  Field,
  Button,
  Choices,
  Chip,
  ErrorNotice,
  Skeleton,
} from "../../design/components";
import { useTheme } from "../../design/theme";
import { useApi } from "../../api/resource";
import { useMe, useProfiles } from "../../api/hooks";
import { request, updateSessionMe } from "../../api/client";
import { streamAnswer } from "../../api/ask-stream";
import { askContext } from "../../api/sse";
import { validate } from "../../api/zod";
import { useFlags } from "../../lib/flags";
import { privateStorage } from "../../lib/storage";
import { useApp } from "../../lib/state";
import { AskCardView } from "./AskCards";
import type {
  Thread,
  Message,
  AskContext,
  AskCard,
} from "../../../contracts/spec-types";
export default function ChatScreen() {
  const params = useLocalSearchParams<Record<string, string>>(),
    id = params.threadId!,
    { t } = useTranslation(),
    app = useApp(),
    flags = useFlags(),
    colors = useTheme(),
    network = useNetInfo(),
    profiles = useProfiles(),
    me = useMe();
  const query = useApi<Thread>(
      `/ask/threads/${id}`,
      "Thread",
      !!flags.askAstrology,
    ),
    [messages, setMessages] = useState<Message[]>([]),
    [text, setText] = useState(""),
    [context, setContext] = useState<AskContext>(() => askContext(params)),
    [busy, setBusy] = useState(false),
    [status, setStatus] = useState("checking"),
    [error, setError] = useState<unknown>(),
    [choosePerson, setChoosePerson] = useState(false),
    controller = useRef<AbortController | null>(null),
    draft = useRef<Message[]>([]),
    lastRequest = useRef<{ text: string; context: AskContext } | undefined>(
      undefined,
    );
  const scroll = useRef<ScrollView>(null);
  const follow = useRef(true);
  const key = `ask-draft:${id}`;
  useEffect(() => {
    if (query.data && !controller.current) {
      const local = privateStorage.getItem(key);
      const saved = local ? JSON.parse(local) : undefined;
      const restored: Message[] = Array.isArray(saved)
        ? saved
        : (saved?.messages ?? query.data.messages ?? []);
      setMessages(restored);
      draft.current = restored;
      if (saved?.request) lastRequest.current = saved.request;
    }
  }, [query.data, key]);
  useEffect(
    () => () => {
      controller.current?.abort();
    },
    [],
  );
  const quota = (me.data ?? app.me)?.ask_quota,
    left = quota ? Math.max(0, quota.limit_per_day - quota.used_today) : 0;
  const subject = profiles.data?.find(
      (p) => p.profile_id === query.data?.profile_id,
    ),
    readOnly = !!query.data && !!profiles.data && !subject;
  const persist = () => {
    if (useApp.getState().signedIn)
      privateStorage.setItem(
        key,
        JSON.stringify({
          messages: draft.current,
          request: lastRequest.current,
        }),
      );
  };
  const send = async (value = text, retry = false) => {
    if (
      busy ||
      !value.trim() ||
      value.length > 1000 ||
      left === 0 ||
      readOnly ||
      network.isConnected === false
    )
      return;
    const payload =
      retry && lastRequest.current
        ? lastRequest.current
        : { text: value.trim(), context };
    lastRequest.current = payload;
    setError(undefined);
    follow.current = true;
    setBusy(true);
    setStatus("checking");
    setText("");
    const abort = new AbortController();
    controller.current = abort;
    const assistantId = Crypto.randomUUID(),
      created_at = new Date().toISOString();
    const previous = retry ? messages.slice(0, -2) : messages;
    draft.current = [
      ...previous,
      {
        message_id: Crypto.randomUUID(),
        role: "user",
        text: payload.text,
        cards: [],
        links: [],
        status: "complete",
        created_at,
      },
      {
        message_id: assistantId,
        role: "assistant",
        text: "",
        cards: [],
        links: [],
        status: "interrupted",
        created_at,
      },
    ];
    setMessages(draft.current);
    persist();
    const update = (fn: (message: Message) => Message) => {
      draft.current = draft.current.map((message) =>
        message.message_id === assistantId ? fn(message) : message,
      );
      setMessages(draft.current);
      persist();
    };
    try {
      await streamAnswer(
        id,
        payload.text,
        payload.context,
        abort.signal,
        (event, raw) => {
          if (event === "delta") {
            const data = z.object({ text: z.string() }).parse(raw);
            update((m) => ({ ...m, text: m.text + data.text }));
            setStatus("writing");
          } else if (event === "status") {
            const data = z
              .object({
                phase: z.enum(["understanding", "computing", "writing"]),
              })
              .passthrough()
              .parse(raw);
            setStatus(data.phase === "writing" ? "writing" : "checking");
          } else if (event === "card") {
            try {
              const card = validate<AskCard>("AskCard", raw);
              update((m) => ({ ...m, cards: [...m.cards, card] }));
            } catch {
              console.warn("Ignored unsupported Ask card");
            }
          } else if (event === "link") {
            const link = z
              .object({ label: z.string(), route: z.string() })
              .parse(raw);
            if (link.route.startsWith("/") && !link.route.startsWith("//"))
              update((m) => ({ ...m, links: [...m.links, link] }));
          } else if (event === "done") {
            const data = z
              .object({
                message_id: z.string(),
                quota: z.object({
                  used_today: z.number(),
                  limit_per_day: z.number(),
                }),
              })
              .parse(raw);
            update((m) => ({
              ...m,
              message_id: data.message_id,
              status: "complete",
            }));
            if (app.me)
              void updateSessionMe({
                ...app.me,
                ask_quota: { ...app.me.ask_quota, ...data.quota },
              });
            AccessibilityInfo.announceForAccessibility(t("ready"));
          } else if (event === "error") throw new Error("Answer failed");
        },
      );
      const result = await query.refetch();
      if (result.data) {
        setMessages(result.data.messages ?? []);
        privateStorage.removeItem(key);
      }
      void me.refetch();
    } catch (e) {
      update((m) => ({
        ...m,
        status: abort.signal.aborted ? "interrupted" : "failed",
      }));
      if (!abort.signal.aborted) {
        setError(e);
        void me.refetch();
      }
    } finally {
      controller.current = null;
      setBusy(false);
    }
  };
  const feedback = (
    message: Message,
    rating: "up" | "down",
    reason?: string,
  ) => {
    void request(
      "POST",
      `/ask/messages/${message.message_id}/feedback`,
      undefined,
      { rating, ...(reason ? { reason } : {}) },
    )
      .then(() =>
        setMessages((current) =>
          current.map((m) =>
            m.message_id === message.message_id
              ? { ...m, feedback: rating }
              : m,
          ),
        ),
      )
      .catch(setError);
  };
  if (!flags.askAstrology)
    return (
      <Screen back title={t("ask")}>
        <Txt>{t("featureUnavailable")}</Txt>
      </Screen>
    );
  return (
    <Screen
      back
      title={subject?.label ?? t("ask")}
      scrollRef={scroll}
      scrollProps={{
        scrollEventThrottle: 100,
        onScroll: ({ nativeEvent: e }) => {
          follow.current =
            e.contentSize.height -
              e.contentOffset.y -
              e.layoutMeasurement.height <
            140;
        },
        onContentSizeChange: () => {
          if (follow.current) scroll.current?.scrollToEnd({ animated: false });
        },
      }}
      footer={
        <View style={{ gap: 8 }}>
          {Object.keys(context).length > 0 && (
            <Choices>
              <Txt kind="caption">
                {t("contextAttached")}
                {context.date ? ` · ${context.date}` : ""}
                {context.month ? ` · ${context.month}` : ""}
                {context.other_profile_id
                  ? ` · ${profiles.data?.find((p) => p.profile_id === context.other_profile_id)?.label ?? t("compatibility")}`
                  : ""}
                {context.place_id ? ` · ${t("place")}` : ""}
                {context.section_key ? ` · ${t("reading")}` : ""}
              </Txt>
              <Button
                secondary
                label={t("removeContext")}
                onPress={() => setContext({})}
              />
            </Choices>
          )}
          {readOnly && <Txt>{t("deletedSubject")}</Txt>}
          {network.isConnected === false && <Txt>{t("offline")}</Txt>}
          {left <= 5 && (
            <Txt kind="caption">
              {left
                ? t("questionsLeft", { count: left })
                : t("quotaReset", {
                    time: quota
                      ? new Intl.DateTimeFormat(app.language, {
                          timeStyle: "short",
                        }).format(new Date(quota.resets_at))
                      : "",
                  })}
            </Txt>
          )}
          <Field
            label={t("question")}
            value={text}
            onChangeText={setText}
            multiline
            maxLength={1000}
            editable={!busy && !readOnly && left > 0}
          />
          <Button
            label={t(busy ? "stop" : "send")}
            disabled={
              !busy &&
              (!text.trim() ||
                left === 0 ||
                readOnly ||
                network.isConnected === false)
            }
            onPress={() => {
              if (busy) controller.current?.abort();
              else void send();
            }}
          />
        </View>
      }
    >
      <Txt kind="caption" muted>
        {t("askDisclaimer")}
      </Txt>
      <Button
        secondary
        label={t("about")}
        onPress={() => Alert.alert(t("ask"), t("askDisclaimer"))}
      />
      <Choices>
        {profiles.data?.map((p) => (
          <Chip
            key={p.profile_id}
            label={p.label}
            selected={p.profile_id === query.data?.profile_id}
            onPress={() => {
              if (busy || p.profile_id === query.data?.profile_id) return;
              void request<Thread>("POST", "/ask/threads", "Thread", {
                profile_id: p.profile_id,
              })
                .then((thread) => router.replace(`/ask/${thread.thread_id}`))
                .catch(setError);
            }}
          />
        ))}
      </Choices>
      {query.isPending && <Skeleton />}
      {!messages.length &&
        !query.isPending &&
        [1, 2, 3, 4, 5, 6].map((number) => (
          <Button
            key={number}
            secondary
            label={t(`starter${number}`)}
            onPress={() => {
              setText(t(`starter${number}`));
              if (number === 4) setChoosePerson(true);
            }}
          />
        ))}
      {choosePerson && (
        <Choices>
          {profiles.data
            ?.filter((p) => p.profile_id !== query.data?.profile_id)
            .map((p) => (
              <Chip
                key={p.profile_id}
                label={p.label}
                selected={context.other_profile_id === p.profile_id}
                onPress={() => {
                  setContext({ ...context, other_profile_id: p.profile_id });
                  setChoosePerson(false);
                }}
              />
            ))}
        </Choices>
      )}
      {messages.map((message) => (
        <View
          key={message.message_id}
          style={{
            gap: 12,
            padding: message.role === "user" ? 16 : 0,
            backgroundColor:
              message.role === "user" ? colors.surfaceAlt : undefined,
            borderRadius: 12,
            alignSelf: message.role === "user" ? "flex-end" : "stretch",
            maxWidth: message.role === "user" ? "90%" : "100%",
          }}
        >
          <Txt kind={message.role === "assistant" ? "reading" : "body"}>
            {message.text}
          </Txt>
          {message.role === "assistant" && (
            <>
              {message.cards.map((card, index) => (
                <AskCardView
                  key={index}
                  card={card}
                  profile={query.data?.profile_id ?? ""}
                />
              ))}
              <Choices>
                {message.links
                  .filter(
                    (link) =>
                      link.route.startsWith("/") &&
                      !link.route.startsWith("//"),
                  )
                  .map((link, index) => (
                    <Chip
                      key={index}
                      label={link.label}
                      selected={false}
                      onPress={() => router.push(link.route as never)}
                    />
                  ))}
              </Choices>
              {!busy && (
                <Choices>
                  <Button
                    secondary
                    label={t("copy")}
                    onPress={() => {
                      void Clipboard.setStringAsync(message.text).catch(
                        setError,
                      );
                    }}
                  />
                  <Button
                    secondary
                    label={t("share")}
                    onPress={() => {
                      void Share.share({ message: message.text }).catch(
                        setError,
                      );
                    }}
                  />
                  {message.status === "complete" && (
                    <>
                      <Chip
                        label={t("helpful")}
                        selected={message.feedback === "up"}
                        onPress={() => feedback(message, "up")}
                      />
                      <Chip
                        label={t("notHelpful")}
                        selected={message.feedback === "down"}
                        onPress={() =>
                          Alert.alert(
                            t("feedbackReason"),
                            undefined,
                            [
                              "notAccurate",
                              "notRelevant",
                              "tooVague",
                              "otherReason",
                            ].map((reason) => ({
                              text: t(reason),
                              onPress: () => feedback(message, "down", reason),
                            })),
                          )
                        }
                      />
                    </>
                  )}
                </Choices>
              )}
              {message.status !== "complete" && !busy && (
                <Txt muted>
                  {t(message.status === "failed" ? "error" : "interrupted")}
                </Txt>
              )}
            </>
          )}
        </View>
      ))}
      {busy && <Txt muted>{t(status)}</Txt>}
      {!busy &&
        messages.at(-1)?.status !== "complete" &&
        lastRequest.current && (
          <Button
            secondary
            label={t("retry")}
            onPress={() => {
              void send(lastRequest.current!.text, true);
            }}
          />
        )}
      <ErrorNotice error={error ?? query.error} />
    </Screen>
  );
}
