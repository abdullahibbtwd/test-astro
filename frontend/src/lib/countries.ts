import countries from "../i18n/countries.json";
export function countryName(
  iso2: string | null | undefined,
  lang: string,
  apiName?: string,
) {
  if (apiName && apiName !== iso2) return apiName;
  const entry = countries[(iso2 ?? "").toUpperCase() as keyof typeof countries];
  return (
    entry?.[lang.startsWith("tr") ? "tr" : "en"] ??
    (lang.startsWith("tr") ? "Bilinmeyen ülke" : "Unknown country")
  );
}
export function countryFlag(iso2: string) {
  return /^[a-z]{2}$/i.test(iso2)
    ? [...iso2.toUpperCase()]
        .map((c) => String.fromCodePoint(127397 + c.charCodeAt(0)))
        .join("")
    : "";
}
