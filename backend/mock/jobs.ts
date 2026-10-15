import { randomUUID } from "node:crypto";
import type { Job } from "../../frontend/contracts/spec-types";

export class Jobs {
  private byId = new Map<
    string,
    { job: Job; start: number; duration: number; fail: boolean }
  >();
  private byKey = new Map<string, string>();
  constructor(
    private now = () => Date.now(),
    private duration = 6000,
  ) {}
  get(id: string) {
    const entry = this.byId.get(id);
    if (!entry) return undefined;
    const elapsed = this.now() - entry.start;
    if (elapsed >= 24 * 60 * 60 * 1000) {
      this.byId.delete(id);
      for (const [key, value] of this.byKey)
        if (value === id) this.byKey.delete(key);
      return undefined;
    }
    const stage = Math.min(3, Math.floor((elapsed / entry.duration) * 4));
    const finished = elapsed >= entry.duration;
    entry.job.status = finished
      ? entry.fail
        ? "failed"
        : "succeeded"
      : elapsed === 0
        ? "queued"
        : "running";
    entry.job.stages = entry.job.stages.map((s, i) => ({
      ...s,
      status: finished
        ? entry.fail && i === 3
          ? "failed"
          : "ok"
        : i < stage
          ? "ok"
          : i === stage
            ? "running"
            : "pending",
    }));
    entry.job.updated_at = new Date(this.now()).toISOString();
    entry.job.error =
      finished && entry.fail
        ? {
            type: "about:blank",
            title: "Generation failed",
            status: 503,
            code: "generation_failed",
          }
        : null;
    return structuredClone(entry.job);
  }
  resource(key: string, kind: Job["kind"], scenario: string, retry: boolean) {
    const current = this.byKey.get(key);
    let job = current ? this.get(current) : undefined;
    if (!job || (retry && job.status === "failed")) {
      const id = randomUUID(),
        time = new Date(this.now()).toISOString();
      job = {
        job_id: id,
        kind,
        status: "queued",
        stages: ["compute_chart", "reading", "translation", "validate"].map(
          (name) => ({ name, status: "pending" }),
        ),
        created_at: time,
        updated_at: time,
        eta_seconds: null,
        error: null,
      };
      this.byId.set(id, {
        job,
        start: this.now(),
        duration: scenario === "slow" ? 90000 : this.duration,
        fail: scenario === "fail",
      });
      this.byKey.set(key, id);
    }
    return this.get(job.job_id)!;
  }
}
