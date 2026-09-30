import { useInfiniteQuery } from "@tanstack/react-query";
import { request } from "./client";
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
  return {
    ...q,
    items: (q.data?.pages.flatMap((p) => p.items) ?? []) as T["items"],
  };
}
