/**
 * Benchmark harness for Solar Return / Family cases under
 * backend/tests/fixtures/benchmarks/.
 *
 * Skips cleanly when no real cases are present (awaiting astrologer).
 * Does not invent expected values or call paid LLMs.
 */
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "fixtures",
);
const schemaPath = path.join(root, "benchmark.schema.json");
const casesDir = path.join(root, "benchmarks");

type BenchmarkCase = {
  id: string;
  kind: "solar_return" | "family";
  birth: {
    date: string;
    time: string;
    latitude: number;
    longitude: number;
  };
  target_year?: number;
  expected: {
    return_utc?: string;
    ascendant?: { sign?: string | null; longitude?: number | null };
    key_placements?: unknown[];
    aspects?: unknown[];
  };
  sample_reading?: unknown;
  mapping?: Record<string, unknown>;
  notes?: string | null;
};

function listCases(): { file: string; data: BenchmarkCase }[] {
  if (!fs.existsSync(casesDir)) return [];
  return fs
    .readdirSync(casesDir)
    .filter((name) => name.endsWith(".json"))
    .map((name) => {
      const file = path.join(casesDir, name);
      const data = JSON.parse(fs.readFileSync(file, "utf8")) as BenchmarkCase;
      return { file, data };
    });
}

function assertCaseShape(data: BenchmarkCase, file: string) {
  assert.ok(data.id, `${file}: id required`);
  assert.ok(
    data.kind === "solar_return" || data.kind === "family",
    `${file}: kind must be solar_return|family`,
  );
  assert.ok(data.birth?.date && data.birth?.time, `${file}: birth required`);
  assert.ok(
    Number.isFinite(data.birth.latitude) &&
      Number.isFinite(data.birth.longitude),
    `${file}: birth lat/lon required`,
  );
  assert.ok(data.expected && typeof data.expected === "object", `${file}: expected`);
  if (data.kind === "solar_return") {
    assert.ok(
      Number.isInteger(data.target_year),
      `${file}: target_year required for solar_return`,
    );
    assert.ok(
      typeof data.expected.return_utc === "string" && data.expected.return_utc,
      `${file}: expected.return_utc required for solar_return`,
    );
  }
}

test("benchmark schema file is present and documents required fields", () => {
  assert.ok(fs.existsSync(schemaPath), "benchmark.schema.json missing");
  const schema = JSON.parse(fs.readFileSync(schemaPath, "utf8"));
  assert.equal(schema.title, "AstrologyBenchmarkCase");
  for (const key of [
    "birth",
    "target_year",
    "expected",
    "sample_reading",
    "mapping",
  ])
    assert.ok(schema.properties[key], `schema missing properties.${key}`);
  assert.ok(schema.properties.expected.properties.return_utc);
  assert.ok(schema.properties.expected.properties.ascendant);
  assert.ok(schema.properties.expected.properties.key_placements);
});

test("benchmark cases (skip until astrologer fixtures are added)", async (t) => {
  const cases = listCases();
  if (!cases.length) {
    t.skip(
      "No files in backend/tests/fixtures/benchmarks/*.json yet — awaiting astrologer benchmark cases",
    );
    return;
  }

  for (const { file, data } of cases) {
    await t.test(data.id || path.basename(file), async (tt) => {
      assertCaseShape(data, file);

      if (data.kind === "solar_return") {
        // Natal sun longitude must come from a computed chart in a full case;
        // until then, cases may embed natal_sun_longitude under mapping.
        const natalLon = (data.mapping as any)?.natal_sun_longitude;
        if (typeof natalLon !== "number") {
          tt.skip(
            `${data.id}: mapping.natal_sun_longitude not set — add before enabling math assert`,
          );
          return;
        }
        let runSolarReturnBridge: (input: {
          natal_sun_longitude: number;
          year: number;
          latitude: number;
          longitude: number;
        }) => Promise<{ return_utc: string }>;
        try {
          ({ runSolarReturnBridge } = await import("../api/solar-return"));
        } catch {
          tt.skip(
            `${data.id}: solar-return API module not on this branch yet`,
          );
          return;
        }
        const math = await runSolarReturnBridge({
          natal_sun_longitude: natalLon,
          year: data.target_year!,
          latitude: data.birth.latitude,
          longitude: data.birth.longitude,
        });
        assert.equal(math.return_utc, data.expected.return_utc);
        return;
      }

      tt.skip(`${data.id}: family benchmark runner not enabled yet`);
    });
  }
});
