import { randomUUID } from "node:crypto";
import type {
  BirthProfile,
  Job,
  Lang,
  NatalReading,
  NatalSection,
  ReadingOutline,
  ReadingFeedbackInput,
} from "../../frontend/contracts/spec-types";
import { Store } from "./store";
import { runReadingBridge } from "./readings";
import { paused, problemError } from "./job-problems";

type Key = NatalSection["key"];
export type SectionRunner = (
  data: any,
  onStage?: (stage: string) => void,
) => Promise<any>;
type Prepared = {
  plan: {
    order: Key[];
    movement: Record<Key, 1 | 2>;
    house: Record<Key, number | null>;
    titles: Record<Key, Record<Lang, string>>;
    routed_ids: Record<Key, string[]>;
  };
  titles: Record<Lang, string>;
  parts: Record<Lang, NatalReading["parts"]>;
};
type Task = {
  profile: BirthProfile;
  key: Key;
  english: boolean;
  job: Job;
  running: boolean;
};
const stamp = () => new Date().toISOString();
const error = (status: number, code: any) =>
  problemError({
    type: "about:blank",
    title: "Reading unavailable",
    status,
    code,
  });
const sectionId = (chart: string, key: string) =>
  `reading-section:${chart}:${key}`;

export class ProgressiveReadings {
  private plans = new Map<string, Promise<Prepared>>();
  private tasks = new Map<string, Task>();
  private running = new Set<Promise<void>>();
  private completeCharts = new Set<string>();
  constructor(
    private store: Store,
    private enabled = false,
    private bridge: SectionRunner = (data, onStage) =>
      runReadingBridge("reading_section_bridge.py", data, onStage),
    private concurrency = 3,
  ) {
    if (!Number.isInteger(concurrency) || concurrency < 1)
      throw new Error("Invalid reading concurrency");
  }
  static async create(
    store: Store,
    enabled = false,
    bridge?: SectionRunner,
    concurrency = 3,
  ) {
    const readings = new ProgressiveReadings(
      store,
      enabled,
      bridge ??
        ((data, onStage) =>
          runReadingBridge("reading_section_bridge.py", data, onStage)),
      concurrency,
    );
    await readings.resume();
    return readings;
  }
  private async resume() {
    for (const record of await this.store.list<any>("reading-section:")) {
      if (
        ["drafting", "finalizing"].includes(record.status) ||
        ["queued", "running"].includes(
          (await this.store.get<Job>("job:" + record.job_id))?.status ?? "",
        )
      ) {
        record.status = record.text_tr ? "ready" : "failed";
        record.error = "interrupted";
        await this.store.put(sectionId(record.chart_key, record.key), record);
      }
    }
    for (const job of await this.store.list<Job>("job:")) {
      if (
        job.kind === "natal_section" &&
        ["queued", "running"].includes(job.status)
      )
        await this.saveJob({ ...job, status: "failed", error: this.failure() });
    }
    for (const record of await this.store.list<any>("reading-complete:")) {
      const job = await this.store.get<Job>("job:" + record.job.job_id);
      if (job) await this.store.put(record.key, { ...record, job });
    }
  }
  private failure() {
    return {
      type: "about:blank",
      title: "Reading could not be prepared",
      status: 503,
      code: "generation_failed" as const,
    };
  }
  private async saveJob(job: Job) {
    await this.store.put("job:" + job.job_id, { ...job, updated_at: stamp() });
  }
  private job(): Job {
    return {
      job_id: randomUUID(),
      kind: "natal_section",
      status: "queued",
      created_at: stamp(),
      updated_at: stamp(),
      eta_seconds: null,
      error: null,
      stages: ["reading", "synthesis", "validate"].map((name) => ({
        name,
        status: "pending",
      })),
    };
  }
  async prepare(profile: BirthProfile): Promise<Prepared> {
    let task = this.plans.get(profile.chart_key);
    if (!task) {
      task = this.bridge({
        op: "prepare",
        chart_key: profile.chart_key,
        chart: await this.store.get("raw:" + profile.profile_id),
        birth: profile.birth,
      })
        .then(async (prepared: Prepared) => {
          const legacy = await this.store.get<Record<Lang, NatalReading>>(
            "reading:" + profile.chart_key,
          );
          if (legacy)
            for (const key of prepared.plan.order) {
              const tr = legacy.tr.sections.find((s) => s.key === key),
                en = legacy.en.sections.find((s) => s.key === key);
              if (!tr) continue;
              const id = sectionId(profile.chart_key, key);
              const existing = await this.store.get(id);
              if (existing?.text_tr) continue;
              const value = await this.bridge({
                op: "publish",
                chart_key: profile.chart_key,
                section_key: key,
                section: {
                  key,
                  text_tr: tr.text,
                  text_en: en?.text,
                  movement: tr.movement,
                  house: tr.house,
                  principle_ids: prepared.plan.routed_ids[key],
                  provenance: "legacy_batch_ids_reconstructed",
                },
              });
              await this.store.put(id, {
                ...value,
                chart_key: profile.chart_key,
                status: "ready",
                generated_at: legacy.tr.generated_at,
              });
            }
          return prepared;
        })
        .catch((e) => {
          this.plans.delete(profile.chart_key);
          throw e;
        });
      this.plans.set(profile.chart_key, task);
    }
    const prepared = await task;
    if (
      (await this.store.get<string>("dossier-ref:" + profile.profile_id)) !==
      profile.chart_key
    ) {
      await this.bridge({
        op: "retain",
        chart_key: profile.chart_key,
        profile_id: profile.profile_id,
      });
      await this.store.put("dossier-ref:" + profile.profile_id, profile.chart_key);
    }
    return prepared;
  }
  private async progress(profile: BirthProfile) {
    const saved = await this.store.get<{
      opened: Key[];
      furthest_index: number;
      chart_key?: string;
      complete_requested_at?: string;
    }>("reading-progress:" + profile.profile_id);
    return saved?.chart_key === profile.chart_key
      ? saved
      : {
          opened: [] as Key[],
          furthest_index: -1,
          chart_key: profile.chart_key,
        };
  }
  private async guard(
    profile: BirthProfile,
    plan: Prepared["plan"],
    key: Key,
    anonymous: boolean,
    ahead = true,
  ) {
    const index = plan.order.indexOf(key);
    if (index < 0) throw error(404, "not_found");
    if (anonymous && plan.movement[key] === 2)
      throw error(403, "account_required");
    const progress = await this.progress(profile);
    if (
      anonymous &&
      ahead &&
      !progress.complete_requested_at &&
      index > progress.furthest_index + 1
    )
      throw error(409, "read_ahead_limit");
  }
  async start(profile: BirthProfile) {
    await this.prepare(profile);
    if (this.enabled) void this.ensure(profile, "core_identity", "tr");
  }
  async outline(
    profile: BirthProfile,
    lang: Lang,
    anonymous = false,
  ): Promise<ReadingOutline> {
    const { plan, titles, parts } = await this.prepare(profile);
    const sections = await Promise.all(
      plan.order.map(async (key) => {
        const record = await this.store.get(sectionId(profile.chart_key, key));
        const status = (
          record?.text_tr
            ? "ready"
            : this.tasks.has(sectionId(profile.chart_key, key))
              ? "generating"
              : record?.status === "failed"
                ? "failed"
                : "not_started"
        ) as "ready" | "generating" | "failed" | "not_started";
        const access = (
          anonymous && plan.movement[key] === 2 ? "account_required" : "open"
        ) as "account_required" | "open";
        return {
          key,
          movement: plan.movement[key],
          house: plan.house[key] ?? null,
          title: plan.titles[key][lang],
          status,
          access,
        };
      }),
    );
    return {
      profile_id: profile.profile_id,
      chart_key: profile.chart_key,
      lang,
      title: titles[lang],
      parts: parts[lang],
      big_three: {
        sun: profile.big_three.sun,
        moon: profile.big_three.moon,
        rising: profile.big_three.ascendant,
      },
      accuracy: await this.accuracy(profile),
      sections,
    };
  }
  private publicSection(
    prepared: Prepared,
    key: Key,
    lang: Lang,
    record: any,
  ): NatalSection {
    return {
      key,
      movement: prepared.plan.movement[key],
      house: prepared.plan.house[key] ?? null,
      title: prepared.plan.titles[key][lang],
      text: record["text_" + lang],
    };
  }
  async section(
    profile: BirthProfile,
    key: Key,
    lang: Lang,
    anonymous = false,
    retry = false,
  ): Promise<{
    section?: NatalSection;
    job?: Job;
    absence?: { reason: string };
  }> {
    const prepared = await this.prepare(profile);
    await this.guard(profile, prepared.plan, key, anonymous);
    const record = await this.store.get(sectionId(profile.chart_key, key));
    if (record?.["text_" + lang])
      return { section: this.publicSection(prepared, key, lang, record) };
    if (!this.enabled) return { absence: paused().absence };
    if (
      record?.error &&
      !retry &&
      !this.tasks.has(sectionId(profile.chart_key, key))
    )
      throw error(503, "generation_failed");
    if (key !== "core_identity")
      void this.ensure(profile, "core_identity", "tr", retry);
    return { job: await this.ensure(profile, key, lang, retry) };
  }
  private async ensure(
    profile: BirthProfile,
    key: Key,
    lang: Lang,
    retry = false,
  ): Promise<Job | undefined> {
    const id = sectionId(profile.chart_key, key),
      existing = this.tasks.get(id),
      record = await this.store.get(id);
    if (existing) {
      existing.english ||= lang === "en";
      return existing.job;
    }
    if (record?.["text_" + lang]) return;
    if (record?.error && !retry)
      return record.job_id
        ? await this.store.get<Job>("job:" + record.job_id)
        : undefined;
    const job = this.job();
    this.tasks.set(id, {
      profile,
      key,
      english: lang === "en",
      job,
      running: false,
    });
    await this.store.put(id, {
      ...record,
      key,
      chart_key: profile.chart_key,
      status: record?.text_tr ? "ready" : "not_started",
      job_id: job.job_id,
      error: null,
    });
    await this.saveJob(job);
    void this.pump();
    return job;
  }
  private async referenced(chart: string) {
    return (await this.store.list<BirthProfile>("profile:")).some(
      (p) => p.chart_key === chart,
    );
  }
  private pump() {
    void this.pumpAsync();
  }
  private async pumpAsync() {
    for (const [id, task] of this.tasks) {
      if (this.running.size >= this.concurrency) break;
      const chart = task.profile.chart_key;
      if (
        task.running ||
        [...this.tasks.values()].filter(
          (t) => t.running && t.profile.chart_key === chart,
        ).length >= (this.completeCharts.has(chart) ? 3 : 2)
      )
        continue;
      if (
        task.key !== "core_identity" &&
        !(await this.store.get(sectionId(chart, "core_identity")))?.text_tr
      ) {
        if ((await this.store.get(sectionId(chart, "core_identity")))?.error) {
          await this.saveJob({
            ...task.job,
            status: "failed",
            error: this.failure(),
          });
          await this.store.put(id, {
            ...(await this.store.get<any>(id)),
            status: "failed",
            error: "core_failed",
          });
          this.tasks.delete(id);
        }
        continue;
      }
      task.running = true;
      task.job = {
        ...task.job,
        status: "running",
        stages: [{ name: "reading", status: "running" }],
      };
      await this.saveJob(task.job);
      const run = Promise.resolve()
        .then(async () => {
          try {
            if (!(await this.referenced(chart)))
              throw new Error("Profile changed");
            const stage = async (name: string) => {
              const names = [
                "reading",
                "synthesis",
                "validate",
                ...(task.english ? ["translation"] : []),
              ];
              const index = names.indexOf(name);
              task.job.stages = names.map((n, i) => ({
                name: n,
                status: i < index ? "ok" : i === index ? "running" : "pending",
              }));
              await this.saveJob(task.job);
              if (name === "synthesis")
                await this.store.put(id, {
                  ...(await this.store.get<any>(id)),
                  status: "finalizing",
                });
            };
            let record = await this.store.get(id);
            if (!record?.text_tr) {
              await this.store.put(id, { ...record, status: "drafting" });
              const generated = await this.bridge(
                { op: "section", chart_key: chart, section_key: task.key },
                stage,
              );
              if (!(await this.referenced(chart)))
                throw new Error("Profile changed");
              if (!generated.text_tr?.trim()) throw new Error("Empty section");
              record = {
                ...record,
                ...generated,
                text_tr: record?.text_tr || generated.text_tr,
                status: "ready",
                generated_at: stamp(),
                error: null,
              };
              await this.store.put(id, record);
            }
            if (task.english && !record.text_en) {
              const translated = await this.bridge(
                { op: "translate", chart_key: chart, section_key: task.key },
                stage,
              );
              if (!(await this.referenced(chart)))
                throw new Error("Profile changed");
              if (!translated.text_en?.trim())
                throw new Error("Empty translation");
              record = { ...record, text_en: translated.text_en, error: null };
              await this.store.put(id, record);
            }
            await this.saveJob({
              ...task.job,
              status: "succeeded",
              stages: [
                "reading",
                "synthesis",
                "validate",
                ...(task.english ? ["translation"] : []),
              ].map((name) => ({ name, status: "ok" })),
            });
          } catch {
            const record = await this.store.get(id);
            if (await this.referenced(chart))
              await this.store.put(id, {
                ...record,
                status: record?.text_tr ? "ready" : "failed",
                error: "generation_failed",
              });
            else await this.store.remove(id);
            await this.saveJob({
              ...task.job,
              status: "failed",
              error: this.failure(),
            });
          }
        })
        .finally(async () => {
          this.tasks.delete(id);
          try {
            await this.updateCompletions();
          } finally {
            this.running.delete(run);
            this.pump();
          }
        });
      this.running.add(run);
    }
  }
  async opened(
    profile: BirthProfile,
    key: Key,
    event: "opened" | "finished",
    anonymous = false,
  ) {
    const { plan } = await this.prepare(profile);
    await this.guard(profile, plan, key, anonymous);
    if (!(await this.store.get(sectionId(profile.chart_key, key)))?.text_tr)
      throw error(409, "read_ahead_limit");
    if (event !== "opened") return;
    const progress = await this.progress(profile);
    progress.opened = [...new Set([...progress.opened, key])];
    progress.furthest_index = Math.max(
      progress.furthest_index,
      plan.order.indexOf(key),
    );
    await this.store.put("reading-progress:" + profile.profile_id, progress);
    if (!this.enabled) return;
    if (progress.opened.length >= 3)
      await this.complete(profile, "tr", anonymous);
    else {
      const next = plan.order[plan.order.indexOf(key) + 1];
      if (next && (!anonymous || plan.movement[next] === 1))
        void this.ensure(profile, next, "tr");
    }
  }
  async complete(
    profile: BirthProfile,
    lang: Lang,
    anonymous = false,
    retry = false,
  ): Promise<Job> {
    if (!this.enabled)
      throw Object.assign(new Error("Paused"), { absence: paused() });
    const { plan } = await this.prepare(profile);
    const progress = await this.progress(profile);
    await this.store.put("reading-progress:" + profile.profile_id, {
      ...progress,
      complete_requested_at: progress.complete_requested_at ?? stamp(),
    });
    this.completeCharts.add(profile.chart_key);
    const key = `reading-complete:${profile.profile_id}:${lang}:${anonymous}`;
    const existing = await this.store.get(key);
    if (existing && !(retry && existing.job.status === "failed"))
      return existing.job;
    const keys = plan.order.filter((k) => !anonymous || plan.movement[k] === 1);
    const job = this.job();
    await this.store.put(key, {
      key,
      chart_key: profile.chart_key,
      lang,
      keys,
      job,
    });
    await this.saveJob(job);
    for (const k of keys) void this.ensure(profile, k, lang, retry);
    void this.updateCompletions();
    return (await this.store.get(key))!.job;
  }
  private async updateCompletions() {
    for (const record of await this.store.list<any>("reading-complete:")) {
      const pending = record.keys.some((key: Key) =>
        this.tasks.has(sectionId(record.chart_key, key)),
      );
      if (
        !pending &&
        !["queued", "running", "failed"].includes(record.job.status)
      )
        continue;
      const sections = await Promise.all(
        record.keys.map((key: Key) =>
          this.store.get(sectionId(record.chart_key, key)),
        ),
      );
      const ready = sections.every((s: any) => s?.["text_" + record.lang]);
      // An old error is not a failure while that section is still being retried.
      const failed =
        !pending &&
        sections.some((s: any) => s?.error && !s?.["text_" + record.lang]);
      if (record.job.status === "failed" && !ready && !pending) continue;
      record.job = {
        ...record.job,
        status: ready ? "succeeded" : failed ? "failed" : "running",
        error: failed ? this.failure() : null,
      };
      await this.store.put(record.key, record);
      await this.saveJob(record.job);
    }
  }
  async reading(
    profile: BirthProfile,
    lang: Lang,
    anonymous = false,
    retry = false,
  ) {
    const prepared = await this.prepare(profile);
    const legacy = await this.store.get<Record<Lang, NatalReading>>(
      "reading:" + profile.chart_key,
    );
    if (!anonymous && legacy?.[lang])
      return { reading: { ...legacy[lang], profile_id: profile.profile_id } };
    const keys = prepared.plan.order.filter(
      (key) => !anonymous || prepared.plan.movement[key] === 1,
    );
    const records = await Promise.all(
      keys.map((key) => this.store.get(sectionId(profile.chart_key, key))),
    );
    if (records.every((r) => r?.["text_" + lang])) {
      const reportKey = `report:${profile.profile_id}:${lang}`;
      if (!anonymous && !(await this.store.get(reportKey)))
        await this.store.put(reportKey, {
          report_id: randomUUID(),
          type: "natal",
          lang,
          title: prepared.titles[lang],
          subtitle: profile.label,
          profile_id: profile.profile_id,
          created_at: records[0].generated_at,
          route: `/chart/reading?profile=${encodeURIComponent(profile.profile_id)}`,
        });
      return {
        reading: {
          profile_id: profile.profile_id,
          chart_key: profile.chart_key,
          lang,
          generated_at: records[0].generated_at,
          title: prepared.titles[lang],
          parts: prepared.parts[lang].filter(
            (p) => !anonymous || p.movement === 1,
          ),
          sections: keys.map((key, i) =>
            this.publicSection(prepared, key, lang, records[i]),
          ),
        },
      };
    }
    if (!this.enabled) return { absence: paused().absence };
    return { job: await this.complete(profile, lang, anonymous, retry) };
  }
  async accuracy(profile: BirthProfile) {
    const votes = (await this.store.list<any>("reading-feedback:")).filter(
      (v) =>
        v.profile_id === profile.profile_id &&
        v.chart_key === profile.chart_key,
    );
    return votes.length
      ? {
          score:
            votes.reduce(
              (n, v) =>
                n +
                (v.rating === "spot_on" ? 2 : v.rating === "partly" ? 1 : 0),
              0,
            ) /
            (2 * votes.length),
          n: votes.length,
        }
      : null;
  }
  async feedback(profile: BirthProfile, input: ReadingFeedbackInput) {
    const { plan } = await this.prepare(profile);
    const target = input.target;
    if (
      (input.comment?.length ?? 0) > 500 ||
      (target.type === "section" && !plan.order.includes(target.key as Key)) ||
      (target.type !== "section" && target.key !== undefined)
    )
      throw error(400, "validation_error");
    const opened = (await this.progress(profile)).opened;
    const ids = [
      ...new Set(opened.flatMap((key) => plan.routed_ids[key] ?? [])),
    ];
    const id = `${profile.profile_id}:${target.type}:${target.key ?? "all"}`;
    await this.store.put("reading-feedback:" + id, {
      ...input,
      chart_key: profile.chart_key,
      opened_sections: opened,
      principle_ids: ids,
      updated_at: stamp(),
    });
    return { accuracy: (await this.accuracy(profile))! };
  }
  async exportDossiers() {
    const keys = [
      ...new Set(await this.store.list<string>("dossier-ref:")),
    ].filter((chart_key) => typeof chart_key === "string");
    const exported = [];
    for (const chart_key of keys) {
      const dossier = await this.exportOneDossier(chart_key);
      if (dossier) exported.push(dossier);
    }
    return exported;
  }
  /**
   * Dossier files live under the process data directory. Postgres keeps the
   * chart reference if that directory was ephemeral or replaced, and the
   * bridge then raises FileNotFoundError. Rebuild from the stored chart and
   * skip references that no longer belong to a profile.
   */
  private async exportOneDossier(chart_key: string) {
    try {
      return await this.bridge({ op: "export", chart_key });
    } catch (error) {
      if (!String((error as Error).message).includes("FileNotFoundError"))
        throw error;
      const profile = (await this.store.list<BirthProfile>("profile:")).find(
        (item) => item.chart_key === chart_key,
      );
      if (!profile) return null;
      this.plans.delete(chart_key);
      await this.prepare(profile);
      return await this.bridge({ op: "export", chart_key });
    }
  }
  assertIdle(chart?: string) {
    if (
      [...this.tasks.values()].some(
        (task) => !chart || task.profile.chart_key === chart,
      )
    )
      throw error(409, "busy");
  }
  async releaseProfile(profile: BirthProfile) {
    this.assertIdle(profile.chart_key);
    await this.bridge({
      op: "release",
      chart_key: profile.chart_key,
      profile_id: profile.profile_id,
    });
    if (
      (await this.store.get("dossier-ref:" + profile.profile_id)) ===
      profile.chart_key
    )
      await this.store.remove("dossier-ref:" + profile.profile_id);
    await this.store.remove("reading-progress:" + profile.profile_id);
    for (const feedback of await this.store.list<any>("reading-feedback:"))
      if (feedback.profile_id === profile.profile_id)
        await this.store.remove(
          `reading-feedback:${profile.profile_id}:${feedback.target.type}:${feedback.target.key ?? "all"}`,
        );
    for (const record of await this.store.list<any>("reading-complete:"))
      if (record.key.startsWith(`reading-complete:${profile.profile_id}:`))
        await this.store.remove(record.key);
    if (
      !(await this.store.list<BirthProfile>("profile:")).some(
        (p) =>
          p.profile_id !== profile.profile_id &&
          p.chart_key === profile.chart_key,
      )
    ) {
      for (const record of await this.store.list<any>(
        `reading-section:${profile.chart_key}:`,
      ))
        await this.store.remove(sectionId(profile.chart_key, record.key));
      this.plans.delete(profile.chart_key);
      this.completeCharts.delete(profile.chart_key);
    }
  }
  async close() {
    // Queued tasks are not in `running` until pump starts them. Waiting only
    // on `running` returns before English translation, failure recording, and
    // completion status updates.
    for (let idle = 0; idle < 100; idle++) {
      this.pump();
      if (this.running.size) {
        idle = 0;
        await Promise.all([...this.running]);
        continue;
      }
      if (!this.tasks.size) break;
      await new Promise((resolve) => setImmediate(resolve));
    }
    await this.updateCompletions();
  }
}
