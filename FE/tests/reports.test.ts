import { test } from "node:test";
import assert from "node:assert/strict";
import { buildApp } from "../mock-api/app";
import { validate } from "../src/api/zod";
import type {
  BirthProfile,
  ReportPage,
  NatalReading,
} from "../contracts/spec-types";
test("saved natal reports are ready-only, localized, paginated and deletable without deleting profiles", async () => {
  let now = Date.now();
  const app = buildApp({ now: () => now, jobMs: 100 });
  const headers = { authorization: "Bearer mock-access" };
  const get = (path: string) => app.inject({ url: `/v1${path}`, headers });
  try {
    const profiles = (await get("/profiles")).json<BirthProfile[]>();
    assert.equal((await get(`/profiles/${profiles[0]!.profile_id}/natal-reading?lang=en`)).statusCode, 503);
    const id = profiles[1]!.profile_id;
    assert.deepEqual((await get("/reports?lang=en")).json().items, []);
    assert.equal(
      (await get(`/profiles/${id}/natal-reading?lang=en`)).statusCode,
      202,
    );
    assert.deepEqual((await get("/reports?lang=en")).json().items, []);
    now += 101;
    const reading = validate<NatalReading>(
      "NatalReading",
      (await get(`/profiles/${id}/natal-reading?lang=en`)).json(),
    );
    await get(`/profiles/${id}/natal-reading?lang=en`);
    let page = validate<ReportPage>(
      "ReportPage",
      (await get("/reports?lang=en")).json(),
    );
    assert.equal(page.items.length, 1);
    assert.equal(page.items[0]!.title, reading.title);
    assert.equal(page.items[0]!.route, `/chart/reading?profile=${id}`);
    assert.equal((await get("/reports?lang=tr")).json().items.length, 0);
    assert.equal(
      (await get("/reports?lang=en&type=compatibility")).json().items.length,
      0,
    );
    const second = profiles[2]!.profile_id;
    await get(`/profiles/${second}/natal-reading?lang=en`);
    now += 101;
    await get(`/profiles/${second}/natal-reading?lang=en`);
    page = (await get("/reports?lang=en&limit=1")).json();
    assert.equal(page.items[0]!.profile_id, second);
    assert.equal(page.next_cursor, "1");
    const next = (
      await get(`/reports?lang=en&limit=1&cursor=${page.next_cursor}`)
    ).json<ReportPage>();
    assert.equal(next.items[0]!.profile_id, id);
    assert.equal(next.next_cursor, null);
    const reportId = next.items[0]!.report_id;
    assert.equal(
      (
        await app.inject({
          method: "DELETE",
          url: `/v1/reports/${reportId}`,
          headers,
        })
      ).statusCode,
      204,
    );
    assert.equal(
      (
        await app.inject({
          method: "DELETE",
          url: `/v1/reports/${reportId}`,
          headers,
        })
      ).statusCode,
      404,
    );
    assert.equal((await get(`/profiles/${id}`)).statusCode, 200);
    assert.equal((await get("/reports?lang=en")).json().items.length, 1);
    await app.inject({
      method: "DELETE",
      url: `/v1/profiles/${second}`,
      headers,
    });
    assert.equal((await get("/reports?lang=en")).json().items.length, 0);
  } finally {
    await app.close();
  }
});
