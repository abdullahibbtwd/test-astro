import { createHash, randomUUID } from "node:crypto";
import { Store } from "./store";
import { runReadingBridge } from "./readings";
import { forecastSegments } from "./forecast";
import { fixture } from "../mock-api/fixtures";
import type {
  BirthProfile,
  Place,
  Lang,
  Lens,
  Job,
} from "../contracts/spec-types";
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
const hash = (value: unknown) =>
  createHash("sha256").update(JSON.stringify(value)).digest("hex");
export class ForecastJobs {
  private running = new Set<Promise<void>>();
  constructor(
    private store: Store,
    private enabled = false,
    private generate = (input: any) =>
      runReadingBridge("forecast_bridge.py", input),
  ) {
    for (const saved of store.list<any>("forecast-job:"))
      if (["running", "queued"].includes(saved.job.status))
        this.save(saved.key, this.failed(saved.job, "interrupted"));
  }
  private save(key: string, job: Job) {
    this.store.transaction(() => {
      this.store.put("forecast-job:" + key, { key, job });
      this.store.put("job:" + job.job_id, job);
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
  async close() {
    await Promise.all(this.running);
  }
  get(context: ForecastContext, lang: Lang, retry = false): any {
    const key = hash(context),
      cached = this.store.get("forecast-reading:" + key);
    if (cached)
      return context.horizon === "day"
        ? { status: "ready", text: cached[lang].reading }
        : {
            status: "ready",
            ...cached[lang],
            focus_title: fixture(`catalogue.${lang}`).lens_focus_titles[
              context.lens
            ],
          };
    const previous = this.store.get("forecast-job:" + key)?.job as
      Job | undefined;
    if (previous && !(retry && previous.status === "failed"))
      return previous.status === "failed"
        ? { status: "failed", error: previous.error }
        : { status: "pending", job: previous };
    if (!this.enabled)
      return { status: "absent", absence: { reason: "not_generated" } };
    if (this.running.size)
      return {
        status: "failed",
        error: {
          type: "about:blank",
          title: "Another forecast is being prepared",
          status: 503,
          code: "generation_failed",
        },
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
    this.save(key, job);
    const task = (async () => {
      try {
        const result = await this.generate({
          context,
          chart: this.store.get("raw:" + context.profile_id),
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
        const p = this.store.get<BirthProfile>("profile:" + context.profile_id);
        const current =
          p &&
          ((p.is_self
            ? this.store.get("me")?.current_place
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
        this.store.put("forecast-reading:" + key, readings);
        this.save(key, {
          ...job,
          status: "succeeded",
          updated_at: new Date().toISOString(),
          stages: [{ name: "reading", status: "ok" }],
        });
      } catch {
        this.save(key, this.failed(job, "generation_failed"));
      }
    })().finally(() => this.running.delete(task));
    this.running.add(task);
    return { status: "pending", job };
  }
}
