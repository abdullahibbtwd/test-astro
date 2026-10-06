import { queryClient } from "./query";
import { request } from "./client";
import { JobWatcher, type JobCompletion } from "./job-watcher-core";
import type { Job } from "../../contracts/spec-types";
const listeners = new Set<(event: JobCompletion, lang: string) => void>();
export const jobWatcher = new JobWatcher({
  fetch: (lang, id) =>
    request<Job>("GET", `/jobs/${encodeURIComponent(id)}?lang=${lang}`, "Job"),
  publish: (lang, id, job) => queryClient.setQueryData(["job", lang, id], job),
  complete: (event, lang) => {
    if (event.missing)
      queryClient.setQueryData(["job", lang, event.job.job_id], event.job);
    for (const key of event.parents)
      void queryClient.invalidateQueries({
        queryKey: key,
        exact: true,
        refetchType: "none",
      });
    for (const listener of listeners) listener(event, lang);
  },
});
export function onJobComplete(
  listener: (event: JobCompletion, lang: string) => void,
) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
export function registerParentJobs(key: readonly unknown[], value: unknown) {
  if (!["resource", "generated"].includes(String(key[0]))) return;
  function walk(value: unknown) {
    if (!value || typeof value !== "object") return;
    if (
      "job" in value &&
      value.job &&
      typeof value.job === "object" &&
      "job_id" in value.job
    ) {
      const job = value.job as Job;
      if (job.status !== "succeeded" && job.status !== "failed")
        jobWatcher.register(
          String(key[1]),
          { id: job.job_id, created_at: job.created_at, job },
          key,
        );
      return;
    }
    for (const child of Object.values(value)) walk(child);
  }
  walk(value);
}
