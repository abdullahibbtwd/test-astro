export function upper(s: string, lang: "tr" | "en"): string {
  return lang === "tr"
    ? s.replace(/i/g, "İ").replace(/ı/g, "I").toUpperCase()
    : s.toUpperCase();
}
