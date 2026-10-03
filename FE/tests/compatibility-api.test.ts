import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { Store } from "../local-api/store";
import { fixture } from "../mock-api/fixtures";
import { buildLocalApp } from "../local-api/app";
import { validate } from "../src/api/zod";
test("compatibility endpoints authenticate, replay safely, paginate and delete", async () => {
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), "compat-api-"));
  const dbPath = path.join(folder, "state.sqlite");
  const store = new Store(dbPath);
  const a = fixture("profile.1.en"),
    b = { ...a, profile_id: "second", chart_key: "second", label: "Second" };
  for (const p of [a, b]) {
    store.put("profile:" + p.profile_id, p);
    store.put("raw:" + p.profile_id, {});
  }
  store.close();
  let app = buildLocalApp({
    dbPath,
    allowPaid: true,
    generateCompatibility: async (data: any) => ({
      context: data.context,
      readings: Object.fromEntries(
        ["en", "tr"].map((lang) => [
          lang,
          {
            title: lang,
            sections: [
              { key: "test", movement: 0, title: lang, text: "Test reading" },
            ],
          },
        ]),
      ),
    }),
  });
  try {
    assert.equal(
      (await app.inject({ url: "/v1/compatibility" })).statusCode,
      401,
    );
    const session = (
      await app.inject({
        method: "POST",
        url: "/v1/auth/email/verify",
        payload: { email: "demo@example.com", code: "000000" },
      })
    ).json();
    const headers = {
      authorization: `Bearer ${session.access_token}`,
      "idempotency-key": "compat-test",
    };
    const payload = {
      profile_a_id: a.profile_id,
      profile_b_id: b.profile_id,
      type: "love",
    };
    const first = await app.inject({
      method: "POST",
      url: "/v1/compatibility",
      headers,
      payload,
    });
    assert.equal(first.statusCode, 201, first.body);
    validate("Compatibility", first.json());
    const repeated = await app.inject({
      method: "POST",
      url: "/v1/compatibility",
      headers,
      payload,
    });
    assert.equal(
      repeated.json().compatibility_id,
      first.json().compatibility_id,
    );
    assert.equal(
      (
        await app.inject({
          method: "POST",
          url: "/v1/compatibility",
          headers,
          payload: { ...payload, type: "work" },
        })
      ).statusCode,
      409,
    );
    await new Promise((resolve) => setImmediate(resolve));
    const url = "/v1/compatibility/" + first.json().compatibility_id;
    const result = (
      await app.inject({ url: url + "?lang=tr", headers })
    ).json();
    validate("Compatibility", result);
    assert.equal(result.reading.status, "ready");
    assert.equal(result.reading.title, "tr");
    const page = (
      await app.inject({ url: "/v1/compatibility?limit=1", headers })
    ).json();
    validate("CompatibilityPage", page);
    assert.equal(page.items.length, 1);
    const reports = (
      await app.inject({
        url: "/v1/reports?type=compatibility&lang=tr",
        headers,
      })
    ).json();
    validate("ReportPage", reports);
    assert.equal(reports.items.length, 1);
    assert.equal(reports.items[0].title, "tr");
    const deleteReport = {
      method: "DELETE" as const,
      url: "/v1/reports/" + reports.items[0].report_id,
      headers,
    };
    assert.equal((await app.inject(deleteReport)).statusCode, 204);
    assert.equal((await app.inject(deleteReport)).statusCode, 404);
    assert.equal(
      (
        await app.inject({
          url: "/v1/reports?type=compatibility&lang=tr",
          headers,
        })
      ).json().items.length,
      0,
    );
    assert.equal(
      (await app.inject({ url: url + "?lang=tr", headers })).json().reading
        .status,
      "ready",
    );
    assert.equal(
      (
        await app.inject({
          url: "/v1/reports?type=compatibility&lang=en",
          headers,
        })
      ).json().items.length,
      1,
    );
    assert.equal(
      (await app.inject({ url: "/v1/reports?limit=0", headers })).statusCode,
      400,
    );

    await app.close();
    app = buildLocalApp({ dbPath });
    assert.equal(
      (
        await app.inject({
          url: "/v1/reports?type=compatibility&lang=tr",
          headers,
        })
      ).json().items.length,
      0,
    );
    assert.equal(
      (await app.inject({ url: url + "?lang=tr", headers })).json().reading
        .status,
      "ready",
    );
    assert.equal(
      (await app.inject({ method: "DELETE", url, headers })).statusCode,
      204,
    );
    assert.equal((await app.inject({ url, headers })).statusCode, 404);
    assert.equal(
      (
        await app.inject({
          method: "POST",
          url: "/v1/compatibility",
          headers,
          payload,
        })
      ).statusCode,
      404,
    );
  } finally {
    await app.close();
    fs.rmSync(folder, { recursive: true, force: true });
  }
});
