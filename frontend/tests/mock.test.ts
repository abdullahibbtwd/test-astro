import { test } from "node:test";
import assert from "node:assert/strict";
import { buildApp } from "../mock-api/app";
const headers = { authorization: "Bearer mock-access" };
const self = "00000000-0000-4000-8000-000000000001",
  partner = "00000000-0000-4000-8000-000000000002";
test("auth, localization, validation and self-profile protection", async () => {
  const app = buildApp();
  try {
    assert.equal((await app.inject("/v1/profiles")).statusCode, 401);
    const login = await app.inject({
      method: "POST",
      url: "/v1/auth/email/verify",
      payload: { email: "demo@example.com", code: "000000" },
    });
    assert.equal(login.statusCode, 200);
    assert.ok(login.json().access_token);
    const tr = (
      await app.inject({ url: "/v1/profiles?lang=tr", headers })
    ).json();
    const en = (
      await app.inject({ url: "/v1/profiles?lang=en", headers })
    ).json();
    assert.equal(tr[0].birth.place.name, "Sofya");
    assert.equal(en[0].birth.place.name, "Sofia");
    assert.equal(
      (
        await app.inject({
          method: "DELETE",
          url: `/v1/profiles/${self}`,
          headers,
        })
      ).statusCode,
      409,
    );
    assert.equal(
      (
        await app.inject({
          method: "POST",
          url: "/v1/profiles",
          headers,
          payload: {
            label: "Test",
            relation: "friend",
            birth_date: "2026-02-30",
            birth_time: "24:00",
            birth_place_id: "geo-sofia",
          },
        })
      ).statusCode,
      400,
    );
  } finally {
    await app.close();
  }
});
test("whole-resource 202 → running → succeeded → 200, stable job id, ETag", async () => {
  let now = Date.now();
  const app = buildApp({ now: () => now, jobMs: 100 });
  const url = `/v1/profiles/${partner}/natal-reading?lang=en`;
  try {
    const first = await app.inject({ url, headers });
    assert.equal(first.statusCode, 202);
    const id = first.json().job.job_id;
    assert.equal((await app.inject({ url, headers })).json().job.job_id, id);
    now += 30;
    assert.equal(
      (await app.inject({ url: `/v1/jobs/${id}`, headers })).json().status,
      "running",
    );
    now += 100;
    assert.equal(
      (await app.inject({ url: `/v1/jobs/${id}`, headers })).json().status,
      "succeeded",
    );
    const ready = await app.inject({ url, headers });
    assert.equal(ready.statusCode, 200);
    assert.equal(ready.json().sections.length, 17);
    assert.equal(
      (
        await app.inject({
          url,
          headers: { ...headers, "if-none-match": String(ready.headers.etag) },
        })
      ).statusCode,
      304,
    );
  } finally {
    await app.close();
  }
});
test("failure can be retried without modifying deterministic chart data", async () => {
  let now = Date.now();
  const app = buildApp({ now: () => now, jobMs: 100 });
  const url = `/v1/profiles/${partner}/natal-reading`;
  try {
    await app.inject({
      url,
      headers: { ...headers, "x-mock-scenario": "fail" },
    });
    now += 110;
    assert.equal((await app.inject({ url, headers })).statusCode, 503);
    assert.equal(
      (await app.inject({ url: url + "?retry=true", headers })).statusCode,
      202,
    );
    now += 110;
    assert.equal((await app.inject({ url, headers })).statusCode, 200);
    assert.equal(
      (
        await app.inject({ url: `/v1/profiles/${partner}/chart`, headers })
      ).json().points.length,
      12,
    );
  } finally {
    await app.close();
  }
});
test("composite readings do not block deterministic data; scenarios and missing fixtures are explicit", async () => {
  const app = buildApp();
  try {
    const home = await app.inject({ url: "/v1/home?lang=en", headers });
    assert.equal(home.statusCode, 200);
    assert.equal(home.json().tiles.length, 4);
    assert.equal(home.json().today.status, "pending");
    const rate = await app.inject({
      url: "/v1/home",
      headers: { ...headers, "x-mock-scenario": "rate_limited" },
    });
    assert.equal(rate.statusCode, 429);
    assert.equal(rate.headers["retry-after"], "30");
    assert.equal(
      (
        await app.inject({
          url: "/v1/meta/config",
          headers: { "x-mock-scenario": "new_off" },
        })
      ).statusCode,
      404,
    );
    const empty = await app.inject({
      url: `/v1/profiles/${self}/calendar/days/2026-10-01`,
      headers: { ...headers, "x-mock-scenario": "empty_day" },
    });
    assert.equal(empty.statusCode, 200);
    assert.deepEqual(empty.json().events, []);
    assert.equal(
      (await app.inject({ url: `/v1/profiles/${self}/natal-reading`, headers }))
        .statusCode,
      503,
    );
    assert.equal(
      (
        await app.inject({
          url: `/v1/profiles/${partner}/calendar/months/2026-10`,
          headers,
        })
      ).statusCode,
      503,
    );
  } finally {
    await app.close();
  }
});

