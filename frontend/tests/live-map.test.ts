import test from "node:test";
import assert from "node:assert/strict";
import { gzipSync } from "node:zlib";
import { Store } from "../local-api/store";
import { computeBirthChart } from "../local-api/engine";
import { LiveMap } from "../local-api/map";
import { fixture } from "../mock-api/fixtures";
import { validate } from "../src/api/zod";
test("map geometry and nearby cities use the selected real birth chart without models", async () => {
  const store = await Store.open(":memory:");
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
    await store.put("profile:" + p.profile_id, p);
    await store.put("raw:" + p.profile_id, computed.raw);
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
  assert.equal((await store.list("map:v1:")).length, 2);
  await store.close();
});

test("real heat layers differ by goal, survive restart and reject unsupported goals", async () => {
  const store = await Store.open(":memory:");
  const maps = new LiveMap(store);
  const computed = await computeBirthChart(
    {
      date: "1990-07-13",
      time: "12:30",
      place: { lat: 42.6977, lon: 23.3217, tz: "Europe/Sofia" },
    },
    "heat-test",
  );
  const p = {
    ...fixture("profile.1.en"),
    profile_id: "heat-test",
    chart_key: computed.chart.chart_key,
  };
  await store.put("profile:" + p.profile_id, p);
  await store.put("raw:" + p.profile_id, computed.raw);
  try {
    await assert.rejects(
      () => maps.heat(p, "invalid"),
      (e: any) => e.statusCode === 400,
    );
    const love = await maps.heat(p, "love"),
      career = await maps.heat(p, "career");
    for (const layer of [love, career]) {
      validate("AcgHeat", layer);
      assert.equal(layer.chart_key, p.chart_key);
      assert.equal(layer.grid_step_deg, 0.5);
      assert.ok(layer.points.length > 1000);
      assert.ok(
        layer.points.every(
          ([lon, lat, level]) =>
            Math.abs(lon) <= 180 &&
            Math.abs(lat) <= 90 &&
            [-1, 0, 1, 2].includes(level),
        ),
      );
    }
    assert.notDeepEqual(love.points, career.points);
    for (const goal of Object.keys(fixture("catalogue.en").goals)) {
      const layer = await maps.heat(p, goal);
      validate("AcgHeat", layer);
      assert.equal(layer.goal, goal);
      assert.ok(layer.points.length > 0);
    }
    const changed = await computeBirthChart(
      {
        date: "1992-02-20",
        time: "12:30",
        place: { lat: 42.6977, lon: 23.3217, tz: "Europe/Sofia" },
      },
      "heat-second",
    );
    const other = {
      ...p,
      profile_id: "heat-second",
      chart_key: changed.chart.chart_key,
    };
    await store.put("raw:" + other.profile_id, changed.raw);
    assert.notDeepEqual((await maps.heat(other, "love")).points, love.points);

    assert.deepEqual(await new LiveMap(store).heat(p, "love"), love);
  } finally {
    await store.close();
  }
});

test("place facts use selected coordinates and preserve high-latitude absence without invented prose", async () => {
  const store = await Store.open(":memory:");
  const maps = new LiveMap(store);
  const computed = await computeBirthChart(
    {
      date: "1990-07-13",
      time: "12:30",
      place: { lat: 42.6977, lon: 23.3217, tz: "Europe/Sofia" },
    },
    "place-test",
  );
  const p = {
    ...fixture("profile.1.en"),
    profile_id: "place-test",
    chart_key: computed.chart.chart_key,
  };
  await store.put("raw:" + p.profile_id, computed.raw);
  try {
    const place = {
      place_id: null,
      name: "Test coordinates",
      country_code: null,
      lat: 42.6977,
      lon: 23.3217,
    };
    const en = await maps.placeReport(p, place, "en", "creativity"),
      tr = await maps.placeReport(p, place, "tr", "creativity");
    validate("PlaceReport", en);
    validate("PlaceReport", tr);
    assert.equal(en.reading.status, "absent");
    assert.equal(en.focus_goal, "creativity");
    assert.equal(en.cards.length, 7);
    assert.deepEqual(
      en.cards.map((c) => c.band),
      tr.cards.map((c) => c.band),
    );
    assert.notEqual(en.cards[0]!.title, tr.cards[0]!.title);
    const polar = await maps.placeReport(
      p,
      { ...place, lat: 75, lon: 20 },
      "en",
    );
    validate("PlaceReport", polar);
    assert.equal(polar.relocation.status, "absent");
    await assert.rejects(() =>
      maps.placeReport(p, { ...place, lat: 91 }, "en"),
    );
  } finally {
    await store.close();
  }
});

test("country and region facts come from the selected chart's scan", async () => {
  const store = await Store.open(":memory:");
  const maps = new LiveMap(store);
  const computed = await computeBirthChart(
    {
      date: "1990-07-13",
      time: "12:30",
      place: { lat: 42.6977, lon: 23.3217, tz: "Europe/Sofia" },
    },
    "area-test",
  );
  const p = {
    ...fixture("profile.1.en"),
    profile_id: "area-test",
    chart_key: computed.chart.chart_key,
  };
  await store.put("raw:" + p.profile_id, computed.raw);
  try {
    const area = await maps.area(p, "country", "BG", "en");
    validate("AreaReport", area);
    assert.equal(area.area.iso2, "BG");
    assert.equal(area.overview.status, "absent");
    assert.ok(area.regions!.length > 0);
    const region = await maps.area(
      p,
      "region",
      area.regions![0]!.admin1_id,
      "tr",
    );
    validate("AreaReport", region);
    assert.equal(region.area.iso2, "BG");
    await assert.rejects(
      () => maps.area(p, "country", "XX", "en"),
      (e: any) => e.statusCode === 404,
    );
  } finally {
    await store.close();
  }
});

test("recommendations retain goal, scope and filters without fabricated explanations", async () => {
  const store = await Store.open(":memory:");
  const maps = new LiveMap(store);
  const computed = await computeBirthChart(
    {
      date: "1990-07-13",
      time: "12:30",
      place: { lat: 42.6977, lon: 23.3217, tz: "Europe/Sofia" },
    },
    "recommend-test",
  );
  const p = {
    ...fixture("profile.1.en"),
    profile_id: "recommend-test",
    chart_key: computed.chart.chart_key,
  };
  await store.put("raw:" + p.profile_id, computed.raw);
  try {
    const needs = await maps.recommend(
      p,
      { query_text: "somewhere nice" },
      "en",
    );
    validate("Recommendation", needs);
    assert.equal(needs.status, "needs_goal");
    const world = await maps.recommend(
      p,
      { goal: "love", scope: "world" },
      "en",
    );
    validate("Recommendation", world);
    assert.ok(world.places.length > 0);
    assert.ok(world.by_line.length > 0);
    for (const goal of ["love", "overall"] as const) {
      const value = await maps.recommend(
        p,
        {
          goal,
          scope: "BG",
          filters: { city_size: ["big", "mid", "small"], purpose: "travel" },
        },
        "en",
      );
      validate("Recommendation", value);
      assert.equal(value.goal, goal);
      assert.equal(value.scope, "BG");
      assert.equal(value.explanations.status, "absent");
      assert.equal(value.filters_applied.purpose, "travel");
      assert.ok(value.places.every((p) => p.country_code === "BG"));
    }
  } finally {
    await store.close();
  }
});
