import { test } from "node:test";
import assert from "node:assert/strict";
import {
  countryAt,
  heatCells,
  distanceLabel,
} from "../src/features/map/geometry";
test("country selection excludes holes and supports multipolygons", () => {
  const geo = {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: { iso2: "TR" },
        geometry: {
          type: "Polygon",
          coordinates: [
            [
              [0, 0],
              [10, 0],
              [10, 10],
              [0, 10],
              [0, 0],
            ],
            [
              [4, 4],
              [6, 4],
              [6, 6],
              [4, 6],
              [4, 4],
            ],
          ],
        },
      },
    ],
  } as const;
  assert.equal(countryAt([2, 2], geo as any), "TR");
  assert.equal(countryAt([5, 5], geo as any), undefined);
  assert.equal(countryAt([12, 2], geo as any), undefined);
});
test("heat geometry preserves provided levels and rounded distance presentation", () => {
  const start = performance.now();
  const result = heatCells({
    chart_key: "x",
    goal: "love",
    grid_step_deg: 0.5,
    points: Array.from({ length: 10000 }, (_, i) => [
      (i % 100) - 50,
      Math.floor(i / 100) - 50,
      1,
    ]),
  });
  assert.equal(result.features.length, 1);
  assert.deepEqual(
    result.features[0]!.geometry.coordinates[0]![0]![0],
    [-50.25, -50.25],
  );
  assert.ok(performance.now() - start < 150);
  assert.equal(distanceLabel("<10"), "< 10 km");
  assert.equal(distanceLabel(40), "≈ 40 km");
});
