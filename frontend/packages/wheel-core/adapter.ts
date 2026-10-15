import type { ChartData } from "../../contracts/spec-types";
const canonical = (id: string) =>
  id
    .split("_")
    .map((s) => s[0]!.toUpperCase() + s.slice(1))
    .join(" ");
/** Rebuild only the canonical renderer's consumed fields. Never compute positions. */
export function toWheelInput(chart: ChartData) {
  const axis = (a: ChartData["axes"]["asc"]) => ({
    ...a,
    sign: canonical(a.sign),
  });
  return {
    points: chart.points.map((p) => ({
      name: canonical(p.body),
      longitude: p.longitude,
      degree_in_sign: p.degree_in_sign,
      sign: canonical(p.sign),
      retrograde: p.retrograde,
      sector: { placidus: p.house },
    })),
    axes: { ascendant: axis(chart.axes.asc), mc: axis(chart.axes.mc) },
    sectors: { placidus_cusps: chart.houses.map((h) => h.cusp_longitude) },
    relations: chart.aspects.map((a) => ({
      scheme: "modern",
      source: canonical(a.a),
      target: canonical(a.b),
      type: a.type,
      orb: a.orb,
    })),
  };
}
