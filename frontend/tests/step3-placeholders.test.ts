import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  assertNoPendingAstrologerMarkers,
  findPendingAstrologerMarkers,
  SOLAR_RETURN_PLACEHOLDER,
} from "../src/features/step3/placeholders.ts";

test("release gate fails while Step 3 placeholders remain in source", () => {
  const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
  const placeholders = fs.readFileSync(
    path.join(root, "src/features/step3/placeholders.ts"),
    "utf8",
  );
  assert.ok(findPendingAstrologerMarkers(placeholders).length > 0);
  assert.throws(
    () =>
      assertNoPendingAstrologerMarkers(placeholders, { isRelease: true }),
    /pending-astrologer/,
  );
});

test("math builders attach the unfinished interpretation markers", async () => {
  const { buildFamilySkeleton, buildSolarReturnSkeleton } = await import(
    "../src/features/step3/math.ts"
  );
  const solar = buildSolarReturnSkeleton({
    return_utc: "2024-01-01T00:00:00Z",
    year: 2024,
    chart: {} as never,
  });
  assert.equal(solar.interpretation, SOLAR_RETURN_PLACEHOLDER);
  assert.equal(solar.math.moment, "find_solar_return_utc");
  assert.equal(solar.math.chart, "compute_solar_return_chart");
  const family = buildFamilySkeleton({
    relationship_type: "sibling",
    profile_a_label: "A",
    profile_b_label: "B",
    aspects: [],
  });
  assert.match(family.interpretation, /pending astrologer/i);
  assert.equal(family.math.aspects, "compute_synastry_aspects");
});
