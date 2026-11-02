import { randomUUID } from "node:crypto";
import { Prisma } from "../src/generated/prisma/client.js";
import type { Job as DbJob } from "../src/generated/prisma/client.js";
import { prisma } from "./db";
import { toApiJob } from "./job-api";
import { paused } from "./job-problems";
import { generateReading } from "./readings";
import { Store } from "./store";
import { validate } from "../../frontend/src/api/zod";
import type {
  BirthProfile,
  Job,
  Lang,
  NatalReading,
  Problem,
} from "../../frontend/contracts/spec-types";

type ReadingPayload = {
  profileId: string;
  chartKey: string;
  /** ISO time of the usage consume at enqueue; used for refunds. */
  chargedAt?: string;
};

const MAX_ATTEMPTS = 3;
const POLL_MS = 50;
const BACKOFF_MS = [0, 1_000, 5_000, 15_000];
const FAST_BACKOFF_MS = [0, 0, 0, 0];

function backoffMs(attempt: number): number {
  const table =
    process.env.ASTRO_JOB_FAST === "1" ? FAST_BACKOFF_MS : BACKOFF_MS;
  return table[Math.min(attempt, table.length - 1)] ?? table.at(-1)!;
}

function failureProblem(detail: string): Problem {
  return {
    type: "about:blank",
    title: "Reading could not be prepared",
    status: 503,
    code: "generation_failed",
    detail,
  };
}

/**
 * Durable natal reading jobs backed by the Prisma `jobs` table.
 * Enqueue returns immediately; a small in-process worker claims with
 * FOR UPDATE SKIP LOCKED, retries with backoff, and reclaims `running`
 * rows as `pending` on start (crash recovery).
 */
export class ReadingJobs {
  private stopped = false;
  private timer: NodeJS.Timeout | undefined;
  private readonly active = new Set<Promise<void>>();
  private waking: Promise<void> | undefined;

  constructor(
    private store: Store,
    private generate = generateReading,
    private enabled = false,
  ) {}

  static async create(
    store: Store,
    generate = generateReading,
    enabled = false,
  ) {
    const jobs = new ReadingJobs(store, generate, enabled);
    await jobs.reclaimRunning();
    if (enabled) jobs.startWorker();
    return jobs;
  }

  /** Crash recovery: any `running` READING job returns to `pending` for retry. */
  async reclaimRunning(): Promise<number> {
    const result = await prisma().job.updateMany({
      where: { kind: "READING", status: "running" },
      data: {
        status: "pending",
        startedAt: null,
        availableAt: new Date(),
      },
    });
    return result.count;
  }

  private startWorker() {
    if (this.timer) return;
    this.timer = setInterval(() => {
      void this.wake();
    }, POLL_MS);
    this.timer.unref?.();
    void this.wake();
  }

  private wake() {
    if (this.stopped) return this.waking;
    if (this.waking) return this.waking;
    this.waking = this.drain()
      .catch(() => {})
      .finally(() => {
        this.waking = undefined;
      });
    return this.waking;
  }

  private async drain() {
    while (!this.stopped) {
      const claimed = await this.claimNext();
      if (!claimed) return;
      const task = this.runClaimed(claimed).finally(() =>
        this.active.delete(task),
      );
      this.active.add(task);
    }
  }

  private async claimNext(): Promise<DbJob | null> {
    return prisma().$transaction(async (tx) => {
      const locked = await tx.$queryRaw<{ id: string }[]>`
        SELECT "id" FROM "jobs"
        WHERE "kind" = CAST('READING' AS "JobKind")
          AND "status" = CAST('pending' AS "JobStatus")
          AND "available_at" <= CURRENT_TIMESTAMP
        ORDER BY "created_at" ASC
        FOR UPDATE SKIP LOCKED
        LIMIT 1`;
      const id = locked[0]?.id;
      if (!id) return null;
      return tx.job.update({
        where: { id },
        data: {
          status: "running",
          startedAt: new Date(),
          attempts: { increment: 1 },
        },
      });
    });
  }

  private async runClaimed(row: DbJob) {
    const payload = row.payload as ReadingPayload;
    const userId = row.userId;
    const { refundUsageIfNoSettledSpend } = await import("./limits");
    const chargedAt = payload.chargedAt
      ? new Date(payload.chargedAt)
      : row.createdAt;
    try {
      await this.store.runAsAsync(userId, async () => {
        const profile = await this.store.get<BirthProfile>(
          "profile:" + payload.profileId,
        );
        if (!profile || profile.chart_key !== payload.chartKey) {
          await refundUsageIfNoSettledSpend(
            userId,
            "NATAL_READING",
            chargedAt,
          );
          await this.finishFailed(row.id, "profile_changed");
          return;
        }
        const raw = await this.store.get("raw:" + profile.profile_id);
        const result = await this.generate(
          raw,
          profile.profile_id,
          payload.chartKey,
          userId,
        );
        for (const language of ["en", "tr"])
          validate("NatalReading", result.readings[language]);
        const current = await this.store.get<BirthProfile>(
          "profile:" + profile.profile_id,
        );
        if (!current || current.chart_key !== payload.chartKey) {
          await refundUsageIfNoSettledSpend(
            userId,
            "NATAL_READING",
            chargedAt,
          );
          await this.finishFailed(row.id, "profile_changed");
          return;
        }
        const created = row.createdAt.toISOString();
        // Avoid Store.transaction: concurrent workers share one Store and would
        // race on swapping this.db inside $transaction.
        await this.store.put("reading:" + payload.chartKey, result.readings);
        for (const language of ["en", "tr"] as const) {
          const reading = result.readings[language];
          await this.store.put(`report:${profile.profile_id}:${language}`, {
            report_id: randomUUID(),
            type: "natal",
            lang: language,
            title: reading.title,
            subtitle: current.label,
            profile_id: profile.profile_id,
            created_at: created,
            route: `/chart/reading?profile=${profile.profile_id}`,
          });
        }
        if (!(await this.stillOwns(row))) return;
        const done = await prisma().job.update({
          where: { id: row.id },
          data: {
            status: "done",
            error: Prisma.DbNull,
            finishedAt: new Date(),
          },
        });
        await this.store.put("job:" + row.id, toApiJob(done));
      });
    } catch {
      if (!(await this.stillOwns(row))) return;
      await this.failOrRetry(row, chargedAt);
    }
  }