test("idempotent profile creation reuses the response and rejects key reuse with another payload", async () => {
  const app = buildApp();
  const key = "10000000-0000-4000-8000-000000000000";
  const payload = {
    label: "Person D",
    relation: "friend",
    birth_date: "1984-06-12",
    birth_time: "14:57",
    birth_place_id: "geo-sofia",
  };
  try {
    const request = {
      method: "POST" as const,
      url: "/v1/profiles",
      headers: { ...headers, "idempotency-key": key },
      payload,
    };
    const first = await app.inject(request);
    assert.equal(first.statusCode, 201);
    assert.deepEqual((await app.inject(request)).json(), first.json());
    assert.equal(
      (
        await app.inject({
          ...request,
          payload: { ...payload, label: "Changed" },
        })
      ).statusCode,
      409,
    );
  } finally {
    await app.close();
  }
});
test("scripted Ask SSE persists the same text and rejects chart data in context", async () => {
  const app = buildApp();
  try {
    const thread = (
      await app.inject({
        method: "POST",
        url: "/v1/ask/threads",
        headers,
        payload: { profile_id: self },
      })
    ).json();
    const url = `/v1/ask/threads/${thread.thread_id}/messages?lang=en`;
    assert.equal(
      (
        await app.inject({
          method: "POST",
          url,
          headers,
          payload: { text: "Hello", context: { chart: { longitude: 10 } } },
        })
      ).statusCode,
      400,
    );
    const stream = await app.inject({
      method: "POST",
      url,
      headers,
      payload: { text: "Tell me about today", context: { date: "2026-09-29" } },
    });
    assert.equal(stream.statusCode, 200);
    assert.match(String(stream.headers["content-type"]), /text\/event-stream/);
    for (const event of ["status", "delta", "card", "link", "done"])
      assert.ok(stream.body.includes(`event: ${event}`));
    const stored = (
      await app.inject({ url: `/v1/ask/threads/${thread.thread_id}`, headers })
    ).json();
    assert.equal(stored.messages.length, 2);
    assert.equal(stored.messages[1].status, "complete");
    assert.ok(stored.messages[1].text.length > 100);
  } finally {
    await app.close();
  }
});
test("recommendation scenarios preserve structured results without composing readings", async () => {
  const app = buildApp();
  const url = `/v1/profiles/${self}/acg/recommendations?lang=en`;
  try {
    const ready = await app.inject({
      method: "POST",
      url,
      headers,
      payload: { goal: "love", scope: "world" },
    });
    assert.equal(ready.statusCode, 200);
    assert.ok(ready.json().places.length > 0);
    assert.equal(ready.json().explanations.status, "pending");
    const goal = await app.inject({
      method: "POST",
      url,
      headers: { ...headers, "x-mock-scenario": "needs_goal" },
      payload: { query_text: "Somewhere" },
    });
    assert.equal(goal.json().status, "needs_goal");
    assert.equal(goal.json().goal_options.length, 11);
    const thin = await app.inject({
      method: "POST",
      url,
      headers: { ...headers, "x-mock-scenario": "thin_result" },
      payload: { goal: "love" },
    });
    assert.equal(thin.json().status, "thin_result");
    assert.equal(thin.json().places.length, 1);
  } finally {
    await app.close();
  }
});

test("profile edits localize places, clear nullable fields and derive stable birth keys", async () => {
  const app = buildApp();
  try {
    const update = await app.inject({
      method: "PATCH",
      url: `/v1/profiles/${partner}?lang=en`,
      headers,
      payload: {
        birth_date: "1988-12-29",
        birth_time: "12:00",
        birth_place_id: "geo-sofia",
        current_place_id: "geo-sofia",
        gender: "female",
      },
    });
    assert.equal(update.statusCode, 200);
    const value = update.json();
    assert.equal(value.birth.place.name, "Sofia");
    assert.equal(
      new Date(value.birth.utc).toISOString(),
      "1988-12-29T10:00:00.000Z",
    );
    const renamed = await app.inject({
      method: "PATCH",
      url: `/v1/profiles/${partner}?lang=tr`,
      headers,
      payload: { label: "Renamed", gender: null, current_place_id: null },
    });
    assert.equal(renamed.statusCode, 200);
    assert.equal(renamed.json().chart_key, value.chart_key);
    assert.equal(renamed.json().gender, null);
    assert.equal(renamed.json().current_place, null);
    assert.equal(renamed.json().birth.place.name, "Sofya");
    const read = (
      await app.inject({ url: `/v1/profiles/${partner}?lang=en`, headers })
    ).json();
    assert.equal(read.birth.place.name, "Sofia");
    const chart = (
      await app.inject({ url: `/v1/profiles/${partner}/chart`, headers })
    ).json();
    assert.equal(chart.chart_key, value.chart_key);
    assert.equal(chart.utc, value.birth.utc);
    assert.equal(
      chart.points.find((p: any) => p.body === "sun").sign,
      value.big_three.sun,
    );
    await app.inject({
      method: "PATCH",
      url: `/v1/profiles/${self}`,
      headers,
      payload: { birth_time: "07:00" },
    });
    assert.equal(
      (await app.inject({ url: "/v1/home", headers })).statusCode,
      503,
    );
  } finally {
    await app.close();
  }
});

test("area search is supported, invalid kinds fail and polling jobs expire after 24 hours", async () => {
  let now = Date.now();
  const app = buildApp({ now: () => now });
  try {
    assert.equal(
      (await app.inject({ url: "/v1/places/search?q=So&kind=area", headers }))
        .statusCode,
      200,
    );
    assert.equal(
      (
        await app.inject({
          url: "/v1/places/search?q=So&kind=invalid",
          headers,
        })
      ).statusCode,
      400,
    );
    const pending = (
      await app.inject({
        url: `/v1/profiles/${partner}/natal-reading`,
        headers,
      })
    ).json();
    now += 24 * 60 * 60 * 1000;
    assert.equal(
      (await app.inject({ url: `/v1/jobs/${pending.job.job_id}`, headers }))
        .statusCode,
      404,
    );
  } finally {
    await app.close();
  }
});
