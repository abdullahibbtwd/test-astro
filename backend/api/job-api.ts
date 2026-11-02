import type { Job as ApiJob, Problem } from "../../frontend/contracts/spec-types";
import type { Job as DbJob, JobStatus } from "../src/generated/prisma/client.js";

/** Map durable DB statuses onto the OpenAPI Job contract. */
export function apiJobStatus(
  status: JobStatus,
): ApiJob["status"] {
  if (status === "pending") return "queued";
  if (status === "done") return "succeeded";
  return status;
}

export function toApiJob(row: DbJob): ApiJob {
  const stageStatus =
    row.status === "pending"
      ? "pending"
      : row.status === "running"
        ? "running"
        : row.status === "done"
          ? "ok"
          : "failed";
  return {
    job_id: row.id,
    kind: "natal_reading",
    status: apiJobStatus(row.status),
    stages: [{ name: "reading", status: stageStatus }],
    created_at: row.createdAt.toISOString(),
    updated_at: row.updatedAt.toISOString(),
    eta_seconds: null,
    error: (row.error as Problem | null) ?? null,
  };
}
