import { test } from "node:test";
import assert from "node:assert/strict";
import { buildApp } from "../mock-api/app";
const headers = { authorization: "Bearer mock-access" };
const self = "00000000-0000-4000-8000-000000000001",
  partner = "00000000-0000-4000-8000-000000000002";
test("forecast navigation keeps real calendar facts and never relabels rolling-month prose", async () => {
  const app = buildApp({ jobMs: 0 });
  try {
    const day = await app.inject({
      url: `/v1/profiles/${self}/forecast/day?date=2026-10-02&lens=personal&lang=en`,
      headers,
    });
    assert.equal(day.statusCode, 200);
    assert.equal(day.json().date, "2026-10-02");
    assert.equal(day.json().reading.status, "absent");
    const month = await app.inject({
      url: `/v1/profiles/${self}/forecast/month?month=2026-10&lens=general&lang=en`,
      headers,
    });
    assert.equal(month.statusCode, 200);
    assert.equal(month.json().segments.late.to, "2026-10-31");
    assert.equal(month.json().reading.status, "absent");
    const year = await app.inject({
      url: `/v1/profiles/${self}/forecast/year?from=2026-09&lens=general&lang=en`,
      headers,
    });
    assert.equal(year.statusCode, 200);
    assert.equal(year.json().from, "2026-09-29");
    assert.equal(year.json().quarters[3].to, "2027-09-28");
  } finally {
    await app.close();
  }
});
test("compatibility creates idempotently, localizes history and never substitutes another pair", async () => {
  const app = buildApp({ jobMs: 0 });
  try {
    const payload = { profile_a_id: self, profile_b_id: partner, type: "love" };
    const create = () =>
      app.inject({
        method: "POST",
        url: "/v1/compatibility?lang=en",
        headers: { ...headers, "idempotency-key": "pair-test" },
        payload,
      });
    const result = await create();
    assert.equal(result.statusCode, 201);
    const id = result.json().compatibility_id;
    assert.equal((await create()).json().compatibility_id, id);
    const report = await app.inject({
      url: `/v1/compatibility/${id}?lang=tr`,
      headers,
    });
    assert.equal(report.statusCode, 200);
    assert.equal(report.json().people.a.profile_id, self);
    const history = await app.inject({
      url: "/v1/compatibility?lang=en",
      headers,
    });
    assert.equal(history.statusCode, 200);
    assert.equal(history.json().items.length, 1);
    const wrong = await app.inject({
      method: "POST",
      url: "/v1/compatibility?lang=en",
      headers,
      payload: {
        ...payload,
        profile_b_id: "00000000-0000-4000-8000-000000000003",
      },
    });
    assert.equal(wrong.statusCode, 503);
    assert.equal(
      (
        await app.inject({
          method: "DELETE",
          url: `/v1/compatibility/${id}`,
          headers,
        })
      ).statusCode,
      204,
    );
    assert.equal(
      (await app.inject({ url: `/v1/compatibility/${id}`, headers }))
        .statusCode,
      404,
    );
  } finally {
    await app.close();
  }
});
test("city search opens the same source-backed city and overall recommendations retain breadth labels", async () => {
  let now = Date.now();
  const app = buildApp({ now: () => now, jobMs: 100 });
  try {
    const search = await app.inject({
      url: "/v1/places/search?kind=city&q=Berlin&lang=en",
      headers,
    });
    assert.equal(search.statusCode, 200);
    const place = search.json()[0];
    assert.equal(place.tz, "Europe/Berlin");
    const url = `/v1/profiles/${self}/acg/places/${place.place_id}?lang=en`;
    const pending = (await app.inject({ url, headers })).json();
    assert.equal(pending.place.name, "Berlin");
    assert.ok(
      pending.cards
        .filter((c: any) => c.band !== "no_emphasis")
        .every((c: any) => c.text === null),
    );
    now += 1000;
    const ready = (await app.inject({ url, headers })).json();
    assert.equal(ready.reading.status, "ready");
    const history = (
      await app.inject({ url: "/v1/reports?lang=en", headers })
    ).json();
    assert.ok(
      history.items.some(
        (r: any) => r.type === "place" && r.title === "Berlin",
      ),
    );
    const overall = await app.inject({
      method: "POST",
      url: `/v1/profiles/${self}/acg/recommendations?lang=en`,
      headers,
      payload: { goal: "overall", scope: "world" },
    });
    assert.equal(overall.statusCode, 200);
    assert.ok(overall.json().places[0].summary_label);
    assert.equal(overall.json().by_line.length, 0);
    const heat = await app.inject({
      url: `/v1/profiles/${self}/acg/heat/love?lang=en`,
      headers,
    });
    assert.equal(heat.statusCode, 200);
    assert.ok(heat.json().points.length > 100);
  } finally {
    await app.close();
  }
});

test("country reports expose deterministic bands, region links and no invented prose", async () => {
  const app = buildApp();
  try {
    const r = await app.inject({
      url: `/v1/profiles/${self}/acg/countries/TR?lang=en`,
      headers,
    });
    assert.equal(r.statusCode, 200);
    assert.equal(Object.keys(r.json().bands).length, 11);
    assert.equal(r.json().overview.status, "absent");
    const region = r.json().regions[0];
    if (region)
      assert.equal(
        (
          await app.inject({
            url: `/v1/profiles/${self}/acg/regions/${region.admin1_id}?lang=en`,
            headers,
          })
        ).statusCode,
        200,
      );
  } finally {
    await app.close();
  }
});
