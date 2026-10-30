import test from "node:test";
import assert from "node:assert/strict";

test("feature flags stay off until /meta/config enables them", async () => {
  // Read the source directly so Node unit tests do not load react-native via flags.ts.
  const { readFileSync } = await import("node:fs");
  const { fileURLToPath } = await import("node:url");
  const path = await import("node:path");
  const src = readFileSync(
    path.join(
      path.dirname(fileURLToPath(import.meta.url)),
      "../src/lib/flags.ts",
    ),
    "utf8",
  );
  assert.match(src, /askAstrology:\s*false/);
  assert.match(src, /solarReturn:\s*false/);
  assert.match(src, /familyCompatibility:\s*false/);
});
