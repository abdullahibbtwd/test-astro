import { mkdirSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { toWheelInput } from "../packages/wheel-core/adapter";
import { renderChart as coreRender } from "../packages/wheel-core/render";
import { renderChart as wheelRender } from "../../Chart_wheel/src/render.js";
import { fixture } from "../../backend/mock/fixtures";

const outRoot = join(
  dirname(fileURLToPath(import.meta.url)),
  "../tests/fixtures/wheels",
);
mkdirSync(outRoot, { recursive: true });
const sources = [
  [0, "1979-03-30"],
  [1, "1988-12-28"],
  [2, "1984-06-12"],
] as const;
for (const [i, date] of sources) {
  const input = toWheelInput(fixture(`chart.${i}`));
  for (const theme of ["light", "dark"] as const) {
    const canonical = wheelRender(input, { theme });
    const actual = coreRender(input, { theme });
    const path = join(outRoot, `chart_wheel_${date}.${theme}.svg`);
    writeFileSync(path, canonical);
    const same =
      createHash("sha256").update(actual).digest("hex") ===
      createHash("sha256").update(canonical).digest("hex");
    console.log(path, "bytes", canonical.length, "match", same);
  }
}
