import { busyProblem, paused, problemError } from "./job-problems";
import { randomUUID } from "node:crypto";
import { Store } from "./store";
import { generateReading } from "./readings";
import { validate } from "../../frontend/src/api/zod";
import type {
  BirthProfile,
  Job,
  Lang,
  NatalReading,
} from "../../frontend/contracts/spec-types";
export class ReadingJobs {
  private running = new Set<Promise<void>>();
  private async blockingJob() {
    return (
      await this.store.list<{ job: Job }>("reading-job:")
    ).find((r) => r.job.status === "running" || r.job.status === "queued")!.job
      .job_id;
  }
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
    await jobs.resume();
    return jobs;
  }
  private async resume() {
    for (const record of await this.store.list<any>("reading-job:")) {
      if (["queued", "running"].includes(record.job.status)) {
        record.job = this.failed(record.job, "interrupted");
        await this.store.put("reading-job:" + record.key, record);
        await this.store.put("job:" + record.job.job_id, record.job);
      }
    }
  }
  private failed(job: Job, reason: string): Job {
    return {
      ...job,
      status: "failed",
      updated_at: new Date().toISOString(),
      stages: [{ name: "reading", status: "failed" }],
      error: {
        type: "about:blank",
        title: "Reading could not be prepared",
        status: 503,
        code: "generation_failed",
        detail: reason,
      },
    };
  }
  async close() {
    await Promise.all(this.running);
  }
  async get(
    profile: BirthProfile,
    lang: Lang,
    retry = false,
  ): Promise<{ reading?: NatalReading; job?: Job; absence?: { reason: string } }> {
    const key = profile.chart_key;
    const cached = await this.store.get("reading:" + key);
    if (cached)
      return { reading: { ...cached[lang], profile_id: profile.profile_id } };
    const previous = await this.store.get("reading-job:" + key);
    if (previous && !(retry && previous.job.status === "failed"))
      return { job: previous.job };
    if (!this.enabled) return { absence: paused().absence };
    if (this.running.size)
      throw problemError(busyProblem(await this.blockingJob()));
    const gate = new Promise<void>(() => {});
    this.running.add(gate);
    try {
    const { consumeGeneration, refundUsageIfNoSettledSpend } = await import(
      "./limits"
    );
    const userId = this.store.tenant();
    await consumeGeneration(userId, "NATAL_READING");
    let charged = true;
    const started = new Date();
    const created = started.toISOString();
    const job: Job = {
      job_id: randomUUID(),
      kind: "natal_reading",
      status: "running",
      created_at: created,
      updated_at: created,
      eta_seconds: null,
      error: null,
      stages: [{ name: "reading", status: "running" }],
    };
    const save = async (value: Job) =>
      this.store.transaction(async () => {
        await this.store.put("reading-job:" + key, { key, job: value });
        await this.store.put("job:" + value.job_id, value);
      });
    await save(job);
    const raw = await this.store.get("raw:" + profile.profile_id);
    const task = Promise.resolve()
      .then(async () => {
        try {
          const result = await this.generate(
            raw,
            profile.profile_id,
            key,
            userId,
          );
          for (const language of ["en", "tr"])
            validate("NatalReading", result.readings[language]);
          const current = await this.store.get<BirthProfile>(
            "profile:" + profile.profile_id,
          );
          if (!current || current.chart_key !== key) {
            if (charged) {
              await refundUsageIfNoSettledSpend(
                userId,
                "NATAL_READING",
                started,
              );
              charged = false;
            }
            await save(this.failed(job, "profile_changed"));
            return;
          }
          await this.store.transaction(async () => {
            await this.store.put("reading:" + key, result.readings);
            for (const language of ["en", "tr"]) {
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
          });
          charged = false;
          await save({
            ...job,
            status: "succeeded",
            updated_at: new Date().toISOString(),
            stages: [{ name: "reading", status: "ok" }],
          });
        } catch {
          if (charged) {
            await refundUsageIfNoSettledSpend(
              userId,
              "NATAL_READING",
              started,
            );
            charged = false;
          }
          await save(this.failed(job, "generation_failed"));
        }
      })
      .finally(() => this.running.delete(task));
    this.running.add(task);
    return { job };
    } finally {
      this.running.delete(gate);
    }
  }
}
