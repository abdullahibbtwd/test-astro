-- Zero-safe domain migration: drop smoke + any legacy Store/budget tables, then create Prisma schema.
DROP TABLE IF EXISTS "prisma_smoke";
DROP TABLE IF EXISTS "records";
DROP TABLE IF EXISTS "budget_calls";
DROP TABLE IF EXISTS "budget_settings";
DROP SEQUENCE IF EXISTS "budget_calls_id_seq";

-- CreateSchema
CREATE SCHEMA IF NOT EXISTS "public";

-- CreateEnum
CREATE TYPE "SessionKind" AS ENUM ('ACCESS', 'REFRESH');

-- CreateEnum
CREATE TYPE "JobKind" AS ENUM ('READING', 'FORECAST', 'MAP_READING', 'COMPAT', 'NATAL_SECTION', 'READING_COMPLETE');

-- CreateEnum
CREATE TYPE "JobStatus" AS ENUM ('queued', 'running', 'ok', 'failed');

-- CreateEnum
CREATE TYPE "ReadingKind" AS ENUM ('NATAL', 'FULL_SECTION', 'FORECAST', 'MAP', 'COMPAT', 'REPORT', 'FORECAST_REPORT', 'MAP_REPORT');

-- CreateEnum
CREATE TYPE "UsageKind" AS ENUM ('ASK', 'PROFILE_CREATE', 'GUEST_READING');

-- CreateTable
CREATE TABLE "users" (
    "id" TEXT NOT NULL,
    "email" TEXT,
    "display_name" TEXT NOT NULL DEFAULT '',
    "language" TEXT NOT NULL DEFAULT 'en',
    "theme" TEXT NOT NULL DEFAULT 'system',
    "current_place" JSONB,
    "consents" JSONB,
    "entitlements" JSONB,
    "notification_prefs" JSONB,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "deleted_users" (
    "id" TEXT NOT NULL,
    "deleted_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "deleted_users_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "sessions" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "kind" "SessionKind" NOT NULL,
    "token_hash" TEXT NOT NULL,
    "expires_at" TIMESTAMP(3) NOT NULL,
    "access_token_hash" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "sessions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "profiles" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "chart_key" TEXT NOT NULL,
    "label" TEXT NOT NULL,
    "relation" TEXT NOT NULL,
    "is_self" BOOLEAN NOT NULL,
    "gender" TEXT,
    "birth" JSONB NOT NULL,
    "big_three" JSONB,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "profiles_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "charts" (
    "profile_id" TEXT NOT NULL,
    "result" JSONB NOT NULL,
    "raw" JSONB,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "charts_pkey" PRIMARY KEY ("profile_id")
);

-- CreateTable
CREATE TABLE "readings" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "profile_id" TEXT,
    "kind" "ReadingKind" NOT NULL,
    "key" TEXT NOT NULL,
    "body" JSONB NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "readings_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "jobs" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "profile_id" TEXT,
    "kind" "JobKind" NOT NULL,
    "status" "JobStatus" NOT NULL,
    "lookup_key" TEXT NOT NULL,
    "payload" JSONB NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "jobs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "usage_counters" (
    "user_id" TEXT NOT NULL,
    "kind" "UsageKind" NOT NULL,
    "date" DATE NOT NULL,
    "count" INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT "usage_counters_pkey" PRIMARY KEY ("user_id","kind","date")
);

-- CreateTable
CREATE TABLE "guest_sessions" (
    "token_hash" TEXT NOT NULL,
    "fingerprint" TEXT NOT NULL,
    "expires_at" TIMESTAMP(3) NOT NULL,
    "profile" JSONB NOT NULL,
    "chart_key" TEXT,
    "chart_result" JSONB,
    "chart_raw" JSONB,
    "section_body" JSONB,
    "claimed_by_id" TEXT,
    "claimed_profile_id" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "guest_sessions_pkey" PRIMARY KEY ("token_hash")
);

