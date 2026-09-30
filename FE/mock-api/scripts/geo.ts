import fs from "node:fs";
import path from "node:path";
type Point = [number, number];
// Douglas–Peucker in longitude/latitude degrees; no astrology computations.
function simplify(points: Point[], tolerance = 0.05): Point[] {
  if (points.length < 3) return points;
  const a = points[0]!,
    b = points.at(-1)!;
  const dx = b[0] - a[0],
    dy = b[1] - a[1];
  const norm = dx * dx + dy * dy;
  let maximum = 0,
    index = 0;
  for (let i = 1; i < points.length - 1; i++) {
    const p = points[i]!;
    const t = norm
      ? Math.max(
          0,
          Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / norm),
        )
      : 0;
    const distance = Math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy);
    if (distance > maximum) {
      maximum = distance;
      index = i;
    }
  }
  return maximum > tolerance
    ? [
        ...simplify(points.slice(0, index + 1), tolerance).slice(0, -1),
        ...simplify(points.slice(index), tolerance),
      ]
    : [a, b];
}
export function geoFixtures(root: string, chartKey: string) {
  const read = (file: string) =>
    JSON.parse(fs.readFileSync(path.join(root, file), "utf8"));
  const dir = "acg_run/20260929-105635_kgc";
  const lines = {
    chart_key: chartKey,
    lines: {
      type: "FeatureCollection",
      features: read(`${dir}/acg_1979-03-30.geojson`).features.map(
        (f: any) => ({
          type: "Feature",
          geometry: {
            type: "MultiLineString",
            coordinates: f.geometry.coordinates.map((part: Point[]) =>
              simplify(part),
            ),
          },
          properties: {
            body: f.properties.body,
            angle: f.properties.angle,
            read: f.properties.read_in_v1,
          },
        }),
      ),
    },
    parans: {
      type: "FeatureCollection",
      features: read(`${dir}/acg_parans_1979-03-30.geojson`)
        .features.filter((f: any) => f.properties.kind === "paran")
        .map((f: any) => ({
          type: "Feature",
          geometry: {
            type: "LineString",
            coordinates: simplify(f.geometry.coordinates),
          },
          properties: {
            id: f.properties.id,
            bodies: f.properties.planets,
            angles: f.properties.angles,
          },
        })),
    },
  };
  const countries = {
    type: "FeatureCollection",
    features: read("Astrocartography/countries.geojson").features.map(
      (f: any) => ({
        type: "Feature",
        geometry: f.geometry,
        properties: {
          iso2: f.properties.iso_a2,
          name_tr: f.properties.name_tr ?? f.properties.name,
          name_en: f.properties.name,
        },
      }),
    ),
  };
  const regions: Record<string, any> = {};
  for (const f of read("Astrocartography/regions.geojson").features) {
    const iso = f.properties.iso_a2;
    regions[iso] ??= { type: "FeatureCollection", features: [] };
    regions[iso].features.push({
      type: "Feature",
      geometry: f.geometry,
      properties: {
        admin1_id: f.properties.admin1_id,
        iso2: iso,
        name_tr: f.properties.name_tr ?? f.properties.name,
        name_en: f.properties.name,
      },
    });
  }
  return { lines, countries, regions };
}
