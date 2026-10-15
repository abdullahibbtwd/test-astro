import type { Job } from "../../contracts/spec-types";
import { JOB_VERY_SLOW_MS } from "./job-timing";
export function pollingDelay(attempt: number, ageMs = 0) {
  if (ageMs >= JOB_VERY_SLOW_MS) return 30_000;
  if (ageMs >= 2 * 60_000) return 10_000;
  return [1000, 2000, 3000][attempt] ?? 4000;
}
export function jobState(job: Job | undefined) {
  if (!job) return "loading";
  if (job.status === "failed") return "failed";
  if (job.status === "succeeded") return "ready";
  return "pending";
}
