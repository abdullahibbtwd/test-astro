import type {
  FeatureCollection,
  Polygon,
  MultiPolygon,
  Position,
} from "geojson";
import type { AcgHeat } from "../../../contracts/spec-types";
export const distanceLabel = (value: number | "<10") =>
  value === "<10" ? "< 10 km" : `≈ ${value} km`;
export function heatCells(
  heat: AcgHeat,
): FeatureCollection<MultiPolygon, { level: number }> {
  const started = performance.now(),
    step = heat.grid_step_deg,
    half = step / 2;
  const rows = new Map<number, [number, number][]>();
  for (const [lon, lat, level] of heat.points) {
    const row = rows.get(lat) ?? [];
    row.push([lon, level]);
    rows.set(lat, row);
  }
  const levels = new Map<number, Position[][][]>();
  for (const [lat, row] of rows) {
    row.sort((a, b) => a[0] - b[0]);
    for (let i = 0; i < row.length;) {
      const [start, level] = row[i]!;
      let end = start;
      i++;
      while (
        i < row.length &&
        row[i]![1] === level &&
        Math.abs(row[i]![0] - end - step) < 1e-8
      ) {
        end = row[i]![0];
        i++;
      }
      const polygons = levels.get(level) ?? [];
      polygons.push([
        [
          [start - half, lat - half],
          [end + half, lat - half],
          [end + half, lat + half],
          [start - half, lat + half],
          [start - half, lat - half],
        ],
      ]);
      levels.set(level, polygons);
    }
  }
  const result: FeatureCollection<MultiPolygon, { level: number }> = {
    type: "FeatureCollection",
    features: [...levels].map(([level, coordinates]) => ({
      type: "Feature",
      properties: { level },
      geometry: { type: "MultiPolygon", coordinates },
    })),
  };
  if (typeof __DEV__ !== "undefined" && __DEV__)
    console.info("Heat geometry", {
      ms: performance.now() - started,
      features: result.features.length,
      cells: heat.points.length,
    });
  return result;
}
const countryIndexes = new WeakMap<
  object,
  {
    feature: FeatureCollection<
      Polygon | MultiPolygon,
      { iso2: string }
    >["features"][number];
    box: number[];
  }[]
>();
function inRing([x, y]: Position, ring: Position[]) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const a = ring[i]!,
      b = ring[j]!;
    if (
      a[1]! > y! !== b[1]! > y! &&
      x! < ((b[0]! - a[0]!) * (y! - a[1]!)) / (b[1]! - a[1]!) + a[0]!
    )
      inside = !inside;
  }
  return inside;
}
export function countryAt(
  point: Position,
  countries: FeatureCollection<Polygon | MultiPolygon, { iso2: string }>,
) {
  let index = countryIndexes.get(countries);
  if (!index) {
    index = countries.features.map((feature) => {
      const points =
        feature.geometry.type === "Polygon"
          ? feature.geometry.coordinates.flat()
          : feature.geometry.coordinates.flat(2);
      const box = [Infinity, Infinity, -Infinity, -Infinity];
      for (const p of points) {
        box[0] = Math.min(box[0]!, p[0]!);
        box[1] = Math.min(box[1]!, p[1]!);
        box[2] = Math.max(box[2]!, p[0]!);
        box[3] = Math.max(box[3]!, p[1]!);
      }
      return { feature, box };
    });
    countryIndexes.set(countries, index);
  }
  return index.find(({ feature: f, box }) => {
    if (
      point[0]! < box[0]! ||
      point[0]! > box[2]! ||
      point[1]! < box[1]! ||
      point[1]! > box[3]!
    )
      return false;
    const polygons =
      f.geometry.type === "Polygon"
        ? [f.geometry.coordinates]
        : f.geometry.coordinates;
    return polygons.some(
      (rings) =>
        inRing(point, rings[0]!) &&
        !rings.slice(1).some((ring) => inRing(point, ring)),
    );
  })?.feature.properties.iso2;
}
