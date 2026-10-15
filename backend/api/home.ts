import type {
  HomeSummary,
  NotificationCandidate,
  UpcomingItem,
  DayForecast,
  Catalogue,
} from "../../frontend/contracts/spec-types";
const kinds: Record<NotificationCandidate["type"], UpcomingItem["kind"]> = {
  favorable_window: "best_window",
  period_start: "period_start",
  lunation_in_house: "lunation",
  retrograde_start: "retrograde_start",
  station_on_point: "transit_peak",
  eclipse_hit: "eclipse",
};
export function homeSummary(
  day: DayForecast,
  label: string,
  catalogue: Catalogue,
  today: HomeSummary["today"],
  notifications: NotificationCandidate[],
): HomeSummary {
  const end = new Date(`${day.date}T12:00:00Z`);
  end.setUTCDate(end.getUTCDate() + 14);
  return {
    date: day.date,
    tz: day.tz,
    greeting_name: label,
    tone: day.tone,
    tone_label: day.tone_label,
    score_10: day.score_10,
    tiles: (["love", "career", "money", "family"] as const).map((key) => ({
      key,
      label: catalogue.goals[key],
      band: day.areas[key].band,
      score_10: day.areas[key].score_10,
    })),
    moon: day.moon,
    today,
    next_up: notifications
      .filter(
        (n) =>
          n.trigger_date > day.date &&
          n.trigger_date <= end.toISOString().slice(0, 10),
      )
      .sort(
        (a, b) =>
          a.trigger_date.localeCompare(b.trigger_date) ||
          a.priority - b.priority,
      )
      .slice(0, 3)
      .map((n) => ({
        kind: kinds[n.type],
        date: n.trigger_date,
        label: n.text,
        deep_link: n.deep_link,
      })),
  };
}
