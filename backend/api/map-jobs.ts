import { countryName } from "../../frontend/src/lib/countries";
import { busyProblem, paused } from "./job-problems";
import { createHash, randomUUID } from "node:crypto";
import { fileURLToPath, URL } from "node:url";
import { Store } from "./store";
import { runReadingBridge } from "./readings";
import { mapRecommendation } from "../mock/scripts/recommend";
import { fixture } from "../mock/fixtures";
import { validate } from "../../frontend/src/api/zod";
import type {
  BirthProfile,
  Job,
  Lang,
  ReportRef,
} from "../../frontend/contracts/spec-types";
export type MapContext = {
  version: 1;
  profile_id: string;
  chart_key: string;
  kind: "place" | "area" | "recommendation";
  input: any;
};
export const mapContext = (
  p: BirthProfile,
  kind: MapContext["kind"],
  input: unknown,
): MapContext => ({
  version: 1,
  profile_id: p.profile_id,
  chart_key: p.chart_key,
  kind,
  input,
});
const hash = (v: unknown) =>
  createHash("sha256").update(JSON.stringify(v)).digest("hex");
const field = (c: MapContext) =>
  c.kind === "place"
    ? "reading"
    : c.kind === "area"
      ? "overview"
      : "explanations";
const schema = (c: MapContext) =>
  c.kind === "place"
    ? "PlaceReport"
    : c.kind === "area"
      ? "AreaReport"
      : "Recommendation";
