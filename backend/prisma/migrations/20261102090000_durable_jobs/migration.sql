-- Align JobStatus with durable worker semantics and add claim/retry columns.
ALTER TYPE "JobStatus" RENAME VALUE 'queued' TO 'pending';
ALTER TYPE "JobStatus" RENAME VALUE 'ok' TO 'done';

ALTER TABLE "jobs"
  ADD COLUMN "attempts" INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN "max_attempts" INTEGER NOT NULL DEFAULT 3,
  ADD COLUMN "error" JSONB,
  ADD COLUMN "started_at" TIMESTAMP(3),
  ADD COLUMN "finished_at" TIMESTAMP(3),
  ADD COLUMN "available_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP;

CREATE INDEX "jobs_status_available_at_idx" ON "jobs"("status", "available_at");
