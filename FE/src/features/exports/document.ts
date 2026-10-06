import type {
  BirthProfile,
  ChartData,
  Catalogue,
  NatalReading,
} from "../../../contracts/spec-types";
import { degrees, isRetrograde, inSign } from "../chart/facts";
import { renderChartResolved } from "../../../packages/wheel-core/resolved";
export const escapeHtml = (value: string) =>
  value.replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ]!,
  );
export const slug = (label: string) =>
  label
    .replace(/ı/g, "i")
    .replace(/İ/g, "I")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "") || "chart";
export const paragraphs = (text: string) =>
  text
    .split(/\n\s*\n/)
    .map((p) => `<p>${escapeHtml(p).replace(/\n/g, "<br>")}</p>`)
    .join("");
export function documentShell(
  title: string,
  body: string,
  disclaimer: string,
  brand: string,
  fonts: { inter: string; serif: string; bold: string },
) {
  return `<!doctype html><html><head><meta charset="utf-8"><style>@font-face{font-family:Inter;src:url(data:font/ttf;base64,${fonts.inter})}@font-face{font-family:Inter;src:url(data:font/ttf;base64,${fonts.bold});font-weight:600}@font-face{font-family:Serif;src:url(data:font/ttf;base64,${fonts.serif})}@page{size:A4;margin:18mm}body{font-family:Inter;color:#232A38;font-size:11pt;line-height:1.5}h1{font-size:26pt}h2{font-size:18pt;break-after:avoid}h3{font-size:13pt;break-after:avoid}p{font-family:Serif;font-size:12pt;white-space:normal}table{width:100%;border-collapse:collapse;font-size:9pt;margin:12pt 0}td,th{padding:7pt 4pt;border-bottom:1px solid #DEDED7;text-align:left}tr{break-inside:avoid}svg{width:100%;height:auto}.page{break-before:page}.cover{text-align:center}.cover svg{max-height:440pt}.small{font-size:9pt;color:#4A5163}.contents a{color:#2E4A7D}footer{margin-top:28pt;font-size:9pt}h1,h2,h3{font-weight:600}</style><title>${escapeHtml(title)}</title></head><body>${body}<footer>${escapeHtml(disclaimer)}<br>${escapeHtml(brand)}</footer></body></html>`;
}
export function chartDocument(
  profile: BirthProfile,
  chart: ChartData,
  cat: Catalogue,
  labels: Record<string, string>,
  reading?: NatalReading,
) {
  const e = escapeHtml,
    table = (headers: string[], rows: string[][]) =>
      `<table><thead><tr>${headers.map((x) => `<th>${e(x)}</th>`).join("")}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((x) => `<td>${e(x)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
  let html = `<section class="cover"><h1>${e(reading?.title ?? labels.chart!)}</h1><h2>${e(profile.label)}</h2><div>${e(profile.birth.date)} · ${e(profile.birth.time)} · ${e(profile.birth.place.name)}</div>${renderChartResolved(chart)}<div>${(["sun", "moon", "ascendant"] as const).map((k) => `${e(labels[k]!)} · ${e(cat.signs[profile.big_three[k]])}`).join(" &nbsp; ")}</div></section>`;
  if (reading) {
    html += `<section class="page contents"><h2>${e(labels.contents!)}</h2>${reading.sections.map((s) => `<div><a href="#${s.key}">${e(s.title)}</a></div>`).join("")}</section>`;
    for (const part of reading.parts) {
      html += `<section class="page"><h2>${e(part.title)}</h2>${reading.sections
        .filter((s) => s.movement === part.movement)
        .map((s) => `<h3 id="${s.key}">${e(s.title)}</h3>${paragraphs(s.text)}`)
        .join("")}</section>`;
    }
  }
  html += `<section class="page"><h2>${e(labels.planets!)}</h2>${table(
    [labels.planets!, labels.sign!, labels.house!],
    chart.points.map((p) => [
      cat.bodies[p.body] +
        (isRetrograde(p) ? ` · ${cat.terms.retrograde}` : ""),
      `${degrees(p.degree_in_sign)} ${cat.signs[p.sign]}`,
      String(p.house),
    ]),
  )}<h2>${e(labels.houses!)}</h2>${table(
    [labels.house!, labels.sign!, labels.planets!],
    chart.houses.map((h) => [
      String(h.house),
      `${degrees(inSign(h.cusp_longitude))} ${cat.signs[h.sign]}`,
      h.planets.map((p) => cat.bodies[p]).join(", "),
    ]),
  )}<h2>${e(labels.aspects!)}</h2>${table(
    [labels.planets!, labels.aspects!, labels.orb!],
    chart.aspects.map((a) => [
      `${cat.bodies[a.a]} · ${cat.bodies[a.b]}`,
      cat.aspects[a.type],
      degrees(a.orb),
    ]),
  )}</section>`;
  return html;
}
