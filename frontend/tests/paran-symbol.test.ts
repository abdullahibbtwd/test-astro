import { URL } from "node:url";
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { paranCoordinates, paranCrossLayout } from "../src/features/map/paran-symbol";

test("paran markers use bundled images in both themes without a glyph server", () => {
  const registration = readFileSync(new URL("../src/features/map/glyph-images.ts", import.meta.url), "utf8");
  for (const dark of [false, true]) {
    const layout = paranCrossLayout(dark)!;
    assert.equal(layout["text-field"], undefined);
    assert.equal(layout["symbol-placement"], "line");
    const image = layout["icon-image"] as string;
    assert.ok(registration.includes(`"${image}": require("../../../assets/map/${image}.png")`));
    const png = readFileSync(new URL(`../assets/map/${image}.png`, import.meta.url));
    assert.equal(png.subarray(1, 4).toString(), "PNG");
    assert.equal(png.readUInt32BE(16), 32);
    assert.equal(png.readUInt32BE(20), 32);
  }
});

test("simplified world-spanning parans retain their latitude through the map seam", () => {
  const points = paranCoordinates([[-180, 42.5], [180, 42.5]]);
  assert.deepEqual(points, [[-180, 42.5], [-90, 42.5], [0, 42.5], [90, 42.5], [180, 42.5]]);
  assert.deepEqual(paranCoordinates([[20, 10], [30, 10]]), [[20, 10], [30, 10]]);
  assert.deepEqual(paranCoordinates([]), []);
});
