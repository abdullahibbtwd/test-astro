import type { ChartData } from "../../../frontend/contracts/spec-types";
const body = (name: string) =>
  name
    .toLowerCase()
    .replaceAll(" ", "_") as ChartData["points"][number]["body"];
const sign = (name: string) =>
  name.toLowerCase() as ChartData["points"][number]["sign"];
/** Allowlist only. Keep full precision and ordering for wheel parity. */
export function mapChart(
  raw: any,
  profile_id: string,
  chart_key: string,
): ChartData {
  const points = raw.points.map((p: any) => ({
    body: body(p.name),
    longitude: p.longitude,
    sign: sign(p.sign),
    degree_in_sign: p.degree_in_sign,
    house: p.sector.placidus,
    retrograde: p.retrograde,
  }));
  const axis = (a: any) => ({
    longitude: a.longitude,
    sign: sign(a.sign),
    degree_in_sign: a.degree_in_sign,
  });
  return {
    profile_id,
    chart_key,
    utc: raw.meta.utc,
    tz: raw.meta.timezone,
    points,
    axes: { asc: axis(raw.axes.ascendant), mc: axis(raw.axes.mc) },
    houses: raw.sectors.placidus_cusps.map((longitude: number, i: number) => {
      const r = raw.sector_rulers.placidus[String(i + 1)];
      return {
        house: i + 1,
        cusp_longitude: longitude,
        sign: sign(r.sign_on_cusp),
        rulers: [
          ...new Set([r.ruler, r.modern_ruler].filter(Boolean).map(body)),
        ],
        planets: points
          .filter((p: any) => p.house === i + 1)
          .map((p: any) => p.body),
      };
    }),
    aspects: raw.relations
      .filter((a: any) => a.scheme === "modern")
      .map((a: any) => ({
        a: body(a.source),
        b: body(a.target),
        type: a.type,
        orb: a.orb,
      })),
  };
}
