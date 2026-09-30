import { useEffect, useState, useCallback } from "react";
import { AppState } from "react-native";
import { useFocusEffect } from "expo-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { request } from "./client";
import { validate } from "./zod";
import { pollingDelay } from "./job-policy";
import { useApp } from "../lib/state";
import type { Job } from "../../contracts/spec-types";
export function useGenerated<T>(
  key: readonly unknown[],
  path: string,
  schema: string,
  enabled = true,
) {
  const lang = useApp((s) => s.language),
    client = useQueryClient();
  const [focused, setFocused] = useState(true);
  useFocusEffect(
    useCallback(() => {
      setFocused(true);
      return () => setFocused(false);
    }, []),
  );
  const [active, setActive] = useState(AppState.currentState === "active"),
    [now, setNow] = useState(Date.now());
  const parentKey = ["generated", lang, ...key];
  const parent = useQuery({
    queryKey: parentKey,
    enabled,
    staleTime: Infinity,
    queryFn: async () => {
      const value = await request<T | { job: Job }>("GET", path);
      return value && typeof value === "object" && "job" in value
        ? {
            kind: "pending" as const,
            job: validate<Job>("Job", value.job),
            started: Date.now(),
          }
        : {
            kind: "ready" as const,
            data: validate<T>(schema, value),
            started: Date.now(),
          };
    },
  });
  const pending = parent.data?.kind === "pending" ? parent.data : undefined;
  const elapsed = now - (pending?.started ?? now),
    expired = elapsed >= 600000;
  const job = useQuery({
    queryKey: ["job", lang, pending?.job.job_id],
    queryFn: () => request<Job>("GET", `/jobs/${pending!.job.job_id}`, "Job"),
    enabled: !!pending && active && focused && !expired,
    refetchInterval: (q) =>
      q.state.data?.status === "failed" || q.state.data?.status === "succeeded"
        ? false
        : pollingDelay(Math.max(0, q.state.dataUpdateCount - 1)),
    refetchIntervalInBackground: false,
  });
  useEffect(() => {
    const listener = AppState.addEventListener("change", (state) =>
      setActive(state === "active"),
    );
    return () => listener.remove();
  }, []);
  useEffect(() => {
    if (!pending || !active || !focused) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [pending, active, focused]);
  const refetchParent = parent.refetch;
  useEffect(() => {
    if (job.data?.status === "succeeded") void refetchParent();
  }, [job.data?.status, refetchParent]);
  const [retryError, setRetryError] = useState(false);
  const retry = async () => {
    setRetryError(false);
    try {
      const value = await request<T | { job: Job }>(
        "GET",
        `${path}${path.includes("?") ? "&" : "?"}retry=true`,
      );
      client.setQueryData(
        parentKey,
        value && typeof value === "object" && "job" in value
          ? {
              kind: "pending",
              job: validate<Job>("Job", value.job),
              started: Date.now(),
            }
          : {
              kind: "ready",
              data: validate<T>(schema, value),
              started: Date.now(),
            },
      );
    } catch {
      setRetryError(true);
    }
  };
  return {
    data: parent.data?.kind === "ready" ? parent.data.data : undefined,
    job: job.data ?? pending?.job,
    state:
      retryError ||
      expired ||
      parent.isError ||
      job.isError ||
      job.data?.status === "failed"
        ? "failed"
        : parent.data?.kind === "ready"
          ? "ready"
          : pending
            ? "pending"
            : "loading",
    slow: elapsed >= 180000,
    retry,
  };
}
