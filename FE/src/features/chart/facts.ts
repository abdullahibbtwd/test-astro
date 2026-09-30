import type {
  AspectType,
  Body,
  ChartData,
  ChartPoint,
  NatalReading,
  Sign,
} from "../../../contracts/spec-types";
export type Selection =
  | { kind: "body"; body: Body }
  | { kind: "sign"; sign: Sign }
  | { kind: "house"; house: number }
  | { kind: "aspect"; index: number }
  | { kind: "axis"; axis: "ASC" | "DSC" | "MC" | "IC" };
export const aspectOrder: AspectType[] = [
  "conjunction",
  "opposition",
  "square",
  "trine",
  "sextile",
];
export const signs: Sign[] = [
  "aries",
  "taurus",
  "gemini",
  "cancer",
  "leo",
  "virgo",
  "libra",
  "scorpio",
  "sagittarius",
  "capricorn",
  "aquarius",
  "pisces",
];
export function degrees(value: number) {
  const minutes = Math.floor(Math.abs(value) * 60 + 1e-8);
  return `${Math.floor(minutes / 60)}°${String(minutes % 60).padStart(2, "0")}′`;
}
export const inSign = (longitude: number) => ((longitude % 30) + 30) % 30;
export const isRetrograde = (point: ChartPoint) =>
  point.retrograde && !point.body.endsWith("_node");
export function axisPoint(chart: ChartData, axis: "ASC" | "DSC" | "MC" | "IC") {
  const source =
    axis === "ASC" || axis === "DSC" ? chart.axes.asc : chart.axes.mc;
  const longitude =
    (source.longitude + (axis === "DSC" || axis === "IC" ? 180 : 0)) % 360;
  return {
    longitude,
    sign: signs[Math.floor(longitude / 30)]!,
    degree_in_sign: inSign(longitude),
  };
}
export function readingSections(
  chart: ChartData,
  reading: NatalReading,
  selection: Selection,
) {
  const keys = new Set<string>();
  const house = (number: number) =>
    reading.sections
      .filter((s) => s.house === number)
      .forEach((s) => keys.add(s.key));
  const body = (name: Body) => {
    const point = chart.points.find((p) => p.body === name);
    if (!point) return;
    if (name === "sun" || name === "moon") {
      keys.add(`${name}_house`);
      keys.add("core_identity");
    } else {
      house(point.house);
      keys.add(
        ["mercury", "venus", "mars"].includes(name)
          ? "inner_drives"
          : "chart_shape",
      );
    }
  };
  if (selection.kind === "body") body(selection.body);
  if (selection.kind === "house") house(selection.house);
  if (selection.kind === "sign")
    chart.points
      .filter((p) => p.sign === selection.sign)
      .forEach((p) => body(p.body));
  if (selection.kind === "aspect") {
    const aspect = chart.aspects[selection.index];
    if (aspect) {
      body(aspect.a);
      body(aspect.b);
    }
  }
  if (selection.kind === "axis") {
    if (selection.axis === "ASC") {
      keys.add("core_identity");
      keys.add("identity");
    }
    if (selection.axis === "MC") keys.add("status_vocation");
    if (selection.axis === "DSC") keys.add("partnerships");
    if (selection.axis === "IC") keys.add("family_home");
  }
  return reading.sections.filter((section) => keys.has(section.key));
}
