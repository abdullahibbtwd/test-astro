import { useInfiniteQuery } from "@tanstack/react-query";
import { request } from "./client";
import { useOfflineError } from "./online";
import { useApp } from "../lib/state";
export function usePages<
  T extends { items: unknown[]; next_cursor: string | null },
>(path: string, schema: string, enabled = true) {
  const lang = useApp((s) => s.language);
  const q = useInfiniteQuery({
    queryKey: ["pages", lang, path],
    initialPageParam: "",
    enabled,
    queryFn: ({ pageParam }) =>
      request<T>(
        "GET",
        `${path}${path.includes("?") ? "&" : "?"}cursor=${encodeURIComponent(pageParam)}`,
        schema,
      ),
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
  const offlineError = useOfflineError(!!q.data);
  return {
    ...q,
    isPending: q.isPending && !offlineError,
    error: offlineError ?? q.error,
    items: (q.data?.pages.flatMap((p) => p.items) ?? []) as T["items"],
  };
}
