import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { schemas } from "../src/api/zod";
import { fixtureRoot } from "../mock-api/fixtures";
test("all generated fixtures validate and contain no internal keys or unambiguous mask terms", () => {
  const manifest = JSON.parse(
    fs.readFileSync(`${fixtureRoot}/manifest.json`, "utf8"),
  );
  const forbidden = new Set([
    "whole_sign",
    "whole_sign_cusps",
    "classifications",
    "derived_points",
    "planetary_day",
    "planetary_hour",
    "principle_ids",
    "trace",
    "sentences",
    "source_ids",
    "contributors",
    "S",
    "P",
    "N",
    "S_agg",
    "R",
    "factors",
    "models",
    "schema_version",
    "tradition",
    "is_diurnal",
  ]);
  const terms =
    /placidus|whole[ -]sign|triplicity|domicile|detriment|exaltation|planetary day|planetary hour|time lord|profection|lot of fortune|lot of spirit|tam burç|üçlük|yücelim/iu;
  function scan(value: any, at: string) {
    if (typeof value === "string")
      assert.ok(!terms.test(value), `masked prose at ${at}`);
    else if (Array.isArray(value))
      value.forEach((v, i) => scan(v, `${at}[${i}]`));
    else if (value && typeof value === "object")
      for (const [key, v] of Object.entries(value)) {
        assert.ok(!forbidden.has(key), `masked key ${at}.${key}`);
        scan(v, `${at}.${key}`);
      }
  }
  for (const entry of manifest) {
    const value = JSON.parse(
      fs.readFileSync(`${fixtureRoot}/${entry.file}`, "utf8"),
    );
    schemas[entry.schema]!.parse(value);
    scan(value, entry.file);
  }
});
