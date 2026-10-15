import type { Job } from "../../contracts/spec-types";
export const JOB_SLOW_MS = 3 * 60_000;
export const JOB_VERY_SLOW_MS = 20 * 60_000;
export const jobAgeMs = (job: Pick<Job, "created_at">, now = Date.now()) =>
  Math.max(0, now - Date.parse(job.created_at));
export function jobPhase(job: Pick<Job, "created_at">, now = Date.now()) {
  const age = jobAgeMs(job, now);
  return age >= JOB_VERY_SLOW_MS
    ? "very_slow"
    : age >= JOB_SLOW_MS
      ? "slow"
      : "normal";
}
