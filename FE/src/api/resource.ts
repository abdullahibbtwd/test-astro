import { useOfflineError } from "./online";
import { keepsReading } from "./cache-policy";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { request } from "./client";
import { useApp } from "../lib/state";
import type { Job } from "../../contracts/spec-types";
import { useParentJobs } from "./use-parent-jobs";
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
  const [retryError, setRetryError] = useState<unknown>();
  const queryKey = [
    "resource",
    lang,
    path,
    ...(postBody ? [JSON.stringify(postBody)] : []),
  ];
  const query = useQuery<T>({
    queryKey,
    ...(keepsReading(queryKey)
      ? { gcTime: Infinity, staleTime: Infinity }
      : {}),
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
  useParentJobs(
    query.data,
    query.error,
    JSON.stringify(queryKey),
    enabled,
    query.refetch,
  );
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
  const offlineError = useOfflineError(!!query.data);
  return {
    ...query,
    isPending: query.isPending && !offlineError,
    error: offlineError ?? retryError ?? query.error,
    retry,
  };
}
