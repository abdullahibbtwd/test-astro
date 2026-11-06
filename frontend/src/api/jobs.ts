import { useOfflineError } from "./online";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { jobPhase } from "./job-timing";
import { request } from "./client";
import { validate } from "./zod";
import { useParentJobs } from "./use-parent-jobs";
import { useApp } from "../lib/state";
import type { Job } from "../../contracts/spec-types";

type GeneratedResponse<T> =
  T | { job: Job } | { status: "absent"; absence: { reason: string } };

function isAbsent(
  value: unknown,
): value is { status: "absent"; absence: { reason: string } } {
  if (!value || typeof value !== "object") return false;
  const candidate = value as {
    status?: unknown;
    absence?: { reason?: unknown };
  };
  return (
    candidate.status === "absent" &&
    typeof candidate.absence?.reason === "string"
  );
}

function generatedResult<T>(value: GeneratedResponse<T>, schema: string) {
  if (isAbsent(value))
    return {
      kind: "absent" as const,
      absence: value.absence,
    };
  return value && typeof value === "object" && "job" in value
    ? {
        kind: "pending" as const,
        job: validate<Job>("Job", value.job),
      }
    : {
        kind: "ready" as const,
        data: validate<T>(schema, value),
      };
}

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
      const value = await request<GeneratedResponse<T>>("GET", path);
      return generatedResult(value, schema);
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
      const value = await request<GeneratedResponse<T>>(
        "GET",
        `${path}${path.includes("?") ? "&" : "?"}retry=true`,
      );
      client.setQueryData(parentKey, generatedResult(value, schema));
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
      (parent.data?.kind === "absent"
        ? { absence: parent.data.absence }
        : undefined) ??
      (job?.data?.status === "failed" ? job?.data.error : undefined),
    data: parent.data?.kind === "ready" ? parent.data.data : undefined,
    job: job?.data ?? pending?.job,
    state:
      offlineError ||
      retryError ||
      parent.isError ||
      parent.data?.kind === "absent" ||
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