  /** Ignore stale workers after reclaim/crash (attempts or status changed). */
  private async stillOwns(row: DbJob): Promise<boolean> {
    const current = await prisma().job.findUnique({ where: { id: row.id } });
    return (
      !!current &&
      current.status === "running" &&
      current.attempts === row.attempts
    );
  }

  private async finishFailed(id: string, detail: string) {
    const updated = await prisma().job.update({
      where: { id },
      data: {
        status: "failed",
        error: failureProblem(detail) as object,
        finishedAt: new Date(),
      },
    });
    await this.mirrorStoreJob(updated);
  }

  private async failOrRetry(row: DbJob, chargedAt: Date) {
    const latest = await prisma().job.findUnique({ where: { id: row.id } });
    if (!latest || latest.status !== "running") return;
    const attempts = latest.attempts;
    const max = latest.maxAttempts || MAX_ATTEMPTS;
    if (attempts >= max) {
      const { refundUsageIfNoSettledSpend } = await import("./limits");
      await refundUsageIfNoSettledSpend(
        row.userId,
        "NATAL_READING",
        chargedAt,
      );
      await this.finishFailed(row.id, "generation_failed");
      return;
    }
    const updated = await prisma().job.update({
      where: { id: row.id },
      data: {
        status: "pending",
        startedAt: null,
        availableAt: new Date(Date.now() + backoffMs(attempts)),
        error: failureProblem(`retrying after attempt ${attempts}`) as object,
      },
    });
    await this.mirrorStoreJob(updated);
  }

  private async mirrorStoreJob(row: DbJob) {
    const userId = row.userId;
    await this.store.runAsAsync(userId, () =>
      this.store.put("job:" + row.id, toApiJob(row)),
    );
  }

  /**
   * Stop the worker. Pass `abandon: true` to simulate a crash (do not await
   * in-flight work); the next worker start reclaimRunning() returns those jobs
   * to pending.
   */
  async close(opts?: { abandon?: boolean }) {
    this.stopped = true;
    if (this.timer) clearInterval(this.timer);
    this.timer = undefined;
    await this.waking;
    if (!opts?.abandon) await Promise.all([...this.active]);
  }

  async getJob(jobId: string): Promise<Job | undefined> {
    const row = await prisma().job.findUnique({ where: { id: jobId } });
    return row && row.kind === "READING" ? toApiJob(row) : undefined;
  }

  async get(
    profile: BirthProfile,
    lang: Lang,
    retry = false,
  ): Promise<{
    reading?: NatalReading;
    job?: Job;
    absence?: { reason: string };
  }> {
    const key = profile.chart_key;
    const cached = await this.store.get("reading:" + key);
    if (cached)
      return { reading: { ...cached[lang], profile_id: profile.profile_id } };

    const userId = this.store.tenant();
    await prisma().user.upsert({
      where: { id: userId },
      create: { id: userId, displayName: "" },
      update: {},
    });

    let row = await prisma().job.findUnique({
      where: {
        userId_kind_lookupKey: {
          userId,
          kind: "READING",
          lookupKey: key,
        },
      },
    });

    if (row?.status === "done") {
      const again = await this.store.get("reading:" + key);
      if (again)
        return { reading: { ...again[lang], profile_id: profile.profile_id } };
    }

    if (row && !(retry && row.status === "failed")) {
      if (this.enabled) void this.wake();
      return { job: toApiJob(row) };
    }

    if (!this.enabled) return { absence: paused().absence };

    // Charge at enqueue so rate limits reject before a job row is created.
    const { consumeGeneration } = await import("./limits");
    await consumeGeneration(userId, "NATAL_READING");
    const payload: ReadingPayload = {
      profileId: profile.profile_id,
      chartKey: key,
      chargedAt: new Date().toISOString(),
    };

    if (row && retry && row.status === "failed") {
      row = await prisma().job.update({
        where: { id: row.id },
        data: {
          status: "pending",
          attempts: 0,
          error: Prisma.DbNull,
          startedAt: null,
          finishedAt: null,
          availableAt: new Date(),
          payload,
        },
      });
    } else {
      row = await prisma().job.create({
        data: {
          id: randomUUID(),
          userId,
          kind: "READING",
          status: "pending",
          lookupKey: key,
          payload,
          attempts: 0,
          maxAttempts: MAX_ATTEMPTS,
          availableAt: new Date(),
        },
      });
    }

    // Dual-write for transitional GET /jobs/{id} Store readers.
    await this.store.put("job:" + row.id, toApiJob(row));
    void this.wake();
    return { job: toApiJob(row) };
  }
}
