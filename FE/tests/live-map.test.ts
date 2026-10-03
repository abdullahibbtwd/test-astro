import test from "node:test";
import assert from "node:assert/strict";
import { gzipSync } from "node:zlib";
import { Store } from "../local-api/store";
import { computeBirthChart } from "../local-api/engine";
import { LiveMap } from "../local-api/map";
import { fixture } from "../mock-api/fixtures";
import { validate } from "../src/api/zod";
test("map geometry and nearby cities use the selected real birth chart without models", async () => {
  const store = new Store(":memory:");
  const maps = new LiveMap(store);
  const outputs = [];
  for (const date of ["1990-07-13", "1992-02-20"]) {
    const computed = await computeBirthChart(
      {
        date,
        time: "12:30",
        place: { lat: 42.6977, lon: 23.3217, tz: "Europe/Sofia" },
      },
      "map-test",
    );
    const p = {
      ...fixture("profile.1.en"),
      profile_id: "map-test",
      chart_key: computed.chart.chart_key,
    };
    store.put("profile:" + p.profile_id, p);
    store.put("raw:" + p.profile_id, computed.raw);
    const lines = await maps.lines(p);
    validate("AcgLines", lines);
    assert.equal(lines.chart_key, p.chart_key);
    assert.equal(lines.lines.features.length, 44);
    assert.ok(lines.parans.features.length > 0);
    assert.equal(
      lines.lines.features.filter((f) => f.properties.read).length,
      40,
    );
    assert.ok(
      lines.lines.features
        .filter((f) => f.properties.body === "north_node")
        .every((f) => !f.properties.read),
    );
    assert.ok(gzipSync(JSON.stringify(lines)).byteLength < 150000);
    assert.deepEqual(await maps.lines(p), lines);
    outputs.push(lines.lines);
    const en = await maps.places(p, "sun", "MC", "en", 5),
      tr = await maps.places(p, "sun", "MC", "tr", 5);
    validate("LinePlaces", en);
    validate("LinePlaces", tr);
    assert.notEqual(en.line.planet_label, tr.line.planet_label);
    assert.deepEqual(
      en.places.map((p) => p.place_id),
      tr.places.map((p) => p.place_id),
    );
    assert.ok(
      en.places.every((p) => p.tier === "tight" || p.tier === "strong"),
    );
  }
  assert.notDeepEqual(outputs[0], outputs[1]);
  assert.equal(store.list("map:v1:").length, 2);
  store.close();
});
