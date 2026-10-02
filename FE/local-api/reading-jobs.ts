import { randomUUID } from "node:crypto";
import { Store } from "./store";
import { generateReading } from "./readings";
import { validate } from "../src/api/zod";
import type {
  BirthProfile,
  Job,
  Lang,
  NatalReading,
} from "../contracts/spec-types";
export class ReadingJobs {
  private running = new Set<Promise<void>>();
  constructor(
    private store: Store,
    private generate = generateReading,
    private enabled = false,
  ) {
    for (const record of store.list<any>("reading-job:")) {
      if (["queued", "running"].includes(record.job.status)) {
        record.job = this.failed(record.job, "interrupted");
        store.put("reading-job:" + record.key, record);
        store.put("job:" + record.job.job_id, record.job);
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
  get(
    profile: BirthProfile,
    lang: Lang,
    retry = false,
  ): { reading?: NatalReading; job?: Job } {
    const key = profile.chart_key;
    const cached = this.store.get("reading:" + key);
    if (cached)
      return { reading: { ...cached[lang], profile_id: profile.profile_id } };
    const previous = this.store.get("reading-job:" + key);
    if (previous && !(retry && previous.job.status === "failed"))
      return { job: previous.job };
    if (!this.enabled)
      throw Object.assign(new Error("Paid generation disabled"), {
        statusCode: 503,
      });
    // One paid report at a time; all provider calls also share the durable dollar cap.
    if (this.running.size)
      throw Object.assign(new Error("Another reading is running"), {
        statusCode: 503,
      });
    const created = new Date().toISOString();
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
    const save = (value: Job) =>
      this.store.transaction(() => {
        this.store.put("reading-job:" + key, { key, job: value });
        this.store.put("job:" + value.job_id, value);
      });
    save(job);
    const raw = this.store.get("raw:" + profile.profile_id);
    const task = Promise.resolve()
      .then(async () => {
        try {
          const result = await this.generate(raw, profile.profile_id, key);
          for (const language of ["en", "tr"])
            validate("NatalReading", result.readings[language]);
          // If edited/deleted during generation, never attach the old reading to the new chart.
          const current = this.store.get<BirthProfile>(
            "profile:" + profile.profile_id,
          );
          if (!current || current.chart_key !== key) {
            save(this.failed(job, "profile_changed"));
            return;
          }
          this.store.transaction(() => {
            this.store.put("reading:" + key, result.readings);
            for (const language of ["en", "tr"]) {
              const reading = result.readings[language];
              this.store.put(`report:${profile.profile_id}:${language}`, {
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
          save({
            ...job,
            status: "succeeded",
            updated_at: new Date().toISOString(),
            stages: [{ name: "reading", status: "ok" }],
          });
        } catch (error) {
          save(
            this.failed(
              job,
              error instanceof Error ? error.message : "generation_failed",
            ),
          );
        }
      })
      .finally(() => this.running.delete(task));
    this.running.add(task);
    return { job };
  }
}
