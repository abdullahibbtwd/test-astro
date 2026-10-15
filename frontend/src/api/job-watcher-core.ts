import type { Job } from "../../contracts/spec-types";
import { pollingDelay } from "./job-policy";
export type WatchedJob = { id: string; created_at?: string; job?: Job };
export type JobCompletion = {
  job: Job;
  parents: readonly unknown[][];
  missing: boolean;
};
type Entry = {
  ref: WatchedJob;
  parents: Map<string, unknown[]>;
  due: number;
  attempt: number;
  lang: string;
};
/** One scheduler owns all job requests. No component starts its own poll. */
export class JobWatcher {
  private entries = new Map<string, Entry>();
  private completed = new Set<string>();
  private timer: ReturnType<typeof setTimeout> | undefined;
  private running = false;
  private active = false;
  private lastStart = -Infinity;
  constructor(
    private io: {
      fetch: (lang: string, id: string) => Promise<Job>;
      publish: (lang: string, id: string, job: Job) => void;
      complete: (event: JobCompletion, lang: string) => void;
      now?: () => number;
      setTimer?: typeof setTimeout;
      clearTimer?: typeof clearTimeout;
    },
  ) {}
  private now = () => this.io.now?.() ?? Date.now();
  register(lang: string, ref: WatchedJob, parent: readonly unknown[]) {
    const key = `${lang}:${ref.id}`;
    if (this.completed.has(key)) return;
    let entry = this.entries.get(key);
    if (!entry) {
      entry = { ref, parents: new Map(), due: this.now(), attempt: 0, lang };
      this.entries.set(key, entry);
    }
    entry.parents.set(JSON.stringify(parent), [...parent]);
    this.schedule();
  }
  setActive(active: boolean) {
    this.active = active;
    if (active)
      for (const e of this.entries.values())
        e.due = Math.min(e.due, this.now());
    this.schedule();
  }
  clear() {
    this.entries.clear();
    this.completed.clear();
    this.active = false;
    this.schedule();
  }
  private schedule() {
    if (this.timer) (this.io.clearTimer ?? clearTimeout)(this.timer);
    this.timer = undefined;
    if (!this.active || this.running || !this.entries.size) return;
    const due = Math.max(
      this.lastStart + 1000,
      Math.min(...[...this.entries.values()].map((e) => e.due)),
    );
    this.timer = (this.io.setTimer ?? setTimeout)(
      () => {
        this.timer = undefined;
        void this.poll();
      },
      Math.max(0, due - this.now()),
    );
  }
  private async poll() {
    if (!this.active || this.running) return;
    const pair = [...this.entries].sort((a, b) => a[1].due - b[1].due)[0];
    if (!pair) return;
    const [key, entry] = pair;
    this.running = true;
    this.lastStart = this.now();
    try {
      const job = {
        ...entry.ref.job,
        ...(await this.io.fetch(entry.lang, entry.ref.id)),
      } as Job;
      if (this.entries.get(key) !== entry) return;
      this.io.publish(entry.lang, entry.ref.id, job);
      if (job.status === "succeeded" || job.status === "failed")
        this.finish(key, entry, job, false);
      else {
        entry.ref.job = job;
        entry.ref.created_at = job.created_at;
        entry.due =
          this.now() +
          pollingDelay(
            entry.attempt++,
            Math.max(0, this.now() - Date.parse(job.created_at)),
          );
      }
    } catch (error) {
      if (this.entries.get(key) !== entry) return;
      if (
        error &&
        typeof error === "object" &&
        "status" in error &&
        error.status === 404
      ) {
        this.finish(
          key,
          entry,
          { ...entry.ref.job, job_id: entry.ref.id, status: "failed" } as Job,
          true,
        );
      } else
        entry.due =
          this.now() +
          pollingDelay(
            entry.attempt++,
            entry.ref.created_at
              ? Math.max(0, this.now() - Date.parse(entry.ref.created_at))
              : 0,
          );
    } finally {
      this.running = false;
      this.schedule();
    }
  }
  private finish(key: string, entry: Entry, job: Job, missing: boolean) {
    this.entries.delete(key);
    this.completed.add(key);
    this.io.complete(
      { job, parents: [...entry.parents.values()], missing },
      entry.lang,
    );
  }
}
