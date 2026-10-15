import fs from "node:fs";
import path from "node:path";
import type { Catalogue, Lang } from "../../../frontend/contracts/spec-types";
export const scores: Record<string, number> = {
  strongly_supportive: 9,
  supportive: 8,
  favorable: 8,
  quiet: 6,
  mixed: 5,
  challenging: 4,
  strongly_challenging: 2,
};
export function calendarFixtures(
  root: string,
  lang: Lang,
  cat: Catalogue,
  labels: any,
  profileId: string,
  source?: { dir: string; birthDate: string; years: number[] },
) {
  const dir =
    source?.dir ?? path.join(root, "cal_run/20260929-130418_c7m_1979-03-30");
  const read = (name: string) =>
    JSON.parse(
      fs.readFileSync(
        path.join(dir, `${name}_${source?.birthDate ?? "1979-03-30"}.json`),
        "utf8",
      ),
    );
  const personal = read("personal_events");
  const periodsRaw = read("periods");
  const rawScores = read("day_scores");
  const bestRaw = read("best_days");
  const texts = read(`texts_${lang}`);
  const byId: Record<string, any> = {};
  for (const year of source?.years ?? [2026, 2027])
    for (const ev of JSON.parse(
      fs.readFileSync(
        path.join(root, `cal_run/_collective/${year}.json`),
        "utf8",
      ),
    ).events)
      byId[ev.id] = ev;
  for (const ev of personal.events) byId[ev.id] = ev;
  for (const p of periodsRaw.periods)
    byId[p.id] = { ...p, period_kind: p.kind, kind: "period" };
  const textById: Record<string, any> = {};
  for (const [key, value] of Object.entries(texts))
    textById[key.slice(2)] = value;
  const label = (id: string) =>
    labels.events[id]?.[lang] ?? textById[id]?.label;
  const kind = (s: string) =>
    ({
      new_moon: "lunation",
      full_moon: "lunation",
      solar_eclipse: "eclipse",
      lunar_eclipse: "eclipse",
      station_retrograde: "station",
      station_direct: "station",
    })[s] ?? s;
  const ref = (id: string) => {
    const e = byId[id];
    if (!e || !label(id)) throw new Error(`Unresolved calendar event ${id}`);
    return {
      id,
      kind: kind(e.kind),
      label: label(id),
      importance: e.importance ?? "collective",
      has_text: Boolean(textById[id]?.text),
    };
  };
  const local = (iso: string) =>
    new Intl.DateTimeFormat("en-CA", {
      timeZone: personal.tz,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(new Date(iso));
  const dateOf = (e: any, which: "start" | "end") =>
    e[`${which}_local`] ??
    (e[`${which}_utc`]
      ? local(e[`${which}_utc`])
      : e.t_utc
        ? local(e.t_utc)
        : undefined);
  const transit = (id: string, date: string) => {
    const e = byId[id];
    const exact = [...e.exacts_local].sort();
    const phase =
      date < exact[0] ? "building" : date > exact.at(-1) ? "easing" : "peak";
    return {
      id,
      label: label(id),
      importance: e.importance,
      transiting: e.t_body,
      aspect: e.aspect,
      natal: ["asc", "dsc", "mc", "ic"].includes(e.n_point)
        ? e.n_point.toUpperCase()
        : e.n_point,
      start: e.start_local,
      end: e.end_local,
      exact_dates: exact,
      phase,
      phase_label: cat.transit_phases[phase],
      has_text: Boolean(textById[id]?.text),
    };
  };
  const periods = periodsRaw.periods.map((p: any) => ({
    id: p.id,
    goal: p.goal,
    goal_label: cat.goals[p.goal as keyof typeof cat.goals],
    kind: p.kind,
    label: label(p.id),
    start: p.start_local,
    end: p.end_local,
    peak: p.peak_local,
    strength: p.strength,
    importance: p.importance,
    has_text: Boolean(textById[p.id]?.text),
  }));
  const retro = (id: string) => ({
    id,
    body: byId[id].body,
    label: label(id),
    start: dateOf(byId[id], "start"),
    end: dateOf(byId[id], "end"),
  });
  const months: Record<string, any> = {};
  const days: Record<string, any> = {};
  for (const filename of fs
    .readdirSync(dir)
    .filter((f) => /^calendar_.*\.json$/.test(f))) {
    const m = JSON.parse(fs.readFileSync(path.join(dir, filename), "utf8"));
    const monthDays = m.days.map((d: any) => ({
      date: d.local_date,
      tone: d.tone,
      tone_label: cat.tones[d.tone as keyof typeof cat.tones],
      moon: {
        phase: d.moon.phase,
        phase_label:
          cat.moon_phases[d.moon.phase as keyof typeof cat.moon_phases],
        sign: d.moon.sign,
        sign_label: cat.signs[d.moon.sign as keyof typeof cat.signs],
        void_of_course: d.moon.voc_local.map((w: any) => ({
          start: (w.start ?? w.from ?? w[0]).slice(-5),
          end: (w.end ?? w.to ?? w[1]).slice(-5),
        })),
      },
      retrograde: d.retrograde,
      events: d.events.map((e: any) => ref(typeof e === "string" ? e : e.id)),
      active_periods: d.active_periods.map((p: any) => {
        const id = typeof p === "string" ? p : p.id;
        const source = byId[id];
        return { id, goal: source.goal, kind: source.period_kind };
      }),
      goals: d.goals,
    }));
    for (const d of monthDays) days[d.date] = d;
    months[m.month] = {
      profile_id: profileId,
      month: m.month,
      tz: m.tz,
      days: monthDays,
      lunations: m.lunations.map(ref),
      eclipses: m.eclipses.map(ref),
      retrograde_periods: m.retrograde_periods.map(retro),
      major_transits: m.major_transits.map((id: string) =>
        transit(id, `${m.month}-15`),
      ),
      periods: m.periods.map((id: string) =>
        periods.find((p: any) => p.id === id),
      ),
    };
  }
  const activities = Object.keys(cat.activities).map((activity) => {
    const a = bestRaw.activities[activity];
    return {
      activity,
      label: cat.activities[activity as keyof typeof cat.activities],
      days: a.days.map((d: any) => ({ date: d.local_date, grade: d.grade })),
      top_days: a.top_days,
      windows: a.windows.map((w: any) => ({
        start: w.start,
        end: w.end,
        days: w.n,
      })),
      avoid_days: a.avoid_days.map((d: any) => d.local_date),
    };
  });
  const best = {
    horizon: { from: bestRaw.horizon.from_local, to: bestRaw.horizon.to_local },
    tz: bestRaw.tz,
    activities,
  };
  const bestDetails: Record<string, any> = {};
  for (const a of activities)
    for (const d of a.days) {
      const reason = bestRaw.activities[a.activity].reasons[d.date];
      const text = texts[`b:${a.activity}:${d.date}`]?.text;
      bestDetails[`${a.activity}/${d.date}`] = {
        activity: a.activity,
        activity_label: a.label,
        date: d.date,
        grade: d.grade,
        grade_label: cat.grades[d.grade as keyof typeof cat.grades],
        reasons: {
          positive: (reason?.positive ?? []).map(
            (r: any) => r[`label_${lang}`],
          ),
          negative: (reason?.negative ?? []).map(
            (r: any) => r[`label_${lang}`],
          ),
        },
        text: text ? { status: "ready", text } : null,
      };
    }
  const good = (date: string) =>
    activities.flatMap((a) => {
      const d = a.days.find((d: any) => d.date === date);
      return d && ["good", "excellent"].includes(d.grade)
        ? [{ activity: a.activity, label: a.label, grade: d.grade }]
        : [];
    });
  const active = (date: string) =>
    personal.events
      .filter(
        (e: any) =>
          e.kind === "transit" &&
          ["major", "moderate"].includes(e.importance) &&
          e.start_local <= date &&
          e.end_local >= date,
      )
      .map((e: any) => transit(e.id, date));
  const dayDetails = Object.fromEntries(
    Object.entries(days).map(([date, d]) => [
      date,
      {
        ...d,
        day_note: texts[`d:${date}`]?.text
          ? { status: "ready", text: texts[`d:${date}`].text }
          : null,
        transits: active(date),
        best_activities: good(date),
      },
    ]),
  );
  const notifications = read("notifications").candidates.map((n: any) => ({
    id: n.id,
    type: n.type,
    priority: n.priority,
    trigger_date: n.trigger_local_date,
    suggested_time: n.suggested_local_time,
    text: n[`text_${lang}`],
    deep_link: n.deep_link,
  }));
  const items = Object.fromEntries(
    Object.entries(byId)
      .filter(
        ([id, e]) =>
          label(id) &&
          [
            "transit",
            "lunation",
            "eclipse",
            "station",
            "station_on_point",
            "ingress",
            "retrograde_period",
            "period",
          ].includes(kind(e.kind)),
      )
      .map(([id, e]: any) => [
        id,
        {
          ...ref(id),
          ...(dateOf(e, "start") ? { start: dateOf(e, "start") } : {}),
          ...(dateOf(e, "end") ? { end: dateOf(e, "end") } : {}),
          ...(e.exacts_local ? { exact_dates: e.exacts_local } : {}),
          ...(e.goal
            ? {
                goal: e.goal,
                goal_label: cat.goals[e.goal as keyof typeof cat.goals],
                period_kind: e.period_kind,
                peak: e.peak_local,
                strength: e.strength,
              }
            : {}),
          ...(e.sign ? { sign: e.sign } : {}),
          ...(e.body ? { body: e.body } : {}),
          text: textById[id]?.text
            ? { status: "ready", text: textById[id].text }
            : null,
        },
      ]),
  );
  const horizon = {
    from: personal.horizon.from_local,
    to: personal.horizon.to_local,
  };
  const unique = (field: string) => [
    ...new Map(
      Object.values(months)
        .flatMap((m: any) => m[field])
        .map((e: any) => [e.id, e]),
    ).values(),
  ];
  const year = {
    horizon,
    lunations: unique("lunations"),
    eclipses: unique("eclipses"),
    retrograde_periods: unique("retrograde_periods"),
    major_transits: unique("major_transits"),
    periods,
  };
  return {
    months,
    days: dayDetails,
    items,
    periods,
    year,
    best,
    bestDetails,
    notifications,
    rawScores: rawScores.days,
    label,
    active,
    good,
  };
}
