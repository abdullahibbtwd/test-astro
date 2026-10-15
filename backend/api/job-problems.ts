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
