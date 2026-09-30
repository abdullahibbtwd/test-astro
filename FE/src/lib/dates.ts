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
