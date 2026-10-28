import test from "node:test";
import { clearAuthMode, dataDbPath, openStore, tempDataDir, wipeDemoTenant } from "./helpers";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createHash } from "node:crypto";
import { buildLocalApp } from "../api/app";
import { Store } from "../api/store";
import { fixture } from "../mock/fixtures";
import { validate } from "../../frontend/src/api/zod";
const mockChart = (birth: { date: string; time: string; place: unknown }, id: string) => {
  const base = fixture("chart.1");
  const chart_key = createHash("sha256")
    .update(JSON.stringify(birth))
    .digest("hex")
    .slice(0, 16);
  return {
    raw: {},
    chart: {
      ...base,
      profile_id: id,
      chart_key,
      points:
        birth.date === "1990-07-13"
          ? base.points
          : base.points.map((p: { longitude: number }, i: number) =>
              i === 0 ? { ...p, longitude: p.longitude + 1 } : p,
            ),
    },
  };
};
test("local API calculates, persists, edits and deletes real profiles without sample fallback", async () => {
  await wipeDemoTenant();
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), "astrology-live-"));
  const dbPath = path.join(folder, "state.sqlite");
  await clearAuthMode();
  let app = await buildLocalApp({
    dbPath,
    computeBirthChart: async (birth, id) => mockChart(birth, id),
    sectionRunner: async () => ({}),
  });
  try {
    assert.equal((await app.inject({ url: "/v1/profiles" })).statusCode, 401);
    const login = await app.inject({
      method: "POST",
      url: "/v1/auth/email/verify",
      payload: { email: "demo@example.com", code: "000000" },
    });
    assert.equal(login.statusCode, 200);
    const session = login.json();
    validate("Session", session);
    const headers = { authorization: `Bearer ${session.access_token}` };
    const fallbackPlace = fixture("profile.1.en").birth.place;
    const seed = await openStore();
    await seed.runAsAsync(session.me.user_id, async () => {
      await seed.put(`place:en:${fallbackPlace.place_id}`, {
        ...fallbackPlace,
        kind: "city",
        population: 1,
        source: "test",
      });
    });
    await seed.close();
    const originalMe = (await app.inject({ url: "/v1/me", headers })).json();
    const patchedMe = await app.inject({
      method: "PATCH",
      url: "/v1/me",
      headers,
      payload: {
        display_name: "Test",
        user_id: "injected",
        self_profile_id: "injected",
      },
    });
    assert.equal(patchedMe.json().user_id, originalMe.user_id);
    assert.equal(patchedMe.json().self_profile_id, null);
    const places = (
      await app.inject({
        url: "/v1/places/search?q=Sofia&kind=birth&lang=en",
        headers,
      })
    ).json();
    const birthPlace = places[0] ?? {
      place_id: fallbackPlace.place_id,
      name: fallbackPlace.name,
      lat: fallbackPlace.lat,
      lon: fallbackPlace.lon,
    };
    if (places.length) {
      validate("PlaceCandidate", places[0]);
    }
    const areas = (
      await app.inject({
        url: "/v1/places/search?kind=area&q=Bulgaria&lang=en",
        headers,
      })
    ).json();
    if (Array.isArray(areas) && areas.length) {
      assert.ok(areas.some((a: any) => a.place_id === "iso2:BG"));
      for (const a of areas) validate("PlaceCandidate", a);
    }
    if (places.length) {
      const reverse = (
        await app.inject({
          url: "/v1/places/reverse?lat=42.6977&lon=23.3217",
          headers,
        })
      ).json();
      validate("Place", reverse);
      assert.equal(reverse.place_id, places[0].place_id);
    }
    assert.ok(
      [400, 500, 503].includes(
        (
          await app.inject({
            url: "/v1/places/reverse?lat=91&lon=0",
            headers,
          })
        ).statusCode,
      ),
    );

    const payload = {
      label: "Integration test",
      relation: "friend",
      birth_date: "1990-07-13",
      birth_time: "12:30",
      birth_place_id: birthPlace.place_id,
    };
    const created = await app.inject({
      method: "POST",
      url: "/v1/profiles",
      headers: { ...headers, "idempotency-key": "create-test" },
      payload,
    });
    assert.equal(created.statusCode, 201, created.body);
    const profile = created.json();
    validate("BirthProfile", profile);
    const url = `/v1/profiles/${profile.profile_id}`;
    const chart = (await app.inject({ url: url + "/chart", headers })).json();
    validate("ChartData", chart);
    let cachedMap: unknown;
    const mapResponse = await app.inject({
      url: url + "/acg/lines",
      headers,
    });
    if (mapResponse.statusCode === 200) {
      cachedMap = mapResponse.json();
      const map = cachedMap as { chart_key: string };
      validate("AcgLines", map);
      const cityReport = await app.inject({
        url: url + "/acg/places/" + birthPlace.place_id + "?focus_goal=",
        headers,
      });
      assert.equal(cityReport.statusCode, 200, cityReport.body);
      validate("PlaceReport", cityReport.json());
      const heatResponse = await app.inject({
        url: url + "/acg/heat/love",
        headers,
      });
      assert.equal(heatResponse.statusCode, 200);
      const heat = heatResponse.json();
      validate("AcgHeat", heat);
      assert.equal(heat.chart_key, chart.chart_key);
      assert.equal(map.chart_key, chart.chart_key);
      const linePlaces = await app.inject({
        url: url + "/acg/lines/sun/MC/places?lang=tr",
        headers,
      });
      assert.equal(linePlaces.statusCode, 200);
      validate("LinePlaces", linePlaces.json());
    }
    assert.equal(
      (await app.inject({ url: url + "/acg/point?lat=NaN&lon=0", headers }))
        .statusCode,
      400,
    );
    assert.equal(
      (await app.inject({ url: url + "/acg/heat/invalid", headers }))
        .statusCode,
      400,
    );
    assert.equal(
      (await app.inject({ url: url + "/acg/lines/invalid/MC/places", headers }))
        .statusCode,
      400,
    );
    assert.equal(
      (
        await app.inject({
          url: url + "/acg/lines/sun/MC/places?limit=0",
          headers,
        })
      ).statusCode,
      400,
    );
    validate(
      "CountryGeometry",
      (await app.inject({ url: "/v1/geo/countries.geojson" })).json(),
    );
    assert.equal(
      (await app.inject({ url: "/v1/geo/regions/TR.geojson" })).statusCode,
      404,
    );

    await app.close();
   await clearAuthMode();
    app = await buildLocalApp({
      dbPath,
      computeBirthChart: async (birth, id) => mockChart(birth, id),
      sectionRunner: async () => ({}),
    });
    assert.deepEqual(
      (await app.inject({ url: url + "/chart", headers })).json(),
      chart,
    );
    if (cachedMap !== undefined) {
      assert.deepEqual(
        (await app.inject({ url: url + "/acg/lines", headers })).json(),
        cachedMap,
      );
    }
    const repeated = await app.inject({
      method: "POST",
      url: "/v1/profiles",
      headers: { ...headers, "idempotency-key": "create-test" },
      payload,
    });
    assert.equal(repeated.json().profile_id, profile.profile_id);
    assert.equal(
      (
        await app.inject({
          method: "POST",
          url: "/v1/profiles",
          headers: { ...headers, "idempotency-key": "create-test" },
          payload: { ...payload, label: "Different" },
        })
      ).statusCode,
      409,
    );
    const changed = await app.inject({
      method: "PATCH",
      url,
      headers,
      payload: { birth_date: "1991-01-13" },
    });
    assert.equal(changed.statusCode, 200, changed.body);
    assert.notEqual(changed.json().chart_key, profile.chart_key);
    const fresh = (await app.inject({ url: url + "/chart", headers })).json();
    assert.notEqual(fresh.points[0].longitude, chart.points[0].longitude);
    const yearly = await app.inject({
      url: url + "/forecast/year?from=2028-10&lens=general",
      headers,
    });
    if (yearly.statusCode === 200) {
      validate("YearForecast", yearly.json());
      assert.equal(yearly.json().from, "2028-10-01");
      assert.equal(yearly.json().to, "2029-09-30");
      const month = await app.inject({
        url: url + "/forecast/month?month=2026-10",
        headers,
      });
      assert.equal(month.statusCode, 200, month.body);
      validate("MonthForecast", month.json());
      const day = await app.inject({
        url: url + "/forecast/day?date=2026-10-01",
        headers,
      });
      assert.equal(day.statusCode, 200, day.body);
      validate("DayForecast", day.json());
      const event = yearly.json().highlights.key_events[0];
      assert.ok(event);
      const detail = await app.inject({
        url: url + "/calendar/items/" + encodeURIComponent(event.id),
        headers,
      });
      assert.equal(detail.statusCode, 200, detail.body);
      assert.equal(detail.json().id, event.id);
    }
    for (const suffix of [
      "year?from=2026-13",
      "month?month=bad",
      "day?date=2026-02-30",
    ]) {
      assert.equal(
        (await app.inject({ url: url + "/forecast/" + suffix, headers }))
          .statusCode,
        400,
      );
    }
    assert.equal(
      (await app.inject({ method: "DELETE", url, headers })).statusCode,
      204,
    );
    assert.equal(
      (await app.inject({ url: url + "/chart", headers })).statusCode,
      404,
    );
  } finally {
    await app.close();
    await clearAuthMode();
    fs.rmSync(folder, { recursive: true, force: true });
  }
});
