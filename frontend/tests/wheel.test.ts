import { nativeWheelSvg } from "../packages/wheel-core/native-svg";
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { toWheelInput } from "../packages/wheel-core/adapter";
import { fixture } from "../../backend/mock/fixtures";
// Phase 0 proves the adapter against the unmodified canonical engine. The TS port is Phase 2.
import { renderChart } from "../packages/wheel-core/render";
import { checkInvariants } from "../packages/wheel-core/invariants";
const wheelDir = join(dirname(fileURLToPath(import.meta.url)), "fixtures/wheels");
const sources = [
  ["1979-03-30", 0],
  ["1988-12-28", 1],
  ["1984-06-12", 2],
] as const;
for (const [date, i] of sources)
  for (const theme of ["light", "dark"] as const)
    test(`W1 and W3 baseline: ${date} ${theme}`, () => {
      const input = toWheelInput(fixture(`chart.${i}`));
      const expected = fs.readFileSync(
        join(wheelDir, `chart_wheel_${date}.${theme}.svg`),
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

test("native wheel resolves CSS tokens without changing geometry", () => {
  const chart = fixture("chart.0");
  for (const theme of ["light", "dark"] as const) {
    const canonical = renderChart(toWheelInput(chart), { theme });
    const native = nativeWheelSvg(chart, theme);
    assert.ok(!native.includes("var("));
    const geometry = /(?:cx|cy|r|x1|x2|y1|y2|d|transform)="[^"]*"/g;
    assert.deepEqual(native.match(geometry), canonical.match(geometry));
  }
});
