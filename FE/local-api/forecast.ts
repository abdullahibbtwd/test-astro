import { scores } from "../mock-api/scripts/calendar";
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
    segments: {
      early: { from: `${month}-01`, to: `${month}-10` },
      mid: { from: `${month}-11`, to: `${month}-20` },
      late: { from: `${month}-21`, to: `${month}-${last}` },
    },
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
