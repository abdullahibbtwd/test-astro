import { useCallback, useEffect, useState } from "react";
import { AppState } from "react-native";
import { useFocusEffect } from "expo-router";
import { useQuery, useQueries, useQueryClient } from "@tanstack/react-query";
import { request } from "./client";
import { useApp } from "../lib/state";
import type { Job } from "../../contracts/spec-types";
import { pollingDelay } from "./job-policy";
export function pendingJobs(value: unknown): Job[] {
  if (!value || typeof value !== "object") return [];
  if ("status" in value && value.status === "pending" && "job" in value)
    return [value.job as Job];
  return Object.values(value).flatMap(pendingJobs);
}
export function useApi<T>(
  path: string,
  schema: string,
  enabled = true,
  postBody?: unknown,
) {
  const lang = useApp((s) => s.language),
    client = useQueryClient();
  const [focused, setFocused] = useState(true),
    [active, setActive] = useState(AppState.currentState === "active"),
    [retryError, setRetryError] = useState<unknown>();
  useFocusEffect(
    useCallback(() => {
      setFocused(true);
      return () => setFocused(false);
    }, []),
  );
  useEffect(() => {
    const sub = AppState.addEventListener("change", (s) =>
      setActive(s === "active"),
    );
    return () => sub.remove();
  }, []);
  const queryKey = [
    "resource",
    lang,
    path,
    ...(postBody ? [JSON.stringify(postBody)] : []),
  ];
  const query = useQuery<T>({
    queryKey,
    queryFn: () =>
      request<T>(postBody ? "POST" : "GET", path, schema, postBody),
    enabled,
    placeholderData: (previous, previousQuery) =>
      !postBody &&
      typeof previousQuery?.queryKey[2] === "string" &&
      previousQuery.queryKey[2].replace(/([?&])lens=[^&]*/g, "$1") ===
        path.replace(/([?&])lens=[^&]*/g, "$1")
        ? previous
        : undefined,
  });
  const jobs = [
    ...new Map(
      pendingJobs(query.data).map((job) => [job.job_id, job]),
    ).values(),
  ];
  const polls = useQueries({
    queries: jobs.map((job) => ({
      queryKey: ["job", lang, job.job_id],
      queryFn: () => request<Job>("GET", `/jobs/${job.job_id}`, "Job"),
      enabled:
        enabled &&
        focused &&
        active &&
        Date.now() - Date.parse(job.created_at) < 600000,
      refetchInterval: (q: {
        state: { data?: Job; dataUpdateCount: number };
      }) =>
        Date.now() - Date.parse(job.created_at) >= 600000 ||
        q.state.data?.status === "succeeded" ||
        q.state.data?.status === "failed"
          ? false
          : pollingDelay(Math.max(0, q.state.dataUpdateCount - 1)),
      refetchIntervalInBackground: false,
    })),
  });
  const finished = polls.map((p) => p.data?.status).join(","),
    refetch = query.refetch;
  useEffect(() => {
    if (finished.includes("succeeded") || finished.includes("failed"))
      void refetch();
  }, [finished, refetch]);
  const retry = async () => {
    setRetryError(undefined);
    try {
      const data = await request<T>(
        postBody ? "POST" : "GET",
        `${path}${path.includes("?") ? "&" : "?"}retry=true`,
        schema,
        postBody,
      );
      client.setQueryData(queryKey, data);
    } catch (e) {
      setRetryError(e);
    }
  };
  return { ...query, error: retryError ?? query.error, retry };
}
