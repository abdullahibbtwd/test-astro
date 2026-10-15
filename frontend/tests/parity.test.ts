import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { gzipSync } from "node:zlib";
import { fixture, fixtureRoot } from "../../backend/mock/fixtures";
const manifest: { file: string }[] = JSON.parse(
  fs.readFileSync(`${fixtureRoot}/manifest.json`, "utf8"),
);
test("TR and EN preserve structure, numeric facts, IDs, dates and enums", () => {
  const fixed = new Set([
    "profile_id",
    "chart_key",
    "user_id",
    "id",
    "place_id",
    "country_code",
    "date",
    "time",
    "tz",
    "utc",
    "body",
    "sign",
    "phase",
    "tone",
    "band",
    "kind",
    "status",
    "goal",
    "type",
    "activity",
    "key",
    "relation",
    "grade",
    "angle",
    "tier",
    "start",
    "end",
    "peak",
    "from",
    "to",
    "month",
    "score_10",
    "country_code",
    "created_at",
    "updated_at",
    "generated_at",
    "version",
    "sun",
    "moon",
    "ascendant",
    "route",
    "ref",
  ]);
  function compare(a: any, b: any, key: string, where: string) {
    assert.equal(typeof a, typeof b, where);
    if (Array.isArray(a)) {
      assert.ok(Array.isArray(b));
      assert.equal(a.length, b.length, where);
      a.forEach((v, i) => compare(v, b[i], key, where + "[" + i + "]"));
    } else if (a && typeof a === "object") {
      assert.deepEqual(Object.keys(a), Object.keys(b), where);
      for (const k of Object.keys(a)) compare(a[k], b[k], k, where + "." + k);
    } else if (typeof a !== "string" || fixed.has(key))
      assert.deepEqual(a, b, where);
  }
  for (const { file } of manifest.filter(
    (x) => x.file.endsWith(".tr.json") && !x.file.startsWith("catalogue."),
  )) {
    compare(
      fixture(file.slice(0, -5)),
      fixture(file.replace(".tr.json", ".en")),
      "",
      file,
    );
  }
});
test("map lines and parans respect the 150 KB compressed budget", () => {
  const data = fixture("acg-lines");
  assert.ok(gzipSync(JSON.stringify(data)).byteLength <= 150 * 1024);
  assert.ok(data.lines.features.length > 0);
  assert.ok(data.parans.features.length > 0);
  assert.ok(data.lines.features.some((f: any) => f.properties.read === false));
  assert.ok(
    data.parans.features.every((f: any) => f.geometry.type === "LineString"),
  );
});
