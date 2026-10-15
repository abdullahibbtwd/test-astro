import { TZDate } from "@date-fns/tz";
import type {
  NotificationCandidate,
  NotificationPrefs,
} from "../../contracts/spec-types";
export type ReminderCandidate = NotificationCandidate & { manual?: boolean };
export interface PlannedNotification {
  id: string;
  date: string;
  instant: number;
  text: string;
  deep_link: NotificationCandidate["deep_link"];
  type: NotificationCandidate["type"];
  manual: boolean;
}
export function notificationInstant(date: string, time: string, tz: string) {
  const [y, m, d] = date.split("-").map(Number),
    [hour, minute] = time.split(":").map(Number);
  return new TZDate(y!, m! - 1, d!, hour!, minute!, tz).getTime();
}
export function inQuietHours(time: string, start: string, end: string) {
  return start === end
    ? false
    : start < end
      ? time >= start && time < end
      : time >= start || time < end;
}
export function planNotifications(
  candidates: ReminderCandidate[],
  prefs: NotificationPrefs,
  tz: string,
  now = Date.now(),
): PlannedNotification[] {
  if (!prefs.enabled) return [];
  const unique = [
    ...new Map(
      candidates.map((candidate, index) => [
        candidate.id,
        { candidate, index },
      ]),
    ).values(),
  ];
  const eligible = unique
    .filter(({ candidate }) => candidate.manual || prefs.types[candidate.type])
    .map(({ candidate, index }) => {
      const time = candidate.manual ? "09:00" : prefs.time;
      const adjusted = inQuietHours(
        time,
        prefs.quiet_hours.start,
        prefs.quiet_hours.end,
      )
        ? prefs.quiet_hours.end
        : time;
      return {
        candidate,
        index,
        instant: notificationInstant(candidate.trigger_date, adjusted, tz),
      };
    })
    .filter((item) => item.instant > now)
    .sort(
      (a, b) =>
        a.candidate.priority - b.candidate.priority ||
        Number(!!b.candidate.manual) - Number(!!a.candidate.manual) ||
        a.candidate.trigger_date.localeCompare(b.candidate.trigger_date) ||
        a.index - b.index,
    );
  const chosen: PlannedNotification[] = [];
  for (const item of eligible) {
    const date = item.candidate.trigger_date;
    if (chosen.filter((x) => x.date === date).length >= prefs.max_per_day)
      continue;
    const dates = [
      ...chosen.map((x) => Date.parse(x.date)),
      Date.parse(date),
    ].sort((a, b) => a - b);
    if (
      dates.some(
        (start, i) =>
          dates.slice(i).filter((day) => day < start + 7 * 86400000).length >
          prefs.max_per_week,
      )
    )
      continue;
    chosen.push({
      id: item.candidate.id,
      date,
      instant: item.instant,
      text: item.candidate.text,
      deep_link: item.candidate.deep_link,
      type: item.candidate.type,
      manual: !!item.candidate.manual,
    });
  }
  return chosen.sort((a, b) => a.instant - b.instant);
}
