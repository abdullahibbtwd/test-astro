import type { Lang, Lens, YearForecast } from "../contracts/spec-types";
import { scores } from "../mock-api/scripts/calendar";
// Mirrors pr_calendar.segment_dates: inclusive civil dates split by day count.
export function forecastSegments<K extends string>(
  from: string,
  to: string,
  keys: K[],
): Record<K, { from: string; to: string }> {
  const first = Date.parse(from),
    days = (Date.parse(to) - first) / 86400000 + 1;
  const at = (n: number) =>
    new Date(first + n * 86400000).toISOString().slice(0, 10);
  return Object.fromEntries(
    keys.map((key, i) => [
      key,
      {
        from: at(Math.floor((days * i) / keys.length)),
        to: at(Math.floor((days * (i + 1)) / keys.length) - 1),
      },
    ]),
  ) as Record<K, { from: string; to: string }>;
}
export function dayForecast(
  cal: any,
  catalogue: any,
  profileId: string,
  date: string,
  lens = "general",
) {
  const day = cal.days[date],
    raw = cal.rawScores.find((d: any) => d.local_date === date);
  if (!day || !raw) return undefined;
  return {
    profile_id: profileId,
    date,
    tz: cal.best.tz,
    lens,
    tone: day.tone,
    tone_label: day.tone_label,
    score_10: scores[day.tone],
    areas: Object.fromEntries(
      Object.entries(raw.goals).map(([key, g]: any) => [
        key,
        {
          band: g.band,
          label: catalogue.day_bands[g.band],
          score_10: scores[g.band],
          drivers: raw.drivers[key].map((id: string) => cal.eventLabels[id]),
        },
      ]),
    ),
    moon: day.moon,
    retrograde: day.retrograde,
    events: day.events,
    transits: day.transits,
    day_note: day.day_note,
    best_activities: day.best_activities,
    reading: { status: "absent", absence: { reason: "not_generated" } },
  };
}
export function monthForecast(
  cal: any,
  profileId: string,
  month: string,
  lens = "general",
) {
  const data = cal.months[month];
  if (!data) return undefined;
  const last = new Date(
    Date.UTC(Number(month.slice(0, 4)), Number(month.slice(5)), 0),
  ).getUTCDate();
  return {
    profile_id: profileId,
    month,
    tz: data.tz,
    lens,
    segments: forecastSegments(`${month}-01`, `${month}-${last}`, [
      "early",
      "mid",
      "late",
    ]),
    reading: { status: "absent", absence: { reason: "not_generated" } },
    highlights: {
      favorable_days: data.days
        .filter((d: any) => d.tone === "favorable")
        .map((d: any) => d.date),
      challenging_days: data.days
        .filter((d: any) => d.tone === "challenging")
        .map((d: any) => d.date),
      periods: data.periods,
      major_transits: data.major_transits,
      lunations: data.lunations,
      eclipses: data.eclipses,
      retrogrades: data.retrograde_periods,
    },
  };
}

/** Calendar-aligned twelve-month view of the existing engine's facts. */
export function yearForecast(
  cal: any,
  profileId: string,
  month: string,
  lang: Lang,
  lens: Lens = "general",
): YearForecast | undefined {
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(month)) return undefined;
  const year = Number(month.slice(0, 4)),
    index = Number(month.slice(5)) - 1;
  const at = (offset: number, day = 1) =>
    new Date(Date.UTC(year, index + offset, day)).toISOString().slice(0, 10);
  const from = at(0),
    to = at(12, 0);
  if (cal.year.horizon.from > from || cal.year.horizon.to < to)
    return undefined;
  const overlaps = (e: any) =>
    e.start && e.end && e.start <= to && e.end >= from;
  const periods = cal.periods
    .filter(overlaps)
    .filter((p: any) => p.importance === "major" || p.strength === "strong")
    .sort(
      (a: any, b: any) =>
        Number(b.importance === "major") - Number(a.importance === "major") ||
        Number(b.strength === "strong") - Number(a.strength === "strong") ||
        a.peak.localeCompare(b.peak) ||
        a.id.localeCompare(b.id),
    );
  const keyEvents = Object.values(cal.items)
    .filter(
      (e: any) =>
        overlaps(e) &&
        (e.kind === "eclipse" ||
          (e.kind === "transit" && e.importance === "major") ||
          (e.kind === "ingress" &&
            ["jupiter", "saturn", "uranus", "neptune", "pluto"].includes(
              e.body,
            ))),
    )
    .sort(
      (a: any, b: any) =>
        a.start.localeCompare(b.start) || a.id.localeCompare(b.id),
    );
  return {
    profile_id: profileId,
    from,
    to,
    tz: cal.best.tz,
    lens,
    quarters: (["q1", "q2", "q3", "q4"] as const).map((key) => ({
      key,
      ...forecastSegments(from, to, ["q1", "q2", "q3", "q4"])[key],
    })),
    reading: { status: "absent", absence: { reason: "not_generated" } },
    highlights: {
      strongest_periods: periods
        .filter((p: any) => p.kind === "favorable")
        .slice(0, 6),
      challenging_periods: periods
        .filter((p: any) => p.kind === "challenging")
        .slice(0, 6),
      key_events: keyEvents.map((e: any) => ({
        id: e.id,
        kind: e.kind,
        label: e.label,
        importance: e.importance,
        has_text: e.has_text,
      })),
      retrogrades: cal.year.retrograde_periods.filter(overlaps),
    },
    months: Array.from({ length: 12 }, (_, i) => ({
      month: at(i).slice(0, 7),
      label: new Intl.DateTimeFormat(lang, {
        month: "long",
        year: "numeric",
        timeZone: "UTC",
      }).format(new Date(at(i))),
    })),
  };
}
