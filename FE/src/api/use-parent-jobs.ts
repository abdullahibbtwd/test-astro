import { useCallback, useEffect, useRef, useState, useMemo } from "react";
import { AppState } from "react-native";
import { useFocusEffect } from "expo-router";
import { useQueries } from "@tanstack/react-query";
import { request } from "./client";
import { ApiError } from "./errors";
import { pollingDelay } from "./job-policy";
import { jobAgeMs } from "./job-timing";
import { useApp } from "../lib/state";
import type { Job } from "../../contracts/spec-types";
export function parentJobs(
  value: unknown,
): { id: string; created_at?: string; blocking: boolean }[] {
  if (!value || typeof value !== "object") return [];
  if (value instanceof ApiError) return parentJobs(value.problem);
  if (
    "code" in value &&
    value.code === "busy" &&
    "blocking_job_id" in value &&
    typeof value.blocking_job_id === "string"
  )
    return [{ id: value.blocking_job_id, blocking: true }];
  if (
    "job" in value &&
    value.job &&
    typeof value.job === "object" &&
    "job_id" in value.job
  ) {
    const job = value.job as Job;
    return [{ id: job.job_id, created_at: job.created_at, blocking: false }];
  }
  return Object.values(value).flatMap(parentJobs);
}
// Parent resumption is focus-bound. A blocker finishing must never start work on an abandoned screen.
export function useParentJobs(
  value: unknown,
  error: unknown,
  identity: string,
  enabled: boolean,
  refresh: () => unknown,
) {
  const lang = useApp((s) => s.language);
  const [focused, setFocused] = useState(false);
  const [active, setActive] = useState(AppState.currentState === "active");
  const handled = useRef(new Set<string>());
  const refreshRef = useRef(refresh);
  useEffect(() => {
    refreshRef.current = refresh;
  }, [refresh]);
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
  const jobs = useMemo(
    () => [
      ...new Map(
        [...parentJobs(value), ...parentJobs(error)].map((j) => [j.id, j]),
      ).values(),
    ],
    [value, error],
  );
  const polls = useQueries({
    queries: jobs.map((job) => ({
      queryKey: ["job", lang, job.id],
      queryFn: () => request<Job>("GET", `/jobs/${job.id}`, "Job"),
      enabled: enabled && active && focused,
      staleTime: 0,
      refetchOnMount: "always" as const,
      refetchIntervalInBackground: false,
      refetchInterval: (q: {
        state: { data?: Job; dataUpdateCount: number; error: unknown };
      }) =>
        q.state.data?.status === "succeeded" ||
        q.state.data?.status === "failed" ||
        (q.state.error instanceof ApiError && q.state.error.status === 404)
          ? false
          : pollingDelay(
              Math.max(0, q.state.dataUpdateCount - 1),
              q.state.data
                ? jobAgeMs(q.state.data)
                : job.created_at
                  ? jobAgeMs({ created_at: job.created_at })
                  : 0,
            ),
    })),
  });
  const changes = polls
    .map(
      (p) =>
        `${p.data?.status}:${p.error instanceof ApiError ? p.error.status : ""}`,
    )
    .join();
  useEffect(() => {
    if (!enabled || !focused || !active) return;
    let resume = false;
    jobs.forEach((j, i) => {
      const p = polls[i]!;
      const terminal =
        p.data?.status === "succeeded" ||
        p.data?.status === "failed" ||
        (p.error instanceof ApiError && p.error.status === 404);
      const key = `${identity}:${j.id}`;
      if (terminal && !handled.current.has(key)) {
        handled.current.add(key);
        resume = true;
      }
    });
    if (resume) void refreshRef.current();
  }, [changes, enabled, active, focused, identity, jobs, polls]);
  return polls;
}
