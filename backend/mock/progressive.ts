import type {
  BirthProfile,
  Lang,
  NatalReading,
  NatalSection,
  ReadingFeedbackInput,
  ReadingOutline,
} from "../../frontend/contracts/spec-types";
import { Jobs } from "./jobs";
import { fixture } from "./fixtures";
export class MockProgressive {
  private opened = new Map<string, Set<string>>();
  private complete = new Set<string>();
  private sectionJobs = new Map<string, string>();
  private votes = new Map<string, ReadingFeedbackInput>();
  constructor(private jobs: Jobs) {}
  private id(profile: BirthProfile) {
    return profile.profile_id + ":" + profile.chart_key;
  }
  private fail(status: number, code: string): never {
    throw Object.assign(new Error(code), { statusCode: status, code });
  }
  private reading(index: number, lang: Lang): NatalReading {
    return fixture(`natal.${index}.${lang}`);
  }
  private allowed(
    profile: BirthProfile,
    sections: NatalSection[],
    key: string,
    anonymous: boolean,
  ) {
    const index = sections.findIndex((s) => s.key === key);
    if (index < 0) this.fail(404, "not_found");
    if (anonymous && sections[index]!.movement === 2)
      this.fail(403, "account_required");
    const opened = this.opened.get(this.id(profile)) ?? new Set();
    const furthest = Math.max(
      -1,
      ...sections.map((s, i) => (opened.has(s.key) ? i : -1)),
    );
    if (
      anonymous &&
      !this.complete.has(this.id(profile)) &&
      index > furthest + 1
    )
      this.fail(409, "read_ahead_limit");
  }
  accuracy(profile: BirthProfile) {
    const votes = [...this.votes.entries()]
      .filter(([key]) => key.startsWith(this.id(profile) + ":"))
      .map(([, vote]) => vote);
    return votes.length
      ? {
          n: votes.length,
          score:
            votes.reduce(
              (n, v) =>
                n +
                (v.rating === "spot_on" ? 2 : v.rating === "partly" ? 1 : 0),
              0,
            ) /
            (2 * votes.length),
        }
      : null;
  }
  outline(
    profile: BirthProfile,
    index: number,
    lang: Lang,
    anonymous: boolean,
  ): ReadingOutline {
    const reading = this.reading(index, lang);
    return {
      profile_id: profile.profile_id,
      chart_key: profile.chart_key,
      lang,
      title: reading.title,
      parts: reading.parts,
      big_three: {
        sun: profile.big_three.sun,
        moon: profile.big_three.moon,
        rising: profile.big_three.ascendant,
      },
      accuracy: this.accuracy(profile),
      sections: reading.sections.map(({ key, movement, house, title }) => {
        const id = this.sectionJobs.get(`${this.id(profile)}:${key}:${lang}`),
          job = id && this.jobs.get(id);
        return {
          key,
          movement,
          house,
          title,
          status: !job
            ? "not_started"
            : job.status === "succeeded"
              ? "ready"
              : job.status === "failed"
                ? "failed"
                : "generating",
          access: anonymous && movement === 2 ? "account_required" : "open",
        };
      }),
    };
  }
  section(
    profile: BirthProfile,
    index: number,
    lang: Lang,
    key: string,
    anonymous: boolean,
    scenario: string,
    retry: boolean,
  ) {
    const reading = this.reading(index, lang);
    this.allowed(profile, reading.sections, key, anonymous);
    const id = `${this.id(profile)}:${key}:${lang}`;
    const job = this.jobs.resource(id, "natal_section", scenario, retry);
    this.sectionJobs.set(id, job.job_id);
    if (job.status === "failed") this.fail(503, "generation_failed");
    return job.status === "succeeded"
      ? { section: reading.sections.find((s) => s.key === key)! }
      : { job };
  }
  progress(
    profile: BirthProfile,
    index: number,
    lang: Lang,
    key: string,
    event: string,
    anonymous: boolean,
    scenario: string,
  ) {
    const reading = this.reading(index, lang);
    this.allowed(profile, reading.sections, key, anonymous);
    const id = this.sectionJobs.get(`${this.id(profile)}:${key}:${lang}`);
    if (!id || this.jobs.get(id)?.status !== "succeeded")
      this.fail(409, "read_ahead_limit");
    if (event !== "opened") return;
    const opened = this.opened.get(this.id(profile)) ?? new Set();
    opened.add(key);
    this.opened.set(this.id(profile), opened);
    if (opened.size >= 3)
      this.finish(profile, index, lang, anonymous, scenario);
    else {
      const next =
        reading.sections[reading.sections.findIndex((s) => s.key === key) + 1];
      if (next && (!anonymous || next.movement === 1))
        this.section(
          profile,
          index,
          lang,
          next.key,
          anonymous,
          scenario,
          false,
        );
    }
  }
  finish(
    profile: BirthProfile,
    index: number,
    lang: Lang,
    anonymous: boolean,
    scenario: string,
  ) {
    this.complete.add(this.id(profile));
    for (const section of this.reading(index, lang).sections)
      if (!anonymous || section.movement === 1)
        this.section(
          profile,
          index,
          lang,
          section.key,
          anonymous,
          scenario,
          false,
        );
    return this.jobs.resource(
      `complete:${this.id(profile)}:${lang}:${anonymous}`,
      "natal_section",
      scenario,
      false,
    );
  }
  feedback(profile: BirthProfile, index: number, input: ReadingFeedbackInput) {
    if (
      (input.comment?.length ?? 0) > 500 ||
      (input.target.type === "section" &&
        !this.reading(index, "tr").sections.some(
          (s) => s.key === input.target.key,
        )) ||
      (input.target.type !== "section" && input.target.key !== undefined)
    )
      this.fail(400, "validation_error");
    this.votes.set(
      `${this.id(profile)}:${input.target.type}:${input.target.key ?? "all"}`,
      input,
    );
    return { accuracy: this.accuracy(profile)! };
  }
}
