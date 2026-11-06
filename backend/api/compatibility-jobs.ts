import { busyProblem, paused, problemError } from "./job-problems";
import { randomUUID } from "node:crypto";
import { Store } from "./store";
import { runReadingBridge } from "./readings";
import { validate } from "../../frontend/src/api/zod";
import { stableHash as hash } from "./stable-hash";
import { computeCompatibilityScore } from "./compatibility-score";
import {
  FAMILY_COMPATIBILITY_PLACEHOLDER,
  familyPlaceholderReadings,
  relationshipTypeFromFamilyRelation,
  runFamilyAspectsBridge,
  type FamilyAspectsInput,
  type FamilyAspectsOutput,
} from "./family-aspects";
import type {
  BirthProfile,
  ReportRef,
  Compatibility,
  CompatibilityInput,
  Job,
  Lang,
} from "../../frontend/contracts/spec-types";
const issue = (statusCode: number) =>
  Object.assign(new Error("Compatibility unavailable"), { statusCode });
export class CompatibilityJobs {
  private running = new Set<Promise<void>>();
  private async blockingJob() {
    return (
      await this.store.list<{ job: Job }>("compat:")
    ).find((r) => r.job.status === "running" || r.job.status === "queued")!.job
      .job_id;
  }
  constructor(
    private store: Store,
    private enabled = false,
    private generate = (data: any) =>
      runReadingBridge(
        "compatibility_bridge.py",
        data,
        undefined,
        data?.budget_user
          ? { ASTRO_BUDGET_USER: String(data.budget_user) }
          : undefined,
      ),
    private generateFamilyAspects: (
      data: FamilyAspectsInput,
    ) => Promise<FamilyAspectsOutput> = runFamilyAspectsBridge,
  ) {}
  static async create(
    store: Store,
    enabled = false,
    generate?: (data: any) => ReturnType<typeof runReadingBridge>,
    generateFamilyAspects?: (
      data: FamilyAspectsInput,
    ) => Promise<FamilyAspectsOutput>,
  ) {
    const jobs = new CompatibilityJobs(
      store,
      enabled,
      generate ??
        ((data: any) =>
          runReadingBridge(
            "compatibility_bridge.py",
            data,
            undefined,
            data?.budget_user
              ? { ASTRO_BUDGET_USER: String(data.budget_user) }
              : undefined,
          )),
      generateFamilyAspects ?? runFamilyAspectsBridge,
    );
    await jobs.resume();
    return jobs;
  }
  private async resume() {
    for (const record of await this.store.list<any>("compat:"))
      if (record.job.status === "running")
        await this.fail(record, "interrupted");
  }
  async close() {
    await Promise.all(this.running);
  }
  private async valid(record: any) {
    for (const p of record.context.people) {
      const current = await this.store.get<BirthProfile>(
        "profile:" + p.profile_id,
      );
      if (
        !current ||
        current.chart_key !== p.chart_key ||
        current.label !== p.label
      )
        return false;
    }
    return true;
  }
  private async save(record: any) {
    await this.store.transaction(async () => {
      await this.store.put("compat:" + record.id, record);
      await this.store.put("job:" + record.job.job_id, record.job);
    });
  }
  private async fail(record: any, reason: string) {
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
    await this.save(record);
  }
  async create(input: CompatibilityInput, lang: Lang): Promise<Compatibility> {
    if (
      input.profile_a_id === input.profile_b_id ||
      (input.type !== "family" && input.family_relation) ||
      (input.type === "family" && !input.family_relation)
    )
      throw issue(400);
    const profiles = await Promise.all(
      [input.profile_a_id, input.profile_b_id].map(async (id) => {
        const p = await this.store.get<BirthProfile>("profile:" + id);
        if (!p) throw issue(404);
        return p;
      }),
    );
    const context = {
      version: 1,
      type: input.type,
      family_relation:
        input.type === "family" ? (input.family_relation ?? null) : null,
      people: profiles.map((p) => ({
        profile_id: p.profile_id,
        chart_key: p.chart_key,
        label: p.label,
      })),
    };
    const existing = (await this.store.list<any>("compat:")).find(
      (r) => hash(r.context) === hash(context),
    );
    if (existing) return this.get(existing.id, lang);
    // Family uses aspect math + placeholder only — no paid LLM path.
    if (input.type === "family")
      return this.createFamilyMath(context, profiles, lang);
    if (!this.enabled)
      throw Object.assign(new Error("generation_paused"), {
        statusCode: 200,
        absence: paused(),
      });
    if (this.running.size)
      throw problemError(busyProblem(await this.blockingJob()));
    const gate = new Promise<void>(() => {});
    this.running.add(gate);
    try {
    const { consumeGeneration, refundUsageIfNoSettledSpend } = await import(
      "./limits"
    );
    const userId = this.store.tenant();
    await consumeGeneration(userId, "COMPAT_READING");
    let charged = true;
    const started = new Date();
    const created = started.toISOString();
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
    await this.save(record);
    this.start(record, userId, started, () => {
      const was = charged;
      charged = false;
      return was;
    });
    return this.get(record.id, lang);
    } finally {
      this.running.delete(gate);
    }
  }
  /** Sync family path: family_aspects_bridge math + placeholder reading. */
  private async createFamilyMath(
    context: any,
    profiles: BirthProfile[],
    lang: Lang,
  ): Promise<Compatibility> {
    const charts = await Promise.all(
      profiles.map(async (p) => {
        const raw = await this.store.get("raw:" + p.profile_id);
        if (!raw)
          throw Object.assign(new Error("Chart unavailable"), {
            statusCode: 503,
          });
        return raw;
      }),
    );
    const relationship_type = relationshipTypeFromFamilyRelation(
      context.family_relation,
    );
    const math = await this.generateFamilyAspects({
      chart_a: charts[0],
      chart_b: charts[1],
      relationship_type,
      profile_a_label: profiles[0].label,
      profile_b_label: profiles[1].label,
    });
    const created = new Date().toISOString();
    const job: Job = {
      job_id: randomUUID(),
      kind: "compatibility",
      status: "succeeded",
      created_at: created,
      updated_at: created,
      eta_seconds: null,
      error: null,
      stages: [{ name: "reading", status: "ok" }],
    };
    const readings = familyPlaceholderReadings(
      math.interpretation ?? FAMILY_COMPATIBILITY_PLACEHOLDER,
    );
    const record = {
      id: randomUUID(),
      context,
      job,
      created_at: created,
      readings,
      aspects: math.aspects ?? [],
    };
    validate("Compatibility", {
      ...(await this.render(record, lang)),
    });
    await this.save(record);
    return this.get(record.id, lang);
  }
  private start(
    record: any,
    userId = this.store.tenant(),
    started = new Date(),
    takeCharge = () => false,
  ) {
    const task = Promise.resolve()
      .then(async () => {
        const { refundUsageIfNoSettledSpend } = await import("./limits");
        try {
          const result = await this.generate({
            context: record.context,
            charts: await Promise.all(
              record.context.people.map((p: any) =>
                this.store.get("raw:" + p.profile_id),
              ),
            ),
            budget_user: userId,
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
              ...(await this.render(record, lang)),
              reading: { ...reading, status: "ready" },
            });
          }
          if (!(await this.store.get("compat:" + record.id))) return;
          if (!(await this.valid(record))) {
            if (takeCharge())
              await refundUsageIfNoSettledSpend(
                userId,
                "COMPAT_READING",
                started,
              );
            await this.fail(record, "profile_changed");
            return;
          }
          takeCharge();
          record.readings = result.readings;
          record.job = {
            ...record.job,
            status: "succeeded",
            updated_at: new Date().toISOString(),
            stages: [{ name: "reading", status: "ok" }],
          };
          await this.save(record);
        } catch {
          if (takeCharge())
            await refundUsageIfNoSettledSpend(
              userId,
              "COMPAT_READING",
              started,
            );
          if (await this.store.get("compat:" + record.id))
            await this.fail(record, "generation_failed");
        }
      })
      .finally(() => this.running.delete(task));
    this.running.add(task);
  }
  private async render(record: any, lang: Lang): Promise<Compatibility> {
    const people = await Promise.all(
      record.context.people.map(async (p: any) => {
        const profile = (await this.store.get<BirthProfile>(
          "profile:" + p.profile_id,
        ))!;
        return {
          profile_id: p.profile_id,
          label: p.label,
          big_three: profile.big_three,
        };
      }),
    );
    const base: Compatibility & { aspects?: unknown } = {
      compatibility_id: record.id,
      type: record.context.type,
      family_relation: record.context.family_relation ?? null,
      people: { a: people[0], b: people[1] },
      created_at: record.created_at,
      // Remains null until docs/COMPATIBILITY_SCORING.md unblocks a formula.
      score: computeCompatibilityScore({
        type: record.context.type,
        aspects: record.aspects,
      }),
      reading: record.readings
        ? { ...record.readings[lang], status: "ready" }
        : record.job.status === "failed"
          ? { status: "failed", error: record.job.error }
          : { status: "pending", job: record.job },
    };
    // Aspects are math-only extras for the family skeleton (Zod passthrough).
    if (record.context.type === "family" && Array.isArray(record.aspects))
      base.aspects = record.aspects;
    return base;
  }
  async get(id: string, lang: Lang, retry = false): Promise<Compatibility> {
    const r = await this.store.get("compat:" + id);
    if (!r || !(await this.valid(r))) throw issue(404);
    if (retry && r.job.status === "failed") {
      if (!this.enabled)
        throw Object.assign(new Error("generation_paused"), {
          statusCode: 200,
          absence: paused(),
        });
      if (this.running.size)
        throw problemError(busyProblem(await this.blockingJob()));
      const gate = new Promise<void>(() => {});
      this.running.add(gate);
      try {
        const { consumeGeneration } = await import("./limits");
        const userId = this.store.tenant();
        await consumeGeneration(userId, "COMPAT_READING");
        let charged = true;
        const started = new Date();
        const now = started.toISOString();
        r.job = {
          ...r.job,
          job_id: randomUUID(),
          status: "running",
          created_at: now,
          updated_at: now,
          error: null,
          stages: [{ name: "reading", status: "running" }],
        };
        await this.save(r);
        this.start(r, userId, started, () => {
          const was = charged;
          charged = false;
          return was;
        });
      } finally {
        this.running.delete(gate);
      }
    }
    return this.render(r, lang);
  }
  async list() {
    const records = await this.store.list<any>("compat:");
    const items = [];
    for (const r of records) {
      if (!(await this.valid(r))) continue;
      const c = await this.render(r, "en");
      items.push({
        compatibility_id: c.compatibility_id,
        type: c.type,
        people: c.people,
        created_at: c.created_at,
        status: c.reading.status,
      });
    }
    return items.sort((a, b) => b.created_at.localeCompare(a.created_at));
  }
  async reports(lang: Lang): Promise<ReportRef[]> {
    const refs: ReportRef[] = [];
    for (const r of await this.store.list<any>("compat:")) {
      if (!r.readings?.[lang] || !(await this.valid(r))) continue;
      refs.push({
        report_id: `compatibility-${r.id}-${lang}`,
        type: "compatibility",
        title: (
          {
            en: {
              love: "Love compatibility",
              work: "Work compatibility",
              family: "Family compatibility",
            },
            tr: {
              love: "Aşk uyumu",
              work: "İş uyumu",
              family: "Aile uyumu",
            },
          } as const
        )[lang][r.context.type as "love" | "work" | "family"],
        subtitle: r.context.people.map((p: any) => p.label).join(" & "),
        profile_id: r.context.people[0].profile_id,
        created_at: r.created_at,
        route: `/match/${r.id}`,
      });
    }
    return refs;
  }
  async remove(id: string) {
    const r = await this.store.get("compat:" + id);
    if (r) await this.store.remove("job:" + r.job.job_id);
    await this.store.remove("compat:" + id);
  }
}
