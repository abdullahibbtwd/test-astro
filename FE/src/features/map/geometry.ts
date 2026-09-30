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
): FeatureCollection<Polygon, { level: number }> {
  const half = heat.grid_step_deg / 2;
  return {
    type: "FeatureCollection",
    features: heat.points.map(([lon, lat, level]) => ({
      type: "Feature",
      properties: { level },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [lon - half, lat - half],
            [lon + half, lat - half],
            [lon + half, lat + half],
            [lon - half, lat + half],
            [lon - half, lat - half],
          ],
        ],
      },
    })),
  };
}
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
  return countries.features.find((f) => {
    const polygons =
      f.geometry.type === "Polygon"
        ? [f.geometry.coordinates]
        : f.geometry.coordinates;
    return polygons.some(
      (rings) =>
        inRing(point, rings[0]!) &&
        !rings.slice(1).some((ring) => inRing(point, ring)),
    );
  })?.properties.iso2;
}
