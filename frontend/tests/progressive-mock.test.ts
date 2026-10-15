import test from "node:test";
import assert from "node:assert/strict";
import { buildApp } from "../../backend/mock/app";
import { validate } from "../src/api/zod";

test("ONB mock API: outline, pending section, ready section, progress, access guards and feedback", async () => {
  let now = Date.now();
  const app = buildApp({ now: () => now, jobMs: 100 });
  const headers = {
    authorization: "Bearer mock-access",
    "x-mock-scenario": "anonymous",
  };
  try {
    const profiles = (
      await app.inject({ url: "/v1/profiles", headers })
    ).json();
    const profile = profiles[1];
    const base = `/v1/profiles/${profile.profile_id}/natal-reading`;
    const outline = await app.inject({
      url: base + "/outline?lang=en",
      headers,
    });
    assert.equal(outline.statusCode, 200, outline.body);
    validate("ReadingOutline", outline.json());
    let response = await app.inject({
      url: base + "/sections/inner_drives",
      headers,
    });
    assert.equal(response.statusCode, 409);
    assert.equal(response.json().code, "read_ahead_limit");
    response = await app.inject({ url: base + "/sections/identity", headers });
    assert.equal(response.statusCode, 403);
    assert.equal(response.json().code, "account_required");
    response = await app.inject({
      url: base + "/sections/core_identity",
      headers,
    });
    assert.equal(response.statusCode, 202);
    validate("JobAccepted", response.json());
    now += 101;
    response = await app.inject({
      url: base + "/sections/core_identity",
      headers,
    });
    assert.equal(response.statusCode, 200);
    validate("NatalSection", response.json());
    assert.doesNotMatch(response.body, /principle_ids|draft_tr|usage/);
    response = await app.inject({
      method: "POST",
      url: base + "/progress",
      headers,
      payload: { key: "core_identity", event: "opened" },
    });
    assert.equal(response.statusCode, 204, response.body);
    response = await app.inject({
      method: "POST",
      url: "/v1/feedback/reading",
      headers,
      payload: {
        profile_id: profile.profile_id,
        target: { type: "reading" },
        rating: "spot_on",
        comment: "Private opinion",
      },
    });
    assert.equal(response.statusCode, 200, response.body);
    validate("ReadingAccuracy", response.json());
    response = await app.inject({
      method: "POST",
      url: base + "/complete",
      headers,
    });
    assert.equal(response.statusCode, 202, response.body);
    validate("JobAccepted", response.json());
  } finally {
    await app.close();
  }
});
