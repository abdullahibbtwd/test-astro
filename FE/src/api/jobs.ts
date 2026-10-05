import { useOfflineError } from "./online";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { jobPhase } from "./job-timing";
import { request } from "./client";
import { validate } from "./zod";
import { useParentJobs } from "./use-parent-jobs";
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
  const [now, setNow] = useState(Date.now());
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
          }
        : {
            kind: "ready" as const,
            data: validate<T>(schema, value),
          };
    },
  });
  const pending = parent.data?.kind === "pending" ? parent.data : undefined;

  const polls = useParentJobs(
    parent.data,
    parent.error,
    JSON.stringify(parentKey),
    enabled,
    parent.refetch,
  );
  const job = polls[0];
  useEffect(() => {
    if (!pending) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [pending]);
  const [retryError, setRetryError] = useState<unknown>();
  const retry = async () => {
    setRetryError(undefined);
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
            }
          : {
              kind: "ready",
              data: validate<T>(schema, value),
            },
      );
    } catch (error) {
      setRetryError(error);
    }
  };
  const offlineError = useOfflineError(parent.data?.kind === "ready");
  return {
    error:
      offlineError ??
      retryError ??
      parent.error ??
      (job?.data?.status === "failed" ? job?.data.error : undefined),
    data: parent.data?.kind === "ready" ? parent.data.data : undefined,
    job: job?.data ?? pending?.job,
    state:
      offlineError ||
      retryError ||
      parent.isError ||
      job?.data?.status === "failed"
        ? "failed"
        : parent.data?.kind === "ready"
          ? "ready"
          : pending
            ? "pending"
            : "loading",
    slow: !!pending && jobPhase(pending.job, now) !== "normal",
    retry,
  };
}
