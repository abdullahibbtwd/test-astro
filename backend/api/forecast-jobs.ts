import { busyProblem, paused } from "./job-problems";
import { randomUUID } from "node:crypto";
import { Store } from "./store";
import { runReadingBridge } from "./readings";
import { forecastSegments } from "./forecast";
import { defaults } from "./defaults";
import { stableHash as hash } from "./stable-hash";
import type {
  BirthProfile,
  ReportRef,
  Place,
  Lang,
  Lens,
  Job,
} from "../../frontend/contracts/spec-types";
export const forecastContext = (
  p: BirthProfile,
  current: Place,
  target: string,
  horizon: "day" | "month" | "year",
  lens: Lens,
) => ({
  version: 2,
  profile_id: p.profile_id,
  chart_key: p.chart_key,
  current: { lat: current.lat, lon: current.lon, tz: current.tz },
  target,
  horizon,
  lens,
});
export type ForecastContext = ReturnType<typeof forecastContext>;
export class ForecastJobs {
  private running = new Set<Promise<void>>();
  private async blockingJob() {
    return (
      await this.store.list<{ job: Job }>("forecast-job:")
    ).find((r) => r.job.status === "running" || r.job.status === "queued")!.job
      .job_id;
  }
  constructor(
    private store: Store,
    private enabled = false,
    private generate = (input: any) =>
      runReadingBridge("forecast_bridge.py", input),
  ) {}
  static async create(
    store: Store,
    enabled = false,
    generate?: (input: any) => ReturnType<typeof runReadingBridge>,
  ) {
    const jobs = new ForecastJobs(
      store,
      enabled,
      generate ??
        ((input: any) => runReadingBridge("forecast_bridge.py", input)),
    );
    await jobs.resume();
    return jobs;
  }
  private async resume() {
    for (const saved of await this.store.list<any>("forecast-job:"))
      if (["running", "queued"].includes(saved.job.status))
        await this.save(saved.key, this.failed(saved.job, "interrupted"));
  }
  private async save(key: string, job: Job) {
    await this.store.transaction(async () => {
      await this.store.put("forecast-job:" + key, { key, job });
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
        title: "Forecast reading unavailable",
        status: 503,
        code: "generation_failed",
        detail: reason,
      },
    };
  }
  private async indexReport(context: ForecastContext) {
    if (context.horizon === "day") return;
    const key = hash(context);
    if (!(await this.store.get("forecast-report:" + key)))
      await this.store.put("forecast-report:" + key, {
        key,
        context,
        created_at:
          (await this.store.get("forecast-job:" + key))?.job.created_at ??
          new Date().toISOString(),
      });
  }
  async reports(lang: Lang): Promise<ReportRef[]> {
    const refs: ReportRef[] = [];
    for (const { key, context, created_at } of await this.store.list<{
      key: string;
      context: ForecastContext;
      created_at: string;
    }>("forecast-report:")) {
      const p = await this.store.get<BirthProfile>(
        "profile:" + context.profile_id,
      );
      if (
        !p ||
        context.horizon === "day" ||
        !(await this.store.get("forecast-reading:" + key))?.[lang]
      )
        continue;
      const current =
        (p.is_self
          ? (await this.store.get("me"))?.current_place
          : p.current_place) ?? p.birth.place;
      if (
        hash(
          forecastContext(
            p,
            current,
            context.target,
            context.horizon,
            context.lens,
          ),
        ) !== key
      )
        continue;
      const month = context.target.slice(0, 7);
      const title = new Intl.DateTimeFormat(lang, {
        month: "long",
        year: "numeric",
        timeZone: "UTC",
      }).format(new Date(context.target));
      const kind =
        context.horizon === "month"
          ? lang === "tr"
            ? "Aylık öngörü"
            : "Monthly forecast"
          : lang === "tr"
            ? "Yıllık öngörü"
            : "Yearly forecast";
      refs.push({
        report_id: `forecast-${key}-${lang}`,
        type:
          context.horizon === "month" ? "forecast_month" : "forecast_year",
        title: `${kind} · ${title}`,
        subtitle: `${p.label} · ${defaults(`catalogue.${lang}`).lenses[context.lens]}`,
        profile_id: p.profile_id,
        created_at,
        route: `/ahead?view=${context.horizon}&profile=${encodeURIComponent(p.profile_id)}&month=${month}&lens=${context.lens}`,
      });
    }
    return refs;
  }
  async close() {
    await Promise.all(this.running);
  }
  async peek(context: ForecastContext, lang: Lang): Promise<any> {
    return this.get(context, lang, false, true);
  }
  async get(
    context: ForecastContext,
    lang: Lang,
    retry = false,
    peekOnly = false,
  ): Promise<any> {
    const key = hash(context),
      cached = await this.store.get("forecast-reading:" + key);
    if (cached) {
      await this.indexReport(context);
      return context.horizon === "day"
        ? { status: "ready", text: cached[lang].reading }
        : {
            status: "ready",
            ...cached[lang],
            focus_title: defaults(`catalogue.${lang}`).lens_focus_titles[
              context.lens
            ],
          };
    }
    const previous = (await this.store.get("forecast-job:" + key))?.job as
      | Job
      | undefined;
    if (previous && !(retry && previous.status === "failed"))
      return previous.status === "failed"
        ? { status: "failed", error: previous.error }
        : { status: "pending", job: previous };
    if (peekOnly)
      return { status: "absent", absence: { reason: "not_generated" } };
    if (!this.enabled) return paused();
    if (this.running.size)
      return {
        status: "failed",
        error: busyProblem(await this.blockingJob()),
      };
    const created = new Date().toISOString();
    const job: Job = {
      job_id: randomUUID(),
      kind: `${context.horizon}_reading`,
      status: "running",
      created_at: created,
      updated_at: created,
      eta_seconds: null,
      error: null,
      stages: [{ name: "reading", status: "running" }],
    };
    await this.save(key, job);
    const task = (async () => {
      try {
        const result = await this.generate({
          context,
          chart: await this.store.get("raw:" + context.profile_id),
        });
        if (hash(result.context) !== key) throw new Error("context_mismatch");
        const start = new Date(context.target),
          y = start.getUTCFullYear(),
          m = start.getUTCMonth();
        const to =
          context.horizon === "day"
            ? context.target
            : new Date(
                Date.UTC(y, m + (context.horizon === "month" ? 1 : 12), 0),
              )
                .toISOString()
                .slice(0, 10);
        const sections =
          context.horizon === "day"
            ? ["reading"]
            : context.horizon === "month"
              ? ["overview", "early", "mid", "late", "focus"]
              : ["overview", "q1", "q2", "q3", "q4", "focus"];
        const segments =
          context.horizon === "day"
            ? {}
            : forecastSegments(context.target, to, sections.slice(1, -1));
        if (
          result.from !== context.target ||
          result.to !== to ||
          hash(result.segments) !== hash(segments)
        )
          throw new Error("window_mismatch");
        const readings = Object.fromEntries(
          (["en", "tr"] as const).map((language) => [
            language,
            Object.fromEntries(
              sections.map((section) => {
                const value = result.readings?.[language]?.[section];
                if (typeof value !== "string" || !value.trim())
                  throw new Error("incomplete_reading");
                return [section, value];
              }),
            ),
          ]),
        );
        const p = await this.store.get<BirthProfile>(
          "profile:" + context.profile_id,
        );
        const current =
          p &&
          ((p.is_self
            ? (await this.store.get("me"))?.current_place
            : p.current_place) ??
            p.birth.place);
        if (
          !p ||
          hash(
            forecastContext(
              p,
              current!,
              context.target,
              context.horizon,
              context.lens,
            ),
          ) !== key
        )
          throw new Error("profile_changed");
        await this.store.put("forecast-reading:" + key, readings);
        await this.indexReport(context);
        await this.save(key, {
          ...job,
          status: "succeeded",
          updated_at: new Date().toISOString(),
          stages: [{ name: "reading", status: "ok" }],
        });
      } catch {
        await this.save(key, this.failed(job, "generation_failed"));
      }
    })().finally(() => this.running.delete(task));
    this.running.add(task);
    return { status: "pending", job };
  }
}
