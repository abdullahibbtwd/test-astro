import type { Job } from "../../contracts/spec-types";
export function pollingDelay(attempt: number) {
  return [1000, 2000, 3000][attempt] ?? 4000;
}
export function jobState(job: Job | undefined, started: number, now: number) {
  if (now - started >= 600000) return "failed";
  if (!job) return "loading";
  if (job.status === "failed") return "failed";
  if (job.status === "succeeded") return "ready";
  return "pending";
}
