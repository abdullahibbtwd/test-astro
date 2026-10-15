import { URL } from "node:url";
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { heatCells, countryAt } from "../src/features/map/geometry";
import type { AcgHeat } from "../contracts/spec-types";
test("merged heat preserves area, cell membership and holes across levels", () => {
  const points: AcgHeat["points"] = [
    [0, 0, 1],
    [0.5, 0, 1],
    [1.5, 0, 1],
    [0, 0.5, 2],
    [0.5, 0.5, 2],
    [1, 0.5, 0],
    [1.5, 0.5, -1],
  ];
  const geo = heatCells({
    chart_key: "x",
    goal: "love",
    grid_step_deg: 0.5,
    points,
  });
  assert.equal(geo.features.length, 4);
  let area = 0;
  for (const f of geo.features)
    for (const polygon of f.geometry.coordinates) {
      const r = polygon[0]!;
      area += (r[1]![0]! - r[0]![0]!) * (r[2]![1]! - r[1]![1]!);
    }
  assert.equal(area, points.length * 0.25);
  const countries = {
    ...geo,
    features: geo.features.map((f) => ({
      ...f,
      properties: { iso2: String(f.properties.level) },
    })),
  };
  for (const [x, y, level] of points)
    assert.equal(countryAt([x, y], countries), String(level));
  assert.equal(countryAt([1, 0], countries), undefined);
});
test("light countries retain every worldview identity and remain below 400 KB", () => {
  const raw = readFileSync(
    new URL("../mock-api/fixtures/geo-countries-simple.json", import.meta.url),
    "utf8",
  );
  const before = JSON.parse(
      readFileSync(
        new URL("../mock-api/fixtures/geo-countries.json", import.meta.url),
        "utf8",
      ),
    ),
    after = JSON.parse(raw);
  assert.ok(Buffer.byteLength(raw) <= 400_000);
  assert.deepEqual(
    after.features.map((f: any) => f.properties),
    before.features.map((f: any) => f.properties),
  );
  for (const point of [
    [29, 41],
    [2.35, 48.86],
    [23.32, 42.69],
  ])
    assert.equal(countryAt(point, after), countryAt(point, before));
});