-- CreateTable
CREATE TABLE "guest_rate_limits" (
    "ip_hash" TEXT NOT NULL,
    "count" INTEGER NOT NULL DEFAULT 0,
    "expires_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "guest_rate_limits_pkey" PRIMARY KEY ("ip_hash")
);

-- CreateTable
CREATE TABLE "budget_settings" (
    "user_id" TEXT NOT NULL,
    "cap" BIGINT NOT NULL,

    CONSTRAINT "budget_settings_pkey" PRIMARY KEY ("user_id")
);

-- CreateTable
CREATE TABLE "budget_calls" (
    "id" BIGSERIAL NOT NULL,
    "user_id" TEXT NOT NULL,
    "model" TEXT,
    "reserved" BIGINT NOT NULL,
    "charged" BIGINT NOT NULL,
    "state" TEXT NOT NULL,

    CONSTRAINT "budget_calls_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "records" (
    "tenant_id" TEXT NOT NULL,
    "key" TEXT NOT NULL,
    "value" JSONB NOT NULL,

    CONSTRAINT "records_pkey" PRIMARY KEY ("tenant_id","key")
);

-- CreateTable
CREATE TABLE "system_config" (
    "key" TEXT NOT NULL,
    "value" JSONB NOT NULL,

    CONSTRAINT "system_config_pkey" PRIMARY KEY ("key")
);

-- CreateIndex
CREATE UNIQUE INDEX "sessions_token_hash_key" ON "sessions"("token_hash");

-- CreateIndex
CREATE INDEX "sessions_user_id_kind_idx" ON "sessions"("user_id", "kind");

-- CreateIndex
CREATE INDEX "sessions_expires_at_idx" ON "sessions"("expires_at");

-- CreateIndex
CREATE INDEX "profiles_user_id_idx" ON "profiles"("user_id");

-- CreateIndex
CREATE INDEX "profiles_chart_key_idx" ON "profiles"("chart_key");

-- CreateIndex
CREATE INDEX "readings_profile_id_idx" ON "readings"("profile_id");

-- CreateIndex
CREATE UNIQUE INDEX "readings_user_id_kind_key_key" ON "readings"("user_id", "kind", "key");

-- CreateIndex
CREATE INDEX "jobs_user_id_status_idx" ON "jobs"("user_id", "status");

-- CreateIndex
CREATE UNIQUE INDEX "jobs_user_id_kind_lookup_key_key" ON "jobs"("user_id", "kind", "lookup_key");

-- CreateIndex
CREATE INDEX "guest_sessions_expires_at_idx" ON "guest_sessions"("expires_at");

-- CreateIndex
CREATE INDEX "guest_rate_limits_expires_at_idx" ON "guest_rate_limits"("expires_at");

-- CreateIndex
CREATE INDEX "budget_calls_user_id_idx" ON "budget_calls"("user_id");

-- AddForeignKey
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "profiles" ADD CONSTRAINT "profiles_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "charts" ADD CONSTRAINT "charts_profile_id_fkey" FOREIGN KEY ("profile_id") REFERENCES "profiles"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "readings" ADD CONSTRAINT "readings_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "readings" ADD CONSTRAINT "readings_profile_id_fkey" FOREIGN KEY ("profile_id") REFERENCES "profiles"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "jobs" ADD CONSTRAINT "jobs_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "jobs" ADD CONSTRAINT "jobs_profile_id_fkey" FOREIGN KEY ("profile_id") REFERENCES "profiles"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "usage_counters" ADD CONSTRAINT "usage_counters_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "guest_sessions" ADD CONSTRAINT "guest_sessions_claimed_by_id_fkey" FOREIGN KEY ("claimed_by_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "records" ADD CONSTRAINT "records_tenant_id_fkey" FOREIGN KEY ("tenant_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- One self profile per user (partial unique; not expressible in Prisma schema alone)
CREATE UNIQUE INDEX IF NOT EXISTS "profiles_one_self_per_user" ON "profiles" ("user_id") WHERE "is_self";
