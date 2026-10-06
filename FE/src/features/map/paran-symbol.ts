import type { SymbolLayerSpecification } from "@maplibre/maplibre-react-native";

// Never use text-field here: the bundled preview map has no glyph endpoint.
export function paranCrossLayout(dark: boolean): SymbolLayerSpecification["layout"] {
  return {
    "symbol-placement": "line",
    "symbol-spacing": 280,
    "icon-image": dark ? "dark-paran-cross" : "light-paran-cross",
    "icon-size": 0.5,
    "icon-rotation-alignment": "viewport",
    "icon-allow-overlap": true,
  };
}

// World-spanning latitude lines may arrive simplified to [-180, lat] and
// [180, lat]. Native wrapping treats those as the same point. Retain their
// intended path using intermediate vertices, without changing the latitude.
export function paranCoordinates(points: number[][]): number[][] {
  return points.flatMap((point, index) => {
    const next = points[index + 1];
    if (!next) return [point];
    const count = Math.max(1, Math.ceil(Math.abs(next[0]! - point[0]!) / 90));
    return Array.from({ length: count }, (_, step) => [
      point[0]! + (next[0]! - point[0]!) * step / count,
      point[1]! + (next[1]! - point[1]!) * step / count,
    ]);
  });
}
