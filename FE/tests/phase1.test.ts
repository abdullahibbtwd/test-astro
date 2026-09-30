import { test } from "node:test";
import assert from "node:assert/strict";
import { validBirth, formatDate, upper } from "../src/lib/dates";
import { pollingDelay, jobState } from "../src/api/job-policy";
import { safeEvent, scrubError } from "../src/lib/telemetry";
import { buildApp } from "../mock-api/app";
test("birth validation rejects missing time, rollover dates and future dates", () => {
  assert.equal(validBirth("2000-02-29", "06:30", "2026-09-29"), true);
  for (const date of ["2001-02-29", "1899-01-01", "2026-09-30"])
    assert.equal(validBirth(date, "06:30", "2026-09-29"), false);
  assert.equal(validBirth("2000-02-29", "", "2026-09-29"), false);
  assert.equal(validBirth("2000-02-29", "24:00", "2026-09-29"), false);
  assert.equal(upper("istanbul", "tr"), "İSTANBUL");
  assert.match(formatDate("2000-01-01", "en"), /January 1, 2000/);
});
test("job polling follows required backoff and expires at ten minutes", () => {
  assert.deepEqual(
    [0, 1, 2, 3, 4].map(pollingDelay),
    [1000, 2000, 3000, 4000, 4000],
  );
  assert.equal(jobState(undefined, 0, 600000), "failed");
});
test("telemetry omits birth data and strips personal route IDs", () => {
  const event = safeEvent("screen_view", {
    route: "/profiles/00000000-0000-4000-8000-000000000001?birth=secret",
    birth_date: "1979-03-30",
    label: "Private",
    request: { body: "private" },
  });
  assert.deepEqual(event.properties, { route: "/profiles/:id" });
  assert.deepEqual(scrubError(), {
    message: "Application error",
    tags: { area: "frontend" },
  });
});
test("fresh mock account creates self with a natal job and updates me", async () => {
  const app = buildApp();
  try {
    const login = (
      await app.inject({
        method: "POST",
        url: "/v1/auth/email/verify",
        payload: { email: "new@example.com", code: "000000" },
      })
    ).json();
    assert.equal(login.is_new_user, true);
    assert.equal(login.me.self_profile_id, null);
    const headers = { authorization: `Bearer ${login.access_token}` };
    const result = await app.inject({
      method: "POST",
      url: "/v1/profiles",
      headers,
      payload: {
        label: "Preview",
        relation: "self",
        birth_date: "1988-12-28",
        birth_time: "13:00",
        birth_place_id: "geo-plovdiv",
      },
    });
    assert.equal(result.statusCode, 201);
    assert.ok(result.json().natal_reading_job.job_id);
    const me = (await app.inject({ url: "/v1/me", headers })).json();
    assert.equal(me.self_profile_id, result.json().profile_id);
  } finally {
    await app.close();
  }
});
