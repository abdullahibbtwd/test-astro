import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {
  computeCompatibilityScore,
  loadCompatibilityScoreWeights,
  scoringConfigured,
} from "../api/compatibility-score";

test("shipped weights file is blocked / empty — scoring stays off", () => {
  const weights = loadCompatibilityScoreWeights();
  assert.equal(weights.formula_id, null);
  assert.equal(scoringConfigured(weights), false);
  assert.equal(
    computeCompatibilityScore({
      type: "love",
      aspects: [{ type: "trine", a_point: "Sun", b_point: "Moon", orb: 1 }],
    }),
    null,
  );
});

test("partial weights without formula_id still return null", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "compat-score-"));
  const file = path.join(dir, "weights.json");
  fs.writeFileSync(
    file,
    JSON.stringify({
      formula_id: null,
      aspect_type_weights: { weights: { trine: 1 } },
    }),
  );
  const prev = process.env.ASTRO_COMPAT_SCORE_WEIGHTS;
  process.env.ASTRO_COMPAT_SCORE_WEIGHTS = file;
  try {
    assert.equal(scoringConfigured(), false);
    assert.equal(computeCompatibilityScore({ type: "love", aspects: [] }), null);
  } finally {
    if (prev === undefined) delete process.env.ASTRO_COMPAT_SCORE_WEIGHTS;
    else process.env.ASTRO_COMPAT_SCORE_WEIGHTS = prev;
  }
});
