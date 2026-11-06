import type { Problem } from "../../frontend/contracts/spec-types";
export const busyProblem = (blocking_job_id: string): Problem => ({
  type: "about:blank",
  title: "Another reading is being prepared",
  status: 409,
  code: "busy",
  blocking_job_id,
});
export const paused = () => ({
  status: "absent" as const,
  absence: { reason: "generation_paused" },
});
export const problemError = (problem: Problem) =>
  Object.assign(new Error(problem.code), {
    statusCode: problem.status,
    problem,
  });

/** True when the LLM spend ledger refused the call (hard cap). */
export function isBudgetExhaustedError(error: unknown): boolean {
  const msg = String(
    error && typeof error === "object" && "message" in error
      ? (error as { message: unknown }).message
      : error,
  );
  return /BudgetExceeded|budget exhausted|Integration testing budget/i.test(
    msg,
  );
}
