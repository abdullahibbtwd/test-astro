import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { buildLocalApp } from "../local-api/app";
import { validate } from "../src/api/zod";
test("local API calculates, persists, edits and deletes real profiles without sample fallback", async () => {
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), "astrology-live-"));
  const dbPath = path.join(folder, "state.sqlite");
  let app = buildLocalApp({ dbPath });
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
    assert.ok(places.length);
    validate("PlaceCandidate", places[0]);
    const payload = {
      label: "Integration test",
      relation: "friend",
      birth_date: "1990-07-13",
      birth_time: "12:30",
      birth_place_id: places[0].place_id,
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
    await app.close();
    app = buildLocalApp({ dbPath });
    assert.deepEqual(
      (await app.inject({ url: url + "/chart", headers })).json(),
      chart,
    );
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
    assert.equal(
      (
        await app.inject({
          url: url + "/forecast/year?from=2026-10&lens=general",
          headers,
        })
      ).statusCode,
      503,
    );
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
    fs.rmSync(folder, { recursive: true, force: true });
  }
});
