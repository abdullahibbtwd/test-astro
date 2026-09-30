export function shiftDate(date: string, days: number) {
  const value = new Date(`${date}T12:00:00Z`);
  value.setUTCDate(value.getUTCDate() + days);
  return value.toISOString().slice(0, 10);
}
export function shiftMonth(month: string, delta: number) {
  const [y, m] = month.split("-").map(Number);
  return new Date(Date.UTC(y!, m! - 1 + delta, 1)).toISOString().slice(0, 7);
}
export function monthDays(month: string) {
  const [y, m] = month.split("-").map(Number);
  const start = new Date(Date.UTC(y!, m! - 1, 1)),
    count = new Date(Date.UTC(y!, m!, 0)).getUTCDate();
  return {
    offset: (start.getUTCDay() + 6) % 7,
    dates: Array.from(
      { length: count },
      (_, i) => `${month}-${String(i + 1).padStart(2, "0")}`,
    ),
  };
}
export function notificationRoute(
  link: { view: string; ref: string },
  profile?: string,
) {
  const suffix = profile ? `?profile=${encodeURIComponent(profile)}` : "";
  if (link.view === "best_days") {
    const [, activity, date] = link.ref.split(":");
    return `/best-days/${activity ?? "love"}${suffix}${suffix ? "&" : "?"}date=${date ?? ""}`;
  }
  if (link.view === "period" || link.view === "event")
    return `/calendar/item/${encodeURIComponent(link.ref)}${suffix}`;
  return `/(tabs)/ahead?view=calendar${profile ? `&profile=${encodeURIComponent(profile)}` : ""}`;
}
export function greetingKey(tz: string, now = new Date()) {
  const hour = Number(
    new Intl.DateTimeFormat("en", {
      timeZone: tz,
      hour: "numeric",
      hourCycle: "h23",
    }).format(now),
  );
  return hour >= 5 && hour < 12
    ? "goodMorning"
    : hour >= 12 && hour < 18
      ? "goodAfternoon"
      : "goodEvening";
}
