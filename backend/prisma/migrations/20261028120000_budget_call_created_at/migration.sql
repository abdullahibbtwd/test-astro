-- Reservations record when they were taken so a crashed process can expire them.
ALTER TABLE "budget_calls" ADD COLUMN "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP;
