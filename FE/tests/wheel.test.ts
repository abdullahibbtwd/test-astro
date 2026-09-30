import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { createHash } from "node:crypto";
import { toWheelInput } from "../packages/wheel-core/adapter";
import { fixture } from "../mock-api/fixtures";
// Phase 0 proves the adapter against the unmodified canonical engine. The TS port is Phase 2.
import { renderChart } from "../../Chart_wheel/src/render.js";
import { checkInvariants } from "../../Chart_wheel/src/invariants.js";
const sources = [
  ["prediction_run/20260929-130811_qpm", "1979-03-30"],
  ["runs/20260924-102926_26p_1988-12-28", "1988-12-28"],
  ["runs/20260922-181953_w1d_1984-06-12", "1984-06-12"],
];
for (const [i, [dir, date]] of sources.entries())
  for (const theme of ["light", "dark"])
    test(`W1 and W3 baseline: ${date} ${theme}`, () => {
      const input = toWheelInput(fixture(`chart.${i}`));
      const expected = fs.readFileSync(
        `../${dir}/chart_wheel_${date}.${theme}.svg`,
        "utf8",
      );
      const actual = renderChart(input, { theme });
      assert.equal(
        createHash("sha256").update(actual).digest("hex"),
        createHash("sha256").update(expected).digest("hex"),
        "byte parity",
      );
      const gate = checkInvariants(input, { theme });
      assert.deepEqual(gate.violations, []);
    });
