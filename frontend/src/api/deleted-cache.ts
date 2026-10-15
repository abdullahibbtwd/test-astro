import { queryClient } from "./query";
/** Remove references from every cached filter before a possibly-offline refetch. */
export function removeDeletedReference(
  field: "report_id" | "compatibility_id" | "thread_id",
  id: string,
) {
  queryClient.setQueriesData<{ pages: { items: Record<string, unknown>[] }[] }>(
    { predicate: (q) => ["reports", "pages"].includes(String(q.queryKey[0])) },
    (old) =>
      old?.pages
        ? {
            ...old,
            pages: old.pages.map((page) => ({
              ...page,
              items: page.items.filter((item) => item[field] !== id),
            })),
          }
        : old,
  );
}
