import { randomUUID, createHash } from "node:crypto";
import { Store } from "./store";
import { runReadingBridge } from "./readings";
import { validate } from "../src/api/zod";
import type {
  BirthProfile,
  ReportRef,
  Compatibility,
  CompatibilityInput,
  Job,
  Lang,
} from "../contracts/spec-types";
const hash = (v: unknown) =>
  createHash("sha256").update(JSON.stringify(v)).digest("hex");
const issue = (statusCode: number) =>
  Object.assign(new Error("Compatibility unavailable"), { statusCode });
export class CompatibilityJobs {
  private running = new Set<Promise<void>>();
  constructor(
    private store: Store,
    private enabled = false,
    private generate = (data: unknown) =>
      runReadingBridge("compatibility_bridge.py", data),
  ) {
    for (const record of store.list<any>("compat:"))
      if (record.job.status === "running") this.fail(record, "interrupted");
  }
  async close() {
    await Promise.all(this.running);
  }
  private valid(record: any) {
    return record.context.people.every((p: any) => {
      const current = this.store.get<BirthProfile>("profile:" + p.profile_id);
      return (
        current &&
        current.chart_key === p.chart_key &&
        current.label === p.label
      );
    });
  }
  private save(record: any) {
    this.store.transaction(() => {
      this.store.put("compat:" + record.id, record);
      this.store.put("job:" + record.job.job_id, record.job);
    });
  }
  private fail(record: any, reason: string) {
    record.job = {
      ...record.job,
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
    this.save(record);
  }
  create(input: CompatibilityInput, lang: Lang): Compatibility {
    if (
      input.profile_a_id === input.profile_b_id ||
      (input.type !== "family" && input.family_relation)
    )
      throw issue(400);
    if (input.type === "family") throw issue(503);
    const profiles = [input.profile_a_id, input.profile_b_id].map((id) => {
      const p = this.store.get<BirthProfile>("profile:" + id);
      if (!p) throw issue(404);
      return p;
    });
    const context = {
      version: 1,
      type: input.type,
      people: profiles.map((p) => ({
        profile_id: p.profile_id,
        chart_key: p.chart_key,
        label: p.label,
      })),
    };
    const existing = this.store
      .list<any>("compat:")
      .find((r) => hash(r.context) === hash(context));
    if (existing) return this.get(existing.id, lang);
    if (!this.enabled || this.running.size) throw issue(503);
    const created = new Date().toISOString();
    const job: Job = {
      job_id: randomUUID(),
      kind: "compatibility",
      status: "running",
      created_at: created,
      updated_at: created,
      eta_seconds: null,
      error: null,
      stages: [{ name: "reading", status: "running" }],
    };
    const record = {
      id: randomUUID(),
      context,
      job,
      created_at: created,
      readings: null as any,
    };
    this.save(record);
    this.start(record);
    return this.get(record.id, lang);
  }
  private start(record: any) {
    const task = Promise.resolve()
      .then(async () => {
        try {
          const result = await this.generate({
            context: record.context,
            charts: record.context.people.map((p: any) =>
              this.store.get("raw:" + p.profile_id),
            ),
          });
          if (hash(result.context) !== hash(record.context))
            throw new Error("context_mismatch");
          for (const lang of ["en", "tr"] as const) {
            const reading = result.readings?.[lang];
            if (
              !reading?.title?.trim() ||
              !reading.sections?.length ||
              reading.sections.some(
                (s: any) => !s.text?.trim() || !s.title?.trim(),
              )
            )
              throw new Error("incomplete_reading");
            validate("Compatibility", {
              ...this.render(record, lang),
              reading: { ...reading, status: "ready" },
            });
          }
          if (!this.store.get("compat:" + record.id)) return;
          if (!this.valid(record)) {
            this.fail(record, "profile_changed");
            return;
          }
          record.readings = result.readings;
          record.job = {
            ...record.job,
            status: "succeeded",
            updated_at: new Date().toISOString(),
            stages: [{ name: "reading", status: "ok" }],
          };
          this.save(record);
        } catch {
          if (this.store.get("compat:" + record.id))
            this.fail(record, "generation_failed");
        }
      })
      .finally(() => this.running.delete(task));
    this.running.add(task);
  }
  private render(record: any, lang: Lang): Compatibility {
    const people = record.context.people.map((p: any) => {
      const profile = this.store.get<BirthProfile>("profile:" + p.profile_id)!;
      return {
        profile_id: p.profile_id,
        label: p.label,
        big_three: profile.big_three,
      };
    });
    return {
      compatibility_id: record.id,
      type: record.context.type,
      family_relation: null,
      people: { a: people[0], b: people[1] },
      created_at: record.created_at,
      score: null,
      reading: record.readings
        ? { ...record.readings[lang], status: "ready" }
        : record.job.status === "failed"
          ? { status: "failed", error: record.job.error }
          : { status: "pending", job: record.job },
    };
  }
  get(id: string, lang: Lang, retry = false): Compatibility {
    const r = this.store.get("compat:" + id);
    if (!r || !this.valid(r)) throw issue(404);
    if (retry && r.job.status === "failed") {
      if (!this.enabled || this.running.size) throw issue(503);
      const now = new Date().toISOString();
      r.job = {
        ...r.job,
        job_id: randomUUID(),
        status: "running",
        created_at: now,
        updated_at: now,
        error: null,
        stages: [{ name: "reading", status: "running" }],
      };
      this.save(r);
      this.start(r);
    }
    return this.render(r, lang);
  }
  list() {
    return this.store
      .list<any>("compat:")
      .filter((r) => this.valid(r))
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
      .map((r) => {
        const c = this.render(r, "en");
        return {
          compatibility_id: c.compatibility_id,
          type: c.type,
          people: c.people,
          created_at: c.created_at,
          status: c.reading.status,
        };
      });
  }
  reports(lang: Lang): ReportRef[] {
    return this.store
      .list<any>("compat:")
      .filter((r) => r.readings?.[lang] && this.valid(r))
      .map((r) => ({
        report_id: `compatibility-${r.id}-${lang}`,
        type: "compatibility",
        title: r.readings[lang].title,
        subtitle: r.context.people.map((p: any) => p.label).join(" & "),
        profile_id: r.context.people[0].profile_id,
        created_at: r.created_at,
        route: `/match/${r.id}`,
      }));
  }
  remove(id: string) {
    const r = this.store.get("compat:" + id);
    if (r) this.store.remove("job:" + r.job.job_id);
    this.store.remove("compat:" + id);
  }
}
