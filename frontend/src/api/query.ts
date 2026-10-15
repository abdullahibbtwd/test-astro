import { keepsReading } from "./cache-policy";
import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "./client";
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 300000,
      gcTime: 7 * 24 * 60 * 60 * 1000,
      retry: (count, error) =>
        count < 2 &&
        (!(error instanceof ApiError) ||
          error.status >= 500 ||
          error.status === 429),
      retryDelay: (attempt, error) =>
        error instanceof ApiError && error.retryAfter
          ? error.retryAfter * 1000
          : Math.min(1000 * 2 ** attempt, 10000),
    },
    mutations: { retry: false },
  },
});
queryClient.setQueryDefaults(["generated"], {
  gcTime: Infinity,
  staleTime: Infinity,
});
queryClient.getQueryCache().subscribe((event) => {
  if (event.type === "added" && keepsReading(event.query.queryKey))
    event.query.setOptions({ ...event.query.options, gcTime: Infinity });
});
export const keys = {
  resource: (name: string, lang: string, ...params: unknown[]) =>
    [name, lang, ...params] as const,
};
