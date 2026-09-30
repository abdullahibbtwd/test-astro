import {
  BANDS,
  DEGREE_TICK,
  PLOTTED_BODIES,
  POINTER_GLYPH_R,
  ASPECT,
  ASPECT_FAMILY,
} from "./constants";
import { project, num, arcMidpoint } from "./transform";
import { spread } from "./spread";
import type { WheelInput } from "./types";
export function computeWheel(chart: WheelInput) {
  const asc = chart.axes.ascendant.longitude;
  const point = (lon: number, r: number) => {
    const p = project(lon, r, asc);
    return { x: num(p.x), y: num(p.y) };
  };
  const cusps = chart.sectors.placidus_cusps;
  const points = spread(
    PLOTTED_BODIES.map((name) =>
      chart.points.find((p) => p.name === name),
    ).filter((p) => p !== undefined),
  ).map((p) => ({
    ...p,
    glyph: point(p.displayLon, BANDS.planetGlyph),
    anchor: point(p.displayLon, POINTER_GLYPH_R),
    top: point(p.trueLon, BANDS.pointerTop),
  }));
  const byName = new Map(chart.points.map((p) => [p.name, p]));
  const chords = chart.relations
    .filter((r) => r.scheme === "modern")
    .flatMap((rel) => {
      const a = byName.get(rel.source),
        b = byName.get(rel.target);
      if (!a || !b) return [];
      const family = ASPECT_FAMILY[rel.type] ?? "conj",
        group = family === "soft" ? ASPECT.soft : ASPECT.hard,
        strength = 1 - Math.min(rel.orb ?? 0, ASPECT.maxOrb) / ASPECT.maxOrb;
      let opacity = group.opacityBase + group.opacitySpan * strength;
      if (family === "soft") opacity = Math.max(opacity, ASPECT.softFloor);
      return [
        {
          rel,
          family,
          a: point(a.longitude, BANDS.hub),
          b: point(b.longitude, BANDS.hub),
          opacity,
          width: group.widthBase + group.widthSpan * strength,
        },
      ];
    });
  return {
    asc,
    point,
    points,
    chords,
    signs: Array.from({ length: 12 }, (_, i) => ({
      start: point(i * 30, BANDS.zodiacInner),
      end: point(i * 30, BANDS.zodiacOuter),
      glyph: point(i * 30 + 15, BANDS.signGlyph),
    })),
    ticks: Array.from({ length: 360 }, (_, d) => {
      const band =
        d % 10 === 0
          ? DEGREE_TICK.bold
          : d % 5 === 0
            ? DEGREE_TICK.major
            : DEGREE_TICK.minor;
      return { a: point(d, band.inner), b: point(d, band.outer) };
    }),
    houses: cusps.map((lon, i) => ({
      house: i + 1,
      longitude: lon,
      a: point(lon, BANDS.houseCuspInner),
      b: point(lon, BANDS.houseCuspOuter),
      label: point(arcMidpoint(lon, cusps[(i + 1) % 12]!), BANDS.houseNum),
    })),
    axes: (
      [
        ["ASC", asc],
        ["DSC", asc + 180],
        ["MC", chart.axes.mc.longitude],
        ["IC", chart.axes.mc.longitude + 180],
      ] as const
    ).map(([axis, lon]) => ({
      axis,
      longitude: lon,
      label: point(lon, 478),
      a: point(lon, BANDS.zodiacInner),
      b: point(lon + 180, BANDS.zodiacInner),
    })),
  };
}
export type WheelModel = ReturnType<typeof computeWheel>;
