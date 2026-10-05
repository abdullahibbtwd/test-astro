export function todayLocal(tz = "Europe/Istanbul", mockDate?: string) {
  if (__DEV__ && mockDate) return mockDate;
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: tz,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}
export function formatDate(date: string, lang: string) {
  const [y, m, d] = date.split("-").map(Number);
  return new Intl.DateTimeFormat(lang, {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(y!, m! - 1, d!)));
}
export function validBirth(date: string, time: string, today: string) {
  return (
    /^\d{4}-\d{2}-\d{2}$/.test(date) &&
    !Number.isNaN(Date.parse(date)) &&
    new Date(date).toISOString().slice(0, 10) === date &&
    date >= "1900-01-01" &&
    date <= today &&
    /^([01]\d|2[0-3]):[0-5]\d$/.test(time)
  );
}
export const upper = (text: string, language: string) =>
  text.toLocaleUpperCase(language === "tr" ? "tr-TR" : "en");

/** Calendar values are always interpreted in UTC, never the device timezone. */
function calendarDate(value: string) {
  return new Date(
    `${value.slice(0, 10)}${value.length === 7 ? "-01" : ""}T12:00:00Z`,
  );
}
const locale = (lang: string) => (lang.startsWith("tr") ? "tr-TR" : "en-GB");
export function formatMonth(value: string, lang: string) {
  return new Intl.DateTimeFormat(locale(lang), {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(calendarDate(value));
}
export function formatDay(
  value: string,
  lang: string,
  options: { weekday?: boolean } = {},
) {
  return new Intl.DateTimeFormat(locale(lang), {
    day: "numeric",
    month: "long",
    ...(options.weekday ? { weekday: "long" as const } : {}),
    timeZone: "UTC",
  }).format(calendarDate(value));
}
export function formatShort(value: string, lang: string) {
  return new Intl.DateTimeFormat(locale(lang), {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  }).format(calendarDate(value));
}
export function formatRange(a: string, b: string, lang: string) {
  if (a === b) return formatShort(a, lang);
  if (a.slice(0, 7) === b.slice(0, 7))
    return `${Number(a.slice(8, 10))}–${formatShort(b, lang)}`;
  if (a.slice(0, 4) === b.slice(0, 4))
    return `${formatShort(a, lang)} – ${formatShort(b, lang)}`;
  const f = new Intl.DateTimeFormat(locale(lang), {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
  return `${f.format(calendarDate(a))} – ${f.format(calendarDate(b))}`;
}
