import type { WheelModel } from "./model";
import { mod360 } from "./transform";
export type WheelHit =
  | { kind: "body"; names: string[] }
  | { kind: "axis"; axis: "ASC" | "DSC" | "MC" | "IC" }
  | { kind: "sign"; index: number }
  | { kind: "house"; house: number }
  | { kind: "aspect"; index: number }
  | null;
export function segmentDistance(
  x: number,
  y: number,
  a: { x: number; y: number },
  b: { x: number; y: number },
) {
  const dx = b.x - a.x,
    dy = b.y - a.y,
    length = dx * dx + dy * dy,
    t = length
      ? Math.max(0, Math.min(1, ((x - a.x) * dx + (y - a.y) * dy) / length))
      : 0;
  return Math.hypot(x - a.x - t * dx, y - a.y - t * dy);
}
export function hitTest(
  model: WheelModel,
  x: number,
  y: number,
  width: number,
  zoom = 1,
): WheelHit {
  const tolerance = Math.max(30, (22 * 1000) / (width * zoom));
  const planets = model.points
    .filter((p) => Math.hypot(x - p.glyph.x, y - p.glyph.y) <= tolerance)
    .sort(
      (a, b) =>
        Math.hypot(x - a.glyph.x, y - a.glyph.y) -
        Math.hypot(x - b.glyph.x, y - b.glyph.y),
    );
  if (planets.length)
    return { kind: "body", names: planets.map((p) => p.name) };
  const axis = model.axes.find(
    (a) =>
      Math.hypot(x - a.label.x, y - a.label.y) <=
      Math.max(24, (22 * 1000) / (width * zoom)),
  );
  if (axis) return { kind: "axis", axis: axis.axis };
  const radius = Math.hypot(x - 500, y - 500),
    longitude = mod360(
      model.asc + ((Math.atan2(500 - y, x - 500) * 180) / Math.PI - 180),
    );
  if (radius >= 410 && radius <= 460)
    return { kind: "sign", index: Math.floor(longitude / 30) };
  if (radius > 236 && radius < 396) {
    const house = model.houses.find(
      (h, i) =>
        mod360(longitude - h.longitude) <
        mod360(model.houses[(i + 1) % 12]!.longitude - h.longitude),
    );
    return house ? { kind: "house", house: house.house } : null;
  }
  if (radius <= 236) {
    const chords = model.chords
      .map((c, index) => ({ index, distance: segmentDistance(x, y, c.a, c.b) }))
      .filter((c) => c.distance <= Math.max(12, (22 * 1000) / (width * zoom)))
      .sort((a, b) => a.distance - b.distance);
    if (chords[0]) return { kind: "aspect", index: chords[0].index };
  }
  return null;
}
export function touchToModel(
  x: number,
  y: number,
  width: number,
  zoom: number,
  panX: number,
  panY: number,
) {
  return {
    x: (((x - width / 2 - panX) / zoom + width / 2) * 1000) / width,
    y: (((y - width / 2 - panY) / zoom + width / 2) * 1000) / width,
  };
}