function apply(context: MapContext, facts: any, value: any) {
  const result = { ...facts, [field(context)]: value[field(context)] };
  if (context.kind === "place") {
    result.cards = facts.cards.map((c: any) => {
      const text = value.card_texts?.[c.goal];
      if (typeof text !== "string" || !text.trim())
        throw new Error("incomplete_cards");
      return { ...c, text };
    });
  }
  if (result[field(context)]?.status !== "ready")
    throw new Error("incomplete_reading");
  return validate(schema(context), result);
}
export class MapJobs {
  private running = new Set<Promise<void>>();
  private async blockingJob() {
    return (
      await this.store.list<{ job: Job }>("map-reading-job:")
    ).find((r) => r.job.status === "running" || r.job.status === "queued")!.job
      .job_id;
  }
  constructor(
    private store: Store,
    private enabled = false,
    private generate = (data: any) =>
      runReadingBridge("map_reading_bridge.py", data),
  ) {}
  static async create(
    store: Store,
    enabled = false,
    generate?: (data: any) => ReturnType<typeof runReadingBridge>,
  ) {
    const jobs = new MapJobs(
      store,
      enabled,
      generate ??
        ((data: any) => runReadingBridge("map_reading_bridge.py", data)),
    );
    await jobs.resume();
    return jobs;
  }
  private async resume() {
    for (const saved of await this.store.list<any>("map-reading-job:"))
      if (["running", "queued"].includes(saved.job.status))
        await this.save(saved.key, this.failed(saved.job, "interrupted"));
  }
  private async save(key: string, job: Job) {
    await this.store.transaction(async () => {
      await this.store.put("map-reading-job:" + key, { key, job });
      await this.store.put("job:" + job.job_id, job);
    });
  }
  private failed(job: Job, reason: string): Job {
    return {
      ...job,
      status: "failed",
      updated_at: new Date().toISOString(),
      stages: [{ name: "reading", status: "failed" }],
      error: {
        type: "about:blank",
        title: "Map reading unavailable",
        status: 503,
        code: "generation_failed",
        detail: reason,
      },
    };
  }
  private async current(context: MapContext) {
    const p = await this.store.get<BirthProfile>(
      "profile:" + context.profile_id,
    );
    if (!p || p.chart_key !== context.chart_key) return false;
    if (context.kind === "recommendation") {
      const home =
        (p.is_self
          ? (await this.store.get("me"))?.current_place
          : p.current_place) ?? p.birth.place;
      if (
        JSON.stringify([home.lat, home.lon]) !==
        JSON.stringify(context.input.home)
      )
        return false;
    }
    return true;
  }
  async close() {
    await Promise.all(this.running);
  }
  async get<T>(
    context: MapContext,
    facts: T,
    lang: Lang,
    retry = false,
  ): Promise<T> {
    const key = hash(context),
      cached = await this.store.get("map-reading:" + key);
    if (cached) return apply(context, facts, cached[lang]) as T;
    const previous = (await this.store.get("map-reading-job:" + key))?.job as
      | Job
      | undefined;
    if (previous && !(retry && previous.status === "failed"))
      return {
        ...facts,
        [field(context)]:
          previous.status === "failed"
            ? { status: "failed", error: previous.error }
            : { status: "pending", job: previous },
      } as T;
    if (!this.enabled) return { ...facts, [field(context)]: paused() } as T;
    if (this.running.size)
      return {
        ...facts,
        [field(context)]: {
          status: "failed",
          error: busyProblem(await this.blockingJob()),
        },
      } as T;
    const created = new Date().toISOString();
    const job: Job = {
      job_id: randomUUID(),
      kind:
        context.kind === "recommendation"
          ? "recommendation"
          : `${context.kind}_reading`,
      status: "running",
      created_at: created,
      updated_at: created,
      eta_seconds: null,
      error: null,
      stages: [{ name: "reading", status: "running" }],
    };
    await this.save(key, job);
    const task = Promise.resolve()
      .then(async () => {
        try {
          const output = await this.generate({
            context,
            chart: await this.store.get("raw:" + context.profile_id),
          });
          if (hash(output.context) !== key) throw new Error("context_mismatch");
          let values = output.readings;
          if (context.kind === "recommendation") {
            values = Object.fromEntries(
              (["en", "tr"] as const).map((language) => {
                const mapped = mapRecommendation(
                  fileURLToPath(new URL("../../", import.meta.url)),
                  language,
                  fixture(`catalogue.${language}`),
                  output.raw,
                );
                const identifiers = (v: any) => [
                  v.places.map((p: any) => p.place_id),
                  v.by_line.map((g: any) => [
                    g.group_id,
                    g.destinations.map((p: any) => p.place_id),
                  ]),
                  v.turkey.places.map((p: any) => p.place_id),
                ];
                if (hash(identifiers(mapped)) !== hash(identifiers(facts)))
                  throw new Error("ranking_changed");
                return [language, { explanations: mapped.explanations }];
              }),
            );
          }
          for (const language of ["en", "tr"])
            apply(context, facts, values[language]);
          if (!(await this.current(context)))
            throw new Error("profile_changed");
          await this.store.transaction(async () => {
            await this.store.put("map-reading:" + key, values);
            await this.store.put("map-report:" + key, {
              key,
              context,
              created_at: created,
              title:
                context.kind === "place"
                  ? (facts as any).place.name
                  : context.kind === "area"
                    ? (facts as any).area.name
                    : null,
            });
          });
          await this.save(key, {
            ...job,
            status: "succeeded",
            updated_at: new Date().toISOString(),
            stages: [{ name: "reading", status: "ok" }],
          });
        } catch {
          await this.save(key, this.failed(job, "generation_failed"));
        }
      })
      .finally(() => this.running.delete(task));
    this.running.add(task);
    return { ...facts, [field(context)]: { status: "pending", job } } as T;
  }
  async reports(lang: Lang): Promise<ReportRef[]> {
    const refs: ReportRef[] = [];
    for (const { key, context, created_at, title } of await this.store.list<
      any
    >("map-report:")) {
      if (
        !(await this.current(context)) ||
        !(await this.store.get("map-reading:" + key))?.[lang]
      )
        continue;
      const p = (await this.store.get<BirthProfile>(
        "profile:" + context.profile_id,
      ))!;
      const input = context.input,
        profile = encodeURIComponent(p.profile_id);
      let route: string;
      if (context.kind === "place") {
        const loc = input.place;
        route = loc.place_id
          ? `/map/place/${encodeURIComponent(loc.place_id)}?profile=${profile}`
          : `/map/point?lat=${loc.lat}&lon=${loc.lon}&profile=${profile}`;
        if (input.focus_goal) route += `&goal=${input.focus_goal}`;
      } else if (context.kind === "area")
        route = `/map/area/${encodeURIComponent(input.code)}?kind=${input.kind}&profile=${profile}`;
      else
        route = `/map/recommend/result?profile=${profile}&request=${encodeURIComponent(JSON.stringify(input.request))}`;
      refs.push({
        report_id: `map-${key}-${lang}`,
        type: context.kind,
        title:
          context.kind === "place"
            ? `${input.place.name}, ${countryName(input.place.country_code, lang, input.place.country_name)}`
            : (title ??
              (lang === "tr" ? "Yer önerileri" : "Destination recommendations")),
        subtitle:
          context.kind === "place"
            ? lang === "tr"
              ? "Yer raporu"
              : "Place report"
            : p.label,
        profile_id: p.profile_id,
        created_at,
        route,
      });
    }
    return refs;
  }
}
